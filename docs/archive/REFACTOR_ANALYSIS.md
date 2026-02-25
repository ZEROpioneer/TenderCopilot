# TenderCopilot 项目整理与去重分析报告

> 分析时间: 2026-02
> 角色: Senior Python Architect

---

## 任务 1：冗余文档清理 (Cleanup Documentation)

### 1.1 根目录下需归档/处理的 Markdown 文件

| 文件 | 类型 | 建议操作 | 说明 |
|------|------|----------|------|
| `GIT_COMMIT_READY.md` | 过程性 | 移至 `docs/archive/` | 提交准备说明，一次性 |
| `CLEANUP_SUMMARY.md` | 过程性 | 移至 `docs/archive/` | 清理总结，历史记录 |
| `MERGE_SUMMARY.md` | 过程性 | 移至 `docs/archive/` | 合并总结，历史记录 |
| `OPTIMIZATION_SUMMARY.md` | 过程性 | 移至 `docs/archive/` | 优化总结，历史记录 |
| `PROJECT_STRUCTURE.md` | 冗余 | 合并至 README 或移至 archive | 与 README 重复，README 已有项目结构 |
| `分层报告示例.md` | 示例/过程性 | 移至 `docs/archive/` | 报告格式示例 |

### 1.2 docs/ 目录下需归档的文件

| 文件 | 类型 | 建议操作 |
|------|------|----------|
| `API_FIX_SUMMARY.md` | 过程性 | 移至 `docs/archive/` |
| `IMPLEMENTATION_COMPLETE.md` | 过程性 | 移至 `docs/archive/` |
| `IMPLEMENTATION_SUMMARY.md` | 过程性 | 移至 `docs/archive/` |
| `TESTING_GUIDE.md` | 核心 | **保留** - 测试指南为开发文档 |

### 1.3 保留的核心文档

- **根目录**: `README.md`, `CHANGELOG.md`
- **docs/**: `TESTING_GUIDE.md`（测试指南）
- **config/**: `README.md`
- **tools/**: `README.md`
- **web/**: `README.md`
- **prototype/**: `README.md`

---

## 任务 2：代码逻辑去重 (Refactor & Deduplicate)

### 2.1 数据库连接 - 重复实现

**现状**: `web/api/history.py` 和 `web/api/intel.py` 各自实现了几乎相同的 `_get_db()` 函数：

```python
# 重复出现在 history.py (L10-22) 和 intel.py (L17-26)
def _get_db():
    import os
    os.chdir(ROOT)
    from src.config.config_manager import ConfigManager
    from src.database.storage import DatabaseManager
    cfg = ConfigManager(str(ROOT / "config")).load_all().to_dict()
    db_path = cfg.get("database", {}).get("path", "data/history.db")
    if not Path(db_path).is_absolute():
        db_path = str(ROOT / db_path)
    return DatabaseManager(db_path)
```

**重构方案**: 在 `src/database/` 中新增 `get_db(project_root: Path) -> DatabaseManager` 工具函数，供 web 层统一调用。

---

### 2.2 配置读取 - 多处重复

| 位置 | 重复内容 | 与 src 的关系 |
|------|----------|---------------|
| `web/api/config.py` | 完整实现 `_load_yaml`, `_save_yaml`，直接读写 `config/*.yaml` | **特殊**: Web 端需要读写能力（PUT 更新）、敏感值脱敏、.env 管理，与 `ConfigManager` 职责不同。ConfigManager 是只读+环境变量替换。**建议**: 保留 config.py 的 Web 专用逻辑，但可将 `_load_yaml`/`_save_yaml` 提取到 `src.config` 的工具函数以减少重复。 |
| `web/api/scheduler.py` | `_load_yaml`, `_save_yaml` 完全重复 | 应改用 `src.config` 或 `web.api.config` 中的实现 |
| `web/api/logs.py` | 手动 `yaml.safe_load(settings.yaml)` 读取 `logging.log_file` | 应使用 `ConfigManager` 或统一工具 |

---

### 2.3 Web 端与 src 的引用关系（当前）

| web 模块 | 已使用 src | 重复逻辑 |
|----------|------------|----------|
| `history.py` | ConfigManager, DatabaseManager | `_get_db()` 重复 |
| `intel.py` | ConfigManager, DatabaseManager | `_get_db()` 重复 |
| `run.py` | main.TenderCopilot, DatabaseManager, CrawlTracker | 无重复，正确 |
| `config.py` | 无 | 自实现 YAML 读写、.env 解析 |
| `scheduler.py` | 无 | 自实现 `_load_yaml`/`_save_yaml` |
| `logs.py` | 无 | 自实现读取 settings.yaml 的 logging 段 |
| `reports.py` | 无 | 仅读文件系统，无 config/db 依赖 |

---

### 2.4 重构目标总结

1. **统一 `_get_db()`**: 在 `src.database` 中提供 `get_db(project_root: Path)` 或通过 `src.database.get_db()` 获取，web 各模块 import 使用。
2. **scheduler.py**: 改用 `src.config.config_manager` 或复用 `web.api.config` 的 YAML 工具。
3. **logs.py**: 使用 `ConfigManager().load_all()` 获取 `logging.log_file`，而非手动读 YAML。
4. **config.py**: 可选 - 将 `_load_yaml`/`_save_yaml` 抽到 `src.config.utils`，供 config.py 和 scheduler 共用。

---

## 任务 3：规范化项目结构 (Standardize Structure)

### 3.1 当前结构 vs 建议结构

**当前**:
```
TenderCopilot/
├── main.py
├── config/
├── src/
├── web/
├── tools/
├── tests/
├── docs/
├── prototype/
└── [多份根目录 .md]
```

**建议（小幅调整）**:
```
TenderCopilot/
├── main.py              # 主入口（保持不变）
├── config/              # 配置（保持不变）
├── src/                 # 核心业务逻辑（保持不变）
├── web/                 # Web 界面（FastAPI + 模板）
│   ├── app.py
│   ├── api/             # 路由层，仅调用 src
│   └── templates/
├── scripts/             # 【可选】将 tools/ 重命名或整合
├── tests/
├── docs/
│   ├── archive/         # 归档的过程性文档
│   └── TESTING_GUIDE.md
├── prototype/
├── README.md
└── CHANGELOG.md
```

### 3.2 建议的调整

| 项目 | 建议 | 理由 |
|------|------|------|
| `tools/` → `scripts/` | 可选 | `scripts` 更通用；若 `main.py` 视为 CLI 入口，`tools/` 作为开发/运维脚本目录也可接受 |
| `web/` 重命名为 `interface/web/` | 暂不推荐 | 增加目录层级，当前 `web/` 已清晰 |
| 根目录 `main.py` | 保持 | 符合常见 Python 项目习惯 |
| `docs/archive/` | 新建 | 存放过程性文档 |

### 3.3 最终推荐结构（简洁版）

```
TenderCopilot/
├── main.py
├── config/
├── src/
├── web/
├── tools/
├── tests/
├── docs/
│   ├── archive/         # 新增：归档文档
│   └── TESTING_GUIDE.md
├── prototype/
├── README.md
└── CHANGELOG.md
```

`tools/` 保持不动，仅在 docs 中明确其用途。

---

## 执行清单汇总

### Phase 1: 文档清理
- [ ] 创建 `docs/archive/`
- [ ] 移动至 archive: `GIT_COMMIT_READY.md`, `CLEANUP_SUMMARY.md`, `MERGE_SUMMARY.md`, `OPTIMIZATION_SUMMARY.md`, `PROJECT_STRUCTURE.md`, `分层报告示例.md`
- [ ] 移动至 archive: `docs/API_FIX_SUMMARY.md`, `docs/IMPLEMENTATION_COMPLETE.md`, `docs/IMPLEMENTATION_SUMMARY.md`
- [ ] 保留 `docs/TESTING_GUIDE.md`

### Phase 2: 代码去重
- [ ] 在 `src/database/` 添加 `get_db(project_root: Path)` 函数
- [ ] `web/api/history.py`: 删除 `_get_db`，改为 `from src.database import get_db`
- [ ] `web/api/intel.py`: 同上
- [ ] `web/api/scheduler.py`: 使用 `src.config` 或提取的 YAML 工具
- [ ] `web/api/logs.py`: 使用 ConfigManager 获取 log_file 路径

### Phase 3: 文档更新
- [ ] 更新 `README.md` 的「项目结构」章节，反映最新布局和 docs/archive 说明

---

*分析完成。请确认后执行。*
