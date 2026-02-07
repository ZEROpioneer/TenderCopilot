"""公告类型筛选器

用于根据配置过滤不需要的公告类型，例如：
- 只保留招标公告 / 采购公告 / 询价公告等
- 排除废标公告 / 中标公告 / 成交公告等
- 针对更正公告（更正公告）可选择性保留
"""

from typing import Any, Dict
from loguru import logger


class NoticeTypeFilter:
    """公告类型筛选"""

    def __init__(self, config: Dict[str, Any]) -> None:
        announcement_filter = config.get("announcement_filter", {})
        self.types_cfg: Dict[str, Any] = announcement_filter.get("notice_types", {})

    def match(self, announcement: Dict[str, Any]) -> Dict[str, Any]:
        """判断公告类型是否匹配

        返回:
            {
                "matched": bool,
                "reason": str,
                "normalized_type": str,
            }
        """
        enabled = self.types_cfg.get("enabled", False)
        notice_type = (
            announcement.get("notice_type_raw")
            or announcement.get("notice_type")
            or "未知公告类型"
        )
        title = (announcement.get("title") or "").strip()

        normalized_type = notice_type.strip() or "未知公告类型"

        # 未启用类型过滤，则直接通过
        if not enabled:
            return {
                "matched": True,
                "reason": "filter_disabled",
                "normalized_type": normalized_type,
            }

        include = set(self.types_cfg.get("include", []))
        exclude = set(self.types_cfg.get("exclude", []))
        include_correction = self.types_cfg.get("include_correction", False)

        # 先根据关键字排除典型的结果类/废标类/流标类公告
        danger_keywords = ["废标", "流标", "中标", "成交", "结果公示", "结果公告"]
        text_for_judge = f"{normalized_type} {title}"
        if any(k in text_for_judge for k in danger_keywords):
            return {
                "matched": False,
                "reason": "keyword_excluded",
                "normalized_type": normalized_type,
            }

        # 显式排除类型（如废标公告 / 中标公告等）
        if normalized_type in exclude:
            return {
                "matched": False,
                "reason": "excluded_type",
                "normalized_type": normalized_type,
            }

        # 更正公告：根据配置决定是否保留
        if "更正" in normalized_type:
            if not include_correction:
                return {
                    "matched": False,
                    "reason": "correction_excluded",
                    "normalized_type": normalized_type,
                }
            # 当前版本：只要允许更正公告，就直接放行
            # 后续可以在这里增加“是否已有主公告”的关联判断
            return {
                "matched": True,
                "reason": "correction_included",
                "normalized_type": normalized_type,
            }

        # 在白名单中的类型（招标公告 / 采购公告 / 询价公告等）
        if include and normalized_type in include:
            return {
                "matched": True,
                "reason": "included_type",
                "normalized_type": normalized_type,
            }

        # 如果 include 为空，则默认不过滤任何非排除类型
        if not include:
            return {
                "matched": True,
                "reason": "no_include_config",
                "normalized_type": normalized_type,
            }

        # 其他未列出的类型：默认不过滤，但打上原因，便于调试
        logger.debug(f"公告类型未在 include/exclude 中显式配置: {normalized_type}")
        return {
            "matched": True,
            "reason": "not_configured_type",
            "normalized_type": normalized_type,
        }

