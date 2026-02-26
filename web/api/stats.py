"""Stats API: 数据聚合，供决策大屏使用"""
import sys
from pathlib import Path

from fastapi import APIRouter

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database import get_db

router = APIRouter()


@router.get("/dashboard")
def dashboard_stats():
    """决策大屏：漏斗、趋势、地域分布。"""
    try:
        db = get_db(ROOT)
        # funnel_data: 总抓取、命中规则、已关注
        funnel_rows = db.execute_query("""
            SELECT
                (SELECT COUNT(*) FROM announcements) AS total_crawled,
                (SELECT COUNT(*) FROM filtered_projects) AS matched,
                (SELECT COUNT(DISTINCT source_announcement_id) FROM interested_projects) AS interested
        """)
        funnel = {"total_crawled": 0, "matched": 0, "interested": 0}
        if funnel_rows:
            r = dict(funnel_rows[0]) if hasattr(funnel_rows[0], "keys") else funnel_rows[0]
            funnel["total_crawled"] = r.get("total_crawled") or 0
            funnel["matched"] = r.get("matched") or 0
            funnel["interested"] = r.get("interested") or 0

        # trend_data: 过去 15 天每日命中量（按 filtered_at 日期）
        trend_rows = db.execute_query("""
            SELECT date(filtered_at) AS d, COUNT(*) AS c
            FROM filtered_projects
            WHERE filtered_at >= date('now', '-15 days')
            GROUP BY date(filtered_at)
            ORDER BY d ASC
        """)
        dates_set = {}
        for r in trend_rows:
            row = dict(r) if hasattr(r, "keys") else r
            d = row.get("d") or ""
            c = row.get("c") or 0
            dates_set[d] = c
        # 补全 15 天
        from datetime import datetime, timedelta
        today = datetime.now().date()
        dates = []
        counts = []
        for i in range(14, -1, -1):
            d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            dates.append(d)
            counts.append(dates_set.get(d, 0))

        # location_data: 地域 Top 10
        loc_rows = db.execute_query("""
            SELECT COALESCE(NULLIF(TRIM(a.location), ''), '未知') AS region, COUNT(*) AS c
            FROM filtered_projects f
            JOIN announcements a ON a.id = f.announcement_id
            GROUP BY region
            ORDER BY c DESC
            LIMIT 10
        """)
        regions = []
        loc_counts = []
        for r in loc_rows:
            row = dict(r) if hasattr(r, "keys") else r
            regions.append(row.get("region") or "未知")
            loc_counts.append(row.get("c") or 0)

        return {
            "funnel_data": funnel,
            "trend_data": {"dates": dates, "counts": counts},
            "location_data": {"regions": regions, "counts": loc_counts},
        }
    except Exception as e:
        return {
            "funnel_data": {"total_crawled": 0, "matched": 0, "interested": 0},
            "trend_data": {"dates": [], "counts": []},
            "location_data": {"regions": [], "counts": []},
            "error": str(e),
        }
