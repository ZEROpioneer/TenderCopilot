"""筛选管理器：双轨制过滤（策略 A 新机会 / 策略 B 追踪）"""
from typing import Any, Dict, List, Optional
from loguru import logger

from .keyword_matcher import KeywordMatcher
from .location_matcher import LocationMatcher
from .notice_type_filter import NoticeTypeFilter
from .deduplicator import Deduplicator
from src.utils.project_fingerprint import (
    extract_project_refs_from_title,
    make_fingerprint,
    normalize_for_fingerprint,
)


class FilterManager:
    """双轨制过滤管理器

    策略 A（新机会）：招标/采购/询价/竞争性谈判 -> 关键词+地域+类型+去重
    策略 B（追踪）：更正/流标/废标/变更 -> 仅检查是否在 interested_projects
    """

    def __init__(
        self,
        config: Dict[str, Any],
        db,
        keyword_matcher: KeywordMatcher,
        location_matcher: LocationMatcher,
        notice_type_filter: NoticeTypeFilter,
        deduplicator: Deduplicator,
    ):
        self.config = config
        self.db = db
        self.keyword_matcher = keyword_matcher
        self.location_matcher = location_matcher
        self.notice_type_filter = notice_type_filter
        self.deduplicator = deduplicator

        ann_filter = config.get("announcement_filter", {})
        smart_cfg = ann_filter.get("smart_track", {})
        self.smart_track_enabled = smart_cfg.get("enabled", True)
        self.smart_track_types = set(smart_cfg.get("smart_track_types", []))
        self._interested_fingerprints: Optional[set] = None

    def _get_interested_fingerprints(self) -> set:
        if self._interested_fingerprints is None:
            self._interested_fingerprints = self.db.get_interested_fingerprints_set()
        return self._interested_fingerprints

    def _refresh_interested_cache(self):
        self._interested_fingerprints = self.db.get_interested_fingerprints_set()

    def _get_notice_type(self, announcement: Dict) -> str:
        return (
            announcement.get("notice_type_raw")
            or announcement.get("notice_type")
            or "未知公告类型"
        ).strip()

    def _strategy_b_track(self, announcement: Dict) -> Optional[Dict]:
        """策略 B：追踪模式。仅当公告关联的项目在 interested_projects 中时放行。"""
        title = (announcement.get("title") or "").strip()
        refs = extract_project_refs_from_title(title)
        if not refs:
            logger.debug(
                f"⏭️ 跳过（追踪模式无法提取项目标识）: {title[:50]}..."
            )
            return None

        fingerprints = self._get_interested_fingerprints()
        for ref in refs:
            fp = make_fingerprint(ref)
            if fp and fp in fingerprints:
                logger.info(
                    f"🎯 追踪命中（高优先级）: {title[:50]}... -> 项目 ref: {ref[:30]}"
                )
                first_direction_id = next(
                    iter(self.config.get("business_directions", {})),
                    "default",
                )
                first_direction = (
                    self.config.get("business_directions", {})
                    .get(first_direction_id, {})
                )
                return {
                    "announcement": announcement,
                    "matched_direction_id": first_direction_id,
                    "match_results": {
                        first_direction_id: {
                            "name": first_direction.get("name", "追踪项目"),
                            "score": 1.0,
                            "matched_keywords": ["追踪"],
                            "location_required": False,
                        }
                    },
                    "location_result": {"matched": True},
                    "is_tracking": True,
                }
        logger.debug(
            f"⏭️ 跳过（追踪模式未命中 interested）: {title[:50]}..."
        )
        return None

    def _strategy_a_new_opportunity(self, announcement: Dict) -> Optional[Dict]:
        """策略 A：新机会模式。关键词+地域+类型+去重。"""
        match_results = self.keyword_matcher.match(announcement)
        if not match_results:
            return None

        best_direction_id = max(
            match_results.keys(), key=lambda k: match_results[k]["score"]
        )
        best_direction = match_results[best_direction_id]
        direction_config = self.config["business_directions"][best_direction_id]

        location_result = self.location_matcher.match(
            announcement, best_direction_id, direction_config
        )
        if not location_result["matched"]:
            logger.debug(
                f"⏭️ 跳过（地域不符-{direction_config['name']}）: {announcement['title'][:50]}..."
            )
            return None

        type_result = self.notice_type_filter.match(announcement)
        if not type_result["matched"]:
            logger.debug(
                f"⏭️ 跳过（公告类型不符-{type_result['normalized_type']}）: {announcement['title'][:50]}..."
            )
            return None

        if self.deduplicator.is_duplicate(announcement):
            logger.debug(f"⏭️ 跳过（重复）: {announcement['title'][:50]}...")
            return None

        return {
            "announcement": announcement,
            "matched_direction_id": best_direction_id,
            "match_results": match_results,
            "location_result": location_result,
            "is_tracking": False,
        }

    def process_one(self, announcement: Dict) -> Optional[Dict]:
        """处理单条公告，返回通过时的 project 字典，否则 None。"""
        notice_type = self._get_notice_type(announcement)

        if self.smart_track_enabled and notice_type in self.smart_track_types:
            return self._strategy_b_track(announcement)

        return self._strategy_a_new_opportunity(announcement)

    def process(self, announcements: List[Dict]) -> List[Dict]:
        """批量处理公告，返回通过筛选的 project 列表。"""
        filtered = []
        for ann in announcements:
            result = self.process_one(ann)
            if result:
                self.db.save_announcement(ann)
                filtered.append(result)
        return filtered
