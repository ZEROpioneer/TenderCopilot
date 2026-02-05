# TenderCopilot 配置说明

本目录包含 TenderCopilot 系统的所有配置文件。

## 配置文件概览

### 主要配置文件

| 文件名 | 用途 | 必需 |
|--------|------|------|
| `settings.yaml` | 主配置文件（爬虫、数据库、AI、日志等） | ✅ 是 |
| `business_directions.yaml` | 业务方向和关键词配置 | ✅ 是 |
| `notifications.yaml` | 通知渠道配置 | ✅ 是 |
| `.env` | 敏感信息（API Key、Webhook等） | ✅ 是 |

### 废弃文件（已合并到 settings.yaml）

- `search_keywords.yaml.deprecated` - 关键词配置（已废弃）
- `filter_settings.yaml.deprecated` - API筛选配置（已废弃）

## 配置文件详解

### 1. settings.yaml - 主配置

包含系统运行的所有主要参数。

#### 关键配置项

**爬取策略** (`crawl_strategy`)：
```yaml
crawl_strategy:
  use_incremental: true           # 使用增量爬取
  enable_db_dedup: true           # 启用数据库去重
  enable_time_filter: false       # 启用时间过滤（默认关闭）
  initial_hours: 168              # 首次运行爬取最近N小时
  max_pages: null                 # 最多爬取页数（null=不限制）
  max_consecutive_exists: 5       # 连续重复停止阈值
  max_total_items: 300            # 保护性上限
  warn_threshold: 200             # 警告阈值
```

**关键配置项说明**：

- **`max_pages`**: 最多爬取页数
  - **类型**: integer 或 null
  - **默认值**: `null`（不限制）
  - **说明**:
    - `null`: 不限制页数，一直爬到连续重复停止（推荐）
    - `数字`: 硬性限制页数（如 5 表示最多5页）
  - **建议**: 设置为 `null`，让系统自动判断何时停止

- **`max_consecutive_exists`**: 连续重复停止阈值
  - **类型**: integer
  - **默认值**: `5`
  - **说明**: 连续遇到多少条已存在的公告后停止爬取
  - **建议**: 保持 5，这是主要的停止机制

- **`max_total_items`**: 保护性上限
  - **类型**: integer
  - **默认值**: `300`
  - **说明**: 单次爬取最多条数，防止异常情况无限爬取
  - **触发**: 达到此上限会警告并停止
  - **建议**: 300条通常已足够（15页），可根据实际情况调整

- **`warn_threshold`**: 警告阈值
  - **类型**: integer
  - **默认值**: `200`
  - **说明**: 爬取超过此数量时发出警告提醒
  - **作用**: 让用户知道正在爬取大量数据，但不会停止
  - **建议**: 设置为保护上限的 60-70%

- **`enable_time_filter`**: 是否启用时间过滤功能
  - **类型**: boolean
  - **默认值**: `false`（关闭）
  - **说明**:
    - `false`: 只依赖数据库ID去重（推荐，性能更好）
    - `true`: 额外应用时间过滤（可能因列表页时间精度不足导致误判）
  - **建议**: 保持关闭。数据库ID去重已足够有效，时间信息会在评分阶段被充分考虑（发布新鲜度5分 + 截止充足度10分）

**爬虫配置** (`spider`)：
```yaml
spider:
  headless: true                  # 无头模式（生产环境建议true）
  timeout: 30                     # 页面加载超时（秒）
  retry_times: 3                  # 失败重试次数
  max_fetch_details: 50           # 最多获取详情数量
  max_attachment_size: 20         # 附件大小限制（MB）
  
  # 性能优化配置
  wait_ajax_load: 0.5             # AJAX加载等待（秒）
  wait_page_refresh: 1            # 页面刷新等待（秒）
  wait_between_pages: 2           # 翻页间隔（秒）
  max_concurrent_details: 3       # 并发爬取详情页数量
```

**AI 分析配置** (`analyzer`)：
```yaml
analyzer:
  provider: "gemini"              # AI提供商: gemini 或 openai
  api_key: "${GEMINI_API_KEY}"    # 从环境变量读取
  model: "gemini-1.5-flash"       # 模型选择
  max_tokens: 2000
  temperature: 0.3
```

**数据库配置** (`database`)：
```yaml
database:
  type: "sqlite"
  path: "data/history.db"
  retention_days: 365             # 数据保留天数
  backup_enabled: true
```

**评分配置** (`scoring`)：
```yaml
scoring:
  min_total_score: 60             # 最低推送分数
  min_relevance_score: 40         # 最低相关度
  min_deadline_days: 3            # 最少投标准备天数
```

### 2. business_directions.yaml - 业务方向

定义关注的业务方向和关键词。

#### 结构说明

```yaml
business_directions:
  cultural_atmosphere:            # 业务方向ID（唯一标识）
    name: "文化氛围类"            # 显示名称
    keywords_include:             # 必须包含的关键词
      - "文化"
      - "氛围"
      - "墙"
    keywords_exclude:             # 排除关键词
      - "拆除"
      - "维修"
    location_required: true       # 是否要求地域匹配
    location_priority:            # 优先地域
      province: "辽宁省"
      city: "大连市"
    weights:                      # 关键词权重
      核心词: 10
      常规词: 5
```

#### 配置技巧

1. **关键词设置**：
   - 使用核心词：短词优于长词（"文化" vs "文化建设"）
   - 适当的排除词：避免误匹配
   - 不要过多：每个方向 5-15 个关键词即可

2. **地域限制**：
   - `location_required: true` - 强制要求
   - `location_required: false` - 可选加分

3. **权重调整**：
   - 核心关键词：8-10 分
   - 常规关键词：3-5 分
   - 扩展关键词：1-2 分

### 3. notifications.yaml - 通知配置

配置多种通知渠道。

#### 企业微信（推荐）

```yaml
wechat_work:
  enabled: true
  webhook_url: "${WECHAT_WORK_WEBHOOK}"  # 从环境变量读取
  mention_users: []                       # @用户列表
  retry_times: 3
```

获取 Webhook URL：
1. 打开企业微信群聊
2. 群设置 → 群机器人 → 添加机器人
3. 复制 Webhook 地址
4. 添加到 `.env` 文件：`WECHAT_WORK_WEBHOOK=你的地址`

#### 邮件通知

```yaml
email:
  enabled: false                          # 启用后设为 true
  smtp_server: "smtp.example.com"
  smtp_port: 465
  use_ssl: true
  sender: "tender@company.com"
  sender_password: "${EMAIL_PASSWORD}"    # 从环境变量读取
  recipients:
    - "user1@company.com"
```

配置步骤：
1. 获取邮箱 SMTP 信息
2. 设置环境变量：`EMAIL_PASSWORD=你的密码`
3. 修改收件人列表
4. 设置 `enabled: true`

#### 通知规则

```yaml
notification_rules:
  high_priority_instant: true      # 高优先级立即通知
  medium_priority_daily: true      # 中优先级日报通知
  low_priority_skip: true          # 低优先级不通知
  daily_report_time: "18:00"       # 日报发送时间
```

### 4. .env - 环境变量

**不要提交到 Git！** 此文件包含敏感信息。

#### 必需配置

```bash
# AI 分析（二选一）
GEMINI_API_KEY=your_gemini_api_key          # 推荐：免费额度大
# OPENAI_API_KEY=your_openai_api_key        # 可选

# 通知（至少配置一项）
WECHAT_WORK_WEBHOOK=https://qyapi.weixin.qq.com/...
```

#### 可选配置

```bash
# 邮件通知
EMAIL_PASSWORD=your_email_password

# 个人微信（通过 Server酱 等）
WECHAT_PERSONAL_TOKEN=your_token

# 钉钉机器人
DINGTALK_WEBHOOK=your_dingtalk_webhook
DINGTALK_SECRET=your_dingtalk_secret
```

#### 获取 API Key

**Gemini API Key**（推荐）：
1. 访问：https://makersuite.google.com/app/apikey
2. 登录 Google 账号
3. 创建 API Key
4. 免费额度：每分钟 15 次请求

**OpenAI API Key**（可选）：
1. 访问：https://platform.openai.com/api-keys
2. 注册账号
3. 创建 API Key
4. 需要绑定信用卡

## 配置修改指南

### 首次配置步骤

1. **复制环境变量模板**：
   ```bash
   cp .env.example .env
   ```

2. **编辑 `.env`**，填入：
   - AI API Key（必需）
   - 企业微信 Webhook（推荐）

3. **检查 `settings.yaml`**：
   - 确认爬取策略符合需求
   - 调整日志级别（生产环境用 INFO）

4. **配置业务方向** (`business_directions.yaml`)：
   - 根据实际业务调整关键词
   - 设置地域优先级

5. **启用通知渠道** (`notifications.yaml`)：
   - 至少启用一个通知渠道
   - 配置通知规则

### 常见配置调整

#### 提高爬取速度

```yaml
# settings.yaml
spider:
  wait_ajax_load: 0.3              # 减少等待时间
  wait_page_refresh: 0.5
  wait_between_pages: 1
  max_concurrent_details: 5        # 增加并发数
```

#### 增加爬取范围

```yaml
# settings.yaml
crawl_strategy:
  max_pages: 10                    # 增加页数
  max_consecutive_exists: 10       # 增加重复阈值
```

#### 调整评分阈值

```yaml
# settings.yaml
scoring:
  min_total_score: 50              # 降低阈值（更多项目）
  min_relevance_score: 30
```

#### 修改定时任务

```yaml
# settings.yaml
scheduler:
  times:
    - "08:00"                      # 自定义时间
    - "12:00"
    - "16:00"
    - "20:00"
```

## 配置验证

系统启动时会自动验证配置：

- ✅ 检查必需配置项
- ✅ 验证环境变量
- ✅ 检查配置值范围
- ⚠️ 显示警告（如使用废弃配置）

### 手动验证配置

```python
from src.config import ConfigManager

config = ConfigManager()
config.load_all()
config.validate()
print("✅ 配置验证通过")
```

## 配置优先级

配置加载顺序（后者覆盖前者）：

1. 默认值（代码中定义）
2. 配置文件（YAML）
3. 环境变量（`.env`）

## 常见问题

### Q: 修改配置后需要重启吗？
A: 是的，配置在启动时加载，修改后需要重启服务。

### Q: 环境变量未生效？
A: 检查：
1. `.env` 文件是否在项目根目录
2. 文件名是否正确（不是 `.env.example`）
3. 格式是否正确（`KEY=value`，无空格）

### Q: 配置文件语法错误？
A: 使用 YAML 验证器检查：
- 缩进必须使用空格（不要用 Tab）
- 冒号后必须有空格
- 字符串包含特殊字符需要引号

### Q: 找不到 search_keywords.yaml？
A: 这个文件已废弃，关键词现在在 `business_directions.yaml` 中配置。

### Q: API Key 泄露了怎么办？
A: 立即：
1. 删除泄露的 Key
2. 在 AI 服务商平台生成新 Key
3. 更新 `.env` 文件
4. 检查 Git 历史，确保未提交

## 最佳实践

1. **安全性**：
   - ✅ 使用环境变量存储敏感信息
   - ✅ 不要提交 `.env` 到 Git
   - ✅ 定期轮换 API Key

2. **性能**：
   - 根据网络情况调整超时和重试
   - 适当设置并发数（不要过高）
   - 定期清理旧数据

3. **可维护性**：
   - 为配置添加注释
   - 记录修改原因
   - 备份重要配置

4. **测试**：
   - 配置修改后先单次测试
   - 确认无误后再启用定时任务

## 技术支持

遇到配置问题？

1. 查看日志文件：`logs/tendercopilot.log`
2. 运行测试：`python main.py --mode once`
3. 检查配置验证输出

---

**配置版本**: v2.0 (2026-02-05)  
**最后更新**: 配置管理器重构，统一配置结构
