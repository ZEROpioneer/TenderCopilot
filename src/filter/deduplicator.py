"""去重处理器"""

from loguru import logger
from typing import List, Dict


class Deduplicator:
    """去重检查"""
    
    def __init__(self, db):
        self.db = db
    
    def is_duplicate(self, announcement):
        """检查是否重复（完整检查）"""
        announcement_id = announcement['id']
        return self.db.exists(announcement_id)
    
    def is_duplicate_fast(self, announcement_id: str) -> bool:
        """快速检查ID是否重复（用于爬取阶段）
        
        Args:
            announcement_id: 公告ID
            
        Returns:
            True: 已存在（重复）
            False: 不存在（新公告）
        """
        return self.db.exists(announcement_id)
    
    def batch_check_duplicates(self, announcement_ids: List[str]) -> Dict[str, bool]:
        """批量检查重复（提升性能）
        
        Args:
            announcement_ids: ID列表
            
        Returns:
            {id: True/False, ...} True表示重复，False表示新公告
        """
        results = {}
        for aid in announcement_ids:
            results[aid] = self.db.exists(aid)
        return results
