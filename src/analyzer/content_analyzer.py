"""内容深度分析器
分析内容与业务方向的相关度（非简单关键词匹配）
"""

from loguru import logger
from typing import Dict, List, TYPE_CHECKING
import re

if TYPE_CHECKING:
    from src.schema import TenderItem


class ContentAnalyzer:
    """内容深度分析器"""
    
    def __init__(self, config: Dict):
        """初始化分析器
        
        Args:
            config: 配置字典
        """
        self.config = config
        logger.info("✅ 内容分析器初始化成功")
    
    def analyze_relevance(
        self,
        item: "TenderItem",
        direction: Dict,
        detail_content: str = ''
    ) -> Dict:
        """分析内容与业务方向的相关度
        
        检查：
        1. 标题关键词密度
        2. 正文内容相关度（非简单关键词匹配）
        3. 关键词位置权重（标题 > 开头 > 中间）
        4. 关键词上下文分析
        
        Args:
            item: 招标项目（TenderItem）
            direction: 业务方向配置
            detail_content: 详情页内容（可选）
            
        Returns:
            {
                'score': 0-100,  # 相关度评分
                'reason': '评分理由',
                'keywords_context': [{关键词上下文}],
                'density': 0-1.0  # 关键词密度
            }
        """
        title = item.title or ''
        summary = item.summary or ''
        content = detail_content or item.content_raw or ''
        
        # 获取业务方向关键词
        keywords_include = direction.get('keywords_include', [])
        keywords_exclude = direction.get('keywords_exclude', [])
        
        # 组合文本（权重：标题 > 摘要 > 内容）
        full_text = f"{title} {title} {summary} {content}"  # 标题重复增加权重
        
        # 1. 计算关键词匹配度
        matched_keywords = []
        keyword_contexts = []
        
        for keyword in keywords_include:
            count = full_text.count(keyword)
            if count > 0:
                matched_keywords.append(keyword)
                
                # 提取关键词上下文
                context = self._extract_context(full_text, keyword)
                keyword_contexts.append({
                    'keyword': keyword,
                    'count': count,
                    'context': context,
                    'in_title': keyword in title
                })
        
        # 2. 检查排除关键词
        has_exclude = any(keyword in full_text for keyword in keywords_exclude)
        if has_exclude:
            return {
                'score': 0,
                'reason': '包含排除关键词',
                'keywords_context': [],
                'density': 0
            }
        
        # 3. 计算基础分数
        if not matched_keywords:
            return {
                'score': 0,
                'reason': '未匹配任何关键词',
                'keywords_context': [],
                'density': 0
            }
        
        # 匹配率
        match_rate = len(matched_keywords) / len(keywords_include)
        base_score = match_rate * 60  # 基础分0-60分
        
        # 4. 位置权重加分（最多+20分）
        position_bonus = 0
        for ctx in keyword_contexts:
            if ctx['in_title']:
                position_bonus += 5  # 标题中出现+5分
        position_bonus = min(position_bonus, 20)  # 最多20分
        
        # 5. 密度加分（最多+10分）
        density = self._calculate_density(matched_keywords, full_text)
        density_bonus = density * 10
        
        # 6. 上下文相关性加分（最多+10分）
        context_bonus = self._analyze_context_relevance(keyword_contexts, direction)
        
        # 总分
        total_score = min(base_score + position_bonus + density_bonus + context_bonus, 100)
        
        # 评分理由
        reason = f"匹配{len(matched_keywords)}/{len(keywords_include)}个关键词"
        if any(ctx['in_title'] for ctx in keyword_contexts):
            reason += "，标题包含关键词"
        
        return {
            'score': round(total_score, 1),
            'reason': reason,
            'keywords_context': keyword_contexts,
            'density': round(density, 3)
        }
    
    def _extract_context(self, text: str, keyword: str, window: int = 30) -> str:
        """提取关键词上下文
        
        Args:
            text: 文本
            keyword: 关键词
            window: 上下文窗口大小（字符数）
            
        Returns:
            上下文字符串
        """
        try:
            pos = text.find(keyword)
            if pos == -1:
                return ''
            
            start = max(0, pos - window)
            end = min(len(text), pos + len(keyword) + window)
            
            context = text[start:end]
            # 添加省略号
            if start > 0:
                context = '...' + context
            if end < len(text):
                context = context + '...'
            
            return context
        except:
            return ''
    
    def _calculate_density(self, keywords: List[str], text: str) -> float:
        """计算关键词密度
        
        Args:
            keywords: 匹配的关键词列表
            text: 文本
            
        Returns:
            密度值 0-1.0
        """
        if not text or not keywords:
            return 0
        
        # 计算总关键词字符数
        total_keyword_chars = sum(text.count(kw) * len(kw) for kw in keywords)
        # 密度 = 关键词字符数 / 总字符数
        density = total_keyword_chars / len(text)
        
        return min(density, 1.0)
    
    def _analyze_context_relevance(
        self,
        keyword_contexts: List[Dict],
        direction: Dict
    ) -> float:
        """分析上下文相关性
        
        Args:
            keyword_contexts: 关键词上下文列表
            direction: 业务方向配置
            
        Returns:
            上下文相关性加分 0-10
        """
        # 简化版本：如果多个关键词同时出现在标题，说明相关性高
        title_keywords = [ctx for ctx in keyword_contexts if ctx['in_title']]
        
        if len(title_keywords) >= 2:
            return 10
        elif len(title_keywords) == 1:
            return 5
        else:
            return 0
