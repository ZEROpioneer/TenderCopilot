"""去重处理器"""

from loguru import logger


class Deduplicator:
    """去重检查"""
    
    def __init__(self, db):
        self.db = db
    
    def is_duplicate(self, announcement):
        """检查是否重复"""
        announcement_id = announcement['id']
        return self.db.exists(announcement_id)
