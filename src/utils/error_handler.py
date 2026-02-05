"""统一的错误处理工具"""

import functools
import time
from typing import Callable, Any, Optional
from loguru import logger


def with_error_handling(
    default_return: Any = None,
    log_errors: bool = True,
    raise_on_error: bool = False
):
    """错误处理装饰器
    
    Args:
        default_return: 发生错误时的默认返回值
        log_errors: 是否记录错误日志
        raise_on_error: 是否在错误后重新抛出异常
        
    Examples:
        @with_error_handling(default_return=[], log_errors=True)
        def fetch_data():
            # 如果出错，返回 []
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.error(f"{func.__name__} 执行失败: {e}")
                
                if raise_on_error:
                    raise
                
                return default_return
        
        return wrapper
    return decorator


def retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None
):
    """失败重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 延迟时间倍增因子
        exceptions: 需要捕获的异常类型
        on_retry: 重试时的回调函数
        
    Examples:
        @retry_on_failure(max_retries=3, delay=1, backoff=2)
        def unstable_operation():
            # 失败时会重试，延迟: 1s, 2s, 4s
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"{func.__name__} 失败（第 {attempt + 1}/{max_retries} 次），"
                            f"{current_delay:.1f}秒后重试: {e}"
                        )
                        
                        if on_retry:
                            on_retry(attempt, e)
                        
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"{func.__name__} 失败（已重试 {max_retries} 次）: {e}"
                        )
            
            # 所有重试都失败，抛出最后一个异常
            raise last_exception
        
        return wrapper
    return decorator


class TenderCopilotError(Exception):
    """TenderCopilot 基础异常"""
    pass


class ConfigError(TenderCopilotError):
    """配置错误"""
    pass


class CrawlerError(TenderCopilotError):
    """爬虫错误"""
    pass


class AnalysisError(TenderCopilotError):
    """分析错误"""
    pass


class DatabaseError(TenderCopilotError):
    """数据库错误"""
    pass


class NotificationError(TenderCopilotError):
    """通知错误"""
    pass
