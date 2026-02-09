"""Scheduler API: status and enable/disable (writes config, does not start process)."""
import sys
from pathlib import Path

from fastapi import APIRouter, Body

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = ROOT / "config"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import load_yaml, save_yaml

router = APIRouter()


@router.get("/status")
def scheduler_status():
    """Return scheduler enabled state. Note: actual schedule process must be started with python main.py --mode schedule."""
    path = CONFIG_DIR / "settings.yaml"
    data = load_yaml(path)
    sched = data.get("scheduler") or {}
    enabled = sched.get("enabled", True)
    return {"enabled": bool(enabled), "message": "定时任务已启用" if enabled else "定时任务已关闭"}


@router.patch("")
def scheduler_toggle(payload: dict = Body(default={})):
    """Set scheduler.enabled. Payload: { \"enabled\": true|false }."""
    path = CONFIG_DIR / "settings.yaml"
    data = load_yaml(path)
    if "scheduler" not in data:
        data["scheduler"] = {}
    if "enabled" in payload:
        data["scheduler"]["enabled"] = bool(payload["enabled"])
    save_yaml(path, data)
    return {"status": "ok", "enabled": data["scheduler"].get("enabled", True)}
