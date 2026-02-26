"""可行性评分器（多维度评分，支持动态规则引擎）"""

import re
from datetime import datetime
from loguru import logger
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.schema import TenderItem


def _get_scoring_weights(config: Dict) -> Dict[str, int]:
    """从配置读取评分权重，缺失时使用默认值。"""
    defaults = {
        "title_keyword": 30,
        "content_keyword": 15,
        "location_match": 20,
        "budget_high": 10,
        "time_urgent": -10,
    }
    weights = config.get("scoring_config", {}).get("weights", {})
    return {k: weights.get(k, v) for k, v in defaults.items()}


# 自定义规则字段映射：配置中的 field 值 -> 实际数据来源
CUSTOM_RULE_FIELD_MAP = {
    "title": lambda item, ai: (item.title or ""),
    "content": lambda item, ai: f"{item.content_raw or ''} {item.summary or ''}",
    "qualifications": lambda item, ai: (ai or {}).get("confidentiality_req") or getattr(item, "confidentiality_req", "") or "",
    "budget": lambda item, ai: (ai or {}).get("budget_info") or (ai or {}).get("budget") or getattr(item, "budget", None) or "",
    "location": lambda item, ai: item.location or "",
}


def _extract_field_value(item: "TenderItem", ai_extracted: Optional[Dict], field: str) -> str:
    """根据 rule['field'] 从 item 中提取对应值。"""
    fn = CUSTOM_RULE_FIELD_MAP.get(field)
    if fn:
        return str(fn(item, ai_extracted) or "").strip()
    # 尝试从 item 或 ai_extracted 直接取属性
    val = getattr(item, field, None) or (ai_extracted or {}).get(field)
    return str(val or "").strip()


def _split_keywords(value: str) -> list:
    """智能切词：将包含中英文逗号、顿号、空格的字符串切分为关键词列表。"""
    if not value or not str(value).strip():
        return []
    return [k.strip() for k in re.split(r"[,，、\s]+", str(value)) if k.strip()]


def _evaluate_custom_rule(
    item: "TenderItem",
    ai_extracted: Optional[Dict],
    rule: Dict,
) -> bool:
    """判断自定义规则是否命中。支持多态操作符与智能切词。"""
    field = rule.get("field", "")
    operator = rule.get("operator", "contains_any")
    value = rule.get("value", "")
    if not field:
        return False
    item_value = _extract_field_value(item, ai_extracted, field)
    value_str = str(value or "").strip()

    # 兼容旧配置：contains -> contains_any, not_contains -> not_contains_any
    if operator == "contains":
        operator = "contains_any"
    if operator == "not_contains":
        operator = "not_contains_any"

    # 文本类操作符：智能切词
    keywords = _split_keywords(value_str)
    if not keywords:
        keywords = [value_str] if value_str else []

    if operator == "contains_any":
        return any(kw in item_value for kw in keywords)
    if operator == "contains_all":
        return all(kw in item_value for kw in keywords)
    if operator == "not_contains_any":
        return not any(kw in item_value for kw in keywords)
    if operator == "equals":
        return item_value.strip() == value_str

    if operator == "greater_than":
        try:
            cmp_val = float(value_str)
            budget_wan = _parse_budget_wan(item_value) if field == "budget" else None
            if budget_wan is not None:
                return budget_wan > cmp_val
            return float(item_value.replace(",", "").replace(" ", "")) > cmp_val
        except (ValueError, TypeError):
            return False
    if operator == "less_than":
        try:
            cmp_val = float(value_str)
            budget_wan = _parse_budget_wan(item_value) if field == "budget" else None
            if budget_wan is not None:
                return budget_wan < cmp_val
            return float(item_value.replace(",", "").replace(" ", "")) < cmp_val
        except (ValueError, TypeError):
            return False
    return False


def _parse_budget_wan(text: str) -> Optional[float]:
    """从预算文本中解析金额（万元）。支持「50万」「500000元」「50万元」等格式。"""
    if not text or not str(text).strip():
        return None
    text = str(text).strip()
    m = re.search(r"([\d.]+)\s*[万千]?元?", text)
    if not m:
        return None
    try:
        val = float(m.group(1))
        if "万" in text or "万千" in text:
            return val
        if "元" in text and "万" not in text:
            return val / 10000
        return val
    except (ValueError, TypeError):
        return None


class FeasibilityScorer:
    """可行性评分（支持多维度评分和分类策略）"""
    
    def __init__(self, config: Dict):
        """初始化评分器
        
        Args:
            config: 配置字典
        """
        self.config = config
        logger.info("✅ 评分器初始化成功")
    
    def calculate(
        self,
        item: "TenderItem",
        match_results: Dict,
        location_result: Dict,
        content_analysis: Optional[Dict] = None,
        ai_extracted: Optional[Dict] = None,
        attachment_analysis: Optional[Dict] = None,
        direction_id: str = None
    ) -> Dict:
        """计算综合评分（0-100），使用可配置的动态规则引擎。
        
        评分维度（从 scoring_config.yaml 读取权重）：
        - title_keyword: 标题命中关键词
        - content_keyword: 正文命中关键词
        - location_match: 命中优先地域
        - budget_high: 高预算加分（>50万）
        - time_urgent: 时间紧迫扣分（距获取文件截止不足3天）
        """
        weights = _get_scoring_weights(self.config)
        budget_threshold = self.config.get("scoring_config", {}).get("budget_high_threshold_wan", 50)
        time_urgent_days = self.config.get("scoring_config", {}).get("time_urgent_threshold_days", 3)

        best_match = max(match_results.values(), key=lambda x: x['score'])
        matched_kw = best_match.get("matched_keywords", [])
        title = item.title or ""
        content = (item.content_raw or "") + " " + (item.summary or "")

        score_breakdown = []
        total = 0.0

        # 1. 标题命中关键词
        title_matched = [kw for kw in matched_kw if kw in title]
        if title_matched:
            pts = weights["title_keyword"]
            total += pts
            kw_str = ", ".join(title_matched[:5])
            if len(title_matched) > 5:
                kw_str += f" 等{len(title_matched)}个"
            score_breakdown.append({"rule": f"标题命中关键词 [{kw_str}]", "points": pts})

        # 2. 正文命中关键词
        content_only = [kw for kw in matched_kw if kw in content and kw not in title]
        if content_only:
            pts = weights["content_keyword"]
            total += pts
            kw_str = ", ".join(content_only[:5])
            if len(content_only) > 5:
                kw_str += f" 等{len(content_only)}个"
            score_breakdown.append({"rule": f"正文命中关键词 [{kw_str}]", "points": pts})

        # 若无标题/正文命中，保留基础关键词分（兼容）
        if not title_matched and not content_only and matched_kw:
            pts = weights["title_keyword"]
            total += pts
            kw_str = ", ".join(matched_kw[:5])
            score_breakdown.append({"rule": f"关键词匹配 [{kw_str}]", "points": pts})

        # 3. 地域加分（命中优先地域）
        if location_result.get("bonus_score", 0) > 0 or location_result.get("is_priority"):
            pts = weights["location_match"]
            total += pts
            loc_reason = location_result.get("reason", "优先地域")
            score_breakdown.append({"rule": f"地域匹配 [{loc_reason}]", "points": pts})

        # 4. 高预算加分
        budget_text = (
            (ai_extracted or {}).get("budget_info")
            or (ai_extracted or {}).get("budget")
            or getattr(item, "budget", None)
            or ""
        )
        budget_wan = _parse_budget_wan(str(budget_text))
        if budget_wan is not None and budget_wan >= budget_threshold:
            pts = weights["budget_high"]
            total += pts
            score_breakdown.append({"rule": f"高预算加分 (≥{budget_threshold}万)", "points": pts})

        # 5. 时间紧迫扣分
        time_score_result = self._calculate_time_score(item, ai_extracted)
        doc_deadline_str = (
            (ai_extracted or {}).get("doc_deadline")
            or getattr(item, "doc_deadline", None)
            or item.deadline
        )
        days_left = self._calculate_days_left(str(doc_deadline_str or "")) if doc_deadline_str else 999
        if 0 <= days_left < time_urgent_days:
            pts = weights["time_urgent"]
            total += pts
            score_breakdown.append({"rule": f"时间紧迫（距获取文件截止不足{time_urgent_days}天）", "points": pts})

        # 6. 内容相关度（补充）
        if content_analysis:
            content_score = (content_analysis.get("score", 0) / 100) * 15
        else:
            content_score = 5
        total += content_score
        score_breakdown.append({"rule": "内容相关度", "points": round(content_score, 1)})

        # 7. 时间评分（新鲜度+截止充足度）
        time_total = time_score_result["total"]
        time_score = min(time_total / 15 * 10, 10) if time_total > 0 else 0
        total += time_score
        score_breakdown.append({"rule": "时间评分（新鲜度+截止充足度）", "points": round(time_score, 1)})

        # 8. 自定义规则（支持完全自定义的动态规则引擎）
        custom_rules = self.config.get("scoring_config", {}).get("custom_rules") or []
        for rule in custom_rules:
            if not isinstance(rule, dict):
                continue
            name = rule.get("name", "自定义规则")
            score_val = rule.get("score", 0)
            try:
                score_val = int(score_val)
            except (TypeError, ValueError):
                score_val = 0
            if _evaluate_custom_rule(item, ai_extracted, rule):
                total += score_val
                score_breakdown.append({"rule": f"命中自定义规则 [{name}]", "points": score_val})

        final_total = max(-100, min(100, round(total, 1)))
        score_breakdown.append({"rule": "🏆 总计", "points": final_total})

        ai_completeness = self._calculate_ai_completeness(ai_extracted) if ai_extracted else 0
        attachment_quality_score = attachment_analysis.get("relevance_score", 0) if attachment_analysis else 0

        scores = {
            "direction_match": total,
            "content_relevance": content_score,
            "time": time_score,
            "location_bonus": weights["location_match"] if (location_result.get("bonus_score", 0) > 0 or location_result.get("is_priority")) else 0,
            "ai_completeness_ratio": ai_completeness,
            "attachment_relevance": attachment_quality_score,
        }

        return {
            "total": final_total,
            "base_score": round(total, 1),
            "breakdown": {k: round(v, 1) for k, v in scores.items()},
            "score_breakdown": score_breakdown,
            "level": self._get_level(final_total),
            "passes_filter": self._check_second_filter(
                final_total,
                total,
                time_score_result.get("deadline_adequacy", 0),
            ),
            "time_score_details": time_score_result.get("details", {}),
        }
    
    def _calculate_ai_completeness(self, ai_extracted: Dict) -> float:
        """计算AI提取的完整性（0-1.0）
        
        检查关键字段：confidentiality_req, project_summary, doc_deadline, bid_deadline, budget_info
        """
        if not ai_extracted:
            return 0
        key_fields = ['confidentiality_req', 'project_summary', 'doc_deadline', 'bid_deadline', 'budget_info']
        empty_vals = ['无', '未提供', 'N/A', '', '未知', '未公布']
        valid_count = sum(
            1 for f in key_fields
            if (ai_extracted.get(f) or '').strip() and str(ai_extracted.get(f) or '').strip() not in empty_vals
        )
        return valid_count / len(key_fields)
    
    def _calculate_time_score(self, item: "TenderItem", ai_extracted: Optional[Dict] = None) -> Dict:
        """计算时间综合评分（优化版）
        
        评分维度：
        - 发布新鲜度 (0-5分): 越新越好
        - 截止充足度 (0-10分): 距离截止时间是否充足
        
        注意：在新的整体策略中，时间只用于区分“是否已过期”和排序，
        不再作为强力淘汰条件，但如果明确已截止，则整体会被视为丢弃档。
        """
        from datetime import datetime, timedelta
        
        now = datetime.now()
        score = {'publish_freshness': 0, 'deadline_adequacy': 0, 'details': {}}
        
        # 1. 发布新鲜度 (5分)
        publish_date_str = item.publish_date or item.pub_date or ''
        if publish_date_str:
            try:
                publish_date = self._parse_date(publish_date_str)
                if publish_date:
                    days_ago = (now - publish_date).days
                    if days_ago <= 1:
                        score['publish_freshness'] = 5
                        score['details']['freshness'] = '今天/昨天发布'
                    elif days_ago <= 3:
                        score['publish_freshness'] = 4
                        score['details']['freshness'] = f'{days_ago}天前发布'
                    elif days_ago <= 7:
                        score['publish_freshness'] = 3
                        score['details']['freshness'] = f'{days_ago}天前发布'
                    elif days_ago <= 14:
                        score['publish_freshness'] = 2
                        score['details']['freshness'] = f'{days_ago}天前发布'
                    else:
                        score['publish_freshness'] = 1
                        score['details']['freshness'] = f'{days_ago}天前发布'
            except:
                score['publish_freshness'] = 2  # 解析失败给默认分
                score['details']['freshness'] = '发布时间未知'
        
        # 2. 截止充足度 (10分)
        deadline_str = (
            (getattr(item, 'bid_deadline', '') or getattr(item, 'doc_deadline', ''))
            or (ai_extracted and (
                ai_extracted.get('bid_deadline') or ai_extracted.get('doc_deadline')
                or ai_extracted.get('opening_time') or ai_extracted.get('deadline')
            ))
            or item.deadline
        )
        
        if deadline_str:
            try:
                days_left = self._calculate_days_left(deadline_str)
                
                if days_left < 0:
                    # 已截止：在上层会被视为丢弃，这里标记为 0 分
                    score['deadline_adequacy'] = 0
                    score['details']['deadline'] = '已截止'
                elif days_left <= 3:
                    # 时间较紧，但仍可作为候选
                    score['deadline_adequacy'] = 4
                    score['details']['deadline'] = f'仅剩{days_left}天'
                elif days_left <= 7:
                    score['deadline_adequacy'] = 7
                    score['details']['deadline'] = f'剩余{days_left}天'
                elif days_left <= 15:
                    score['deadline_adequacy'] = 9
                    score['details']['deadline'] = f'剩余{days_left}天'
                else:
                    score['deadline_adequacy'] = 10
                    score['details']['deadline'] = f'剩余{days_left}天，充足'
            except:
                score['deadline_adequacy'] = 6  # 解析失败给略高于中等分
                score['details']['deadline'] = '截止时间解析失败'
        else:
            # 没有截止时间，给中等偏上的分，并在文案中提示
            score['deadline_adequacy'] = 7
            score['details']['deadline'] = '未提供截止时间'
        
        score['total'] = score['publish_freshness'] + score['deadline_adequacy']
        return score
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """解析日期字符串
        
        Args:
            date_str: 日期字符串
            
        Returns:
            datetime对象，失败返回None
        """
        if not date_str:
            return None
        
        try:
            # 尝试多种日期格式
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', 
                       '%Y年%m月%d日 %H:%M:%S', '%Y年%m月%d日 %H:%M', '%Y年%m月%d日']:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except:
                    continue
            
            # 如果包含"年月日"但格式不标准，尝试提取
            import re
            match = re.search(r'(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})', date_str)
            if match:
                year, month, day = match.groups()
                return datetime(int(year), int(month), int(day))
            
            return None
        except:
            return None
    
    def _calculate_deadline_score(self, item: "TenderItem", ai_extracted: Optional[Dict]) -> float:
        """计算时间充足度评分（0-10）
        
        Args:
            announcement: 公告信息
            ai_extracted: AI提取结果
            
        Returns:
            时间评分 0-10
        """
        # 尝试从多个来源获取截止时间
        deadline_str = (
            (getattr(item, 'bid_deadline', '') or getattr(item, 'doc_deadline', ''))
            or (ai_extracted and (
                ai_extracted.get('bid_deadline') or ai_extracted.get('doc_deadline')
                or ai_extracted.get('opening_time') or ai_extracted.get('deadline')
            ))
            or item.deadline
        )
        
        if not deadline_str:
            # 没有明确截止时间，给中等分
            return 5
        
        try:
            days_left = self._calculate_days_left(deadline_str)
            
            if days_left >= 7:
                return 10  # 充足时间
            elif days_left >= 5:
                return 8
            elif days_left >= 3:
                return 6  # 最少3天（用户要求）
            elif days_left >= 1:
                return 3  # 时间紧张
            else:
                return 0  # 已过期
        except:
            return 5  # 解析失败，给中等分
    
    def _calculate_days_left(self, deadline_str: str) -> int:
        """计算剩余天数
        
        Args:
            deadline_str: 截止时间字符串
            
        Returns:
            剩余天数
        """
        try:
            # 尝试多种日期格式
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', 
                       '%Y年%m月%d日 %H:%M', '%Y年%m月%d日']:
                try:
                    deadline = datetime.strptime(deadline_str.strip(), fmt)
                    days = (deadline - datetime.now()).days
                    return max(0, days)
                except:
                    continue
            
            # 如果包含"年月日"但格式不标准，尝试提取
            import re
            match = re.search(r'(\d{4})[年-](\d{1,2})[月-](\d{1,2})', deadline_str)
            if match:
                year, month, day = match.groups()
                deadline = datetime(int(year), int(month), int(day))
                days = (deadline - datetime.now()).days
                return max(0, days)
            
            return 7  # 默认7天
        except:
            return 7
    
    def _check_second_filter(
        self,
        total_score: float,
        ai_extracted: Optional[Dict],
        deadline_score: float
    ) -> bool:
        """二次过滤检查
        
        过滤标准：
        1. 投标时间 >= 3天
        2. 综合评分 >= 60分
        3. 没有明确不符合的资格要求（可选）
        
        Args:
            total_score: 总分
            ai_extracted: AI提取结果
            deadline_score: 时间评分
            
        Returns:
            True: 通过二次过滤
            False: 不通过
        """
        # 1. 首先检查总分是否达到基础推荐门槛
        min_score = self.config.get("scoring", {}).get("min_total_score", 60)
        if total_score < min_score:
            return False

        # 2. 要求方向匹配足够强（方向分至少 40/60）
        # 这里通过传入的 direction_score_z (实际值) 来判断
        # 注意：direction_score_z 在调用处转换为 0-60 区间
        # 为兼容旧签名，这里只检查总分，方向强弱主要体现在总分上

        # 3. 截止时间：只要不是“明显时间不足”即可
        # deadline_score >= 6 代表至少还有约 3 天，这里略微放宽
        if deadline_score < 3:
            return False
        
        # TODO: 可以添加资格要求检查（需要AI模型支持）
        
        return True
    
    def _get_level(self, score: float) -> str:
        """评分等级
        
        Args:
            score: 总分
            
        Returns:
            等级描述
        """
        if score >= 80:
            return '高度推荐'
        elif score >= 70:
            return '强烈推荐'
        elif score >= 60:
            return '推荐'
        elif score >= 50:
            return '可考虑'
        else:
            return '不推荐'
