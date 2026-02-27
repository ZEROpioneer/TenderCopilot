"""定时任务引擎 - 随 Web 服务启动，支持配置热重载。"""
import sys
from pathlib import Path

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 强制使用上海时区
TZ = pytz.timezone("Asia/Shanghai")

_scheduler: BackgroundScheduler | None = None


def _load_scheduler_config():
    """从 settings.yaml 读取 scheduler 配置。"""
    import yaml
    path = CONFIG_DIR / "settings.yaml"
    if not path.exists():
        return {"enabled": False, "times": [], "timezone": "Asia/Shanghai"}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    sched = data.get("scheduler") or {}
    times = sched.get("times") or []
    if isinstance(times, str):
        times = [t.strip() for t in times.split("\n") if t.strip()]
    return {
        "enabled": sched.get("enabled", True),
        "times": times,
        "timezone": sched.get("timezone", "Asia/Shanghai"),
    }


def _run_pipeline_job():
    """调度器触发的流水线任务（延迟导入避免循环依赖）。"""
    import os
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        from main import TenderCopilot
        app = TenderCopilot()
        app.run_pipeline()
    except Exception as e:
        logger.error(f"❌ 定时任务执行失败: {e}")
        raise


def _get_scheduler() -> BackgroundScheduler:
    """获取或创建调度器实例。"""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone=TZ)
        logger.info("⏰ 调度器已创建（时区: Asia/Shanghai）")
    return _scheduler


def reload_scheduler() -> None:
    """热重载定时任务：清除旧任务，按最新配置重新添加。"""
    sched = _get_scheduler()
    sched.remove_all_jobs()
    cfg = _load_scheduler_config()

    if not cfg.get("enabled", True):
        logger.info("⏰ 定时任务已关闭（enable_scheduler=false），未添加任何任务")
        return

    times = cfg.get("times") or ["09:00", "11:55", "13:00", "17:55"]
    if isinstance(times, str):
        times = [t.strip() for t in times.split("\n") if t.strip()]

    added = []
    for time_str in times:
        time_str = str(time_str or "").strip()
        if not time_str:
            continue
        try:
            parts = time_str.split(":")
            h = int(parts[0]) if parts else 0
            m = int(parts[1]) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            logger.warning(f"⏰ 跳过无效时间格式: {time_str}")
            continue

        job_id = f"spider_job_{h:02d}_{m:02d}"
        sched.add_job(
            _run_pipeline_job,
            trigger=CronTrigger(hour=h, minute=m, timezone=TZ),
            id=job_id,
            name=f"招标爬取 {time_str}",
            replace_existing=True,
        )
        added.append(time_str)
        logger.info(f"✅ 已添加定时任务: 每天 {time_str} (id={job_id})")

    if added:
        logger.success(f"✅ 定时任务已热更新，当前设定时间: {added}")
        jobs = sched.get_jobs()
        for j in jobs:
            next_run = getattr(j, "next_run_time", None)
            if next_run:
                logger.info(f"   下次执行: {j.id} -> {next_run.astimezone(TZ).strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        logger.warning("⏰ 未添加任何定时任务（times 为空或格式错误）")


def start_scheduler() -> None:
    """启动调度器并加载任务。"""
    sched = _get_scheduler()
    if not sched.running:
        reload_scheduler()
        sched.start()
        logger.success("🚀 定时任务调度器已启动")


def shutdown_scheduler() -> None:
    """关闭调度器。"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("🔚 定时任务调度器已关闭")
    _scheduler = None
