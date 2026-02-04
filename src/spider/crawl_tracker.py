"""
爬取追踪器
管理爬取历史，实现增量爬取策略
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from loguru import logger


class CrawlTracker:
    """爬取追踪器"""
    
    def __init__(self, db_manager, config: Dict):
        """初始化追踪器
        
        Args:
            db_manager: 数据库管理器
            config: 配置字典
        """
        self.db = db_manager
        self.config = config
        self.crawl_strategy = config.get('filter_settings', {}).get('crawl_strategy', {})
        
        logger.info("✅ 爬取追踪器初始化成功")
    
    def get_last_crawl_time(self) -> datetime:
        """获取上次爬取时间（用于增量爬取）
        
        Returns:
            上次爬取时间，如果是首次运行则返回24小时前
        """
        last_crawl = self._get_last_crawl_time()
        
        if not last_crawl:
            # 首次运行：返回24小时前（保守起见）
            default_hours = self.crawl_strategy.get('initial_hours', 24)
            last_crawl = datetime.now() - timedelta(hours=default_hours)
            logger.info(f"🆕 首次运行，爬取最近 {default_hours} 小时的公告")
        else:
            hours_since_last = (datetime.now() - last_crawl).total_seconds() / 3600
            logger.info(f"🔄 增量爬取，距上次爬取 {hours_since_last:.1f} 小时")
        
        return last_crawl
    
    def get_date_range(self) -> Tuple[str, str]:
        """根据爬取策略计算日期范围（用于API调用）
        
        Returns:
            (start_date, end_date) 格式: 'YYYY-MM-DD'
        """
        last_crawl = self.get_last_crawl_time()
        end_date = datetime.now()
        
        return (
            last_crawl.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
    
    def update_last_crawl_time(self, crawl_time: datetime = None):
        """更新爬取时间记录
        
        Args:
            crawl_time: 爬取时间，默认为当前时间
        """
        if crawl_time is None:
            crawl_time = datetime.now()
        
        logger.info(f"📝 更新爬取时间: {crawl_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def record_crawl(self, count: int, success: bool = True):
        """记录本次爬取
        
        Args:
            count: 爬取数量
            success: 是否成功
        """
        try:
            self.db.execute_query("""
                INSERT INTO crawl_history (crawl_time, announcement_count, success)
                VALUES (?, ?, ?)
            """, (datetime.now().isoformat(), count, 1 if success else 0))
            
            logger.info(f"📝 已记录爬取历史: {count} 条，状态: {'成功' if success else '失败'}")
        except Exception as e:
            logger.error(f"❌ 记录爬取历史失败: {e}")
    
    def _get_last_crawl_time(self) -> Optional[datetime]:
        """获取上次成功爬取的时间
        
        Returns:
            上次爬取时间，如果没有则返回 None
        """
        try:
            result = self.db.execute_query("""
                SELECT crawl_time FROM crawl_history 
                WHERE success = 1 
                ORDER BY crawl_time DESC 
                LIMIT 1
            """)
            
            if result:
                time_str = result[0][0]
                return datetime.fromisoformat(time_str)
            
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ 获取上次爬取时间失败: {e}")
            return None
    
    def get_statistics(self) -> Dict:
        """获取爬取统计信息
        
        Returns:
            统计信息字典
        """
        try:
            # 总爬取次数
            total_crawls = self.db.execute_query("""
                SELECT COUNT(*) FROM crawl_history
            """)[0][0]
            
            # 成功次数
            successful_crawls = self.db.execute_query("""
                SELECT COUNT(*) FROM crawl_history WHERE success = 1
            """)[0][0]
            
            # 总公告数
            total_announcements = self.db.execute_query("""
                SELECT SUM(announcement_count) FROM crawl_history WHERE success = 1
            """)[0][0] or 0
            
            # 最近一次爬取
            last_crawl = self._get_last_crawl_time()
            
            # 今天爬取次数
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_crawls = self.db.execute_query("""
                SELECT COUNT(*) FROM crawl_history 
                WHERE crawl_time >= ?
            """, (today_start.isoformat(),))[0][0]
            
            return {
                'total_crawls': total_crawls,
                'successful_crawls': successful_crawls,
                'success_rate': f"{successful_crawls / total_crawls * 100:.1f}%" if total_crawls > 0 else "N/A",
                'total_announcements': total_announcements,
                'last_crawl_time': last_crawl.strftime('%Y-%m-%d %H:%M:%S') if last_crawl else 'N/A',
                'today_crawls': today_crawls
            }
            
        except Exception as e:
            logger.error(f"❌ 获取统计信息失败: {e}")
            return {}
    
    def cleanup_old_records(self, days: int = 90):
        """清理旧的爬取记录
        
        Args:
            days: 保留最近多少天的记录
        """
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            deleted = self.db.execute_query("""
                DELETE FROM crawl_history 
                WHERE crawl_time < ?
            """, (cutoff_date,))
            
            logger.info(f"🗑️ 已清理 {days} 天前的爬取记录")
            
        except Exception as e:
            logger.error(f"❌ 清理爬取记录失败: {e}")
