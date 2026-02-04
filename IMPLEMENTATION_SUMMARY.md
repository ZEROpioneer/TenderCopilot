# 招标筛选系统优化改造 - 实施总结

> **文档更新**: 2026-02-04  
> **状态**: 待实施（Plan模式已确认）  
> **详细计划**: `.cursor/plans/招标筛选系统优化改造_74ccbd2b.plan.md`

## 🎯 核心目标

将系统从"广泛爬取+严格筛选"改为"精准搜索+深度分析+增量爬取"模式，适配每天4次高频爬取场景。

---

## 📋 关键决策确认

### 1. 爬取策略（针对每天4次）
- **增量爬取**: 从上次爬取时间到现在的所有新公告
- **时间窗口**: 动态计算（上次爬取时间 → 当前时间）
  
  **重要示例**：
  ```
  场景1：正常间隔
  - 上次爬取: 03:00
  - 当前时间: 09:00
  - 爬取范围: 03:00 - 09:00 的所有公告（6小时）
  
  场景2：跨天或异常间隔
  - 上次爬取: 昨天 21:00
  - 当前时间: 今天 09:00
  - 爬取范围: 21:00 - 09:00 的所有公告（12小时）
  ✅ 不会遗漏中间的公告
  ```

- **数据库去重**: 跳过已存在的公告ID（防止重复）
- **完整爬取**: 只要在时间范围内且符合关键词，就全部爬取（不设智能停止）

### 2. 地域限制策略（重要）
- **文化氛围类**: 
  - ✅ 必须是辽宁省（硬性过滤）
  - ✅ 大连市项目优先推送（高权重 +5分）
- **其他三类**（数字史馆、VR仿真、院线电影）:
  - ✅ 全国范围不限制（不过滤）
  - ✅ 靠近辽宁省低权重加分（影响不大）：
    - 辽宁省：+3分
    - 东北（吉林、黑龙江）：+2分
    - 华北（河北、内蒙古）：+1分
    - 其他地区：0分（不减分）

### 3. 搜索方式
- 逐个关键词搜索（使用网站内置搜索框）
- 从配置文件读取关键词列表
- 完整爬取：在时间范围内且符合关键词的全部爬取
- 保护性上限：每关键词最多200条（防止异常情况）

### 4. 深度分析
- ✅ 内容相关度深度分析（非简单关键词匹配）
- ✅ AI提取结构化信息（只对初筛通过的项目）
- ✅ 下载并分析附件（PDF/Word文本提取）

### 5. 二次过滤标准
- 供应商资格要求是否符合
- 项目预算无限制（所有范围都接受）
- 投标准备时间 >= 3天
- 综合评分 >= 60分

### 6. 通知策略
- 只推送评分 >= 60分的高质量项目
- 减少低质量项目的误报

---

## 🔧 实施任务清单

### ✅ 已完成
- 无（待开始实施）

### 🔄 待实施（共9项）

1. **search_spider**: 改造爬虫模块，添加关键词搜索和智能翻页
2. **adjust_location**: 调整地域限制（文化类保留，其他移除）
3. **incremental_crawl**: 实现增量爬取（时间窗口+数据库去重）
4. **content_analyzer**: 新增内容深度分析器
5. **attachment_enhanced**: 增强附件处理（PDF/Word提取）
6. **scoring_refactor**: 重构评分系统（多维度+分类策略）
7. **main_flow**: 改造主流程（整合所有新功能）
8. **config_update**: 更新配置文件
9. **test_validate**: 完整测试和参数调优

---

## 📂 涉及的文件

### 需要修改的文件
```
src/spider/plap_spider.py           # 添加 search_by_keyword()
src/spider/crawl_tracker.py         # 增强时间窗口计算
src/filter/deduplicator.py          # 添加快速去重
src/filter/location_matcher.py      # 按类别区分地域策略
src/analyzer/feasibility_scorer.py  # 重构多维度评分
src/spider/attachment_handler.py    # 添加 PDF/Word 提取
main.py                             # 改造主流程
config/business_directions.yaml     # 更新地域配置
config/settings.yaml                # 新增深度分析配置
```

### 需要新建的文件
```
config/search_keywords.yaml         # 搜索关键词和爬取策略
src/analyzer/content_analyzer.py   # 内容相关度分析器
src/analyzer/attachment_analyzer.py # 附件内容分析器
```

---

## 🔄 新工作流程

```
[启动] → 计算时间窗口（上次爬取时间 → 当前时间）
  ↓
准备关键词列表（文化/史馆/VR/电影）
  ↓
逐个关键词搜索
  ├─ 访问网站搜索框
  ├─ 解析搜索结果
  ├─ 检查时间窗口（在窗口内 + 符合关键词 → 全部爬取）
  └─ 数据库快速去重（已存在则跳过）
  ↓
关键词初步匹配验证
  ├─ 文化类 → 检查辽宁省 → 不符合则过滤
  └─ 其他类 → 直接通过
  ↓
深度分析（只分析通过初筛的项目）
  ├─ 获取详情页内容
  ├─ 内容相关度分析（25分）
  ├─ AI结构化提取（20分）
  └─ 下载并分析附件（15分）
  ↓
综合评分（0-100分）
  ├─ 关键词匹配: 20分
  ├─ 内容相关度: 25分
  ├─ AI提取完整性: 20分
  ├─ 附件质量: 15分
  ├─ 地域评分: 10分（文化类大连+5分）
  └─ 时间充足度: 10分
  ↓
二次过滤
  ├─ 资格要求检查
  ├─ 投标时间 >= 3天
  └─ 总分 >= 60分
  ↓
[推送] 高质量项目通知
```

---

## ⚙️ 配置要点

### config/business_directions.yaml
```yaml
cultural_atmosphere:
  location_required: true        # 仅文化类为 true
  location_priority:
    province: "辽宁省"
    city: "大连市"

digital_hall:
  location_required: false       # 其他类别为 false

simulation_training:
  location_required: false

cinema_service:
  location_required: false
```

### config/search_keywords.yaml（新建）
```yaml
crawl_strategy:
  enable_db_dedup: true          # 启用数据库去重
  use_incremental: true          # 使用增量模式（从上次爬取时间开始）
  max_per_keyword: 200           # 每关键词最多爬取数（保护性上限）
  # 不使用智能停止，只要符合条件就全部爬取
```

### config/settings.yaml（新增）
```yaml
deep_analysis:
  enabled: true
  analyze_content: true          # 内容分析
  analyze_attachments: true      # 附件分析
  extract_ai: true               # AI提取

scoring:
  min_total_score: 60            # 推送最低分
  min_deadline_days: 3           # 最少准备天数
```

---

## 💰 性价比优化

### API费用控制
- 只对通过初筛的项目进行AI分析
- 预期每次爬取: 20-50条 → 初筛5-15条 → AI分析5-15次
- **节省 60-70% API费用**

### 时间成本优化
- 增量爬取：从上次爬取到现在的新公告（每天4次，平均间隔6小时）
- 数据库去重：快速跳过已爬取
- 完整爬取：确保不遗漏任何符合条件的公告
- **每次运行时间: 根据新公告数量动态调整（通常1-3分钟）**

### 质量保障
- 多维度评分确保相关度
- 只推送 >= 60分的项目
- 减少误报，提升用户体验

---

## 📦 新增依赖

```bash
pip install pdfplumber       # PDF文本提取
pip install python-docx      # Word文本提取（已有）
pip install jieba            # 中文分词（可选，用于语义分析）
```

---

## ⚠️ 风险提示

1. **搜索功能依赖**: 需确认网站有可用的搜索框
2. **首次测试**: 建议先手动测试搜索功能是否正常
3. **附件存储**: 需要定期清理下载的附件文件
4. **时间调整**: 首次运行可能需要调整时间窗口参数

---

## 🚀 快速开始下一个会话

### 第一步：阅读关键文件
```python
# 1. 阅读详细计划
".cursor/plans/招标筛选系统优化改造_74ccbd2b.plan.md"

# 2. 阅读当前实现
"src/spider/plap_spider.py"      # 当前爬虫实现
"main.py"                        # 当前主流程
"config/business_directions.yaml" # 当前业务配置
```

### 第二步：按任务顺序实施
1. 先实现 `search_spider` + `incremental_crawl`（爬虫基础）
2. 再调整 `adjust_location`（地域策略）
3. 然后新增 `content_analyzer` + `attachment_enhanced`（深度分析）
4. 接着重构 `scoring_refactor`（评分系统）
5. 最后改造 `main_flow` + `config_update`（主流程整合）
6. 完成后 `test_validate`（完整测试）

### 第三步：测试验证
```bash
# 测试单个关键词搜索
python main.py --test-search --keyword "文化墙"

# 测试增量爬取
python main.py --mode incremental

# 完整流程测试
python main.py
```

---

## 📝 会话上下文

### 用户关键需求（已确认）
1. 每天爬取4次，需要增量机制避免重复
2. 只有文化氛围类限制辽宁省（大连优先）
3. 其他类别全国不限
4. 性价比优化：平衡质量和效率
5. 只推送高质量项目（>=60分）

### 用户选择的策略（通过问答确认）
- 爬取策略: 增量爬取
- 去重处理: 数据库检查 + 时间窗口
- 文化类地域: 辽宁省都要，大连市优先推送
- 其他类地域: 完全不限制
- 性价比侧重: 质量 + 平衡

---

## 📞 相关文件索引

- **详细计划**: `.cursor/plans/招标筛选系统优化改造_74ccbd2b.plan.md`
- **项目README**: `README.md`
- **历史对话**: `C:\Users\zhangjiye\.cursor\projects\d-Projects-TenderCopilot\agent-transcripts\d439b307-01c8-488e-abf9-0617ab4980e6.txt`
- **API修复总结**: `API_FIX_SUMMARY.md`（前一个问题的解决方案）

---

**下一步**: 切换到 Agent 模式开始实施，按照任务清单逐步完成改造。
