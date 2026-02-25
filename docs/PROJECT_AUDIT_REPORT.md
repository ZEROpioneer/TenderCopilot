# TenderCopilot 项目全景梳理报告

> 代码盘点 (Codebase Audit) · 架构师视角

---

## 1. 核心工作流 (Data Flow)

### 流程图

```mermaid
flowchart TB
    subgraph 入口
        A[python main.py] --> B{TenderCopilot.run_pipeline}
    end

    subgraph 步骤1_时间窗口
        B --> C[CrawlTracker.get_last_crawl_time]
        C --> D[上次爬取时间 / 首次则 168 小时前]
    end

    subgraph 步骤2_爬取
        D --> E[PLAPSpider.fetch_announcements]
        E --> F[军队采购网列表页 · 多页爬取]
        F --> G[DB 去重: exists?id]
        G --> H[连续 5 条重复则停止]
        H --> I[all_announcements]
    end

    subgraph 步骤3_记录
        I --> J[CrawlTracker.record_crawl]
        J --> K[写入 crawl_history]
    end

    subgraph 步骤4_筛选
        I --> L[FilterManager.process]
        L --> M{公告类型?}
        M -->|招标/采购/询价等| N[策略 A: 关键词+地域+类型+去重]
        M -->|更正/流标/废标等| O[策略 B: 仅检查 interested_projects]
        N --> P[KeywordMatcher · LocationMatcher · NoticeTypeFilter · Deduplicator]
        O --> P
        P --> Q[filtered 项目列表]
        Q --> R[DB: save_announcement]
    end

    subgraph 步骤5_深度分析
        Q --> S[deep_analyze_projects]
        S --> T[fetch_detail 获取详情]
        T --> U[ContentAnalyzer 内容相关度]
        T --> V[InfoExtractor AI 提取]
        T --> W[AttachmentAnalyzer 附件分析]
        U --> X[FeasibilityScorer 综合评分]
        V --> X
        W --> X
        X --> Y[DB: save_filtered_project · save_analysis_result]
        X --> Z[高分项目 → add_interested_project]
    end

    subgraph 步骤6_报告与推送
        Q --> AA[MarkdownReporter.generate_daily_report]
        AA --> AB[data/reports/daily_report_*.md]
        AB --> AC[NotificationManager.send_report]
        AC --> AD[企业微信 · 邮件 · 个人微信]
    end

    subgraph Web 展示
        AB --> AE[/api/reports 读取文件列表]
        Y --> AF[/api/intel 查询 filtered_projects]
        K --> AG[/api/history/crawls 查询 crawl_history]
    end
```

### 文字说明

**数据从哪里开始抓取？**

- 入口：`python main.py --mode once` 或 `--mode schedule`
- 爬虫：`PLAPSpider.fetch_announcements()` 访问军队采购网列表页 (`config/settings.yaml` 中的 `announcement_list_url`)
- 多页爬取：从第 1 页开始，解析列表项，每页检查 `db.exists(announcement_id)`；连续 5 条已存在则停止（认为已进入历史数据）
- 数据源：列表页 HTML 或 API（项目同时支持 DrissionPage 爬虫和 API 客户端）

**经过哪些过滤步骤？**

1. **爬虫层去重**：`db.exists(id)` + 本次运行内 `seen_in_run`（url/id）
2. **筛选层（FilterManager）**：
   - **策略 A（新机会）**：招标/采购/询价/竞争性谈判 → 关键词匹配 → 地域匹配 → 公告类型过滤 → 数据库去重
   - **策略 B（追踪）**：更正/流标/废标/变更 → 仅当标题中的项目编号在 `interested_projects` 中时放行
3. **关键词**：`KeywordMatcher` 匹配 `business_directions` 中的 `keywords_include`，排除 `global_exclude`
4. **地域**：`LocationMatcher` 根据 `location_required`、`location_priority` 判断
5. **公告类型**：`NoticeTypeFilter` 根据 `include`/`exclude`/`include_correction` 过滤

**AI 分析在哪一步介入？**

- 在 **步骤 5（深度分析）** 中，对通过初筛的 `filtered` 项目逐个分析
- 每个项目：先 `fetch_detail` 获取详情内容，再调用 `InfoExtractor.extract()`（对接 OpenAI 兼容接口，如智谱）
- AI 提取：项目编号、项目名称、预算、截止日期等结构化信息
- 结果写入 `analysis_results` 表，并参与 `FeasibilityScorer` 综合评分

**最终数据如何存储和推送？**

- **数据库**：`announcements`（公告）、`filtered_projects`（筛选+评分）、`analysis_results`（AI 提取）、`crawl_history`（爬取记录）、`interested_projects`（高分追踪）
- **报告**：`MarkdownReporter.generate_daily_report()` 生成 Markdown，保存到 `data/reports/daily_report_YYYYMMDD_HHMMSS.md`
- **推送**：`NotificationManager.send_report()` 将报告内容发送到企业微信 / 邮件 / 个人微信（根据 `notifications.yaml` 配置）
- **Web**：报告列表来自 `data/reports/` 目录；高分项目来自 `filtered_projects` JOIN `announcements`；爬取历史来自 `crawl_history`

---

## 2. 核心模块职责拆解 (Module Responsibilities)

| 目录 | 核心作用 | 关键类/函数 | 调用关系 |
|------|----------|-------------|----------|
| **src/spider** | 爬取公告列表与详情 | `PLAPSpider.fetch_announcements()`, `fetch_detail()` | 被 main 调用；使用 db 做去重 |
| **src/spider** | 附件下载 | `AttachmentHandler.download()` | 被 `_analyze_single_project` 调用 |
| **src/spider** | 爬取时间与历史 | `CrawlTracker.get_last_crawl_time()`, `record_crawl()` | 被 main 调用；读写 crawl_history |
| **src/filter** | 关键词匹配 | `KeywordMatcher.match()` | 被 FilterManager 调用 |
| **src/filter** | 地域匹配 | `LocationMatcher.match()` | 被 FilterManager 调用 |
| **src/filter** | 公告类型过滤 | `NoticeTypeFilter.match()` | 被 FilterManager 调用 |
| **src/filter** | 去重检查 | `Deduplicator.is_duplicate()` | 被 FilterManager 调用；查 announcements 表 |
| **src/filter** | 筛选编排 | `FilterManager.process()` | 被 main.filter_announcements 调用；协调上述子模块 |
| **src/analyzer** | AI 信息提取 | `InfoExtractor.extract()` | 被 `_analyze_single_project` 调用 |
| **src/analyzer** | 内容相关度 | `ContentAnalyzer.analyze_relevance()` | 被 `_analyze_single_project` 调用 |
| **src/analyzer** | 附件相关度 | `AttachmentAnalyzer.analyze()` | 被 `_analyze_single_project` 调用 |
| **src/analyzer** | 综合评分 | `FeasibilityScorer.calculate()` | 被 `_analyze_single_project` 调用 |
| **src/reporter** | 报告生成 | `MarkdownReporter.generate_daily_report()` | 被 main 调用；接收 filtered 列表 |
| **src/database** | 持久化 | `DatabaseManager` 各 save/execute 方法 | 被 spider、filter、main 调用 |
| **src/notifier** | 通知推送 | `NotificationManager.send_report()` | 被 main 调用 |
| **src/scheduler** | 定时任务 | `TaskScheduler` | 被 main.start_scheduler 调用；定时调用 run_pipeline |
| **src/config** | 配置加载 | `ConfigManager.load_all()` | 被 main、各 API 调用 |
| **src/utils** | 项目指纹 | `project_fingerprint` | 被 FilterManager 策略 B、add_interested_project 使用 |

---

## 3. Web 端与核心逻辑的关系

### 架构概览

```
Web 层 (FastAPI)          核心逻辑层 (main.py + src/)
─────────────────────────────────────────────────────────────────
/                         → dashboard.html (模板)
/projects                  → projects.html
/settings                  → settings.html
/history                   → history.html

POST /api/run              → 新线程: main.TenderCopilot().run_pipeline()
GET  /api/run/status       → 内存 _run_state 字典
GET  /api/reports          → 读取 data/reports/*.md 文件列表
GET  /api/reports/{id}     → 读取对应 .md 文件内容
GET  /api/history/crawls   → 查询 crawl_history 表
GET  /api/history/stats    → 聚合 crawl_history 按日统计
GET  /api/intel/top        → 查询 filtered_projects + announcements + analysis_results
GET  /api/config           → 读取 config/*.yaml + .env 掩码
PUT  /api/config           → 写回 config/*.yaml + .env
GET  /api/logs/stream_logs → SSE 实时 tail 日志文件
GET  /api/scheduler/status → 读取 settings.yaml 的 scheduler
PATCH /api/scheduler       → 更新 scheduler.enabled
```

### 「立即运行」按钮的底层调用链

1. 前端：点击按钮 → `POST /api/run`
2. `web/api/run.py`：`trigger_run()` 创建后台线程，调用 `_run_pipeline()`
3. `_run_pipeline()`：`from main import TenderCopilot` → `app = TenderCopilot()` → `app.run_pipeline()`
4. `run_pipeline()`：执行完整 7 步流程（爬取 → 筛选 → 深度分析 → 报告 → 推送）

### Web 页面数据来源

| 页面 | 数据来源 |
|------|----------|
| 控制台 · 高分项目 | 前端 HTMX 请求 `/api/intel/top/html`，后端查 `filtered_projects` 等表 |
| 控制台 · 实时日志 | 前端 EventSource 连接 `/api/logs/stream_logs`，后端 tail 日志文件 |
| 控制台 · 运行状态 | 前端轮询 `/api/run/status`，读取内存 `_run_state` |
| 历史报告 | 前端请求 `/api/reports` 和 `/api/reports/{id}`，读取 `data/reports/` 目录 |
| 爬取历史 | 前端请求 `/api/history/crawls`，查询 `crawl_history` 表 |
| 配置管理 | 前端请求 `/api/config`，读取 `config/*.yaml`；保存时 PUT 写回 |

---

## 4. 配置文件地图 (Config Map)

| 文件 | 控制内容 |
|------|----------|
| **config/settings.yaml** | 目标站点、爬虫参数、爬取策略、定时任务、数据库、AI 分析、深度分析、评分权重、公告类型过滤、报告、日志、监控、代理等 |
| **config/business_directions.yaml** | 业务方向（关键词、地域、权重）、全局排除、筛选阈值 |
| **config/notifications.yaml** | 企业微信、邮件、个人微信、钉钉、通知规则、管理员告警 |
| **.env** | 敏感变量：`CUSTOM_OPENAI_API_KEY`、`WECHAT_WORK_WEBHOOK`、`EMAIL_PASSWORD` 等（YAML 中用 `${VAR}` 引用） |

`ConfigManager` 会合并上述 YAML，替换 `${VAR}` 为环境变量，并应用默认值。

---

## 5. 当前架构的「脆弱点」与「隐藏逻辑」 (Technical Debt)

### 5.1 去重逻辑

- **现状**：爬虫、筛选、数据库、报告四层均有去重（url/id、seen_in_run、seen_keys、当日过滤、报告兜底）
- **风险**：多套逻辑分散，后续改动容易漏改；`filtered_projects` 无 `announcement_id` 唯一约束，依赖代码逻辑保证
- **建议**：在文档中明确「去重链」约定，避免新增逻辑时破坏一致性

### 5.2 Web 与 CLI 的配置隔离

- **现状**：Web 通过 `POST /api/run` 启动的 `TenderCopilot` 会重新加载配置；定时任务模式下的 `main.py` 也是每次启动时加载
- **风险**：Web 修改配置后，若未保存到 YAML，下次运行仍用旧配置；若保存了，需确保进程能正确读取（当前无热重载）

### 5.3 运行状态与日志

- **现状**：`_run_state` 仅存在内存，Web 重启后丢失；日志写入 `logs/detail/run_*.log`，SSE 会 tail 最新文件
- **风险**：Web 触发运行后，若 uvicorn 重启，`_run_state` 重置，但后台线程可能仍在跑；日志与运行状态可能不一致

### 5.4 配置与数据结构的耦合

- **现状**：`ConfigManager` 返回的 `config` 既可能是 dict，也可能是 `ConfigManager` 实例（支持点号访问）；部分代码用 `config.get('key')`，部分用 `config['key']`
- **风险**：混用导致 KeyError 或类型错误；`config` 的 `to_dict()` 需在需要纯 dict 时显式调用

### 5.5 数据库与并发

- **现状**：`DatabaseManager` 使用 `check_same_thread=False`，多线程共享同一连接
- **风险**：SQLite 并发写有限制；`deep_analyze_projects` 使用 `ThreadPoolExecutor` 并发写库，高并发下可能出问题

### 5.6 爬虫与 API 的切换

- **现状**：`init_components` 同时初始化 `api_client` 和 `spider`，但 `run_pipeline` 实际只用 `PLAPSpider`
- **风险**：API 客户端若未来启用，需明确与爬虫的切换逻辑；当前存在未使用的初始化代码

### 5.7 废弃配置的兼容

- **现状**：`filter_settings.yaml`、`search_keywords.yaml` 已标记废弃，但 `ConfigManager` 仍会尝试加载并合并
- **风险**：旧配置残留可能覆盖新配置；建议迁移完成后移除兼容逻辑

### 5.8 通知与报告内容

- **现状**：`send_report` 发送的是整份 Markdown 报告，企业微信有 4096 字符限制，会分段发送
- **风险**：分段后上下文丢失；`projects` 参数传入但主要用于标题生成，不改变报告内容

---

以上为 TenderCopilot 项目的全景梳理，便于后续暂停新功能开发、专注架构梳理与重构时参考。
