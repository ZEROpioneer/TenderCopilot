---
name: tender-reporter
description: 招标项目分析报告生成。格式化筛选后的项目信息，生成可读性强的报告，包含匹配度、可行性评分、关键信息摘要。当需要生成项目报告、格式化输出时使用。
---

# 招标项目报告生成规范

## 报告类型

### 1. 日报（Daily Report）

每天定时推送，包含当天发现的所有匹配项目。

### 2. 单项目详细报告

针对高评分项目生成详细分析报告。

## 报告格式

### Markdown 格式（推荐）

适用于企业微信、Slack 等支持 Markdown 的通知渠道。

```markdown
# 🎯 招标项目日报 - 2026年02月04日

> 共发现 3 个符合条件的项目

---

## ⭐ 高度推荐项目

### 1. 某部队文化氛围建设项目

**项目编号**: ZB202602040001  
**发布日期**: 2026-02-04  
**业务方向**: 文化氛围类  
**可行性评分**: 85.5 / 100 ⭐⭐⭐⭐⭐

#### 📊 匹配详情

- **关键词匹配**: 文化 ✓、氛围 ✓、宣传 ✓ (匹配度: 75%)
- **地域匹配**: 辽宁省大连市 ✓ (加分项)
- **截止时间**: 2026-02-10 17:00 (剩余 6 天)

#### 💰 项目信息

- **预算限价**: 100万元
- **开标时间**: 2026-02-15 09:30
- **开标地点**: 辽宁省大连市XX区XX路XX号

#### 📋 资格要求

- 具有有效的营业执照
- 具有软件开发或文化设计相关资质
- 近三年有类似项目业绩

#### 📞 联系方式

- **联系人**: 张三
- **电话**: 0411-12345678
- **邮箱**: zhangsan@example.com

#### 📎 附件

- [报名表.docx](data/attachments/xxx.docx)

#### 🔗 链接

[查看原始公告](https://www.plap.mil.cn/xxx)

---

## 推荐项目

### 2. XX数字史馆建设项目

**项目编号**: ZB202602040002  
**发布日期**: 2026-02-04  
**业务方向**: 数字史馆类  
**可行性评分**: 68.0 / 100 ⭐⭐⭐⭐

...

---

## 📊 今日统计

- **爬取公告总数**: 45
- **匹配项目数**: 3
- **高度推荐**: 1
- **推荐**: 2
- **可考虑**: 0

## 🔔 提醒事项

- ⏰ 项目 #1 报名截止时间较近，请尽快准备材料
- 📄 项目 #1 需要提供保密承诺书

---

*本报告由 TenderCopilot 自动生成 | 生成时间: 2026-02-04 14:30:00*
```

### HTML 格式

适用于邮件通知，样式更丰富。

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #1890ff; color: white; padding: 20px; }
        .project { border: 1px solid #ddd; margin: 20px 0; padding: 15px; }
        .score-high { color: #52c41a; font-weight: bold; }
        .score-medium { color: #faad14; font-weight: bold; }
        .info-item { margin: 10px 0; }
        .label { font-weight: bold; color: #666; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 招标项目日报</h1>
        <p>2026年02月04日</p>
    </div>
    
    <div class="project">
        <h2>某部队文化氛围建设项目</h2>
        <div class="info-item">
            <span class="label">可行性评分:</span>
            <span class="score-high">85.5 / 100</span>
        </div>
        <!-- 更多内容 -->
    </div>
</body>
</html>
```

## 报告生成器实现

### 1. Markdown 生成器

```python
from datetime import datetime
from loguru import logger

class MarkdownReporter:
    def generate_daily_report(self, filtered_projects, stats):
        """生成日报"""
        logger.info("📝 正在生成 Markdown 日报...")
        
        # 按评分排序
        projects = sorted(
            filtered_projects,
            key=lambda x: x['feasibility']['total'],
            reverse=True
        )
        
        # 分组
        high_priority = [p for p in projects if p['feasibility']['total'] >= 80]
        medium_priority = [p for p in projects if 60 <= p['feasibility']['total'] < 80]
        low_priority = [p for p in projects if p['feasibility']['total'] < 60]
        
        # 生成报告
        report = []
        report.append(f"# 🎯 招标项目日报 - {datetime.now().strftime('%Y年%m月%d日')}\n")
        report.append(f"> 共发现 {len(projects)} 个符合条件的项目\n")
        report.append("---\n")
        
        # 高度推荐项目
        if high_priority:
            report.append("## ⭐ 高度推荐项目\n")
            for i, project in enumerate(high_priority, 1):
                report.append(self._format_project(i, project, detailed=True))
        
        # 推荐项目
        if medium_priority:
            report.append("## 推荐项目\n")
            for i, project in enumerate(medium_priority, 1):
                report.append(self._format_project(i, project, detailed=False))
        
        # 统计信息
        report.append(self._format_stats(stats))
        
        # 提醒事项
        report.append(self._format_reminders(projects))
        
        # 页脚
        report.append(f"\n---\n\n*本报告由 TenderCopilot 自动生成 | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
        
        return "\n".join(report)
    
    def _format_project(self, index, project, detailed=True):
        """格式化单个项目"""
        ann = project['announcement']
        feas = project['feasibility']
        direction = project['matched_directions'][0]
        
        lines = []
        lines.append(f"### {index}. {ann['title']}\n")
        lines.append(f"**项目编号**: {ann.get('id', 'N/A')}  ")
        lines.append(f"**发布日期**: {ann['pub_date']}  ")
        lines.append(f"**业务方向**: {direction['name']}  ")
        lines.append(f"**可行性评分**: {feas['total']} / 100 {self._get_stars(feas['total'])}\n")
        
        if detailed:
            # 详细信息
            lines.append("#### 📊 匹配详情\n")
            lines.append(f"- **关键词匹配**: {', '.join(direction.get('matched_keywords', []))} (匹配度: {direction['keyword_score']*100:.0f}%)")
            
            if ann.get('location'):
                lines.append(f"- **地域匹配**: {ann['location']} ✓")
            
            if ann.get('deadline'):
                lines.append(f"- **截止时间**: {ann['deadline']}")
            
            # 提取的信息
            if ann.get('extracted_info'):
                info = ann['extracted_info']
                
                lines.append("\n#### 💰 项目信息\n")
                if info.get('max_budget'):
                    lines.append(f"- **预算限价**: {info['max_budget']}")
                
                if info.get('bidding_info'):
                    bid = info['bidding_info']
                    lines.append(f"- **开标时间**: {bid.get('date')} {bid.get('time')}")
                    lines.append(f"- **开标地点**: {bid.get('location')}")
                
                lines.append("\n#### 📋 资格要求\n")
                if info.get('supplier_qualifications'):
                    quals = info['supplier_qualifications'].split('；')
                    for qual in quals:
                        lines.append(f"- {qual}")
                
                lines.append("\n#### 📞 联系方式\n")
                if info.get('contact'):
                    contact = info['contact']
                    if contact.get('name'):
                        lines.append(f"- **联系人**: {contact['name']}")
                    if contact.get('phone'):
                        lines.append(f"- **电话**: {contact['phone']}")
                    if contact.get('email'):
                        lines.append(f"- **邮箱**: {contact['email']}")
            
            # 附件
            if ann.get('attachments'):
                lines.append("\n#### 📎 附件\n")
                for att in ann['attachments']:
                    lines.append(f"- [{att['name']}]({att.get('local_path', att['url'])})")
            
            # 原文链接
            lines.append(f"\n#### 🔗 链接\n")
            lines.append(f"[查看原始公告]({ann['url']})")
        
        lines.append("\n---\n")
        return "\n".join(lines)
    
    def _get_stars(self, score):
        """评分星级"""
        if score >= 80:
            return "⭐⭐⭐⭐⭐"
        elif score >= 60:
            return "⭐⭐⭐⭐"
        elif score >= 40:
            return "⭐⭐⭐"
        else:
            return "⭐⭐"
    
    def _format_stats(self, stats):
        """格式化统计信息"""
        lines = []
        lines.append("## 📊 今日统计\n")
        lines.append(f"- **爬取公告总数**: {stats.get('total_crawled', 0)}")
        lines.append(f"- **匹配项目数**: {stats.get('total_matched', 0)}")
        lines.append(f"- **高度推荐**: {stats.get('high_priority', 0)}")
        lines.append(f"- **推荐**: {stats.get('medium_priority', 0)}")
        lines.append(f"- **可考虑**: {stats.get('low_priority', 0)}")
        lines.append("")
        return "\n".join(lines)
    
    def _format_reminders(self, projects):
        """格式化提醒事项"""
        lines = []
        lines.append("## 🔔 提醒事项\n")
        
        # 检查紧急截止
        for project in projects:
            ann = project['announcement']
            if ann.get('deadline'):
                # 计算剩余天数
                # TODO: 实现日期计算逻辑
                lines.append(f"- ⏰ 项目《{ann['title']}》报名截止时间较近，请尽快准备材料")
        
        if len(lines) == 1:
            lines.append("- 暂无特别提醒")
        
        lines.append("")
        return "\n".join(lines)
```

### 2. 报告存储

```python
def save_report(report_content, format='markdown'):
    """保存报告到文件"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if format == 'markdown':
        filename = f"data/reports/daily_report_{timestamp}.md"
    elif format == 'html':
        filename = f"data/reports/daily_report_{timestamp}.html"
    else:
        filename = f"data/reports/daily_report_{timestamp}.txt"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    logger.success(f"✅ 报告已保存: {filename}")
    return filename
```

## 报告推送适配

### 企业微信 Markdown 格式

```python
def format_for_wechat_work(report):
    """适配企业微信 Markdown"""
    # 企业微信支持的 Markdown 语法有限
    # 需要进行格式转换
    
    # 替换不支持的语法
    adapted = report.replace('⭐⭐⭐⭐⭐', '★★★★★')
    adapted = adapted.replace('###', '**')
    
    return adapted
```

### 邮件 HTML 格式

```python
def format_for_email(projects, stats):
    """生成邮件 HTML"""
    html_reporter = HTMLReporter()
    return html_reporter.generate_daily_report(projects, stats)
```

## 使用示例

```python
# 生成并推送报告
def generate_and_send_report(filtered_projects, stats, config):
    """生成报告并推送"""
    # 1. 生成 Markdown 报告
    reporter = MarkdownReporter()
    report = reporter.generate_daily_report(filtered_projects, stats)
    
    # 2. 保存报告
    filepath = save_report(report, format='markdown')
    
    # 3. 推送到企业微信
    if config['notifications']['wechat_work']['enabled']:
        adapted_report = format_for_wechat_work(report)
        wechat_notifier.send(adapted_report)
    
    # 4. 发送邮件
    if config['notifications']['email']['enabled']:
        html_report = format_for_email(filtered_projects, stats)
        email_sender.send(html_report)
    
    logger.success("✅ 报告生成和推送完成")
```

## 配置

从 `config/settings.yaml` 读取：

```yaml
reporter:
  output_format: "markdown"  # markdown, html, json
  save_to_file: true
  output_dir: "data/reports/"
  include_attachments: true
  max_projects_per_report: 50
```
