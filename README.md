# TenderCopilot - 招投标智能助手

军队采购网招标信息智能爬虫和筛选系统，自动监控、筛选、分析招标公告，推送匹配的项目机会。

## ✨ 功能特性

- 🕷️ **智能爬虫**: 使用筛选器精准爬取相关招标公告
- 🎯 **关键词匹配**: 基于业务方向自动筛选匹配项目
- 📍 **地域筛选**: 优先匹配特定地域的项目
- 🤖 **AI 分析**: 使用 Gemini/OpenAI 提取关键信息
- 📊 **可行性评分**: 自动评估项目可行性
- 📱 **实时通知**: 企业微信/邮件/钉钉多渠道推送
- ⏰ **定时任务**: 每天4次自动监控，增量爬取避免重复
- 📈 **数据管理**: SQLite 数据库存储历史记录

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

## 📁 项目结构

```
TenderCopilot/
├── main.py                 # 主程序入口
├── requirements.txt        # Python 依赖
├── .env.example           # 环境变量模板
├── .env                   # 环境变量（不上传）
│
├── config/                 # 配置文件
│   ├── settings.yaml      # 主配置
│   ├── business_directions.yaml  # 业务方向和关键词
│   ├── search_keywords.yaml      # 搜索关键词
│   ├── filter_settings.yaml      # 筛选配置
│   └── notifications.yaml        # 通知配置
│
├── src/                    # 源代码
│   ├── spider/            # 爬虫模块
│   ├── filter/            # 筛选模块
│   ├── analyzer/          # AI 分析模块
│   ├── reporter/          # 报告生成模块
│   ├── notifier/          # 通知模块
│   ├── scheduler/         # 定时任务模块
│   └── database/          # 数据库模块
│
├── tests/                  # 测试文件
│   ├── test_config.py     # 配置测试
│   ├── test_imports.py    # 导入测试
│   └── test_wechat_webhook.py  # Webhook 测试
│
├── docs/                   # 项目文档
│   ├── IMPLEMENTATION_SUMMARY.md   # 实施总结
│   ├── IMPLEMENTATION_COMPLETE.md  # 实施完成报告
│   ├── TESTING_GUIDE.md           # 测试指南
│   └── API_FIX_SUMMARY.md         # API 修复总结
│
├── tools/                  # 开发工具
│   ├── find_api_endpoint.py      # API 端点查找
│   ├── test_api_endpoints.py     # API 端点测试
│   └── verify_codes.py           # 代码验证
│
├── data/                   # 数据目录（不上传）
│   ├── history.db         # SQLite 数据库
│   ├── reports/           # 生成的报告
│   └── attachments/       # 下载的附件
│
└── logs/                   # 日志文件（不上传）
```

## 🔧 高级配置

### 爬虫配置

编辑 `config/settings.yaml`:

```yaml
spider:
  headless: true          # 无头模式
  max_fetch_details: 50   # 每次最多获取 50 个详情
  request_delay_range:    # 请求延迟（秒）
    - 1
    - 2
```

### 筛选阈值

```yaml
thresholds:
  min_keyword_match_score: 0.25  # 最低关键词匹配分数
  min_feasibility_score: 40      # 最低可行性评分
```

### 数据保留

```yaml
database:
  retention_days: 365    # 数据保留 365 天
  backup_enabled: true   # 启用自动备份
```

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

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 📮 联系方式

如有问题或建议，请提交 Issue。

---

**Made with ❤️ for efficient bidding monitoring**
