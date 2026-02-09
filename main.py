"""TenderCopilot - 招投标智能助手 主程序"""

import sys
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入模块
from src.config import ConfigManager
from src.database.storage import DatabaseManager
from src.spider.plap_spider import PLAPSpider
from src.spider.attachment_handler import AttachmentHandler
from src.spider.crawl_tracker import CrawlTracker
from src.filter.keyword_matcher import KeywordMatcher
from src.filter.location_matcher import LocationMatcher
from src.filter.deduplicator import Deduplicator
from src.filter.notice_type_filter import NoticeTypeFilter
from src.filter.manager import FilterManager
from src.analyzer.info_extractor import InfoExtractor
from src.analyzer.feasibility_scorer import FeasibilityScorer
from src.reporter.report_generator import MarkdownReporter
from src.notifier.notification_manager import NotificationManager
from src.scheduler.task_scheduler import TaskScheduler


class TenderCopilot:
    """招投标智能助手"""
    
    def __init__(self):
        self.config = self.load_config()
        self.setup_logger()
        
        # 初始化组件
        self.db = DatabaseManager(self.config['database']['path'])
        self.crawl_tracker = CrawlTracker(self.db, self.config)
        self.api_client = None
        self.spider = None
        self.attachment_handler = None
        self.keyword_matcher = None
        self.location_matcher = None
        self.deduplicator = None
        self.analyzer = None
        self.scorer = None
        self.reporter = None
        self.notification_manager = None
        
        logger.info("🎯 TenderCopilot 初始化完成")
    
    def load_config(self):
        """加载配置文件（使用新的配置管理器）"""
        try:
            config_manager = ConfigManager()
            config_manager.load_all()
            logger.success("✅ 配置加载成功")
            return config_manager
        except Exception as e:
            logger.error(f"❌ 配置加载失败: {e}")
            raise
    
    def setup_logger(self):
        """配置日志（控制台精简输出 + 详细日志文件）"""
        from datetime import datetime
        from pathlib import Path

        log_config = self.config['logging']

        # 兼容旧配置：如果未配置 console_level / file_level，则回退到 level
        console_level = log_config.get('console_level', log_config.get('level', 'INFO'))
        file_level = log_config.get('file_level', log_config.get('level', 'INFO'))
        detail_dir = log_config.get('detail_dir')

        # 生成本次运行的详细日志文件路径
        if detail_dir:
            detail_path = Path(detail_dir)
            detail_path.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file_path = detail_path / f"run_{timestamp}.log"
        else:
            # 兼容旧配置：仍然使用 log_file
            log_file_path = Path(log_config['log_file'])
            log_file_path.parent.mkdir(parents=True, exist_ok=True)

        # 移除默认处理器
        logger.remove()

        # 控制台输出：只展示关键步骤和统计信息
        logger.add(
            sys.stdout,
            format=log_config['format'],
            level=console_level,
        )

        # 详细文件日志：记录完整 DEBUG 级别信息
        logger.add(
            str(log_file_path),
            format=log_config['format'],
            level=file_level,
            rotation=log_config['rotation'],
            retention=log_config['retention'],
            compression=log_config['compression'],
            encoding='utf-8',
        )
    
    def init_components(self):
        """初始化所有组件"""
        logger.info("🔧 正在初始化组件...")
        
        # 初始化 API 客户端（优先使用）
        from src.spider.api_client import PLAPApiClient
        self.api_client = PLAPApiClient(self.config)
        
        self.spider = PLAPSpider(self.config)
        self.attachment_handler = AttachmentHandler(self.config)
        self.keyword_matcher = KeywordMatcher(self.config)
        self.location_matcher = LocationMatcher()
        self.notice_type_filter = NoticeTypeFilter(self.config)
        self.deduplicator = Deduplicator(self.db)
        self.filter_manager = FilterManager(
            self.config,
            self.db,
            self.keyword_matcher,
            self.location_matcher,
            self.notice_type_filter,
            self.deduplicator,
        )
        
        # 初始化 AI 信息提取器（内部根据 provider / 配置自行决定是否可用）
        self.analyzer = InfoExtractor(self.config)
        
        # 新增分析器
        from src.analyzer.content_analyzer import ContentAnalyzer
        from src.analyzer.attachment_analyzer import AttachmentAnalyzer
        
        self.content_analyzer = ContentAnalyzer(self.config)
        self.attachment_analyzer = AttachmentAnalyzer(self.config)
        
        self.scorer = FeasibilityScorer(self.config)
        self.reporter = MarkdownReporter()
        self.notification_manager = NotificationManager(self.config)
        
        logger.success("✅ 组件初始化完成")
    
    def run_pipeline(self):
        """执行完整流程（列表页增量爬取 + 本地关键词筛选）"""
        logger.info("=" * 60)
        logger.info("🚀 TenderCopilot 开始运行（列表页增量爬取 + 本地筛选）")
        logger.info("=" * 60)
        
        try:
            # 初始化组件
            if not self.spider:
                self.init_components()
            
            # 步骤1: 获取上次爬取时间
            logger.info("📅 步骤 1/7: 计算增量爬取时间窗口")
            from datetime import datetime
            last_crawl_time = self.crawl_tracker.get_last_crawl_time()
            logger.info(f"  上次爬取: {last_crawl_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"  本次爬取: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"  时间间隔: {((datetime.now() - last_crawl_time).total_seconds() / 3600):.1f} 小时")
            
            # 步骤2: 准备搜索关键词（用于后续筛选）
            logger.info("🔑 步骤 2/7: 准备搜索关键词")
            keywords = self._get_search_keywords()
            logger.info(f"  共 {len(keywords)} 个关键词: {', '.join(keywords[:5])}...")
            
            # 步骤3: 多页增量爬取（已验证的稳定方案）
            logger.info("📥 步骤 3/7: 多页增量爬取")
            logger.info(f"  📅 时间范围: {last_crawl_time.strftime('%Y-%m-%d %H:%M')} → 现在")
            
            # ✅ 使用改进的多页爬取（带去重和智能停止）
            try:
                logger.info("  🕷️ 正在爬取采购公告列表页（多页模式）...")
                
                # 传递数据库管理器用于去重
                crawl_config = self.config.get('crawl_strategy', {})
                max_pages = crawl_config.get('max_pages')  # None = 不限制页数
                max_consecutive = crawl_config.get('max_consecutive_exists', 5)  # 连续5条重复停止
                max_total_items = crawl_config.get('max_total_items', 300)  # 保护性上限
                warn_threshold = crawl_config.get('warn_threshold', 200)  # 警告阈值
                
                all_announcements = self.spider.fetch_announcements(
                    max_pages=max_pages,
                    db_manager=self.db,
                    max_consecutive_exists=max_consecutive,
                    max_total_items=max_total_items,
                    warn_threshold=warn_threshold
                )
                
                logger.info(f"  ✅ 爬取成功，共获取 {len(all_announcements)} 条新公告")
                
                # 可选的时间过滤
                if all_announcements and self.config.get('crawl_strategy.enable_time_filter', False):
                    logger.info(f"  ⏱️ 应用时间过滤（可选功能，保留 {last_crawl_time.strftime('%Y-%m-%d %H:%M')} 之后的）")
                    original_count = len(all_announcements)
                    all_announcements = [
                        ann for ann in all_announcements
                        if self._is_new_announcement(ann, last_crawl_time)
                    ]
                    logger.info(f"  ✅ 时间过滤: {original_count} → {len(all_announcements)} 条")
                elif all_announcements:
                    logger.info(f"  ⏭️ 跳过时间过滤（依赖数据库ID去重）")
                
            except Exception as e:
                logger.error(f"❌ 列表页爬取失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                all_announcements = []
            
            # 记录爬取历史并更新时间
            self.crawl_tracker.record_crawl(len(all_announcements), success=True)
            self.crawl_tracker.update_last_crawl_time()
            
            if not all_announcements:
                logger.warning("⚠️ 未爬取到任何新公告，流程结束")
                return
            
            # 步骤4: 本地关键词筛选+地域检查
            logger.info("🔍 步骤 4/7: 本地关键词筛选+地域检查")
            logger.info(f"  📋 待筛选: {len(all_announcements)} 条公告")
            logger.info(f"  🔑 关键词: {', '.join(keywords[:3])}... 等{len(keywords)}个")
            filtered = self.filter_announcements(all_announcements)
            logger.info(f"✅ 筛选出 {len(filtered)} 个匹配项目（匹配率: {len(filtered)/len(all_announcements)*100:.1f}%）")
            
            # 步骤5: 深度分析（只分析通过初筛的项目）
            logger.info("🤖 步骤 5/7: 深度分析（内容+AI+附件）")
            self.deep_analyze_projects(filtered)
            
            # 步骤6: 分析结果分层（推荐+备选）
            logger.info("🎯 步骤 6/7: 结果分层（推荐项目 + 备选项目）")
            recommended = [p for p in filtered if p['feasibility']['total'] >= 65]  # 推荐项目（与报告阈值一致）
            alternatives = [p for p in filtered if p['feasibility']['total'] < 65]   # 备选项目
            
            logger.info(f"  ✅ 推荐项目: {len(recommended)} 个（评分≥65分）")
            if len(recommended) > 0:
                excellent = sum(1 for p in recommended if p['feasibility']['total'] >= 80)
                good = len(recommended) - excellent
                if excellent > 0:
                    logger.info(f"     - 优秀: {excellent} 个（≥80分）")
                if good > 0:
                    logger.info(f"     - 良好: {good} 个（65-79分）")
            
            if alternatives:
                logger.info(f"  📌 备选项目: {len(alternatives)} 个（评分<65分，可人工复核）")
            
            # 步骤7: 生成报告并推送（包含所有项目）
            logger.info("📝 步骤 7/7: 生成报告并推送通知")
            stats = {
                'total_crawled': len(all_announcements),
                'total_matched': len(filtered),
                'recommended': len(recommended),
                'excellent': sum(1 for p in recommended if p['feasibility']['total'] >= 80),
                'good': sum(1 for p in recommended if 65 <= p['feasibility']['total'] < 80),
                'alternatives': len(alternatives)
            }
            
            # 生成包含所有项目的报告
            report = self.reporter.generate_daily_report(filtered, stats)
            
            # 推送通知（优先通知推荐项目）
            logger.info("📤 推送通知")
            if recommended:
                logger.info(f"   🎯 优先通知 {len(recommended)} 个推荐项目")
            if alternatives:
                logger.info(f"   📌 报告包含 {len(alternatives)} 个备选项目（供人工复核）")
            self.notification_manager.send_report(report, recommended if recommended else filtered)
            
            # 显示统计
            crawl_stats = self.crawl_tracker.get_statistics()
            logger.info("=" * 60)
            logger.info("📊 爬取统计信息")
            logger.info(f"  总爬取次数: {crawl_stats.get('total_crawls', 0)}")
            logger.info(f"  成功率: {crawl_stats.get('success_rate', 'N/A')}")
            logger.info(f"  今日爬取: {crawl_stats.get('today_crawls', 0)} 次")
            logger.info(f"  上次爬取: {crawl_stats.get('last_crawl_time', 'N/A')}")
            logger.info("=" * 60)
            
            logger.success("✅ 流程执行完成")
            
        except Exception as e:
            logger.error(f"❌ 流程执行失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            if self.spider:
                self.spider.close()
    
    def _is_new_announcement(self, announcement, last_crawl_time):
        """判断公告是否是新的（发布时间晚于上次爬取时间）
        
        使用 DateParser 工具类进行日期解析
        
        特别处理：
        - 如果日期只有年月日（时分秒为00:00:00），则只比较日期部分
        - 这样可以避免同一天的公告被错误过滤
        
        Args:
            announcement: 公告字典
            last_crawl_time: 上次爬取时间
            
        Returns:
            bool: 是否是新公告
        """
        try:
            publish_date_str = announcement.get('publish_date', '')
            if not publish_date_str:
                # 如果没有发布时间，保守起见认为是新的
                return True
            
            # 使用工具类解析日期
            from src.utils import DateParser
            from datetime import datetime
            
            publish_date = DateParser.parse(publish_date_str)
            
            if not publish_date:
                # 如果无法解析，保守起见认为是新的
                logger.debug(f"  ⚠️ 无法解析发布时间: {publish_date_str}")
                return True
            
            # 关键修复：如果日期只有年月日（时分秒为00:00:00）
            # 说明列表页没有提供精确时间，只比较日期部分
            if publish_date.time() == datetime.min.time():
                # 只比较日期：同一天或更晚的都认为是新的
                is_new = publish_date.date() >= last_crawl_time.date()
                logger.debug(f"  📅 日期比较: {publish_date.date()} >= {last_crawl_time.date()} = {is_new}")
                return is_new
            else:
                # 有具体时间，正常比较
                is_new = publish_date > last_crawl_time
                logger.debug(f"  ⏰ 时间比较: {publish_date} > {last_crawl_time} = {is_new}")
                return is_new
            
        except Exception as e:
            logger.debug(f"  ⚠️ 判断新公告时出错: {e}")
            return True  # 出错时保守起见认为是新的
    
    def _get_search_keywords(self):
        """获取搜索关键词列表
        
        Returns:
            关键词列表
        """
        keywords = []
        search_keywords_config = self.config.get('search_keywords', {})
        
        # 从配置文件获取所有业务方向的关键词
        for direction_id, direction_keywords in search_keywords_config.items():
            if isinstance(direction_keywords, list):
                keywords.extend(direction_keywords)
        
        # 如果配置为空，使用业务方向的关键词
        if not keywords:
            for direction_id, direction_config in self.config['business_directions'].items():
                keywords.extend(direction_config.get('keywords_include', []))
        
        # 去重
        keywords = list(set(keywords))
        
        return keywords
    
    def filter_announcements(self, announcements):
        """初步筛选公告（双轨制：策略 A 新机会 / 策略 B 智能追踪）"""
        return self.filter_manager.process(announcements)
    
    def _analyze_single_project(self, project_info):
        """分析单个项目（可并发执行）
        
        Args:
            project_info: (index, total, project) 元组
            
        Returns:
            更新后的 project 字典
        """
        i, total, project = project_info
        ann = project['announcement']
        direction_id = project['matched_direction_id']
        direction_config = self.config['business_directions'][direction_id]
        deep_analysis_enabled = self.config.get('deep_analysis', {}).get('enabled', True)
        
        logger.info(f"  📊 [{i}/{total}] 分析: {ann['title'][:40]}...")
        
        try:
            # 1. 获取详情内容
            detail_content = ''
            if not ann.get('content'):
                try:
                    detail = self.spider.fetch_detail(ann['url'])
                    if detail:
                        ann['content'] = detail.get('content', '')
                        ann['attachments'] = detail.get('attachments', [])
                        detail_content = ann['content']
                except Exception as e:
                    logger.warning(f"     ⚠️ 获取详情失败: {e}")
            else:
                detail_content = ann.get('content', '')
            
            # 2. 内容相关度分析
            content_analysis = None
            if deep_analysis_enabled and self.config.get('deep_analysis', {}).get('analyze_content', True):
                try:
                    content_analysis = self.content_analyzer.analyze_relevance(
                        ann,
                        direction_config,
                        detail_content
                    )
                    logger.debug(f"     内容相关度: {content_analysis['score']}/100")
                except Exception as e:
                    logger.warning(f"     ⚠️ 内容分析失败: {e}")
            
            # 3. AI提取结构化信息
            ai_extracted = None
            if self.analyzer and deep_analysis_enabled and self.config.get('deep_analysis', {}).get('extract_ai', True):
                try:
                    content = f"{ann['title']}\n\n{detail_content}"
                    ai_extracted = self.analyzer.extract(content[:12000])
                    logger.debug(f"     AI提取: 完成")
                except Exception as e:
                    logger.warning(f"     ⚠️ AI提取失败: {e}")
            
            # 4. 附件分析
            attachment_analysis = None
            if deep_analysis_enabled and self.config.get('deep_analysis', {}).get('analyze_attachments', True):
                attachments = ann.get('attachments', [])
                if attachments:
                    try:
                        # 下载第一个附件并分析
                        att = attachments[0]
                        filepath = self.attachment_handler.download(att)
                        if filepath:
                            keywords = direction_config.get('keywords_include', [])
                            attachment_analysis = self.attachment_analyzer.analyze(
                                filepath,
                                keywords,
                                direction_config
                            )
                            logger.debug(f"     附件分析: {attachment_analysis['relevance_score']}/100")
                    except Exception as e:
                        logger.warning(f"     ⚠️ 附件分析失败: {e}")
            
            # 5. 综合评分
            feasibility = self.scorer.calculate(
                ann,
                project['match_results'],
                project['location_result'],
                content_analysis=content_analysis,
                ai_extracted=ai_extracted,
                attachment_analysis=attachment_analysis,
                direction_id=direction_id
            )
            
            # 保存结果
            project['feasibility'] = feasibility
            project['content_analysis'] = content_analysis
            project['ai_extracted'] = ai_extracted
            project['attachment_analysis'] = attachment_analysis
            
            # 保存到数据库
            self.db.save_filtered_project(ann['id'], project['match_results'], feasibility)
            if ai_extracted:
                self.db.save_analysis_result(ann['id'], ai_extracted, 0.8)

            # 高分项目加入追踪名单（智能追踪：后续更正/流标等只提醒已关注项目）
            threshold = (
                self.config.get("announcement_filter", {})
                .get("smart_track", {})
                .get("score_threshold", 60)
            )
            if (
                self.config.get("announcement_filter", {})
                .get("smart_track", {})
                .get("enabled", True)
                and feasibility["total"] >= threshold
            ):
                project_code = (ai_extracted or {}).get("project_code") if ai_extracted else None
                project_name = (ai_extracted or {}).get("project_name") if ai_extracted else None
                if not project_code and not project_name:
                    from src.utils.project_fingerprint import extract_project_refs_from_content
                    content = ann.get("content") or ""
                    refs = extract_project_refs_from_content(content)
                    if refs:
                        project_code, project_name = refs[0][0] or "", refs[0][1] or ""
                if project_code or project_name:
                    n = self.db.add_interested_project(
                        project_code=project_code,
                        project_name=project_name,
                        source_announcement_id=ann["id"],
                        feasibility_score=feasibility["total"],
                    )
                    if n > 0:
                        logger.debug(f"     已加入追踪名单 (指纹数: {n})")

            # 显示评分
            score_info = f"{feasibility['total']}/100 ({feasibility['level']})"
            if feasibility.get('passes_filter'):
                logger.success(f"     ✅ 评分: {score_info}")
            else:
                logger.info(f"     ⚠️ 评分: {score_info} (未通过二次过滤)")
            
            return project
            
        except Exception as e:
            logger.error(f"     ❌ 分析失败: {e}")
            return project
    
    def deep_analyze_projects(self, projects):
        """深度分析项目（并发版：内容+AI+附件+评分）
        
        Args:
            projects: 项目列表
        """
        if not projects:
            return
        
        # 获取并发配置
        max_workers = self.config.get('spider', {}).get('max_concurrent_details', 3)
        
        # 如果只有1-2个项目，不启用并发
        if len(projects) <= 2:
            logger.info(f"项目数量少（{len(projects)}个），使用串行处理")
            for i, project in enumerate(projects, 1):
                self._analyze_single_project((i, len(projects), project))
            return
        
        # 并发处理多个项目
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        logger.info(f"启用并发分析（{max_workers} 个工作线程）")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_project = {
                executor.submit(
                    self._analyze_single_project, 
                    (i, len(projects), project)
                ): project 
                for i, project in enumerate(projects, 1)
            }
            
            # 收集结果
            completed = 0
            for future in as_completed(future_to_project):
                try:
                    result = future.result()
                    completed += 1
                except Exception as e:
                    logger.error(f"并发分析异常: {e}")
                    completed += 1
            
            logger.info(f"✅ 并发分析完成：{completed}/{len(projects)} 个项目")
    
    def start_scheduler(self):
        """启动定时任务（当 scheduler.enabled 为 true 时）"""
        if not self.config.get("scheduler", {}).get("enabled", True):
            logger.warning("⏰ 定时任务已关闭（scheduler.enabled=false），仅单次运行可用")
            return
        logger.info("⏰ 启动定时任务模式")
        scheduler = TaskScheduler(
            self.config["scheduler"],
            self.run_pipeline
        )
        scheduler.add_daily_tasks()
        scheduler.start()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='TenderCopilot - 招投标智能助手')
    parser.add_argument('--mode', choices=['once', 'schedule'], default='once',
                        help='运行模式: once=单次执行, schedule=定时任务')
    
    args = parser.parse_args()
    
    app = TenderCopilot()
    
    if args.mode == 'once':
        # 单次执行
        app.run_pipeline()
    else:
        # 定时任务模式
        app.start_scheduler()


if __name__ == "__main__":
    main()
