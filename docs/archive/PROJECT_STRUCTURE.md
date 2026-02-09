# TenderCopilot 项目结构

## 📁 目录结构

```
TenderCopilot/
├── .cursor/                     # Cursor IDE 配置
│   └── skills/                  # 项目技能定义
│       ├── tender-analyzer/     # 招标文件智能分析
│       ├── tender-filter/       # 招标项目智能筛选
│       ├── tender-reporter/     # 招标项目报告生成
│       ├── tender-spider/       # 爬虫开发规范
│       └── tender-workflow/     # 工作流程管理
│
├── config/                      # 配置文件目录
│   ├── business_directions.yaml # 业务方向配置（关键词、地域限制）
│   ├── filter_settings.yaml     # 筛选设置
│   ├── notifications.yaml       # 通知配置
│   ├── search_keywords.yaml     # 搜索关键词配置
│   └── settings.yaml            # 主配置文件
│
├── src/                         # 源代码目录
│   ├── analyzer/                # 分析模块
│   │   ├── attachment_analyzer.py  # 附件分析
│   │   ├── content_analyzer.py     # 内容分析
│   │   ├── feasibility_scorer.py   # 可行性评分
│   │   └── info_extractor.py       # 信息提取（AI）
│   │
│   ├── database/                # 数据库模块
│   │   └── storage.py           # 数据存储管理
│   │
│   ├── filter/                  # 筛选模块
│   │   ├── deduplicator.py      # 去重
│   │   ├── keyword_matcher.py   # 关键词匹配
│   │   └── location_matcher.py  # 地域匹配
│   │
│   ├── notifier/                # 通知模块
│   │   ├── email_sender.py      # 邮件通知
│   │   ├── notification_manager.py  # 通知管理器
│   │   ├── wechat.py            # 微信通知
│   │   └── wechat_work.py       # 企业微信通知
│   │
│   ├── reporter/                # 报告模块
│   │   └── report_generator.py  # 报告生成器
│   │
│   ├── scheduler/               # 调度模块
│   │   └── task_scheduler.py    # 任务调度器
│   │
│   └── spider/                  # 爬虫模块
│       ├── api_client.py        # API 客户端
│       ├── attachment_handler.py # 附件处理
│       ├── crawl_tracker.py     # 爬取追踪
│       └── plap_spider.py       # 军队采购网爬虫（核心）
│
├── prototype/                   # 原型测试代码（保留作为参考）
│   ├── results/                 # 测试结果（已清理）
│   ├── common_utils.py          # 通用工具函数
│   ├── test_*.py               # 测试脚本
│   └── README.md               # 原型代码说明
│
├── tests/                       # 正式测试目录
│   ├── test_config.py          # 配置测试
│   ├── test_imports.py         # 导入测试
│   └── test_wechat_webhook.py  # 微信 Webhook 测试
│
├── tools/                       # 工具脚本
│   ├── find_api_endpoint.py    # API 端点查找
│   ├── test_api_endpoints.py   # API 端点测试
│   ├── verify_codes.py         # 代码验证
│   └── README.md               # 工具说明
│
├── docs/                        # 文档目录
│   ├── archive/                # 归档的过程性文档
│   ├── API_FIX_SUMMARY.md      # API 修复总结
│   ├── IMPLEMENTATION_COMPLETE.md  # 实现完成文档
│   ├── IMPLEMENTATION_SUMMARY.md   # 实现总结
│   └── TESTING_GUIDE.md        # 测试指南
│
├── data/                        # 数据目录（Git 忽略）
│   ├── .gitkeep                # 保持目录结构
│   ├── history.db              # SQLite 数据库
│   └── debug/                  # 调试数据（已清理）
│
├── logs/                        # 日志目录（Git 忽略，需创建）
│
├── main.py                      # 主程序入口
├── requirements.txt             # Python 依赖
├── .env.example                 # 环境变量示例
├── .gitignore                   # Git 忽略配置
│
├── README.md                    # 项目说明
├── CHANGELOG.md                 # 更新日志
└── MERGE_SUMMARY.md             # 合并总结
```

## 📄 核心文件说明

### 配置文件
- **settings.yaml**: 主配置文件，包含数据库路径、OpenAI API、定时任务等
- **business_directions.yaml**: 业务方向定义和关键词配置
- **search_keywords.yaml**: 搜索关键词配置（预爬取筛选）
- **notifications.yaml**: 通知渠道配置

### 核心模块
- **main.py**: 主程序，协调所有模块运行
- **plap_spider.py**: 军队采购网爬虫，支持多页爬取、智能去重、增量停止
- **keyword_matcher.py**: 多维度关键词匹配和评分
- **feasibility_scorer.py**: 项目可行性评分算法
- **report_generator.py**: 生成可读性强的分析报告

## 🔧 开发指南

### 环境配置
```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 OpenAI API Key 等

# 3. 创建必要目录
mkdir logs
```

### 运行程序
```bash
# 手动运行一次
python main.py

# 或使用调度器（配置在 settings.yaml）
python -m src.scheduler.task_scheduler
```

### 运行测试
```bash
# 正式测试
python -m pytest tests/

# 原型测试（仅开发参考）
cd prototype
python test_full_workflow.py
```

## 📦 Git 使用

### 忽略的文件
- `data/`: 数据库和爬取数据
- `logs/`: 日志文件
- `.env`: 敏感配置
- `__pycache__/`: Python 缓存
- `*.pyc`: 编译文件

### 提交前检查
```bash
# 查看状态
git status

# 查看将要提交的文件
git diff --cached

# 提交
git add .
git commit -m "你的提交信息"
```

## 🗂️ 数据目录说明

### data/
- **history.db**: SQLite 数据库，存储爬取历史和公告数据
- **debug/**: 调试数据（页面截图、HTML 源码等）

### logs/
- 运行日志文件，按日期命名

## 📚 文档索引

- **README.md**: 项目概述和快速开始
- **CHANGELOG.md**: 详细的版本更新记录
- **MERGE_SUMMARY.md**: 代码合并总结
- **prototype/README.md**: 原型测试代码说明
- **tools/README.md**: 工具脚本使用说明
- **docs/**: 详细的技术文档

## 🚀 部署清单

部署前确保：
- [ ] `.env` 文件配置完整
- [ ] `config/` 目录配置正确
- [ ] 创建 `logs/` 目录
- [ ] 创建 `data/` 目录
- [ ] 安装所有依赖
- [ ] 测试数据库连接
- [ ] 测试 OpenAI API 连接
- [ ] 配置定时任务

## 🔐 安全注意事项

**请勿提交到 Git 的文件：**
- `.env` - 包含 API 密钥
- `data/` - 包含爬取数据和数据库
- `logs/` - 可能包含敏感信息
- 任何包含密码、密钥的文件

**环境变量示例（.env.example）：**
```
OPENAI_API_KEY=your_api_key_here
OPENAI_API_BASE=https://api.openai.com/v1
```
