# TenderCopilot - 招投标智能助手

军队采购网招标信息智能爬虫和筛选系统，自动监控、筛选、分析招标公告，推送匹配的项目机会。

## ✨ 功能特性

- 🕷️ **智能爬虫**: 使用 DrissionPage 精准爬取军队采购网招标公告
- 🎯 **关键词匹配**: 基于业务方向自动筛选匹配项目
- 📍 **地域筛选**: 优先匹配特定地域的项目
- 🤖 **AI 分析**: 使用 Gemini/OpenAI 提取关键信息
- 📊 **可行性评分**: 动态规则引擎，支持自定义评分权重与规则
- 📱 **实时通知**: 企业微信/邮件多渠道推送
- ⏰ **定时任务**: 可配置执行时间，增量爬取避免重复
- 📈 **数据管理**: SQLite 数据库存储历史记录
- 🧪 **开发者实验室**: AI 提取、规则测试、爬虫探针、全链路干跑、数据清理

## 🚀 快速开始

### 1. 环境准备

**系统要求**:
- Python 3.8+
- Windows/Linux/macOS

**安装依赖**:
```bash
pip install -r requirements.txt
```

### 2. 配置

#### 2.1 环境变量配置

复制环境变量模板：
```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的配置：

```env
# AI API Key（必需）
GEMINI_API_KEY=your_actual_api_key_here

# 企业微信机器人 Webhook（如果使用企业微信通知）
WECHAT_WORK_WEBHOOK=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY
```

**获取 API Key**:
- Gemini API Key: https://makersuite.google.com/app/apikey （推荐，有免费额度）
- OpenAI API Key: https://platform.openai.com/api-keys

#### 2.2 业务方向配置

编辑 `config/business_directions.yaml`，配置你关注的业务方向和关键词：

```yaml
business_directions:
  cultural_atmosphere:
    name: "文化氛围类"
    keywords_include:
      - "文化"
      - "氛围"
      - "墙"
      - "宣传"
    location_required: true
    location_priority:
      province: "辽宁省"
      city: "大连市"
```

#### 2.3 通知配置

编辑 `config/notifications.yaml`，配置通知渠道：

```yaml
wechat_work:
  enabled: true
  webhook_url: "${WECHAT_WORK_WEBHOOK}"  # 从环境变量读取
```

### 3. 运行

#### 单次运行（测试）:
```bash
python main.py --mode once
```

#### 定时任务模式:
```bash
python main.py --mode schedule
```

定时任务默认在以下时间运行：
- 09:00
- 11:55
- 13:00
- 17:55

#### Web 控制台（推荐）:
```bash
uvicorn web.app:app --reload --host 127.0.0.1 --port 8000
```
访问 http://127.0.0.1:8000 使用完整 Web 界面：

| 页面 | 说明 |
|------|------|
| **控制台** | 一键运行、实时日志、高分项目、快速配置 |
| **项目列表** | 高分项目情报列表 |
| **情报监控台** | 全屏展示最近抓取的招标项目（AI 核心决策信息） |
| **追踪雷达** | 已关注项目集中管理 |
| **配置管理** | 业务方向、公告类型、AI 模型、通知、定时与爬虫、评分权重 |
| **历史报告** | 日报列表与爬取历史 |
| **开发者实验室** | AI 提取狙击手、规则透视镜、爬虫探针、全链路干跑、**数据清理** |

## 📁 项目结构

```
TenderCopilot/
├── main.py                 # 主程序入口
├── requirements.txt        # Python 依赖
├── .env.example           # 环境变量模板
├── .env                   # 环境变量（不上传）
│
├── config/                 # 配置文件
│   ├── settings.yaml      # 主配置（爬虫、调度、数据库、日志等）
│   ├── business_directions.yaml  # 业务方向和关键词
│   ├── notifications.yaml       # 通知配置
│   └── scoring_config.yaml      # 评分权重与自定义规则（可 Web 编辑）
│
├── src/                    # 核心业务逻辑
│   ├── config/            # 配置管理（ConfigManager、YAML 工具）
│   ├── spider/            # 爬虫模块
│   ├── filter/            # 筛选模块
│   ├── analyzer/          # AI 分析模块
│   ├── reporter/          # 报告生成模块
│   ├── notifier/          # 通知模块
│   ├── scheduler/         # 定时任务模块
│   ├── database/          # 数据库模块 (SQLite)
│   │   └── storage.py    # 存储、get_table_counts、clear_business_data
│   └── utils/             # 工具函数
│
├── web/                    # Web 界面（FastAPI + HTMX + Alpine.js + Tailwind）
│   ├── app.py             # 应用入口
│   ├── api/               # API 路由
│   │   ├── config.py      # 配置读写、评分权重 (GET/POST /api/config/scoring)
│   │   ├── system.py      # 系统级：数据统计、清空业务数据
│   │   ├── lab.py         # 实验室：AI 提取、规则测试、爬虫探针、干跑
│   │   ├── intel.py       # 情报监控、项目关注
│   │   ├── radar.py       # 追踪雷达
│   │   ├── run.py         # 一键运行
│   │   ├── scheduler.py   # 定时任务状态
│   │   ├── stats.py       # 决策大屏数据
│   │   ├── history.py     # 爬取历史
│   │   ├── logs.py        # 日志
│   │   └── reports.py     # 报告
│   ├── templates/         # Jinja2 模板 (settings, lab, dashboard, intel, radar...)
│   └── static/            # 静态资源
│
├── tests/                  # 测试文件
├── docs/                   # 项目文档
│   ├── archive/           # 归档的过程性文档
│   ├── TESTING_GUIDE.md   # 测试指南
│   └── REFACTOR_ANALYSIS.md  # 重构分析参考
│
├── tools/                  # 开发/运维工具
│   ├── find_api_endpoint.py
│   ├── test_api_endpoints.py
│   └── verify_codes.py
│
├── prototype/              # 原型测试代码（开发参考）
├── data/                   # 数据目录（不上传）
│   ├── history.db         # SQLite 数据库
│   ├── reports/           # 生成的报告
│   └── attachments/       # 下载的附件
│
└── logs/                   # 日志文件（不上传）
```

## 🔧 高级配置

### 配置管理（Web 端推荐）

通过 **配置管理** 页面可在线编辑：

- **业务方向**：关键词、地域、权重
- **公告类型**：保留/排除类型
- **AI 模型**：OpenAI / Gemini / 自定义接口
- **通知**：企业微信、邮件
- **定时与爬虫**：执行时间、时区（固定 Asia/Shanghai）、超时、入库分数线、最大抓取数
- **评分权重**：基础权重滑块、自定义评分规则（HTMX 提交）

### 爬虫与评分（YAML 或 Web）

```yaml
spider:
  max_fetch_details: 50   # 单次最大详情抓取数，建议 50 防封 IP

scoring:
  min_total_score: 60     # 自动入库分数线，低于此分不推送不入库
```

### 数据清理

正式上线前可清空测试脏数据：进入 **开发者实验室** → **🧹 数据清理 (Data Cleanup)**，一键清空 `announcements`、`filtered_projects`、`analysis_results`、`interested_projects`。抓取规则和评分权重配置**不会被删除**。

## 📊 工作流程

```
1. 爬取公告列表（使用筛选器）
   ↓
2. 获取公告详情
   ↓
3. 关键词匹配
   ↓
4. 地域筛选
   ↓
5. AI 分析提取信息
   ↓
6. 可行性评分
   ↓
7. 生成报告
   ↓
8. 推送通知
```

## 🔒 安全说明

- ⚠️ **不要将 `.env` 文件上传到 Git**（已在 .gitignore 中配置）
- ⚠️ **不要在配置文件中硬编码敏感信息**
- ✅ 所有敏感配置通过环境变量管理
- ✅ `data/` 和 `logs/` 目录不会被上传
- ⚠️ **数据清理**（开发者实验室）会永久删除业务数据，操作前有确认弹窗

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 📮 联系方式

如有问题或建议，请提交 Issue。

---

**Made with ❤️ for efficient bidding monitoring**
