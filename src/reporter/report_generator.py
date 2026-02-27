"""报告生成器"""

from datetime import datetime
from pathlib import Path
from typing import List, TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from src.schema import TenderItem


class MarkdownReporter:
    """Markdown 报告生成器"""
    
    def generate_daily_report(self, filtered_projects: List["TenderItem"], stats: dict) -> str:
        """生成日报（分层展示）。按 url 或 id 去重，确保同一项目只出现一次。"""
        logger.info("📝 正在生成 Markdown 日报...")
        
        # 兜底去重：按 url 或 id 去重，保留首次出现的项目（评分最高）
        seen = {}
        unique_projects: List["TenderItem"] = []
        for p in filtered_projects:
            key = (p.url or p.project_id or "").strip() or f"__id_{p.project_id}"
            if key in seen:
                logger.debug(f"⏭️ 报告去重跳过: {(p.title or '')[:50]}...")
                continue
            seen[key] = True
            unique_projects.append(p)
        if len(unique_projects) < len(filtered_projects):
            logger.info(f"📋 报告去重: {len(filtered_projects)} → {len(unique_projects)} 条")
        
        # 按综合评分排序
        projects = sorted(
            unique_projects,
            key=lambda x: x.feasibility["total"],
            reverse=True,
        )

        push_threshold = stats.get("push_threshold", 65)
        recommended = [p for p in projects if p.feasibility["total"] >= push_threshold]
        alternatives = [p for p in projects if p.feasibility["total"] < push_threshold]

        excellent = [p for p in recommended if p.feasibility["total"] >= 80]
        good = [p for p in recommended if push_threshold <= p.feasibility["total"] < 80]
        
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
        
        # 第一部分：推荐项目（≥push_threshold分）
        if recommended:
            report.append(f"## 🎯 推荐项目（评分 ≥ {push_threshold}分）\n")
            report.append("> 方向高度匹配，优先关注\n\n")

            if excellent:
                report.append("### ⭐ 优秀项目（≥80分）\n")
                for i, project in enumerate(excellent, 1):
                    report.append(self._format_project(i, project, detailed=True))

            if good:
                report.append(f"### ✅ 良好项目（{push_threshold}-79分）\n")
                for i, project in enumerate(good, 1):
                    report.append(self._format_project(i, project, detailed=True))
        
        # 第二部分：备选项目（<push_threshold分）
        if alternatives:
            report.append(f"## 📌 备选项目（评分 < {push_threshold}分）\n")
            report.append("> 可作备选，建议人工复核\n\n")
            for i, project in enumerate(alternatives, 1):
                report.append(self._format_alternative_project(i, project))
        
        # 统计信息
        report.append(self._format_stats(stats, push_threshold))
        
        # 页脚
        report.append(f"\n---\n\n*本报告由 TenderCopilot 自动生成 | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
        
        content = "\n".join(report)
        logger.success("✅ 日报生成完成")
        return content
    
    def _format_project(self, index: int, item: "TenderItem", detailed: bool = True) -> str:
        """格式化单个项目为微型尽调卡片（企微推送友好）"""
        feas = item.feasibility
        loc = (item.location or "未知").strip()
        title = (item.title or "未知项目").strip()
        pid = item.project_id or ""

        # 标题行：### 1. [大连] 某某采购项目 (2026-xxx)
        header = f"### {index}. [{loc}] {title}"
        if pid:
            header += f" ({pid})"
        lines = [header + "\n"]

        # 预算
        budget = getattr(item, "budget_info", "") or item.budget or ""
        lines.append(f"💰 预算: {budget.strip() or '未公布'}")

        # 摘要
        summary = getattr(item, "project_summary", "") or ""
        lines.append(f"🎯 摘要: {summary.strip() or '未知'}")

        # 资质（一票否决项）
        conf = getattr(item, "confidentiality_req", "") or ""
        lines.append(f"🛑 资质: {conf.strip() or '未知'}")

        # 报名截止
        doc_dl = getattr(item, "doc_deadline", "") or item.deadline or ""
        lines.append(f"⏰ 报名截止: {doc_dl.strip() or '未知'}")

        # 开标时间
        bid_dl = getattr(item, "bid_deadline", "") or ""
        lines.append(f"⏳ 开标时间: {bid_dl.strip() or '未知'}")

        # AI 评分：真实总分来自 feasibility 动态规则引擎
        total_score = feas.get("total")
        if total_score is None:
            total_score = getattr(item, "ai_score", 0) or 0
        score_line = f"🤖 AI评分: {float(total_score):.1f}/100"
        breakdown = feas.get("score_breakdown") or feas.get("score_details") or []
        if breakdown:
            parts = []
            for b in breakdown[:4]:
                rule = (b.get("rule") or b.get("name") or "").strip()
                pts = b.get("points", b.get("score", 0))
                if rule and "总计" not in rule and pts != 0:
                    parts.append(f"{rule} {'+' if pts > 0 else ''}{pts}")
            if parts:
                score_line += f" ({', '.join(parts)})"
        lines.append(score_line)

        # 链接
        if detailed and item.url:
            lines.append(f"🔗 [查看原文]({item.url})")

        lines.append("")
        return "\n".join(lines)
    
    def _format_alternative_project(self, index: int, item: "TenderItem") -> str:
        """格式化备选项目（简化微型卡片，支持人工复核）"""
        return self._format_project(index, item, detailed=True)
    
    def _get_direction_name(self, item: "TenderItem") -> str:
        """从 TenderItem 中获取业务方向名称"""
        direction_id = item.matched_direction_id
        match_results = item.match_results or {}
        
        if direction_id and direction_id in match_results:
            return match_results[direction_id].get('name', direction_id)
        
        if match_results:
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
    
    def _format_stats(self, stats, push_threshold: int = 65):
        """格式化统计信息"""
        lines = []
        lines.append("## 📊 今日统计\n")
        lines.append(f"- **爬取公告总数**: {stats.get('total_crawled', 0)}")
        lines.append(f"- **初筛匹配数**: {stats.get('total_matched', 0)}")
        lines.append(f"- **推荐项目**: {stats.get('recommended', 0)} 个（≥{push_threshold}分）")
        if stats.get('excellent', 0) > 0:
            lines.append(f"  - 优秀项目: {stats.get('excellent', 0)} 个（≥80分）")
        if stats.get('good', 0) > 0:
            lines.append(f"  - 良好项目: {stats.get('good', 0)} 个（{push_threshold}-79分）")
        if stats.get('alternatives', 0) > 0:
            lines.append(f"- **备选项目**: {stats.get('alternatives', 0)} 个（<{push_threshold}分，可人工复核）")
        lines.append("")
        return "\n".join(lines)
    
    def _save_report(self, content, earliest_str: str = "", latest_str: str = ""):
        """保存报告到本地 .md 文件。可选插入精确时间区间（仅本地，不推送企微）。"""
        report_dir = Path('data/reports')
        report_dir.mkdir(parents=True, exist_ok=True)

        # 在统计数据下方插入时间区间（仅写入本地 .md，不推送企微）
        if earliest_str and latest_str:
            date_range_line = f"\n> 📅 **本次抓取数据区间**: {earliest_str} 至 {latest_str}\n"
            if "\n---\n" in content:
                parts = content.split("\n---\n", 1)
                content = parts[0] + date_range_line + "\n---\n" + (parts[1] if len(parts) > 1 else "")
            else:
                content = content + date_range_line

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = report_dir / f"daily_report_{timestamp}.md"

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"💾 报告已保存: {filename}")
