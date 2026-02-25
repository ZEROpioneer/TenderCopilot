"""报告生成器"""

from datetime import datetime
from pathlib import Path
from loguru import logger


class MarkdownReporter:
    """Markdown 报告生成器"""
    
    def generate_daily_report(self, filtered_projects, stats):
        """生成日报（分层展示）。按 url 或 id 去重，确保同一项目只出现一次。"""
        logger.info("📝 正在生成 Markdown 日报...")
        
        # 兜底去重：按 url 或 id 去重，保留首次出现的项目（评分最高）
        seen = {}
        unique_projects = []
        for p in filtered_projects:
            ann = p.get("announcement") or {}
            key = (ann.get("url") or ann.get("id") or "").strip() or f"__id_{ann.get('id', '')}"
            if key in seen:
                logger.debug(f"⏭️ 报告去重跳过: {ann.get('title', '')[:50]}...")
                continue
            seen[key] = True
            unique_projects.append(p)
        if len(unique_projects) < len(filtered_projects):
            logger.info(f"📋 报告去重: {len(filtered_projects)} → {len(unique_projects)} 条")
        
        # 按综合评分排序
        projects = sorted(
            unique_projects,
            key=lambda x: x["feasibility"]["total"],
            reverse=True,
        )
        
        # 分组（根据新的评分心智：方向优先）
        recommended = [p for p in projects if p["feasibility"]["total"] >= 65]  # 推荐项目（≥65分）
        alternatives = [p for p in projects if p["feasibility"]["total"] < 65]  # 备选项目（<65分）
        
        # 进一步细分推荐项目
        excellent = [p for p in recommended if p["feasibility"]["total"] >= 80]  # 优秀（≥80分）
        good = [p for p in recommended if 65 <= p["feasibility"]["total"] < 80]  # 良好（65-79分）
        
        # 生成报告
        report = []
        report.append(f"# 🎯 招标项目日报 - {datetime.now().strftime('%Y年%m月%d日')}\n")
        
        # 报告摘要
        summary_parts = []
        if recommended:
            summary_parts.append(f"**{len(recommended)}个推荐项目**")
        if alternatives:
            summary_parts.append(f"{len(alternatives)}个备选项目")
        report.append(f"> {' | '.join(summary_parts) if summary_parts else '暂无符合项目'}\n")
        report.append("---\n")
        
        # 第一部分：推荐项目（≥65分）
        if recommended:
            report.append("## 🎯 推荐项目（评分 ≥ 65分）\n")
            report.append("> 方向高度匹配，优先关注\n\n")
            
            # 优秀项目（≥80分）
            if excellent:
                report.append("### ⭐ 优秀项目（≥80分）\n")
                for i, project in enumerate(excellent, 1):
                    report.append(self._format_project(i, project, detailed=True))
            
            # 良好项目（65-79分）
            if good:
                report.append("### ✅ 良好项目（65-79分）\n")
                for i, project in enumerate(good, 1):
                    report.append(self._format_project(i, project, detailed=True))
        
        # 第二部分：备选项目（<65分）
        if alternatives:
            report.append("## 📌 备选项目（评分 < 65分）\n")
            report.append("> 可作备选，建议人工复核\n\n")
            for i, project in enumerate(alternatives, 1):
                report.append(self._format_alternative_project(i, project))
        
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
        direction_name = self._get_direction_name(project)
        breakdown = feas.get("breakdown", {})
        
        lines = []
        lines.append(f"### {index}. {ann['title']}\n")
        lines.append(f"**项目编号**: {ann.get('id', 'N/A')}  ")
        lines.append(f"**业务方向**: {direction_name}  ")
        lines.append(f"**可行性评分**: {feas['total']} / 100 {self._get_stars(feas['total'])}\n")
        
        # 关键信息标签：方向匹配 / AI / 附件 / 时间
        tags = []
        direction_score = breakdown.get("direction_match", 0)
        if direction_score >= 45:
            tags.append("方向匹配度：高")
        elif direction_score >= 30:
            tags.append("方向匹配度：中")
        else:
            tags.append("方向匹配度：低")

        ai_ratio = breakdown.get("ai_completeness_ratio", 0)
        if ai_ratio >= 0.8:
            tags.append("AI 信息：完整")
        elif ai_ratio >= 0.4:
            tags.append("AI 信息：一般")
        else:
            tags.append("AI 信息：缺失/较少")

        att_rel = breakdown.get("attachment_relevance", 0)
        if att_rel > 0:
            if att_rel >= 70:
                tags.append("附件质量：高")
            elif att_rel >= 40:
                tags.append("附件质量：中")
            else:
                tags.append("附件质量：低")
        else:
            tags.append("附件：无或未分析")

        if tags:
            lines.append(f"**标签**: {' | '.join(tags)}  ")
        
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
    
    def _format_alternative_project(self, index, project):
        """格式化备选项目（简化信息，支持人工复核）"""
        ann = project['announcement']
        feas = project['feasibility']
        direction_name = self._get_direction_name(project)
        breakdown = feas.get("breakdown", {})
        
        lines = []
        lines.append(f"### {index}. {ann['title']}\n")
        
        # 基本信息（一行显示）
        basic_info = []
        basic_info.append(f"**评分**: {feas['total']}/100")
        basic_info.append(f"**方向**: {direction_name}")
        if ann.get('location'):
            basic_info.append(f"**地域**: {ann['location']}")
        lines.append(f"{' | '.join(basic_info)}  ")
        
        # 关键信息标签（简化版）
        tags = []
        direction_score = breakdown.get("direction_match", 0)
        if direction_score >= 45:
            tags.append("方向：高匹配")
        elif direction_score >= 30:
            tags.append("方向：中等")
        else:
            tags.append("方向：一般")

        ai_ratio = breakdown.get("ai_completeness_ratio", 0)
        if ai_ratio >= 0.8:
            tags.append("AI：完整")
        elif ai_ratio >= 0.4:
            tags.append("AI：一般")
        else:
            tags.append("AI：缺失")

        if tags:
            lines.append(f"**标签**: {' | '.join(tags)}  ")
        
        # 时间信息（关键）
        time_info = []
        if ann.get('publish_date') or ann.get('pub_date'):
            publish_date = ann.get('publish_date') or ann.get('pub_date')
            time_info.append(f"发布: {publish_date}")
        if ann.get('deadline'):
            time_info.append(f"截止: {ann['deadline']}")
        if time_info:
            lines.append(f"**时间**: {' | '.join(time_info)}  ")
        
        # 链接（支持人工复核）
        if ann.get('url'):
            lines.append(f"**链接**: [查看详情]({ann['url']})  ")
        
        lines.append("")
        return "\n".join(lines)
    
    def _get_direction_name(self, project):
        """从项目结构中安全获取业务方向名称
        
        兼容两种结构：
        - 旧结构：project['matched_directions'] 为方向列表
        - 新结构：使用 matched_direction_id + match_results
        """
        # 兼容旧字段
        if 'matched_directions' in project and project['matched_directions']:
            direction = project['matched_directions'][0]
            return direction.get('name', '未知方向')
        
        # 新结构：根据 matched_direction_id 和 match_results 推断
        direction_id = project.get('matched_direction_id')
        match_results = project.get('match_results') or {}
        
        if direction_id and direction_id in match_results:
            return match_results[direction_id].get('name', direction_id)
        
        # 兜底：取任意一个匹配方向名称
        if isinstance(match_results, dict) and match_results:
            any_direction = next(iter(match_results.values()))
            return any_direction.get('name', '未知方向')
        
        return '未知方向'
    
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
        lines.append(f"- **初筛匹配数**: {stats.get('total_matched', 0)}")
        lines.append(f"- **推荐项目**: {stats.get('recommended', 0)} 个（≥65分）")
        if stats.get('excellent', 0) > 0:
            lines.append(f"  - 优秀项目: {stats.get('excellent', 0)} 个（≥80分）")
        if stats.get('good', 0) > 0:
            lines.append(f"  - 良好项目: {stats.get('good', 0)} 个（65-79分）")
        if stats.get('alternatives', 0) > 0:
            lines.append(f"- **备选项目**: {stats.get('alternatives', 0)} 个（<65分，可人工复核）")
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
