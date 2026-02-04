"""地域匹配器"""

from loguru import logger


class LocationMatcher:
    """地域匹配（仅文化氛围类）"""
    
    PROVINCES = ['辽宁省', '辽宁']
    CITIES = ['大连市', '大连']
    
    def match(self, announcement, direction_id, direction_config):
        """检查地域匹配"""
        # 只有文化氛围类需要地域检查
        if direction_id != 'cultural_atmosphere':
            return {'required': False, 'matched': True, 'score': 1.0}
        
        text = f"{announcement['title']} {announcement.get('content', '')} {announcement.get('location', '')}"
        
        # 检查是否在辽宁省
        in_province = any(p in text for p in self.PROVINCES)
        in_city = any(c in text for c in self.CITIES)
        
        if not in_province:
            return {'required': True, 'matched': False, 'score': 0}
        
        # 大连市加分
        score = 1.2 if in_city else 1.0
        
        return {
            'required': True,
            'matched': True,
            'score': score,
            'province': in_province,
            'city': in_city
        }
