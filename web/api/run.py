"""Run API: trigger pipeline and get status."""
import threading
from pathlib import Path
from fastapi import APIRouter, HTTPException

ROOT = Path(__file__).resolve().parent.parent.parent

router = APIRouter()

# In-memory state for single run (no concurrent runs)
_run_state = {
    "status": "idle",  # idle | running | success | failed
    "message": None,
    "last_run_time": None,
    "crawled_count": None,
    "matched_count": None,
}


def _run_pipeline():
    global _run_state
    import os
    try:
        _run_state["status"] = "running"
        _run_state["message"] = "流程执行中..."
        os.chdir(ROOT)
        sys_path = __import__("sys")
        if str(ROOT) not in sys_path.path:
            sys_path.path.insert(0, str(ROOT))
        from main import TenderCopilot
        app = TenderCopilot()
        app.run_pipeline()
        _run_state["status"] = "success"
        _run_state["message"] = "运行完成"
        # Try to get last crawl stats from db
        try:
            from src.database.storage import DatabaseManager
            from src.spider.crawl_tracker import CrawlTracker
            cfg = app.config
            db = DatabaseManager(cfg.get("database", {}).get("path", "data/history.db"))
            tracker = CrawlTracker(db, cfg)
            stats = tracker.get_statistics()
            _run_state["last_run_time"] = stats.get("last_crawl_time")
            _run_state["crawled_count"] = None
            _run_state["matched_count"] = None
        except Exception:
            pass
    except Exception as e:
        _run_state["status"] = "failed"
        _run_state["message"] = str(e)
    finally:
        pass


@router.post("")
def trigger_run():
    """Start one pipeline run. Only one run at a time."""
    if _run_state["status"] == "running":
        raise HTTPException(status_code=409, detail="已有任务在运行中")
    thread = threading.Thread(target=_run_pipeline)
    thread.daemon = True
    thread.start()
    return {"status": "running", "message": "已启动"}


@router.get("/status")
def run_status():
    """Current run status and last run info."""
    return {
        "status": _run_state["status"],
        "message": _run_state.get("message"),
        "last_run_time": _run_state.get("last_run_time"),
        "crawled_count": _run_state.get("crawled_count"),
        "matched_count": _run_state.get("matched_count"),
    }
