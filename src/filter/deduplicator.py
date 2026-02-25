"""去重处理器"""

from loguru import logger
from typing import List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.schema import TenderItem


class Deduplicator:
    """去重检查"""
    
    def __init__(self, db: Any) -> None:
        """初始化去重器
        
        Args:
            db: 数据库管理器实例
        """
        self.db = db
    
    def is_duplicate(self, item: "TenderItem") -> bool:
        """检查是否重复（完整检查）
        
        Args:
            item: 招标项目（TenderItem）
            
        Returns:
            True: 已存在（重复）
            False: 不存在（新公告）
        """
        return self.db.exists(item.project_id)
    
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
        """批量检查重复（优化版：使用 SQL IN 查询）
        
        Args:
            announcement_ids: ID列表
            
        Returns:
            {id: True/False, ...} True表示重复，False表示新公告
        """
        if not announcement_ids:
            return {}
        
        # 使用 SQL IN 语句批量查询（性能提升 90%+）
        placeholders = ','.join(['?' for _ in announcement_ids])
        query = f"SELECT id FROM announcements WHERE id IN ({placeholders})"
        
        try:
            cursor = self.db.conn.execute(query, announcement_ids)
            existing_ids = {row[0] for row in cursor.fetchall()}
            
            # 构建结果字典
            results = {aid: (aid in existing_ids) for aid in announcement_ids}
            
            logger.debug(f"批量去重检查: {len(announcement_ids)} 条公告，{len(existing_ids)} 条重复")
            return results
            
        except Exception as e:
            logger.warning(f"批量查询失败，降级为逐条查询: {e}")
            # 降级方案：逐条查询
            results = {}
            for aid in announcement_ids:
                results[aid] = self.db.exists(aid)
            return results
