"""统一的日期解析工具"""

from datetime import datetime
from typing import Optional
from loguru import logger


class DateParser:
    """日期解析器"""
    
    # 支持的日期格式
    DATE_FORMATS = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d',
        '%Y年%m月%d日 %H:%M:%S',
        '%Y年%m月%d日 %H:%M',
        '%Y年%m月%d日',
        '%Y/%m/%d %H:%M:%S',
        '%Y/%m/%d %H:%M',
        '%Y/%m/%d',
    ]
    
    @classmethod
    def parse(cls, date_str: str) -> Optional[datetime]:
        """解析日期字符串
        
        Args:
            date_str: 日期字符串
            
        Returns:
            datetime 对象，解析失败返回 None
            
        Examples:
            >>> DateParser.parse("2024-02-05")
            datetime(2024, 2, 5, 0, 0)
            >>> DateParser.parse("2024年02月05日")
            datetime(2024, 2, 5, 0, 0)
        """
        if not date_str or not isinstance(date_str, str):
            return None
        
        # 清理字符串
        date_str = date_str.strip()
        
        # 尝试所有格式
        for fmt in cls.DATE_FORMATS:
            try:
                return datetime.strptime(date_str, fmt)
            except (ValueError, TypeError):
                continue
        
        logger.debug(f"无法解析日期: {date_str}")
        return None
    
    @classmethod
    def parse_or_default(cls, date_str: str, default: datetime = None) -> datetime:
        """解析日期，失败时返回默认值
        
        Args:
            date_str: 日期字符串
            default: 默认值，如果为 None 则返回当前时间
            
        Returns:
            datetime 对象
        """
        result = cls.parse(date_str)
        if result is not None:
            return result
        
        if default is None:
            default = datetime.now()
        
        return default
    
    @classmethod
    def format(cls, dt: datetime, fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
        """格式化日期
        
        Args:
            dt: datetime 对象
            fmt: 格式字符串
            
        Returns:
            格式化后的日期字符串
        """
        if not isinstance(dt, datetime):
            return ''
        
        try:
            return dt.strftime(fmt)
        except Exception as e:
            logger.debug(f"日期格式化失败: {e}")
            return ''
    
    @classmethod
    def is_date_string(cls, text: str) -> bool:
        """判断字符串是否是日期
        
        Args:
            text: 文本字符串
            
        Returns:
            True 如果是日期格式
        """
        return cls.parse(text) is not None
