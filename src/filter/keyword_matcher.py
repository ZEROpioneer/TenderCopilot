"""关键词匹配器"""

from loguru import logger
from typing import Dict, List, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.schema import TenderItem


class KeywordMatcher:
    """业务方向关键词匹配"""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """初始化关键词匹配器
        
        Args:
            config: 配置字典，包含 business_directions 和 global_exclude
        """
        self.directions = config['business_directions']
        self.exclude_keywords = config['global_exclude']['keywords']
    
    def match(self, item: "TenderItem") -> Optional[Dict[str, Dict[str, Any]]]:
        """匹配业务方向
        
        Args:
            item: 招标项目（TenderItem）
            
        Returns:
            匹配结果字典，如果无匹配则返回 None
        """
        title = item.title or ""
        content = item.content_raw or ""
        summary = item.summary or ""
        text = f"{title} {summary} {content}"
        
        # 检查排除关键词
        if self._should_exclude(text):
            logger.debug(f"⏭️ 跳过（包含排除关键词）: {title[:50]}")
            return None
        
        results = {}
        for direction_id, direction in self.directions.items():
            score = self._calculate_score(text, direction)
            if score > 0:
                matched_keywords = self._find_matched_keywords(text, direction)
                results[direction_id] = {
                    'name': direction['name'],
                    'score': score,
                    'matched_keywords': matched_keywords,
                    'location_required': direction.get('location_required', False)
                }
                logger.debug(f"✅ 匹配到 [{direction['name']}]: {title[:40]}... (评分: {score:.2f}, 关键词: {matched_keywords})")
        
        if not results:
            logger.debug(f"⏭️ 无匹配: {title[:50]}")
        
        return results if results else None
    
    def _calculate_score(self, text, direction):
        """计算匹配分数"""
        keywords = direction['keywords_include']
        matches = sum(1 for kw in keywords if kw in text)
        return matches / len(keywords) if keywords else 0
    
    def _find_matched_keywords(self, text, direction):
        """找到匹配的关键词"""
        keywords = direction['keywords_include']
        return [kw for kw in keywords if kw in text]
    
    def _should_exclude(self, text):
        """检查是否应排除"""
        return any(kw in text for kw in self.exclude_keywords)
