"""Radar API: 追踪雷达 - 管理已关注项目"""
import html
import json
import re
import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database import get_db

router = APIRouter()


def _strip_json_markdown(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```\s*$", "", text).strip()
    if "{" in text and "}" in text:
        start, end = text.find("{"), text.rfind("}") + 1
        if end > start:
            return text[start:end]
    return text


def _parse_ai_extracted(extracted_json: str) -> dict:
    defaults = {
        "project_summary": "未知",
        "budget_info": "未公布",
        "confidentiality_req": "未知",
        "doc_deadline": "未知",
        "bid_deadline": "未知",
        "bid_location": "未知",
        "contact_info": "未知",
        "doc_claim_method": "未知",
        "bid_method": "未知",
        "ai_score": 0,
    }
    if not extracted_json or not str(extracted_json).strip():
        return defaults
    text = _strip_json_markdown(str(extracted_json))
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            return defaults
        score = data.get("score")
        if isinstance(score, (int, float)):
            defaults["ai_score"] = round(float(score), 1)
        for k in ["project_summary", "budget_info", "confidentiality_req", "doc_deadline", "bid_deadline",
                  "bid_location", "contact_info", "doc_claim_method", "bid_method"]:
            v = data.get(k)
            if v is not None and str(v).strip():
                defaults[k] = str(v).strip()
        return defaults
    except json.JSONDecodeError:
        return defaults


@router.get("/list")
def radar_list():
    """获取所有已关注项目，按关注时间倒序。"""
    try:
        db = get_db(ROOT)
        rows = db.execute_query("""
            SELECT a.id, a.title, a.location, a.url, a.pub_date, a.deadline, a.budget,
                   f.feasibility_score, ar.extracted_info, MAX(ip.added_at) AS added_at
            FROM interested_projects ip
            JOIN announcements a ON a.id = ip.source_announcement_id
            LEFT JOIN filtered_projects f ON f.announcement_id = a.id
            LEFT JOIN analysis_results ar ON ar.announcement_id = a.id
            GROUP BY ip.source_announcement_id
            ORDER BY added_at DESC
        """)
        out = []
        for row in rows:
            r = dict(row) if hasattr(row, "keys") else row
            if not r:
                continue
            ai = _parse_ai_extracted(r.get("extracted_info") or "")
            score = r.get("feasibility_score")
            if score is not None:
                ai["ai_score"] = round(float(score), 1)
            out.append({
                "id": r.get("id"),
                "title": r.get("title") or "",
                "location": r.get("location") or "未知",
                "url": r.get("url") or "",
                "pub_date": r.get("pub_date") or "",
                "deadline": r.get("deadline") or "",
                "budget": r.get("budget") or "",
                "project_summary": ai["project_summary"],
                "budget_info": ai["budget_info"],
                "confidentiality_req": ai["confidentiality_req"],
                "doc_deadline": ai["doc_deadline"],
                "bid_deadline": ai["bid_deadline"],
                "bid_location": ai["bid_location"],
                "contact_info": ai["contact_info"],
                "doc_claim_method": ai["doc_claim_method"],
                "bid_method": ai["bid_method"],
                "ai_score": ai["ai_score"],
                "added_at": r.get("added_at") or "",
            })
        return {"projects": out}
    except Exception as e:
        return {"projects": [], "error": str(e)}


@router.get("/html", response_class=HTMLResponse)
def radar_html():
    """追踪雷达 HTML 片段（卡片流）。"""
    data = radar_list()
    projects = data.get("projects") or []
    parts = []
    for p in projects:
        pid = html.escape(p.get("id") or "")
        title_esc = html.escape((p.get("title") or "")[:80])
        loc_esc = html.escape((p.get("location") or "未知")[:20])
        summary_esc = html.escape((p.get("project_summary") or "未知"))
        budget_esc = html.escape((p.get("budget_info") or p.get("budget") or "未公布"))
        doc_dl = html.escape((p.get("doc_deadline") or "未知"))
        bid_dl = html.escape((p.get("bid_deadline") or "未知"))
        score = p.get("ai_score") or 0
        url_esc = html.escape(p.get("url") or "#")
        parts.append(f"""
<div class="radar-card border border-gray-700 rounded-lg p-3 bg-gray-800/80 hover:border-gray-600 transition">
  <div class="flex justify-between items-start gap-2 mb-2">
    <h3 class="font-medium text-gray-100 text-sm leading-snug flex-1 min-w-0">[{loc_esc}] {title_esc}</h3>
    <span class="flex-shrink-0 font-mono font-bold text-cyan-400 text-sm">{score:.1f}</span>
  </div>
  <p class="text-amber-200/90 text-xs font-medium mb-2">🎯 {summary_esc}</p>
  <div class="flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-400 mb-2">
    <span>💰 {budget_esc}</span>
    <span>⏰ {doc_dl}</span>
    <span>⏳ {bid_dl}</span>
  </div>
  <div class="flex items-center justify-between pt-2 border-t border-gray-700">
    <a href="{url_esc}" target="_blank" rel="noopener" class="text-cyan-400 hover:text-cyan-300 text-xs font-medium">查看原文</a>
    <button type="button"
            hx-post="/api/radar/untrack/{pid}"
            hx-target="closest .radar-card"
            hx-swap="outerHTML"
            class="text-red-400 hover:text-red-300 text-xs font-medium">
      ❌ 取消关注
    </button>
  </div>
</div>""")
    if not parts:
        parts.append('<p class="text-gray-500 col-span-full py-8 text-center">暂无关注项目，在情报监控台点击「⭐ 关注」添加。</p>')
    return '<div class="grid gap-3">' + "".join(parts) + "</div>"


@router.post("/untrack/{project_id}", response_class=HTMLResponse)
def untrack_project(project_id: str):
    """取消关注：从 interested_projects 删除，返回空字符串供 HTMX 移除卡片。"""
    try:
        db = get_db(ROOT)
        db.execute_query(
            "DELETE FROM interested_projects WHERE source_announcement_id = ?",
            (project_id,),
        )
        return ""
    except Exception:
        return ""