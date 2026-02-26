"""System API: 数据统计、危险操作（清空业务数据）"""
import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database import get_db

router = APIRouter()


@router.get("/data_stats")
def data_stats():
    """返回各核心业务表当前数据量，供前端危险区域展示。"""
    db = get_db(ROOT)
    counts = db.get_table_counts()
    return counts


@router.post("/clear_data", response_class=HTMLResponse)
def clear_data():
    """清空所有业务数据，返回 HTMX 成功提示。"""
    try:
        db = get_db(ROOT)
        db.clear_business_data()
        return HTMLResponse('<span class="text-green-400 font-medium">✅ 所有测试业务数据已清空！</span>')
    except Exception as e:
        return HTMLResponse(f'<span class="text-red-400 font-medium">❌ 清空失败: {e}</span>', status_code=500)
