"""History API: crawl history and stats."""
from pathlib import Path
from fastapi import APIRouter

ROOT = Path(__file__).resolve().parent.parent.parent

router = APIRouter()


def _get_db():
    import sys
    import os
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    from src.config.config_manager import ConfigManager
    from src.database.storage import DatabaseManager
    cfg = ConfigManager(str(ROOT / "config")).load_all().to_dict()
    db_path = cfg.get("database", {}).get("path", "data/history.db")
    if not Path(db_path).is_absolute():
        db_path = str(ROOT / db_path)
    return DatabaseManager(db_path)


@router.get("/crawls")
def list_crawls(limit: int = 50):
    """List crawl history rows (crawl_time, announcement_count, success)."""
    try:
        db = _get_db()
        rows = db.execute_query(
            "SELECT id, crawl_time, announcement_count, success FROM crawl_history ORDER BY crawl_time DESC LIMIT ?",
            (limit,),
        )
        out = []
        for row in rows:
            r = dict(row) if hasattr(row, "keys") else {"id": row[0], "crawl_time": row[1], "announcement_count": row[2], "success": bool(row[3])}
            if "success" in r and not isinstance(r["success"], bool):
                r["success"] = bool(r["success"])
            out.append(r)
        return {"crawls": out}
    except Exception as e:
        return {"crawls": [], "error": str(e)}


@router.get("/stats")
def get_stats(days: int = 30):
    """Aggregate stats for charts (e.g. per-day crawl count, match count)."""
    try:
        db = _get_db()
        # By day: date, total_crawls, total_announcements
        rows = db.execute_query("""
            SELECT date(crawl_time) as d, COUNT(*), COALESCE(SUM(announcement_count), 0)
            FROM crawl_history
            WHERE crawl_time >= date('now', ?)
            GROUP BY date(crawl_time)
            ORDER BY d ASC
        """, (f"-{days} days",))
        by_day = []
        for r in rows:
            if hasattr(r, "keys"):
                by_day.append({"date": r["d"], "crawl_count": r[1], "announcement_count": r[2]})
            else:
                by_day.append({"date": r[0], "crawl_count": r[1], "announcement_count": r[2]})
        return {"by_day": by_day}
    except Exception as e:
        return {"by_day": [], "error": str(e)}
