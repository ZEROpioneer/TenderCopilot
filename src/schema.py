"""TenderCopilot 数据契约 - 招标项目全生命周期标准结构

流水线与标准数据契约：从爬取到推送，全链路使用 TenderItem 作为唯一数据载体。
所有字段均提供安全默认值，避免 KeyError 级联崩溃。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _default_feasibility() -> Dict[str, Any]:
    """可行性评分的安全默认值（AI 分析失败时使用）"""
    return {
        "total": 60,
        "level": "及格",
        "base_score": 60,
        "breakdown": {},
        "passes_filter": True,
        "time_score_details": {},
        "reason": "AI分析失败或超时，给予默认及格分以保证流程继续",
    }


@dataclass
class TenderItem:
    """招标项目标准数据契约

    覆盖从爬取 → 筛选 → AI 分析 → 报告 → 推送的全生命周期字段。
    所有字段均有默认值，非必填字段允许 None 或空，绝不因缺字段而报错。
    """

    # ---------- 爬取阶段（Spider 产出）----------
    project_id: str = ""
    title: str = ""
    url: str = ""
    publish_date: str = ""
    announcement_type: str = "未知公告类型"
    location: str = "未知"
    content_raw: str = ""
    summary: str = ""
    crawled_at: str = ""
    attachments: List[Dict[str, Any]] = field(default_factory=list)

    # ---------- 数据库兼容字段（announcements 表）----------
    budget: Optional[str] = None
    deadline: Optional[str] = None
    contact: Optional[str] = None
    status: str = "discovered"

    # ---------- 筛选阶段（Filter 产出）----------
    matched_direction_id: str = ""
    matched_keywords: List[str] = field(default_factory=list)
    match_results: Dict[str, Any] = field(default_factory=dict)
    location_result: Dict[str, Any] = field(default_factory=lambda: {"matched": True})
    is_tracking: bool = False

    # ---------- 分析阶段（Analyzer 产出）----------
    feasibility: Dict[str, Any] = field(default_factory=_default_feasibility)
    content_analysis: Optional[Dict[str, Any]] = None
    ai_extracted: Optional[Dict[str, Any]] = None
    attachment_analysis: Optional[Dict[str, Any]] = None

    # ---------- AI 精准提取的核心要素（用于微型尽调卡片）----------
    confidentiality_req: str = ""       # 保密资质要求（一票否决项）
    project_summary: str = ""            # 一句话项目摘要（到底买啥）
    doc_deadline: str = ""               # 招标文件获取/报名截止时间
    bid_deadline: str = ""               # 开标/递交投标文件时间
    budget_info: str = ""                # 预算或最高限价
    bid_location: str = ""               # 开标地点
    contact_info: str = ""               # 采购方/代理联系人及电话
    doc_claim_method: str = ""           # 招标文件申领方式
    bid_method: str = ""                 # 开标方式 (线下/线上等)
    ai_score: float = 0.0                # AI 推荐度评分 0-100（用于展示）

    # ---------- 兼容属性 ----------
    @property
    def id(self) -> str:
        """兼容旧代码中的 ann['id'] / announcement['id']"""
        return self.project_id

    @property
    def pub_date(self) -> str:
        """兼容 pub_date 字段名"""
        return self.publish_date

    @property
    def notice_type_raw(self) -> str:
        """兼容 notice_type_raw 字段名"""
        return self.announcement_type

    @property
    def content(self) -> str:
        """兼容 content 字段名"""
        return self.content_raw

    _DICT_KEYS = frozenset({
        "id", "project_id", "title", "url", "publish_date", "pub_date",
        "notice_type_raw", "notice_type", "location", "content", "content_raw",
        "summary", "attachments", "crawled_at", "budget", "deadline", "contact",
    })

    def get(self, key: str, default: Any = None) -> Any:
        """兼容 dict 的 .get() 调用，供尚未重构的模块无缝使用"""
        _mapping = {
            "id": self.project_id,
            "project_id": self.project_id,
            "title": self.title,
            "url": self.url,
            "publish_date": self.publish_date,
            "pub_date": self.publish_date,
            "notice_type_raw": self.announcement_type,
            "notice_type": self.announcement_type,
            "location": self.location,
            "content": self.content_raw,
            "content_raw": self.content_raw,
            "summary": self.summary,
            "attachments": self.attachments,
            "crawled_at": self.crawled_at,
            "budget": self.budget,
            "deadline": self.deadline,
            "contact": self.contact,
        }
        return _mapping.get(key, default)

    def __getitem__(self, key: str) -> Any:
        """兼容 dict 的 [] 访问，未知 key 抛出 KeyError"""
        if key not in self._DICT_KEYS:
            raise KeyError(key)
        return self.get(key)

    def __post_init__(self):
        """确保 feasibility 始终具备必要键"""
        if "total" not in self.feasibility:
            self.feasibility["total"] = 60
        if "level" not in self.feasibility:
            self.feasibility["level"] = "及格"

    # ---------- 工厂方法：从爬虫 dict 创建 ----------
    @classmethod
    def from_crawl_dict(cls, d: Dict[str, Any]) -> "TenderItem":
        """从爬虫解析的 dict 创建 TenderItem（生肉装箱）"""
        return cls(
            project_id=d.get("id", "") or d.get("project_id", ""),
            title=d.get("title", ""),
            url=d.get("url", ""),
            publish_date=d.get("publish_date", "") or d.get("pub_date", ""),
            announcement_type=d.get("notice_type_raw", "") or d.get("notice_type", "未知公告类型"),
            location=d.get("location", "未知"),
            content_raw=d.get("content", "") or d.get("content_raw", ""),
            summary=d.get("summary", ""),
            crawled_at=d.get("crawled_at", ""),
            attachments=d.get("attachments", []),
            budget=d.get("budget"),
            deadline=d.get("deadline"),
            contact=d.get("contact"),
        )

