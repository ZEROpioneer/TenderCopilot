"""定时任务调度（main.py --mode schedule 使用）"""

from datetime import datetime

import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

# 强制使用上海时区
TZ = pytz.timezone("Asia/Shanghai")


class TaskScheduler:
    """定时任务调度器（BlockingScheduler，用于独立进程模式）"""

    def __init__(self, config, pipeline_func):
        self.scheduler = BlockingScheduler(timezone=TZ)
        self.config = config
        self.pipeline_func = pipeline_func

    def add_daily_tasks(self):
        """添加每日定时任务"""
        times = self.config.get("times", ["09:00", "11:55", "13:00", "17:55"])
        if isinstance(times, str):
            times = [t.strip() for t in times.split("\n") if t.strip()]

        for time_str in times:
            time_str = str(time_str or "").strip()
            if not time_str:
                continue
            try:
                parts = time_str.split(":")
                hour, minute = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
            except (ValueError, IndexError):
                logger.warning(f"⏰ 跳过无效时间格式: {time_str}")
                continue

            job_id = f"daily_task_{time_str}"
            self.scheduler.add_job(
                func=self._run_task,
                trigger=CronTrigger(hour=hour, minute=minute, timezone=TZ),
                id=job_id,
                name=f"每日招标爬取任务 {time_str}",
                replace_existing=True,
            )
            logger.info(f"✅ 已添加定时任务: 每天 {time_str} (id={job_id})")

        for j in self.scheduler.get_jobs():
            next_run = getattr(j, "next_run_time", None)
            if next_run:
                logger.info(f"   下次执行: {j.id} -> {next_run.astimezone(TZ).strftime('%Y-%m-%d %H:%M:%S')}")
    
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
