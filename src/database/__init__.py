"""数据库模块"""

from pathlib import Path

from .storage import DatabaseManager


def get_db(project_root: Path) -> DatabaseManager:
    """获取数据库管理器（供 Web 层等调用）。

    Args:
        project_root: 项目根目录路径

    Returns:
        DatabaseManager 实例
    """
    import os
    from src.config.config_manager import ConfigManager

    os.chdir(project_root)
    cfg = ConfigManager(str(project_root / "config")).load_all().to_dict()
    db_path = cfg.get("database", {}).get("path", "data/history.db")
    if not Path(db_path).is_absolute():
        db_path = str(project_root / db_path)
    return DatabaseManager(db_path)


__all__ = ['DatabaseManager', 'get_db']
