"""Reports API: list and get daily report content."""
import html
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = ROOT / "data" / "reports"

router = APIRouter()

# Match daily_report_YYYYMMDD_HHMMSS.md
REPORT_PATTERN = re.compile(r"daily_report_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})\.md")


def _markdown_to_html(text: str) -> str:
    """将 Markdown 转为 HTML，无 markdown 库时用 pre 包裹。"""
    try:
        import markdown
        return markdown.markdown(text)
    except ImportError:
        return f'<pre class="whitespace-pre-wrap text-gray-300 font-mono text-sm">{html.escape(text)}</pre>'


def _list_reports(limit: int = 20):
    if not REPORTS_DIR.exists():
        return []
    files = list(REPORTS_DIR.glob("daily_report_*.md"))
    out = []
    for f in sorted(files, key=lambda p: p.name, reverse=True)[:limit]:
        m = REPORT_PATTERN.match(f.name)
        if m:
            y, mo, d, h, mi, s = m.groups()
            out.append({
                "id": f.stem,
                "filename": f.name,
                "created": f"{y}-{mo}-{d} {h}:{mi}:{s}",
            })
        else:
            out.append({"id": f.stem, "filename": f.name, "created": None})
    return out


@router.get("")
def list_reports(limit: int = 20):
    """List recent reports (id, filename, created time)."""
    return {"reports": _list_reports(limit=limit)}


@router.get("/view/{report_id}", response_class=HTMLResponse)
def view_report(report_id: str):
    """读取报告文件内容，返回 HTML 片段供 HTMX 弹窗展示。"""
    if ".." in report_id or "/" in report_id:
        raise HTTPException(status_code=400, detail="Invalid report id")
    report_id = report_id.removesuffix(".md") if report_id.endswith(".md") else report_id
    path = REPORTS_DIR / f"{report_id}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    text = path.read_text(encoding="utf-8")
    html_content = _markdown_to_html(text)
    return HTMLResponse(
        f'<div class="prose prose-invert prose-sm max-w-none">'
        f'{html_content}'
        f'</div>'
    )


@router.get("/{report_id}")
def get_report(report_id: str):
    """Get one report by id (stem of filename). Returns markdown and optional html."""
    if ".." in report_id or "/" in report_id:
        raise HTTPException(status_code=400, detail="Invalid report id")
    path = REPORTS_DIR / f"{report_id}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    text = path.read_text(encoding="utf-8")
    return {"id": report_id, "markdown": text}
