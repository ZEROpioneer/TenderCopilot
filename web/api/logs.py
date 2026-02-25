"""Logs API: tail log file for Live Logs panel. SSE streaming for real-time logs."""
import re
import sys
import time
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse, StreamingResponse

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import ConfigManager

router = APIRouter()


def _get_log_path() -> Path:
    """Resolve main log file path from config or default."""
    try:
        cfg = ConfigManager(str(ROOT / "config")).load_all().to_dict()
        log_file = (cfg.get("logging") or {}).get("log_file", "logs/tendercopilot.log")
    except Exception:
        log_file = "logs/tendercopilot.log"
    p = Path(log_file)
    if not p.is_absolute():
        p = ROOT / p
    return p


def _get_latest_log_path() -> Path:
    """Return the latest log file: prefer newest run_*.log in detail_dir, else main log."""
    try:
        cfg = ConfigManager(str(ROOT / "config")).load_all().to_dict()
        detail_dir = (cfg.get("logging") or {}).get("detail_dir")
        if detail_dir:
            detail_path = Path(detail_dir)
            if not detail_path.is_absolute():
                detail_path = ROOT / detail_path
            if detail_path.exists():
                run_logs = sorted(detail_path.glob("run_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
                if run_logs:
                    return run_logs[0]
        return _get_log_path()
    except Exception:
        return _get_log_path()


def _strip_ansi(text: str) -> str:
    """Remove ANSI color codes for plain text display."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _stream_logs_generator(initial_lines: int = 50):
    """Generator that tails the latest log file and yields SSE events (tail -f style)."""
    log_path = _get_latest_log_path()
    if not log_path.exists():
        yield f"data: # Log file not found: {log_path}\n\n"
        return
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            # Send initial content (last N lines)
            all_lines = f.readlines()
            last = all_lines[-initial_lines:] if len(all_lines) >= initial_lines else all_lines
            initial = _strip_ansi("".join(last))
            if initial.strip():
                for line in initial.splitlines():
                    yield f"data: {line}\n\n"
            # Seek to end and keep reading new content
            f.seek(0, 2)
            while True:
                line = f.readline()
                if line:
                    yield f"data: {_strip_ansi(line).rstrip()}\n\n"
                else:
                    time.sleep(0.5)
    except Exception as e:
        yield f"data: # Error: {e}\n\n"


@router.get("/stream_logs")
def stream_logs(initial_lines: int = Query(50, ge=1, le=200)):
    """SSE endpoint: stream log file in real-time (tail -f style)."""
    return StreamingResponse(
        _stream_logs_generator(initial_lines=initial_lines),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/tail", response_class=PlainTextResponse)
def tail_log(lines: int = Query(50, ge=1, le=200)):
    """Return last N lines of the main log file. For Live Logs panel (fallback)."""
    log_path = _get_latest_log_path()
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
