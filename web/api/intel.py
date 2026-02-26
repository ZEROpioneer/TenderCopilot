"""Intel API: top feasibility projects from history.db."""
import html
import json
import re
import sys
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from loguru import logger

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database import get_db
from src.utils.project_fingerprint import extract_project_refs_from_content

router = APIRouter()


def _parse_score_breakdown(sb_raw) -> list:
    """解析 score_breakdown JSON 字符串为列表。"""
    if not sb_raw:
        return []
    try:
        out = json.loads(sb_raw)
        return out if isinstance(out, list) else []
    except Exception:
        return []


def _score_breakdown_html(score_breakdown: list, score: float) -> str:
    """生成算分明细的 HTML 片段（可展开的灰色 pre 区域）。"""
    if not score_breakdown or not isinstance(score_breakdown, list):
        return ""
    lines = []
    for item in score_breakdown:
        if not isinstance(item, dict):
            continue
        rule = item.get("rule", "")
        pts = item.get("points", 0)
        try:
            pts_f = float(pts)
        except (TypeError, ValueError):
            pts_f = 0
        if "总计" in rule or "🏆" in rule:
            lines.append(f"🏆 {rule}: {int(pts_f)}分")
        else:
            sign = "+" if pts_f >= 0 else ""
            lines.append(f"✅ {rule}: {sign}{int(pts_f)}分")
    if not lines:
        return ""
    content = html.escape("\n".join(lines))
    return f'''
<details class="inline-block align-middle" onclick="event.stopPropagation()">
  <summary class="cursor-pointer text-gray-500 hover:text-cyan-400 text-xs font-medium select-none">🔍 算分明细</summary>
  <pre class="mt-2 p-3 bg-gray-800/90 rounded-lg text-xs text-gray-300 overflow-x-auto border border-gray-700 whitespace-pre-wrap">{content}</pre>
</details>'''


def _track_button_html(project_id: str, is_tracked: bool) -> str:
    """生成关注/已关注按钮 HTML（供 HTMX 替换）。"""
    pid = html.escape(project_id or "")
    if is_tracked:
        return '<button type="button" disabled class="text-amber-400/60 text-sm cursor-default">🌟 已关注</button>'
    return f'<button type="button" hx-post="/api/intel/track/{pid}" hx-swap="outerHTML" hx-target="this" class="text-amber-400/80 hover:text-amber-400 text-sm">⭐ 关注</button>'


def _strip_json_markdown(text: str) -> str:
    """剥离 Markdown 代码块标记，只保留 {} 内内容。"""
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
    """解析 analysis_results.extracted_info JSON，提取 AI 核心字段。兼容新旧键名。"""
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
        # 新键名 + 旧格式兼容
        key_map = {
            "project_summary": ["project_summary", "project_overview"],
            "budget_info": ["budget_info", "budget"],
            "confidentiality_req": ["confidentiality_req", "supplier_qualifications"],
            "doc_deadline": ["doc_deadline", ("registration_requirements", "deadline")],
            "bid_deadline": ["bid_deadline", ("bidding_info", "date"), ("bidding_info", "time")],
            "bid_location": ["bid_location"],
            "contact_info": ["contact_info"],
            "doc_claim_method": ["doc_claim_method"],
            "bid_method": ["bid_method"],
        }
        for target_key, candidates in key_map.items():
            val = None
            for c in candidates:
                if isinstance(c, tuple):
                    v = data.get(c[0])
                    v = v.get(c[1]) if isinstance(v, dict) else None
                else:
                    v = data.get(c)
                if isinstance(v, dict):
                    v = v.get("deadline") or v.get("date") or v.get("time") or ""
                if v is not None and str(v).strip():
                    val = str(v).strip()
                    break
            if val:
                defaults[target_key] = val
        return defaults
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ Web 端解析 extracted_info 失败: {e}，原文前 500 字: {(extracted_json or '')[:500]}")
        return defaults


@router.post("/track/{project_id}", response_class=HTMLResponse)
def track_project(project_id: str):
    """将项目加入 interested_projects，返回「已关注」按钮 HTML 供 HTMX 替换。"""
    try:
        db = get_db(ROOT)
        row = db.execute_query("""
            SELECT a.id, a.title, a.content, f.feasibility_score
            FROM announcements a
            LEFT JOIN filtered_projects f ON f.announcement_id = a.id
            WHERE a.id = ?
        """, (project_id,))
        rows = list(row)
        if not rows:
            return '<span class="text-red-400 text-sm">未找到</span>'
        r = dict(rows[0]) if hasattr(rows[0], "keys") else {}
        title = (r.get("title") or "").strip()
        content = r.get("content") or ""
        score = r.get("feasibility_score")
        feasibility_score = round(float(score), 1) if score is not None else 60.0

        project_code, project_name = None, title
        refs = extract_project_refs_from_content(content)
        if refs:
            project_code, project_name = refs[0][0] or "", refs[0][1] or title
        if not project_name:
            project_name = title or project_id

        db.add_interested_project(
            project_code=project_code or None,
            project_name=project_name,
            source_announcement_id=project_id,
            feasibility_score=feasibility_score,
        )
        return '<button type="button" disabled class="text-amber-400/60 text-sm cursor-default">🌟 已关注</button>'
    except Exception as e:
        return f'<span class="text-red-400 text-sm">失败: {html.escape(str(e)[:50])}</span>'


@router.get("/latest")
def latest_projects(limit: int = Query(50, ge=1, le=100)):
    """最近抓取的招标项目（仅 SELECT，无爬虫逻辑）。含 AI 提取字段与 is_tracked。"""
    try:
        db = get_db(ROOT)
        rows = db.execute_query("""
            SELECT a.id, a.title, a.location, a.url, a.pub_date, a.deadline, a.budget,
                   f.feasibility_score, f.score_breakdown, ar.extracted_info,
                   (SELECT 1 FROM interested_projects ip WHERE ip.source_announcement_id = a.id LIMIT 1) AS is_tracked
            FROM announcements a
            LEFT JOIN filtered_projects f ON f.announcement_id = a.id
            LEFT JOIN analysis_results ar ON ar.announcement_id = a.id
            ORDER BY a.created_at DESC, a.id DESC
            LIMIT ?
        """, (limit,))
        out = []
        for row in rows:
            r = dict(row) if hasattr(row, "keys") else None
            if not r:
                continue
            ai = _parse_ai_extracted(r.get("extracted_info") or "")
            score = r.get("feasibility_score")
            if score is not None:
                ai["ai_score"] = round(float(score), 1)
            is_tracked = r.get("is_tracked") is not None
            score_breakdown = _parse_score_breakdown(r.get("score_breakdown"))
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
                "score_breakdown": score_breakdown if isinstance(score_breakdown, list) else [],
                "is_tracked": is_tracked,
            })
        return {"projects": out}
    except Exception as e:
        return {"projects": [], "error": str(e)}


@router.get("/latest/html", response_class=HTMLResponse)
def latest_projects_html(limit: int = Query(50, ge=1, le=100)):
    """情报监控台 HTML 片段（数据卡片流）。"""
    data = latest_projects(limit=limit)
    projects = data.get("projects") or []
    parts = []
    for p in projects:
        pid = html.escape(p.get("id") or "")
        title_esc = html.escape((p.get("title") or "")[:80])
        loc_esc = html.escape((p.get("location") or "未知")[:20])
        summary_esc = html.escape((p.get("project_summary") or "未知"))
        budget_esc = html.escape((p.get("budget_info") or p.get("budget") or "未公布"))
        conf_esc = html.escape((p.get("confidentiality_req") or "未知"))
        doc_dl = html.escape((p.get("doc_deadline") or "未知"))
        bid_dl = html.escape((p.get("bid_deadline") or "未知"))
        bid_loc = html.escape((p.get("bid_location") or "未知"))
        contact = html.escape((p.get("contact_info") or "未知"))
        doc_claim = html.escape((p.get("doc_claim_method") or "未知"))
        bid_meth = html.escape((p.get("bid_method") or "未知"))
        score = p.get("ai_score") or 0
        url_esc = html.escape(p.get("url") or "#")
        parts.append(f"""
<div class="intel-card border border-gray-700 rounded-xl p-4 bg-gray-800/80 hover:border-gray-600 hover:bg-gray-800 transition">
  <div class="flex justify-between items-start gap-3 mb-3">
    <h3 class="font-semibold text-gray-100 text-base leading-snug flex-1 min-w-0">[{loc_esc}] {title_esc}</h3>
    <span class="flex-shrink-0 flex items-center gap-2">
      <span class="font-mono font-bold text-cyan-400">{score:.1f}</span>
      {_score_breakdown_html(p.get("score_breakdown") or [], score)}
    </span>
  </div>
  <p class="text-amber-200/90 text-sm font-medium mb-2">🎯 {summary_esc}</p>
  <div class="flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-400 mb-2">
    <span>💰 {budget_esc}</span>
    <span>🛑 {conf_esc}</span>
  </div>
  <div class="flex flex-col gap-1 text-sm text-gray-500 mb-3 break-words">
    <div>⏰ 获取文件: {doc_dl}</div>
    <div>⏳ 开标/递交: {bid_dl}</div>
    <div>📍 开标地点: {bid_loc}</div>
    <div>📞 联系人: {contact}</div>
    <div>📋 申领方式: {doc_claim}</div>
    <div>📤 开标方式: {bid_meth}</div>
  </div>
  <div class="flex items-center gap-2 pt-2 border-t border-gray-700">
    <a href="{url_esc}" target="_blank" rel="noopener" class="text-cyan-400 hover:text-cyan-300 text-sm font-medium">查看原文</a>
    {_track_button_html(pid, p.get("is_tracked", False))}
  </div>
</div>""")
    if not parts:
        parts.append('<p class="text-gray-500 col-span-full py-8 text-center">暂无数据，点击「立即运行」抓取。</p>')
    return '<div class="grid gap-4">' + "".join(parts) + "</div>"


@router.get("/latest/compact_html", response_class=HTMLResponse)
def latest_projects_compact_html(limit: int = Query(20, ge=1, le=50)):
    """首页轻量级最新动态：仅 [地域] 标题、评分、预算、摘要。"""
    data = latest_projects(limit=limit)
    projects = data.get("projects") or []
    parts = []
    for p in projects:
        pid = html.escape(p.get("id") or "")
        title_esc = html.escape((p.get("title") or "")[:60])
        loc_esc = html.escape((p.get("location") or "未知")[:15])
        summary_esc = html.escape((p.get("project_summary") or "未知")[:50])
        budget_esc = html.escape((p.get("budget_info") or p.get("budget") or "未公布")[:30])
        score = p.get("ai_score") or 0
        url_esc = html.escape(p.get("url") or "#")
        parts.append(f"""
<div class="intel-card-compact border-b border-gray-700 py-3 last:border-b-0">
  <div class="flex justify-between items-start gap-2">
    <a href="{url_esc}" target="_blank" rel="noopener" class="font-medium text-gray-100 text-sm leading-snug flex-1 min-w-0 hover:text-cyan-400">[{loc_esc}] {title_esc}</a>
    <span class="flex-shrink-0 flex items-center gap-1">
      <span class="font-mono font-bold text-cyan-400 text-sm">{score:.1f}</span>
      {_score_breakdown_html(p.get("score_breakdown") or [], score)}
    </span>
  </div>
  <p class="text-amber-200/80 text-xs mt-1">🎯 {summary_esc}</p>
  <p class="text-gray-500 text-xs mt-0.5">💰 {budget_esc}</p>
</div>""")
    if not parts:
        parts.append('<p class="text-gray-500 py-6 text-center text-sm">暂无数据，点击「立即运行」抓取。</p>')
    return '<div class="space-y-0">' + "".join(parts) + "</div>"


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
    order: str = Query("score", pattern="^(score|time)$"),
):
    """List top feasibility projects (for Intel Center). order=score (default) or time."""
    try:
        db = get_db(ROOT)
        order_col = "f.feasibility_score DESC, f.filtered_at DESC" if order == "score" else "f.filtered_at DESC, f.feasibility_score DESC"
        rows = db.execute_query(f"""
            SELECT a.id, a.title, a.location, a.url, a.deadline, a.pub_date,
                   f.feasibility_score, f.feasibility_level, f.matched_directions, f.score_breakdown,
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
            score_breakdown = _parse_score_breakdown(r.get("score_breakdown"))
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
                "score_breakdown": score_breakdown if isinstance(score_breakdown, list) else [],
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
    order: str = Query("score", pattern="^(score|time)$"),
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
        sb_html = _score_breakdown_html(p.get("score_breakdown") or [], score)
        parts.append(f"""
<div class="intel-card border border-gray-700 rounded-lg p-4 bg-gray-900/50 hover:border-gray-600 transition cursor-pointer"
     hx-get="/api/intel/project/{pid}/html" hx-trigger="click" hx-swap="outerHTML" hx-target="this">
  <div class="flex justify-between items-start gap-2">
    <div class="min-w-0 flex-1">
      <span class="text-gray-400 text-sm">[{loc_esc}]</span>
      <p class="font-medium text-gray-100 truncate">{title_esc}</p>
    </div>
    <span class="flex-shrink-0 flex items-center gap-1">
      <span class="font-mono font-bold {sc}">{(int(score))}</span>
      {sb_html}
    </span>
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
    ai_parsed = _parse_ai_extracted(json.dumps(ext_obj) if isinstance(ext_obj, dict) else (ext or ""))
    doc_dl = html.escape(ai_parsed.get("doc_deadline") or "未知")
    bid_dl = html.escape(ai_parsed.get("bid_deadline") or "未知")
    bid_loc = html.escape(ai_parsed.get("bid_location") or "未知")
    contact = html.escape(ai_parsed.get("contact_info") or "未知")
    doc_claim = html.escape(ai_parsed.get("doc_claim_method") or "未知")
    bid_meth = html.escape(ai_parsed.get("bid_method") or "未知")
    ext_pre = html.escape(json.dumps(ext_obj, ensure_ascii=False, indent=2)[:2000])
    sb_html = _score_breakdown_html(detail.get("score_breakdown") or [], score)
    return f"""
<div class="intel-card-expanded border border-gray-600 rounded-lg p-4 bg-gray-900 space-y-3">
  <div class="flex justify-between items-start">
    <div>
      <span class="text-gray-400 text-sm">[{loc_esc}]</span>
      <p class="font-medium text-gray-100">{title_esc}</p>
    </div>
    <span class="flex items-center gap-2">
      <span class="font-mono font-bold {sc}">{(int(score))}</span>
      {sb_html}
    </span>
  </div>
  <p class="text-sm text-gray-500"><a href="{url_esc}" target="_blank" class="text-cyan-400 hover:underline">原文链接</a></p>
  <div class="flex flex-col gap-1 text-sm text-gray-500 break-words">
    <div>⏰ 获取文件: {doc_dl}</div>
    <div>⏳ 开标/递交: {bid_dl}</div>
    <div>📍 开标地点: {bid_loc}</div>
    <div>📞 联系人: {contact}</div>
    <div>📋 申领方式: {doc_claim}</div>
    <div>📤 开标方式: {bid_meth}</div>
  </div>
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
                   f.feasibility_score, f.feasibility_level, f.matched_directions, f.score_breakdown,
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
            "score_breakdown": _parse_score_breakdown(r.get("score_breakdown")),
            "extracted_info": r.get("extracted_info"),
        }
    except Exception as e:
        return {"error": str(e)}
