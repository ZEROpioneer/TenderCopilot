"""定时任务调度"""

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import time
from loguru import logger
import pytz


class TaskScheduler:
    """定时任务调度器"""
    
    def __init__(self, config, pipeline_func):
        timezone = config.get('timezone', 'Asia/Shanghai')
        self.scheduler = BlockingScheduler(timezone=pytz.timezone(timezone))
        self.config = config
        self.pipeline_func = pipeline_func
    
    def add_daily_tasks(self):
        """添加每日4次定时任务"""
        times = self.config.get('times', ['09:00', '11:55', '13:00', '17:55'])
        
        for time_str in times:
            hour, minute = map(int, time_str.split(':'))
            
            self.scheduler.add_job(
                func=self._run_task,
                trigger=CronTrigger(hour=hour, minute=minute),
                id=f'daily_task_{time_str}',
                name=f'每日招标爬取任务 {time_str}',
                replace_existing=True
            )
            logger.info(f"✅ 已添加定时任务: 每天 {time_str}")
    
    def _run_task(self):
        """执行任务"""
        task_id = datetime.now().strftime('%Y%m%d%H%M%S')
        logger.info(f"🚀 开始执行任务: {task_id}")
        
        start_time = datetime.now()
        
        try:
            # 调用流程函数
            self.pipeline_func()
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.success(f"✅ 任务完成: {task_id} (耗时: {duration:.2f}秒)")
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"❌ 任务失败: {task_id} - {e}")
    
    def start(self):
        """启动调度器"""
        logger.info("🚀 定时任务调度器启动")
        logger.info(f"📅 定时任务: {self.config.get('times')}")
        self.scheduler.start()
    
    def shutdown(self):
        """关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("🔚 定时任务调度器已关闭")
