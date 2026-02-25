"""地域匹配器"""

from loguru import logger
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.schema import TenderItem


class LocationMatcher:
    """地域匹配（按业务类别区分策略）"""
    
    # 地域关键词定义
    LIAONING = ['辽宁省', '辽宁']
    DALIAN = ['大连市', '大连']
    NORTHEAST = ['吉林省', '吉林', '黑龙江省', '黑龙江', '长春', '哈尔滨', '沈阳']
    NORTH_CHINA = ['河北省', '河北', '内蒙古', '石家庄', '呼和浩特']
    
    def match(self, item: "TenderItem", direction_id: str, direction_config: dict) -> dict:
        """检查地域匹配（根据业务类别区分策略）
        
        策略：
        1. 文化氛围类：必须是辽宁省，大连市高权重加分
        2. 其他类别：不限制，靠近辽宁省低权重加分（影响不大）
        
        Returns:
            {
                'matched': True/False,  # 是否通过地域要求
                'score': 0-1.0,  # 地域评分
                'bonus_score': 0-10,  # 地域加分（用于总评分）
                'is_priority': True/False,  # 是否优先地区
                'location': '具体地区',
                'reason': '匹配/不匹配原因'
            }
        """
        location_required = direction_config.get('location_required', False)
        location_bonus = direction_config.get('location_bonus', False)
        
        # 提取文本
        text = f"{item.title or ''} {item.content_raw or ''} {item.summary or ''} {item.location or ''}"
        
        # 识别地域
        in_liaoning = any(keyword in text for keyword in self.LIAONING)
        in_dalian = any(keyword in text for keyword in self.DALIAN)
        in_northeast = any(keyword in text for keyword in self.NORTHEAST)
        in_north_china = any(keyword in text for keyword in self.NORTH_CHINA)
        
        # 文化氛围类：必须辽宁省
        if location_required:
            if not in_liaoning:
                return {
                    'matched': False,
                    'score': 0,
                    'bonus_score': 0,
                    'is_priority': False,
                    'location': '非辽宁省',
                    'reason': '文化类必须为辽宁省项目'
                }
            
            # 通过辽宁省检查
            bonus_score = 5 if in_dalian else 0  # 大连市额外+5分
            
            return {
                'matched': True,
                'score': 1.0,
                'bonus_score': bonus_score,
                'is_priority': in_dalian,
                'location': '大连市' if in_dalian else '辽宁省',
                'reason': f"{'大连市优先' if in_dalian else '辽宁省项目'}"
            }
        
        # 其他类别：不限制，但地域加分（如果启用）
        if location_bonus:
            if in_liaoning:
                bonus_score = 3
                location_name = '辽宁省'
            elif in_northeast:
                bonus_score = 2
                location_name = '东北三省'
            elif in_north_china:
                bonus_score = 1
                location_name = '华北地区'
            else:
                bonus_score = 0
                location_name = '其他地区'
            
            return {
                'matched': True,
                'score': 1.0,
                'bonus_score': bonus_score,
                'is_priority': False,
                'location': location_name,
                'reason': f"地域加分 +{bonus_score}分"
            }
        
        # 不要求地域，也不加分
        return {
            'matched': True,
            'score': 1.0,
            'bonus_score': 0,
            'is_priority': False,
            'location': '全国',
            'reason': '不限地域'
        }
