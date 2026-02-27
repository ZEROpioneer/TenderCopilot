"""Scheduler API: status, enable/disable, and hot-reload integration."""
import sys
from pathlib import Path

from fastapi import APIRouter, Body

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = ROOT / "config"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_yaml, save_yaml

router = APIRouter()


def _reload_scheduler():
    """触发热重载。"""
    try:
        from web.scheduler_engine import reload_scheduler
        reload_scheduler()
    except Exception as e:
        from loguru import logger
        logger.warning(f"⏰ 定时任务热重载失败: {e}")


@router.get("/status")
def scheduler_status():
    """Return scheduler enabled state and next run info."""
    path = CONFIG_DIR / "settings.yaml"
    data = load_yaml(path)
    sched = data.get("scheduler") or {}
    enabled = sched.get("enabled", True)
    return {"enabled": bool(enabled), "message": "定时任务已启用" if enabled else "定时任务已关闭"}


@router.patch("")
def scheduler_toggle(payload: dict = Body(default={})):
    """Set scheduler.enabled. Payload: { \"enabled\": true|false }. Triggers hot-reload."""
    path = CONFIG_DIR / "settings.yaml"
    data = load_yaml(path)
    if "scheduler" not in data:
        data["scheduler"] = {}
    if "enabled" in payload:
        data["scheduler"]["enabled"] = bool(payload["enabled"])
    save_yaml(path, data)
    _reload_scheduler()
    return {"status": "ok", "enabled": data["scheduler"].get("enabled", True)}
