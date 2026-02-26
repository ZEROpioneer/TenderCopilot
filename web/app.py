"""
TenderCopilot Web UI - FastAPI application entry.
Run: uvicorn web.app:app --reload --host 127.0.0.1 --port 8000
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web.api import reports, run as run_api, config as config_api, history, logs as logs_api, intel as intel_api, scheduler as scheduler_api, lab as lab_api, radar as radar_api, stats as stats_api, system as system_api

templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

app = FastAPI(
    title="TenderCopilot",
    description="招标项目智能助手 - Web 操作界面",
    version="1.0.0",
)

# CORS for local dev (optional)
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(run_api.router, prefix="/api/run", tags=["run"])
app.include_router(config_api.router, prefix="/api/config", tags=["config"])
app.include_router(history.router, prefix="/api/history", tags=["history"])
app.include_router(logs_api.router, prefix="/api/logs", tags=["logs"])
app.include_router(intel_api.router, prefix="/api/intel", tags=["intel"])
app.include_router(scheduler_api.router, prefix="/api/scheduler", tags=["scheduler"])
app.include_router(lab_api.router, prefix="/api/lab", tags=["lab"])
app.include_router(radar_api.router, prefix="/api/radar", tags=["radar"])
app.include_router(stats_api.router, prefix="/api/stats", tags=["stats"])
app.include_router(system_api.router, prefix="/api/system", tags=["system"])

# Static files (after routes so /api/* take precedence)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "TenderCopilot"}


@app.get("/")
def dashboard(request: Request):
    """控制台：控制面板、实时日志、高分项目、快速配置。"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/projects")
def projects(request: Request):
    """项目列表：高分项目情报。"""
    return templates.TemplateResponse("projects.html", {"request": request})


@app.get("/settings")
def settings(request: Request):
    """配置管理：完整配置表单（深色卡片）。"""
    return templates.TemplateResponse("settings.html", {"request": request})


@app.get("/history")
def history_page(request: Request):
    """历史报告：日报列表与爬取历史（深色数据表格）。"""
    return templates.TemplateResponse("history.html", {"request": request})


@app.get("/intel")
def intel_monitor(request: Request):
    """情报监控台：全屏展示最近抓取的招标项目（AI 核心决策信息）。"""
    return templates.TemplateResponse("intel.html", {"request": request})


@app.get("/lab")
def lab_page(request: Request):
    """开发者实验室：幽灵测试模式（强制去重、静音推送）。"""
    return templates.TemplateResponse("lab.html", {"request": request})


@app.get("/radar")
def radar_page(request: Request):
    """追踪雷达：已关注项目集中管理。"""
    return templates.TemplateResponse("radar.html", {"request": request})
