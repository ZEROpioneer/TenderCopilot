"""测试阶段数据库清理脚本

用途：
- 清空历史爬取的公告及相关联的筛选 / 分析 / 通知 / 爬取记录
- 方便在测试阶段频繁跑完整流程，而不受「数据库去重」和「增量爬取」的影响

注意：
- 这是一个「危险操作」，会删除 data/history.db 中的业务数据，但不会删库文件本身。
- 仅建议在测试/开发环境使用，不要在生产环境随便执行。
"""

import os
import sys
from loguru import logger

# 确保可以从项目根目录导入 src 包
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config import ConfigManager
from src.database.storage import DatabaseManager


def clear_database():
    """清空历史业务数据"""
    # 读取配置，获取数据库路径（保持与主程序一致）
    config = ConfigManager().load_all()
    db_path = config["database"]["path"]

    logger.info(f"🧹 准备清理数据库数据: {db_path}")

    db = DatabaseManager(db_path)

    # 按依赖关系从「子表 → 父表」依次清理
    tables = [
        "notification_logs",
        "analysis_results",
        "filtered_projects",
        "task_logs",
        "crawl_history",
        "announcements",
    ]

    total_deleted = {}

    for table in tables:
        try:
            logger.info(f"   🔄 删除表 {table} 中的所有记录...")
            deleted = db.execute_query(f"DELETE FROM {table}")
            total_deleted[table] = deleted
            logger.info(f"   ✅ {table}: 删除 {deleted} 行")
        except Exception as e:
            logger.error(f"   ❌ 清理表 {table} 失败: {e}")

    # 可选：整理碎片
    try:
        logger.info("   🔧 执行 VACUUM 压缩数据库文件...")
        db.execute_query("VACUUM")
    except Exception as e:
        logger.warning(f"   ⚠️ VACUUM 失败（可忽略）: {e}")

    db.close()

    logger.success("✅ 数据库业务数据清理完成")
    logger.info("📊 本次删除统计：")
    for table, count in total_deleted.items():
        logger.info(f"   - {table}: {count} 行")


if __name__ == "__main__":
    clear_database()

