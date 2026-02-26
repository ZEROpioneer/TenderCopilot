"""筛选管理器：双轨制过滤（策略 A 新机会 / 策略 B 追踪）"""
from typing import Any, Dict, List, Optional
from loguru import logger

from .keyword_matcher import KeywordMatcher
from .location_matcher import LocationMatcher
from .notice_type_filter import NoticeTypeFilter
from .deduplicator import Deduplicator
from src.schema import TenderItem

# 追踪模式公告类型关键词：仅当关联项目在历史记录中时才放行，否则一律丢弃
TRACK_MODE_KEYWORDS = ("更正", "变更", "流标", "废标", "结果", "中标")


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

    def _get_notice_type(self, item: TenderItem) -> str:
        return (item.announcement_type or item.notice_type_raw or "未知公告类型").strip()

    def _is_track_mode_announcement(self, notice_type: str) -> bool:
        """判断是否为追踪模式公告（更正/变更/流标/废标/结果/中标等后续公告）"""
        return any(kw in notice_type for kw in TRACK_MODE_KEYWORDS)

    def _build_tracking_item(self, item: TenderItem) -> TenderItem:
        """构建追踪模式放行项：老项目有更新，跳过关键词打分，给默认基础分与标签。"""
        first_direction_id = next(
            iter(self.config.get("business_directions", {})),
            "default",
        )
        first_direction = (
            self.config.get("business_directions", {}).get(first_direction_id, {})
        )
        item.matched_direction_id = first_direction_id
        item.match_results = {
            first_direction_id: {
                "name": first_direction.get("name", "追踪项目"),
                "score": 1.0,
                "matched_keywords": ["追踪", "🔴 关注项目有更新"],
                "location_required": False,
            }
        }
        item.location_result = {"matched": True}
        item.is_tracking = True
        item.matched_keywords = ["追踪", "🔴 关注项目有更新"]
        item.status = "filtered"
        # 默认基础分 70，确保通过下游 min_total_score 筛选
        item.feasibility = {
            **item.feasibility,
            "total": 70,
            "level": "及格",
            "base_score": 70,
            "reason": "关注项目有更新，给予默认基础分",
            "score_breakdown": [
                {"rule": "🔴 关注项目有更新（追踪模式）", "points": 70},
                {"rule": "🏆 总计", "points": 70},
            ],
        }
        return item

    def _strategy_a_new_opportunity(self, item: TenderItem, force_mode: bool = False) -> Optional[TenderItem]:
        """策略 A：新机会模式。关键词+地域+类型+去重。"""
        match_results = self.keyword_matcher.match(item)
        if not match_results:
            return None

        best_direction_id = max(
            match_results.keys(), key=lambda k: match_results[k]["score"]
        )
        best_direction = match_results[best_direction_id]
        direction_config = self.config["business_directions"][best_direction_id]

        location_result = self.location_matcher.match(
            item, best_direction_id, direction_config
        )
        if not location_result["matched"]:
            logger.debug(
                f"⏭️ 跳过（地域不符-{direction_config['name']}）: {(item.title or '')[:50]}..."
            )
            return None

        type_result = self.notice_type_filter.match(item)
        if not type_result["matched"]:
            logger.debug(
                f"⏭️ 跳过（公告类型不符-{type_result['normalized_type']}）: {(item.title or '')[:50]}..."
            )
            return None

        if self.deduplicator.is_duplicate(item, force_mode=force_mode):
            logger.debug(f"⏭️ 跳过（重复）: {(item.title or '')[:50]}...")
            return None

        item.matched_direction_id = best_direction_id
        item.match_results = match_results
        item.location_result = location_result
        item.is_tracking = False
        item.matched_keywords = best_direction.get("matched_keywords", [])
        item.status = "filtered"
        return item

    def process_one(self, item: TenderItem, force_mode: bool = False) -> Optional[TenderItem]:
        """处理单条公告，返回通过时的 TenderItem（已更新属性），否则 None。

        双轨制分流：
        - 逻辑 A（追踪模式）：更正/变更/流标/废标/结果/中标类公告
          -> 仅当 db.is_project_tracked 为 True 时放行，否则直接 return None 丢弃
        - 逻辑 B（海选模式）：其他正常公告 -> 关键词+地域+类型+去重
        """
        notice_type = self._get_notice_type(item)

        if self.smart_track_enabled and self._is_track_mode_announcement(notice_type):
            if not self.db.is_project_tracked(item.project_id, item.title):
                logger.debug(
                    f"⏭️ 丢弃（追踪模式-非关注项目）: {(item.title or '')[:50]}..."
                )
                return None
            logger.info(
                f"🎯 追踪命中（关注项目有更新）: {(item.title or '')[:50]}..."
            )
            return self._build_tracking_item(item)

        return self._strategy_a_new_opportunity(item, force_mode=force_mode)

    def process(self, items: List[TenderItem], force_mode: bool = False) -> List[TenderItem]:
        """批量处理公告，返回通过筛选的 TenderItem 列表。
        使用 url 或 id 去重，确保同一公告（多业务方向命中）只出现一次。
        """
        filtered: List[TenderItem] = []
        seen_keys: set = set()
        for item in items:
            result = self.process_one(item, force_mode=force_mode)
            if result:
                key = (item.url or item.project_id or "").strip()
                if not key:
                    key = f"__id_{item.project_id}"
                if key in seen_keys:
                    logger.debug(f"⏭️ 跳过（内存去重）: {(item.title or '')[:50]}...")
                    continue
                seen_keys.add(key)
                self.db.save_announcement(item)
                filtered.append(result)
        return filtered
