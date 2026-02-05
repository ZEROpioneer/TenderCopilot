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
        """配置日志"""
        log_config = self.config['logging']
        
        # 移除默认处理器
        logger.remove()
        
        # 添加控制台输出
        logger.add(
            sys.stdout,
            format=log_config['format'],
            level=log_config['level']
        )
        
        # 添加文件输出
        logger.add(
            log_config['log_file'],
            format=log_config['format'],
            level=log_config['level'],
            rotation=log_config['rotation'],
            retention=log_config['retention'],
            compression=log_config['compression'],
            encoding='utf-8'
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
        self.deduplicator = Deduplicator(self.db)
        
        # 检查是否配置了 API Key
        if self.config['analyzer'].get('api_key'):
            self.analyzer = InfoExtractor(self.config)
        else:
            logger.warning("⚠️ 未配置 API Key，AI 分析功能将不可用")
        
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
                max_pages = crawl_config.get('max_pages', 5)  # 默认5页
                max_consecutive = crawl_config.get('max_consecutive_exists', 5)  # 连续5条重复停止
                
                all_announcements = self.spider.fetch_announcements(
                    max_pages=max_pages,
                    db_manager=self.db,
                    max_consecutive_exists=max_consecutive
                )
                
                logger.info(f"  ✅ 爬取成功，共获取 {len(all_announcements)} 条新公告")
                
                # 时间过滤：只保留增量时间窗口内的公告
                if all_announcements:
                    logger.info(f"  ⏱️ 应用时间过滤（保留 {last_crawl_time.strftime('%Y-%m-%d %H:%M')} 之后的）")
                    original_count = len(all_announcements)
                    all_announcements = [
                        ann for ann in all_announcements
                        if self._is_new_announcement(ann, last_crawl_time)
                    ]
                    logger.info(f"  ✅ 过滤完成: {original_count} → {len(all_announcements)} 条新公告")
                
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
            
            if not filtered:
                logger.warning("⚠️ 未找到匹配项目，流程结束")
                return
            
            # 步骤5: 深度分析（只分析通过初筛的项目）
            logger.info("🤖 步骤 5/7: 深度分析（内容+AI+附件）")
            self.deep_analyze_projects(filtered)
            
            # 步骤6: 二次过滤（只保留高质量项目）
            logger.info("🎯 步骤 6/7: 二次过滤（评分>=60分）")
            high_quality = [p for p in filtered if p['feasibility'].get('passes_filter', False)]
            logger.info(f"✅ 筛选出 {len(high_quality)} 个高质量项目（评分>=60）")
            
            if not high_quality:
                logger.warning("⚠️ 没有高质量项目，跳过推送")
                return
            
            # 步骤7: 生成报告并推送
            logger.info("📝 步骤 7/7: 生成报告并推送通知")
            stats = {
                'total_crawled': len(all_announcements),
                'total_matched': len(filtered),
                'high_quality': len(high_quality),
                'excellent': sum(1 for p in high_quality if p['feasibility']['total'] >= 80),
                'good': sum(1 for p in high_quality if 60 <= p['feasibility']['total'] < 80)
            }
            report = self.reporter.generate_daily_report(high_quality, stats)
            
            # 推送通知
            logger.info("📤 推送通知")
            self.notification_manager.send_report(report, high_quality)
            
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
            publish_date = DateParser.parse(publish_date_str)
            
            if not publish_date:
                # 如果无法解析，保守起见认为是新的
                logger.debug(f"  ⚠️ 无法解析发布时间: {publish_date_str}")
                return True
            
            # 比较时间
            return publish_date > last_crawl_time
            
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
        """初步筛选公告（关键词+地域）"""
        filtered = []
        
        for ann in announcements:
            # 1. 关键词匹配
            match_results = self.keyword_matcher.match(ann)
            if not match_results:
                continue
            
            # 2. 获取最佳匹配方向
            best_direction_id = max(match_results.keys(), key=lambda k: match_results[k]['score'])
            best_direction = match_results[best_direction_id]
            direction_config = self.config['business_directions'][best_direction_id]
            
            # 3. 地域匹配检查
            location_result = self.location_matcher.match(
                ann, 
                best_direction_id,
                direction_config
            )
            
            # 如果地域要求不通过，跳过
            if not location_result['matched']:
                logger.info(f"⏭️ 跳过（地域不符-{direction_config['name']}）: {ann['title'][:50]}...")
                continue
            
            # 4. 去重
            if self.deduplicator.is_duplicate(ann):
                logger.debug(f"⏭️ 跳过（重复）: {ann['title'][:50]}...")
                continue
            
            # 5. 保存到数据库
            self.db.save_announcement(ann)
            
            # 6. 添加到结果（暂时不计算评分，等深度分析后再计算）
            filtered.append({
                'announcement': ann,
                'matched_direction_id': best_direction_id,
                'match_results': match_results,
                'location_result': location_result
            })
            
            logger.info(f"✅ 通过初筛: {ann['title'][:50]}... ({direction_config['name']})")
        
        return filtered
    
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
        """启动定时任务"""
        logger.info("⏰ 启动定时任务模式")
        
        scheduler = TaskScheduler(
            self.config['scheduler'],
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
