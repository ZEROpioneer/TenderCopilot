"""
TenderCopilot Web UI - FastAPI application entry.
Run: uvicorn web.app:app --reload --host 127.0.0.1 --port 8000
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from web.api import reports, run as run_api, config as config_api, history

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

# Static files (after routes so /api/* take precedence)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "TenderCopilot"}


@app.get("/")
def index():
    """Serve the single-page UI."""
    index_file = Path(__file__).parent / "static" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "TenderCopilot API", "docs": "/docs", "ui": "Place static/index.html for UI"}
