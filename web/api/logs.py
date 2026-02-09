"""Logs API: tail log file for Live Logs panel."""
import re
import sys
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import ConfigManager

router = APIRouter()


def _get_log_path() -> Path:
    """Resolve log file path from config or default."""
    try:
        cfg = ConfigManager(str(ROOT / "config")).load_all().to_dict()
        log_file = (cfg.get("logging") or {}).get("log_file", "logs/tendercopilot.log")
    except Exception:
        log_file = "logs/tendercopilot.log"
    p = Path(log_file)
    if not p.is_absolute():
        p = ROOT / p
    return p


def _strip_ansi(text: str) -> str:
    """Remove ANSI color codes for plain text display."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


@router.get("/tail", response_class=PlainTextResponse)
def tail_log(lines: int = Query(50, ge=1, le=200)):
    """Return last N lines of the main log file. For Live Logs panel."""
    log_path = _get_log_path()
    if not log_path.exists():
        return "# Log file not found: " + str(log_path)
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        last = all_lines[-lines:] if len(all_lines) >= lines else all_lines
        raw = "".join(last)
        return _strip_ansi(raw)
    except Exception as e:
        return f"# Error reading log: {e}"
