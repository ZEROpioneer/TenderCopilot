"""Intel API: top feasibility projects from history.db."""
import html
import json
import sys
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database import get_db

router = APIRouter()


def _summary_from_extracted(extracted_json: str) -> str:
    """One-line summary from analysis extracted_info JSON."""
    if not extracted_json:
        return ""
    try:
        data = json.loads(extracted_json)
        if isinstance(data, dict):
            return (data.get("project_overview") or "").strip() or ""
    except Exception:
        pass
    return ""


@router.get("/top")
def top_projects(
    min_score: int = Query(80, ge=0, le=100),
    limit: int = Query(20, ge=1, le=100),
    order: str = Query("score", regex="^(score|time)$"),
):
    """List top feasibility projects (for Intel Center). order=score (default) or time."""
    try:
        db = get_db(ROOT)
        order_col = "f.feasibility_score DESC, f.filtered_at DESC" if order == "score" else "f.filtered_at DESC, f.feasibility_score DESC"
        rows = db.execute_query(f"""
            SELECT a.id, a.title, a.location, a.url, a.deadline, a.pub_date,
                   f.feasibility_score, f.feasibility_level, f.matched_directions,
                   ar.extracted_info
            FROM filtered_projects f
            JOIN announcements a ON a.id = f.announcement_id
            LEFT JOIN analysis_results ar ON ar.announcement_id = a.id
            WHERE f.feasibility_score >= ?
            ORDER BY {order_col}
            LIMIT ?
        """, (min_score, limit))
        out = []
        for row in rows:
            r = dict(row) if hasattr(row, "keys") else None
            if not r:
                continue
            summary = _summary_from_extracted(r.get("extracted_info") or "")
            if not summary and r.get("title"):
                summary = (r.get("title") or "")[:80] + ("..." if len((r.get("title") or "")) > 80 else "")
            out.append({
                "id": r.get("id"),
                "title": r.get("title"),
                "location": r.get("location") or "",
                "url": r.get("url"),
                "deadline": r.get("deadline"),
                "pub_date": r.get("pub_date"),
                "feasibility_score": round(float(r.get("feasibility_score") or 0), 1),
                "feasibility_level": r.get("feasibility_level"),
                "summary": summary,
                "extracted_info": r.get("extracted_info"),
            })
        return {"projects": out, "order": order}
    except Exception as e:
        return {"projects": [], "order": order, "error": str(e)}


def _score_class(score: float) -> str:
    if score >= 80:
        return "text-green-500"
    if score >= 60:
        return "text-yellow-500"
    return "text-gray-500"


@router.get("/top/html", response_class=HTMLResponse)
def top_projects_html(
    min_score: int = Query(80, ge=0, le=100),
    limit: int = Query(20, ge=1, le=100),
    order: str = Query("score", regex="^(score|time)$"),
):
    """HTML fragment of top project cards for HTMX."""
    data = top_projects(min_score=min_score, limit=limit, order=order)
    projects = data.get("projects") or []
    order_val = data.get("order", "score")
    parts = []
    for p in projects:
        score = p.get("feasibility_score") or 0
        sc = _score_class(score)
        title_esc = html.escape((p.get("title") or "")[:60])
        loc_esc = html.escape((p.get("location") or "")[:20])
        summary_esc = html.escape((p.get("summary") or "")[:120])
        pid = html.escape(p.get("id") or "")
        url_esc = html.escape(p.get("url") or "")
        parts.append(f"""
<div class="intel-card border border-gray-700 rounded-lg p-4 bg-gray-900/50 hover:border-gray-600 transition cursor-pointer"
     hx-get="/api/intel/project/{pid}/html" hx-trigger="click" hx-swap="outerHTML" hx-target="this">
  <div class="flex justify-between items-start gap-2">
    <div class="min-w-0 flex-1">
      <span class="text-gray-400 text-sm">[{loc_esc}]</span>
      <p class="font-medium text-gray-100 truncate">{title_esc}</p>
    </div>
    <span class="flex-shrink-0 font-mono font-bold {sc}">{(int(score))}</span>
  </div>
  <p class="text-sm text-gray-500 mt-2 line-clamp-2">{summary_esc}</p>
</div>""")
    if not parts:
        parts.append('<p class="text-gray-500 col-span-full">暂无高分项目，点击「立即运行」抓取。</p>')
    return "<div class=\"intel-center-content grid gap-3\">" + "".join(parts) + "</div>"


@router.get("/project/{announcement_id}/html", response_class=HTMLResponse)
def project_detail_html(announcement_id: str):
    """Single project expanded HTML for HTMX swap."""
    detail = project_detail(announcement_id)
    if detail.get("error"):
        return f'<div class="p-4 text-red-400">加载失败: {html.escape(detail["error"])}</div>'
    score = detail.get("feasibility_score") or 0
    sc = _score_class(score)
    title_esc = html.escape(detail.get("title") or "")
    loc_esc = html.escape(detail.get("location") or "")
    url_esc = html.escape(detail.get("url") or "")
    content_esc = html.escape((detail.get("content") or "")[:500])
    ext = detail.get("extracted_info")
    try:
        ext_obj = json.loads(ext) if isinstance(ext, str) else ext
    except Exception:
        ext_obj = {}
    ext_pre = html.escape(json.dumps(ext_obj, ensure_ascii=False, indent=2)[:2000])
    return f"""
<div class="intel-card-expanded border border-gray-600 rounded-lg p-4 bg-gray-900 space-y-3">
  <div class="flex justify-between items-start">
    <div>
      <span class="text-gray-400 text-sm">[{loc_esc}]</span>
      <p class="font-medium text-gray-100">{title_esc}</p>
    </div>
    <span class="font-mono font-bold {sc}">{(int(score))}</span>
  </div>
  <p class="text-sm text-gray-500"><a href="{url_esc}" target="_blank" class="text-cyan-400 hover:underline">原文链接</a></p>
  <details class="text-sm">
    <summary class="cursor-pointer text-gray-400">AI 分析详情</summary>
    <pre class="mt-2 p-2 bg-black/40 rounded overflow-x-auto text-xs text-gray-400">{ext_pre}</pre>
  </details>
  <button type="button" hx-get="/api/intel/top/html?min_score=80&limit=20" hx-swap="outerHTML" hx-target="closest .intel-center-content"
          class="text-gray-500 hover:text-gray-300 text-sm">← 返回列表</button>
</div>"""


@router.get("/project/{announcement_id}")
def project_detail(announcement_id: str):
    """Single project detail (for card expand)."""
    try:
        db = get_db(ROOT)
        row = db.execute_query("""
            SELECT a.id, a.title, a.content, a.location, a.url, a.deadline, a.pub_date, a.contact, a.attachments,
                   f.feasibility_score, f.feasibility_level, f.matched_directions,
                   ar.extracted_info
            FROM announcements a
            LEFT JOIN filtered_projects f ON f.announcement_id = a.id
            LEFT JOIN analysis_results ar ON ar.announcement_id = a.id
            WHERE a.id = ?
        """, (announcement_id,))
        rows = list(row)
        if not rows:
            return {"error": "not_found"}
        r = dict(rows[0]) if hasattr(rows[0], "keys") else {}
        return {
            "id": r.get("id"),
            "title": r.get("title"),
            "content": r.get("content"),
            "location": r.get("location"),
            "url": r.get("url"),
            "deadline": r.get("deadline"),
            "pub_date": r.get("pub_date"),
            "contact": r.get("contact"),
            "attachments": r.get("attachments"),
            "feasibility_score": round(float(r.get("feasibility_score") or 0), 1),
            "feasibility_level": r.get("feasibility_level"),
            "matched_directions": r.get("matched_directions"),
            "extracted_info": r.get("extracted_info"),
        }
    except Exception as e:
        return {"error": str(e)}
