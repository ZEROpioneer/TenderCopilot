"""报告生成器"""

from datetime import datetime
from pathlib import Path
from loguru import logger


class MarkdownReporter:
    """Markdown 报告生成器"""
    
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
        
        # 页脚
        report.append(f"\n---\n\n*本报告由 TenderCopilot 自动生成 | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
        
        content = "\n".join(report)
        
        # 保存报告
        self._save_report(content)
        
        logger.success("✅ 日报生成完成")
        return content
    
    def _format_project(self, index, project, detailed=True):
        """格式化单个项目"""
        ann = project['announcement']
        feas = project['feasibility']
        direction = project['matched_directions'][0]
        
        lines = []
        lines.append(f"### {index}. {ann['title']}\n")
        lines.append(f"**项目编号**: {ann.get('id', 'N/A')}  ")
        lines.append(f"**业务方向**: {direction['name']}  ")
        lines.append(f"**可行性评分**: {feas['total']} / 100 {self._get_stars(feas['total'])}\n")
        
        # 时间信息突出显示
        time_info = []
        if ann.get('publish_date') or ann.get('pub_date'):
            publish_date = ann.get('publish_date') or ann.get('pub_date')
            time_info.append(f"📅 发布: {publish_date}")
        if ann.get('deadline'):
            time_info.append(f"⏰ 截止: {ann['deadline']}")
        
        if time_info:
            lines.append(f"**⏱️ 时间**: {' | '.join(time_info)}  ")
        
        # 如果有时间评分详情，显示评价
        if feas.get('time_score_details'):
            details = feas['time_score_details']
            time_details = []
            if details.get('freshness'):
                time_details.append(f"新鲜度: {details['freshness']}")
            if details.get('deadline'):
                time_details.append(f"截止: {details['deadline']}")
            if time_details:
                lines.append(f"  - {' | '.join(time_details)}  ")
        
        lines.append("")
        
        if detailed and ann.get('url'):
            lines.append(f"**链接**: [查看原始公告]({ann['url']})\n")
        
        lines.append("---\n")
        return "\n".join(lines)
    
    def _get_stars(self, score):
        """评分星级"""
        if score >= 80:
            return "⭐⭐⭐⭐⭐"
        elif score >= 60:
            return "⭐⭐⭐⭐"
        else:
            return "⭐⭐⭐"
    
    def _format_stats(self, stats):
        """格式化统计信息"""
        lines = []
        lines.append("## 📊 今日统计\n")
        lines.append(f"- **爬取公告总数**: {stats.get('total_crawled', 0)}")
        lines.append(f"- **匹配项目数**: {stats.get('total_matched', 0)}")
        lines.append(f"- **高度推荐**: {stats.get('high_priority', 0)}")
        lines.append(f"- **推荐**: {stats.get('medium_priority', 0)}")
        lines.append("")
        return "\n".join(lines)
    
    def _save_report(self, content):
        """保存报告"""
        report_dir = Path('data/reports')
        report_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = report_dir / f"daily_report_{timestamp}.md"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"💾 报告已保存: {filename}")


class HTMLReporter:
    """HTML 报告生成器（简化版）"""
    
    def generate_daily_report(self, filtered_projects, stats):
        """生成 HTML 日报"""
        # 简化实现，复用 Markdown 内容
        markdown_reporter = MarkdownReporter()
        return markdown_reporter.generate_daily_report(filtered_projects, stats)
