"""Lab API: 开发者实验室 - 幽灵测试模式"""
import html
import re
import sys
from pathlib import Path

from fastapi import APIRouter, Form, Query
from fastapi.responses import HTMLResponse

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

router = APIRouter()

# 实验室 Live Terminal 读取的日志文件（与 main.py setup_logger 中的 app.log 一致）
APP_LOG = ROOT / "data" / "app.log"


def _strip_ansi(text: str) -> str:
    """移除 ANSI 颜色码，便于纯文本展示"""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _form_to_bool(val) -> bool:
    """将表单值严谨转为 Boolean。未勾选时字段可能缺失或为空。"""
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in ("on", "true", "1", "yes")


@router.post("/run_workflow", response_class=HTMLResponse)
def run_workflow(
    force_mode: str = Form(default=""),
    mute_notify: str = Form(default=""),
):
    """发起全链路干跑测试，返回结果 HTML 片段。"""
    force = _form_to_bool(force_mode)
    mute = _form_to_bool(mute_notify)
    try:
        import os
        os.chdir(ROOT)
        from main import TenderCopilot
        app = TenderCopilot()
        stats = app.run_pipeline(force_mode=force, mute_notify=mute)
        if stats.get("error"):
            return f'<div id="test-result" class="mt-4 p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-400">❌ 执行失败: {html.escape(str(stats["error"])[:200])}</div>'
        crawled = stats.get("total_crawled", 0)
        matched = stats.get("total_matched", 0)
        rec = stats.get("recommended", 0)
        exc = stats.get("excellent", 0)
        good = stats.get("good", 0)
        alt = stats.get("alternatives", 0)
        return f'''<div id="test-result" class="mt-4 p-4 rounded-lg bg-green-900/20 border border-green-700 text-green-400">
  <p class="font-semibold">✅ 测试完成！</p>
  <ul class="mt-2 text-sm space-y-1">
    <li>抓取: {crawled} 条</li>
    <li>放行: {matched} 条</li>
    <li>推荐 (≥65分): {rec} 个 (优秀 {exc} / 良好 {good})</li>
    <li>备选: {alt} 个</li>
  </ul>
  <p class="mt-2 text-xs text-gray-500">{"[静音] 企微未推送" if mute else ""} {"[强制] 已无视去重" if force else ""}</p>
</div>'''
    except Exception as e:
        return f'<div id="test-result" class="mt-4 p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-400">❌ 异常: {html.escape(str(e)[:300])}</div>'


def _get_log_path():
    """优先 app.log，不存在则回退到 logs 模块解析的最新日志。"""
    if APP_LOG.exists():
        return APP_LOG
    try:
        from web.api.logs import _get_latest_log_path
        return _get_latest_log_path()
    except Exception:
        return APP_LOG


@router.get("/logs", response_class=HTMLResponse)
def lab_logs(lines: int = Query(50, ge=1, le=200)):
    """读取 app.log 最后 N 行，返回 HTML 片段供 Live Terminal 展示。"""
    log_path = _get_log_path()
    if not log_path.exists():
        return '<div class="text-gray-500 font-mono text-xs">日志文件尚未创建，请先发起一次测试。</div>'
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        last = all_lines[-lines:] if len(all_lines) >= lines else all_lines
        raw = "".join(last)
        content = html.escape(_strip_ansi(raw))
        return f'<div class="text-green-400 font-mono text-xs whitespace-pre-wrap break-words">{content}</div>'
    except Exception as e:
        return f'<div class="text-red-400 font-mono text-xs">读取失败: {html.escape(str(e))}</div>'


# ---------- AI 提取狙击手 ----------


def _render_sniper_card(item) -> str:
    """将 TenderItem 的 8 个核心字段渲染为 Tailwind 卡片 HTML。"""
    def _e(v):
        return html.escape(str(v or "未知").strip())[:200]

    score = getattr(item, "ai_score", 0) or 0
    url_esc = html.escape(getattr(item, "url", "") or "#")
    return f"""
<div class="intel-card border border-cyan-700/50 rounded-xl p-4 bg-gray-800/80">
  <div class="flex justify-between items-start gap-3 mb-3">
    <h3 class="font-semibold text-gray-100 text-base">🎯 AI 提取结果</h3>
    <span class="flex-shrink-0 font-mono font-bold text-cyan-400">{score:.1f}</span>
  </div>
  <p class="text-amber-200/90 text-sm font-medium mb-2">📋 {_e(getattr(item, "project_summary", ""))}</p>
  <div class="flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-400 mb-2">
    <span>💰 {_e(getattr(item, "budget_info", ""))}</span>
    <span>🛑 {_e(getattr(item, "confidentiality_req", ""))}</span>
  </div>
  <div class="flex flex-col gap-1 text-sm text-gray-500 mb-3 break-words">
    <div>⏰ 获取文件: {_e(getattr(item, "doc_deadline", ""))}</div>
    <div>⏳ 开标/递交: {_e(getattr(item, "bid_deadline", ""))}</div>
    <div>📍 开标地点: {_e(getattr(item, "bid_location", ""))}</div>
    <div>📞 联系人: {_e(getattr(item, "contact_info", ""))}</div>
    <div>📋 申领方式: {_e(getattr(item, "doc_claim_method", ""))}</div>
    <div>📤 开标方式: {_e(getattr(item, "bid_method", ""))}</div>
  </div>
  <div class="pt-2 border-t border-gray-700">
    <a href="{url_esc}" target="_blank" rel="noopener" class="text-cyan-400 hover:text-cyan-300 text-sm font-medium">查看原文</a>
  </div>
</div>"""


# ---------- 规则透视镜 ----------


def _config_to_dict(config) -> dict:
    """将 ConfigManager 或 dict 转为纯 dict。"""
    if hasattr(config, "to_dict"):
        return config.to_dict()
    if hasattr(config, "_config"):
        return getattr(config, "_config", config)
    return dict(config) if config else {}


@router.post("/rule_test", response_class=HTMLResponse)
def rule_test(
    title: str = Form(...),
    content: str = Form(default=""),
    budget: str = Form(default=""),
    location: str = Form(default=""),
):
    """规则透视镜：纯粹测试评分与过滤逻辑，不调爬虫、不调 AI。"""
    title = (title or "").strip()
    if not title:
        return '<div class="p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-400">❌ 请输入项目标题</div>'

    try:
        import os
        os.chdir(ROOT)
        try:
            from dotenv import load_dotenv
            load_dotenv(ROOT / ".env")
        except Exception:
            pass
        from src.config import ConfigManager
        from src.schema import TenderItem
        from src.database.storage import DatabaseManager
        from src.filter.keyword_matcher import KeywordMatcher
        from src.filter.location_matcher import LocationMatcher
        from src.filter.notice_type_filter import NoticeTypeFilter
        from src.filter.deduplicator import Deduplicator
        from src.filter.manager import FilterManager
        from src.analyzer.feasibility_scorer import FeasibilityScorer

        cfg = ConfigManager(str(ROOT / "config")).load_all()
        config = _config_to_dict(cfg)
        db = DatabaseManager(config.get("database", {}).get("path", "data/history.db"))
        keyword_matcher = KeywordMatcher(config)
        location_matcher = LocationMatcher()
        notice_type_filter = NoticeTypeFilter(config)
        deduplicator = Deduplicator(db)
        filter_manager = FilterManager(
            config, db, keyword_matcher, location_matcher, notice_type_filter, deduplicator
        )
        scorer = FeasibilityScorer(config)

        budget_str = str(budget).strip() if budget else ""
        if budget_str and budget_str.replace(".", "").isdigit():
            budget_str = f"{budget_str}万元"
        item = TenderItem(
            project_id="lab_rule_test_" + str(abs(hash(title)) % 10**8),
            title=title,
            content_raw=(content or "").strip(),
            budget=budget_str or None,
            location=(location or "").strip() or "未知",
            announcement_type="招标公告",
        )
        if budget_str:
            item.budget_info = budget_str
            item.ai_extracted = {"budget_info": budget_str, "budget": budget_str}

        filtered = filter_manager.process_one(item, force_mode=True)
        if filtered is None:
            return '''<div class="p-4 rounded-lg bg-amber-900/30 border border-amber-700 text-amber-400">
  <p class="font-semibold">⏭️ 未放行</p>
  <p class="mt-2 text-sm">可能原因：关键词不匹配、地域不符、公告类型不符或去重命中。请调整标题/正文/地域后重试。</p>
</div>'''

        best_direction_id = filtered.matched_direction_id
        match_results = filtered.match_results
        location_result = filtered.location_result
        feasibility = scorer.calculate(
            filtered,
            match_results,
            location_result,
            content_analysis=None,
            ai_extracted=item.ai_extracted,
            attachment_analysis=None,
            direction_id=best_direction_id,
        )
        filtered.feasibility = feasibility

        total = feasibility.get("total", 0)
        passes = feasibility.get("passes_filter", True)
        breakdown = feasibility.get("score_breakdown") or []
        total_esc = html.escape(str(total))
        pass_class = "text-green-400" if passes else "text-amber-400"
        pass_text = "✅ 放行" if passes else "⏭️ 未通过二次过滤"

        rows = []
        for b in breakdown:
            rule_esc = html.escape(str(b.get("rule", "")))
            pts = b.get("points", 0)
            try:
                pts_int = int(float(pts))
            except (TypeError, ValueError):
                pts_int = 0
            sign = "+" if pts_int >= 0 else ""
            rows.append(f'<div class="flex justify-between py-1 text-sm"><span class="text-gray-400">{rule_esc}</span><span class="font-mono { "text-cyan-400" if pts_int >= 0 else "text-amber-400" }">{sign}{pts_int}分</span></div>')

        rows_html = "\n".join(rows) if rows else '<div class="text-gray-500 text-sm">无明细</div>'
        return _render_rule_result(total_esc, pass_class, pass_text, rows_html, title_esc=None)
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        return f'<div class="p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-400">❌ 异常: {html.escape(str(e)[:300])}<pre class="mt-2 text-xs text-gray-500 overflow-x-auto max-h-40">{html.escape(err[-2000:])}</pre></div>'


def _render_rule_result(total_esc: str, pass_class: str, pass_text: str, rows_html: str, title_esc: str = None) -> str:
    """复用规则透视镜结果 HTML 模板。"""
    title_block = ""
    if title_esc:
        title_block = f'<div class="mb-3"><span class="text-gray-400 text-sm">抓取标题</span><p class="text-gray-200 mt-1 break-words">{title_esc}</p></div>'
    return f'''<div class="p-4 rounded-lg bg-gray-800/80 border border-gray-600">
  {title_block}
  <div class="flex justify-between items-center mb-3">
    <span class="font-semibold text-gray-200">最终得分</span>
    <span class="font-mono font-bold text-cyan-400">{total_esc}</span>
  </div>
  <div class="flex justify-between items-center mb-4">
    <span class="text-gray-400">是否放行</span>
    <span class="font-medium {pass_class}">{pass_text}</span>
  </div>
  <div class="border-t border-gray-700 pt-3">
    <p class="text-xs text-gray-500 uppercase tracking-wider mb-2">算分明细 (score_breakdown)</p>
    <div class="space-y-0">{rows_html}</div>
  </div>
</div>'''


@router.post("/rule_test_url", response_class=HTMLResponse)
def rule_test_url(url: str = Form(...)):
    """规则透视镜 URL 模式：抓取真实 URL → AI 提取 → 算分与过滤。"""
    url = (url or "").strip()
    if not url:
        return '<div class="p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-400">❌ 请输入有效 URL</div>'
    if not url.startswith(("http://", "https://")):
        return '<div class="p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-400">❌ 请输入以 http:// 或 https:// 开头的 URL</div>'

    try:
        import os
        os.chdir(ROOT)
        try:
            from dotenv import load_dotenv
            load_dotenv(ROOT / ".env")
        except Exception:
            pass
        from src.config import ConfigManager
        from src.schema import TenderItem
        from src.database.storage import DatabaseManager
        from src.filter.keyword_matcher import KeywordMatcher
        from src.filter.location_matcher import LocationMatcher
        from src.filter.notice_type_filter import NoticeTypeFilter
        from src.filter.deduplicator import Deduplicator
        from src.filter.manager import FilterManager
        from src.analyzer.feasibility_scorer import FeasibilityScorer
        from src.spider.plap_spider import PLAPSpider
        from src.analyzer.info_extractor import InfoExtractor

        cfg = ConfigManager(str(ROOT / "config")).load_all()
        config = _config_to_dict(cfg)
        analyzer_cfg = config.setdefault("analyzer", {})
        analyzer_cfg.setdefault("provider", "custom_openai")
        analyzer_cfg.setdefault("custom_base_url", "https://open.bigmodel.cn/api/paas/v4")
        if not (analyzer_cfg.get("custom_api_key") or "").strip():
            analyzer_cfg["custom_api_key"] = (os.getenv("CUSTOM_OPENAI_API_KEY") or "").strip()

        spider = PLAPSpider(config)
        if not spider.init_browser():
            return '<div class="p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-400">❌ 浏览器初始化失败</div>'

        item = TenderItem(project_id="rule_url_" + str(abs(hash(url)) % 10**8), url=url, title="", content_raw="")
        spider.fetch_detail(item)
        content = getattr(item, "content_raw", "") or ""

        if not content or len(content) < 50:
            return '<div class="p-4 rounded-lg bg-amber-900/30 border border-amber-700 text-amber-400">⚠️ 未能抓取到有效正文（内容过短或为空），请检查 URL 是否为有效详情页</div>'

        title = ""
        if hasattr(spider, "page") and spider.page:
            try:
                h1 = spider.page.ele("css:h1", timeout=0.5)
                if h1:
                    title = (h1.text or "").strip()
                if not title:
                    title = (getattr(spider.page, "title", None) or "").strip()
                if not title:
                    title = (content[:100] + "…") if len(content) > 100 else content
            except Exception:
                title = (content[:100] + "…") if len(content) > 100 else content
        else:
            title = (content[:100] + "…") if len(content) > 100 else content
        item.title = title or "未获取标题"

        extractor = InfoExtractor(config)
        ai_result = extractor.extract(content, item, force_ai=True)
        if ai_result is None:
            return '<div class="p-4 rounded-lg bg-amber-900/30 border border-amber-700 text-amber-400">⚠️ AI 提取未启用或未配置，无法获取 budget/location 等结构化数据</div>'

        item.ai_extracted = ai_result
        item.announcement_type = "招标公告"
        loc = (ai_result.get("bid_location") or "").strip()
        if loc:
            item.location = loc

        db = DatabaseManager(config.get("database", {}).get("path", "data/history.db"))
        keyword_matcher = KeywordMatcher(config)
        location_matcher = LocationMatcher()
        notice_type_filter = NoticeTypeFilter(config)
        deduplicator = Deduplicator(db)
        filter_manager = FilterManager(
            config, db, keyword_matcher, location_matcher, notice_type_filter, deduplicator
        )
        scorer = FeasibilityScorer(config)

        filtered = filter_manager.process_one(item, force_mode=True)
        if filtered is None:
            return '''<div class="p-4 rounded-lg bg-amber-900/30 border border-amber-700 text-amber-400">
  <p class="font-semibold">⏭️ 未放行</p>
  <p class="mt-2 text-sm">可能原因：关键词不匹配、地域不符、公告类型不符。请尝试其他 URL 或使用手动模式。</p>
</div>'''

        best_direction_id = filtered.matched_direction_id
        match_results = filtered.match_results
        location_result = filtered.location_result
        feasibility = scorer.calculate(
            filtered,
            match_results,
            location_result,
            content_analysis=None,
            ai_extracted=item.ai_extracted,
            attachment_analysis=None,
            direction_id=best_direction_id,
        )
        filtered.feasibility = feasibility

        total = feasibility.get("total", 0)
        passes = feasibility.get("passes_filter", True)
        breakdown = feasibility.get("score_breakdown") or []
        total_esc = html.escape(str(total))
        pass_class = "text-green-400" if passes else "text-amber-400"
        pass_text = "✅ 放行" if passes else "⏭️ 未通过二次过滤"
        title_esc = html.escape((item.title or "")[:200])

        rows = []
        for b in breakdown:
            rule_esc = html.escape(str(b.get("rule", "")))
            pts = b.get("points", 0)
            try:
                pts_int = int(float(pts))
            except (TypeError, ValueError):
                pts_int = 0
            sign = "+" if pts_int >= 0 else ""
            rows.append(f'<div class="flex justify-between py-1 text-sm"><span class="text-gray-400">{rule_esc}</span><span class="font-mono {"text-cyan-400" if pts_int >= 0 else "text-amber-400"}">{sign}{pts_int}分</span></div>')
        rows_html = "\n".join(rows) if rows else '<div class="text-gray-500 text-sm">无明细</div>'

        return _render_rule_result(total_esc, pass_class, pass_text, rows_html, title_esc=title_esc)
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        return f'<div class="p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-400">❌ 异常: {html.escape(str(e)[:300])}<pre class="mt-2 text-xs text-gray-500 overflow-x-auto max-h-40">{html.escape(err[-2000:])}</pre></div>'


# ---------- 爬虫探针 ----------


@router.post("/spider_test", response_class=HTMLResponse)
def spider_test(url: str = Form(...)):
    """爬虫探针：纯粹测试抓取网页纯文本，不调 AI、不走后续流程。"""
    url = (url or "").strip()
    if not url:
        return '<div class="p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-400">❌ 请输入有效 URL</div>'
    if not url.startswith(("http://", "https://")):
        return '<div class="p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-400">❌ 请输入以 http:// 或 https:// 开头的 URL</div>'

    try:
        import os
        os.chdir(ROOT)
        try:
            from dotenv import load_dotenv
            load_dotenv(ROOT / ".env")
        except Exception:
            pass
        from src.config import ConfigManager
        from src.schema import TenderItem
        from src.spider.plap_spider import PLAPSpider

        cfg = ConfigManager(str(ROOT / "config")).load_all()
        config = _config_to_dict(cfg)
        spider = PLAPSpider(config)
        if not spider.init_browser():
            return '<div class="p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-400">❌ 浏览器初始化失败</div>'

        item = TenderItem(project_id="spider_probe", url=url, title="", content_raw="")
        spider.fetch_detail(item)
        content = getattr(item, "content_raw", "") or ""
        char_count = len(content)

        content_esc = html.escape(content) if content else "(空)"
        if char_count < 50:
            hint = '<p class="text-amber-400 text-sm mt-2">⚠️ 内容过短，可能被反爬拦截或选择器失效，请检查 URL 是否为有效详情页。</p>'
        else:
            hint = ""

        return f'''<div class="p-4 rounded-lg bg-gray-800/80 border border-gray-600">
  <p class="text-sm text-gray-400 mb-2">纯文本总字数: <span class="font-mono text-cyan-400">{char_count}</span> 字</p>
  {hint}
  <pre class="mt-3 p-3 bg-black/60 rounded-lg overflow-x-auto overflow-y-auto max-h-96 text-xs text-gray-300 whitespace-pre-wrap break-words border border-gray-700">{content_esc}</pre>
</div>'''
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        return f'<div class="p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-400">❌ 异常: {html.escape(str(e)[:300])}<pre class="mt-2 text-xs text-gray-500 overflow-x-auto max-h-40">{html.escape(err[-2000:])}</pre></div>'


# ---------- AI 提取狙击手 ----------


@router.post("/sniper", response_class=HTMLResponse)
def sniper(url: str = Form(...)):
    """AI 提取狙击手：单 URL 抓取 + 强制 AI 提取，不入库不推送。"""
    url = (url or "").strip()
    if not url:
        return '<div class="p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-400">❌ 请输入有效 URL</div>'
    if not url.startswith(("http://", "https://")):
        return '<div class="p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-400">❌ 请输入以 http:// 或 https:// 开头的 URL</div>'

    try:
        import os
        os.chdir(ROOT)
        # 确保 .env 已加载，否则 ConfigManager 无法解析 ${CUSTOM_OPENAI_API_KEY} 等
        try:
            from dotenv import load_dotenv
            load_dotenv(ROOT / ".env")
        except Exception:
            pass
        from src.config import ConfigManager
        from src.schema import TenderItem
        from src.spider.plap_spider import PLAPSpider
        from src.analyzer.info_extractor import InfoExtractor

        cfg = ConfigManager(str(ROOT / "config")).load_all()
        config = cfg.to_dict() if hasattr(cfg, "to_dict") else getattr(cfg, "_config", cfg)
        analyzer_cfg = config.setdefault("analyzer", {})
        analyzer_cfg.setdefault("provider", "custom_openai")
        analyzer_cfg.setdefault("custom_base_url", "https://open.bigmodel.cn/api/paas/v4")
        # 确保 API Key 能从 .env 读到（ConfigManager 的 ${VAR} 在 load_dotenv 前可能为空）
        if not (analyzer_cfg.get("custom_api_key") or "").strip():
            analyzer_cfg["custom_api_key"] = (os.getenv("CUSTOM_OPENAI_API_KEY") or "").strip()

        spider = PLAPSpider(config)
        if not spider.init_browser():
            return '<div class="p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-400">❌ 浏览器初始化失败</div>'

        item = TenderItem(project_id="sniper", url=url, title="", content_raw="")
        spider.fetch_detail(item)
        content = getattr(item, "content_raw", "") or item.content_raw or ""

        if not content or len(content) < 50:
            return '<div class="p-4 rounded-lg bg-amber-900/30 border border-amber-700 text-amber-400">⚠️ 未能抓取到有效正文（内容过短或为空），请检查 URL 是否为有效详情页</div>'

        extractor = InfoExtractor(config)
        result = extractor.extract(content, item, force_ai=True)

        if result is None:
            return '<div class="p-4 rounded-lg bg-amber-900/30 border border-amber-700 text-amber-400">⚠️ AI 分析未启用或未配置</div>'

        return _render_sniper_card(item)
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        return f'<div class="p-4 rounded-lg bg-red-900/30 border border-red-700 text-red-400">❌ 异常: {html.escape(str(e)[:300])}<pre class="mt-2 text-xs text-gray-500 overflow-x-auto">{html.escape(err[-1500:])}</pre></div>'
