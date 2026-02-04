"""TenderCopilot - 招投标智能助手 主程序"""

import sys
import yaml
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

# 导入模块
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
        """加载配置文件"""
        # 主配置
        with open('config/settings.yaml', 'r', encoding='utf-8') as f:
            settings = yaml.safe_load(f)
        
        # 业务方向配置
        with open('config/business_directions.yaml', 'r', encoding='utf-8') as f:
            business = yaml.safe_load(f)
        
        # 通知配置
        with open('config/notifications.yaml', 'r', encoding='utf-8') as f:
            notifications = yaml.safe_load(f)
        
        # 筛选配置（新增）
        try:
            with open('config/filter_settings.yaml', 'r', encoding='utf-8') as f:
                filter_settings = yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning("⚠️ 未找到 filter_settings.yaml，将使用传统爬取模式")
            filter_settings = {}
        
        # 搜索关键词配置（新增）
        try:
            with open('config/search_keywords.yaml', 'r', encoding='utf-8') as f:
                search_config = yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning("⚠️ 未找到 search_keywords.yaml，使用默认配置")
            search_config = {}
        
        # 合并配置
        config = {**settings}
        config['business_directions'] = business['business_directions']
        config['global_exclude'] = business['global_exclude']
        config['filter_settings'] = filter_settings
        config['search_keywords'] = search_config.get('search_keywords', {})
        config['crawl_strategy'] = search_config.get('crawl_strategy', {})
        config.update(notifications)
        
        # 处理环境变量
        api_key_config = config['analyzer'].get('api_key', '')
        if '${GEMINI_API_KEY}' in api_key_config:
            config['analyzer']['api_key'] = os.getenv('GEMINI_API_KEY', '')
        elif '${OPENAI_API_KEY}' in api_key_config:
            config['analyzer']['api_key'] = os.getenv('OPENAI_API_KEY', '')
        
        # 处理企业微信 webhook（新增）
        webhook_url = config.get('wechat_work', {}).get('webhook_url', '')
        if '${WECHAT_WORK_WEBHOOK}' in webhook_url:
            config['wechat_work']['webhook_url'] = os.getenv('WECHAT_WORK_WEBHOOK', '')
        
        return config
    
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
        """执行完整流程（新的增量搜索模式）"""
        logger.info("=" * 60)
        logger.info("🚀 TenderCopilot 开始运行（增量搜索模式）")
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
            
            # 步骤2: 准备搜索关键词
            logger.info("🔑 步骤 2/7: 准备搜索关键词")
            keywords = self._get_search_keywords()
            logger.info(f"  共 {len(keywords)} 个关键词: {', '.join(keywords[:5])}...")
            
            # 步骤3: 逐个关键词搜索爬取（增量模式）
            logger.info("📥 步骤 3/7: 逐个关键词搜索爬取")
            all_announcements = []
            for i, keyword in enumerate(keywords, 1):
                logger.info(f"  🔍 [{i}/{len(keywords)}] 搜索: '{keyword}'")
                results = self.spider.search_by_keyword(
                    keyword=keyword,
                    last_crawl_time=last_crawl_time,
                    db_manager=self.db,
                    max_results=self.config.get('crawl_strategy', {}).get('max_per_keyword', 200)
                )
                all_announcements.extend(results)
                logger.info(f"     获取 {len(results)} 条新公告")
            
            logger.info(f"✅ 搜索完成，共获取 {len(all_announcements)} 条新公告")
            
            # 记录爬取历史并更新时间
            self.crawl_tracker.record_crawl(len(all_announcements), success=True)
            self.crawl_tracker.update_last_crawl_time()
            
            if not all_announcements:
                logger.warning("⚠️ 未爬取到任何新公告，流程结束")
                return
            
            # 步骤4: 初步筛选（关键词+地域）
            logger.info("🔍 步骤 4/7: 初步筛选（关键词匹配+地域检查）")
            filtered = self.filter_announcements(all_announcements)
            logger.info(f"✅ 筛选出 {len(filtered)} 个匹配项目")
            
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
    
    def deep_analyze_projects(self, projects):
        """深度分析项目（内容+AI+附件+评分）
        
        Args:
            projects: 项目列表
        """
        deep_analysis_enabled = self.config.get('deep_analysis', {}).get('enabled', True)
        
        for i, project in enumerate(projects, 1):
            ann = project['announcement']
            direction_id = project['matched_direction_id']
            direction_config = self.config['business_directions'][direction_id]
            
            logger.info(f"  📊 [{i}/{len(projects)}] 分析: {ann['title'][:40]}...")
            
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
