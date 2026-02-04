"""可行性评分器"""

from datetime import datetime
from loguru import logger


class FeasibilityScorer:
    """可行性评分"""
    
    def calculate(self, announcement, match_results, location_result):
        """计算可行性评分（0-100）"""
        scores = {
            'keyword_match': 0,      # 关键词匹配度 (0-40)
            'location_match': 0,     # 地域匹配度 (0-30)
            'deadline_urgency': 0    # 截止时间紧急度 (0-30)
        }
        
        # 1. 关键词匹配分（最高 40 分）
        best_match = max(match_results.values(), key=lambda x: x['score'])
        scores['keyword_match'] = best_match['score'] * 40
        
        # 2. 地域匹配分（最高 30 分）
        if location_result.get('matched', False):
            scores['location_match'] = location_result.get('score', 1.0) * 30
        
        # 3. 截止时间分（最高 30 分）
        if announcement.get('deadline'):
            days_left = self._calculate_days_left(announcement['deadline'])
            if days_left >= 7:
                scores['deadline_urgency'] = 30
            elif days_left >= 3:
                scores['deadline_urgency'] = 20
            elif days_left >= 1:
                scores['deadline_urgency'] = 10
        else:
            scores['deadline_urgency'] = 15  # 默认中等分数
        
        total = sum(scores.values())
        return {
            'total': round(total, 2),
            'breakdown': scores,
            'level': self._get_level(total)
        }
    
    def _calculate_days_left(self, deadline_str):
        """计算剩余天数"""
        try:
            deadline = datetime.fromisoformat(deadline_str)
            days = (deadline - datetime.now()).days
            return max(0, days)
        except:
            return 7  # 默认7天
    
    def _get_level(self, score):
        """评分等级"""
        if score >= 80:
            return '高度推荐'
        elif score >= 60:
            return '推荐'
        elif score >= 40:
            return '可考虑'
        else:
            return '不推荐'
