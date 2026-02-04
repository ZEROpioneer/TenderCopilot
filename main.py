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
        
        # 合并配置
        config = {**settings}
        config['business_directions'] = business['business_directions']
        config['global_exclude'] = business['global_exclude']
        config['filter_settings'] = filter_settings
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
        
        self.scorer = FeasibilityScorer()
        self.reporter = MarkdownReporter()
        self.notification_manager = NotificationManager(self.config)
        
        logger.success("✅ 组件初始化完成")
    
    def run_pipeline(self):
        """执行完整流程"""
        logger.info("=" * 60)
        logger.info("🚀 TenderCopilot 开始运行")
        logger.info("=" * 60)
        
        try:
            # 初始化组件
            if not self.spider:
                self.init_components()
            
            # 1. 准备筛选条件
            logger.info("📥 步骤 1/6: 准备爬取筛选条件")
            
            # 计算日期范围
            date_range = self.crawl_tracker.get_date_range()
            logger.info(f"  📅 日期范围: {date_range[0]} ~ {date_range[1]}")
            
            # 获取筛选配置
            filter_config = self.config.get('filter_settings', {})
            filters_enabled = filter_config.get('filters', {})
            
            # 公告类型
            notice_types = None
            if filters_enabled.get('notice_types', {}).get('enabled'):
                notice_types = filters_enabled['notice_types'].get('types', [])
                logger.info(f"  📋 公告类型: {', '.join(notice_types)}")
            
            # 地区
            regions = None
            if filters_enabled.get('regions', {}).get('enabled'):
                priority_regions = filters_enabled['regions'].get('priority', [])
                included_regions = filters_enabled['regions'].get('included', [])
                
                regions = []
                # 优先地区
                for r in priority_regions:
                    regions.append(r['name'])
                    if r.get('include_cities') and r.get('cities'):
                        regions.extend(r['cities'])
                # 其他关注地区
                regions.extend(included_regions)
                
                logger.info(f"  📍 关注地区: {', '.join(regions[:5])}{'...' if len(regions) > 5 else ''}")
            
            # 最大结果数
            max_results = filter_config.get('crawl_strategy', {}).get('max_results_per_request', 50)
            
            # 2. 使用筛选条件爬取
            logger.info("📥 步骤 2/6: 使用筛选条件爬取公告")
            announcements = self.spider.fetch_by_filters(
                date_range=date_range,
                notice_types=notice_types,
                regions=regions,
                max_results=max_results,
                use_api=True  # 优先使用 API
            )
            logger.info(f"✅ 爬取到 {len(announcements)} 条公告")
            
            # 记录爬取历史
            self.crawl_tracker.record_crawl(len(announcements), success=True)
            
            if not announcements:
                logger.warning("⚠️ 未爬取到任何公告，流程结束")
                return
            
            # 3. 获取详情内容（针对需要完整内容分析的公告）
            logger.info("📄 步骤 3/6: 获取公告详情内容")
            for i, ann in enumerate(announcements):
                # 如果 API 已返回内容，跳过
                if ann.get('content'):
                    logger.debug(f"  ⏭️ [{i+1}/{len(announcements)}] 已有内容: {ann['title'][:40]}...")
                    continue
                
                try:
                    logger.info(f"  📖 [{i+1}/{len(announcements)}] 获取: {ann['title'][:40]}...")
                    detail = self.spider.fetch_detail(ann['url'])
                    if detail:
                        ann['content'] = detail.get('content', '')
                        ann['attachments'] = detail.get('attachments', [])
                except Exception as e:
                    logger.warning(f"  ⚠️ 获取详情失败: {e}")
                    continue
            
            # 4. 筛选项目
            logger.info("🔍 步骤 4/6: 筛选匹配项目")
            logger.info(f"💡 开始关键词匹配（业务方向：文化氛围、数字史馆、仿真训练、院线电影）")
            filtered = self.filter_announcements(announcements)
            logger.info(f"✅ 筛选出 {len(filtered)} 个匹配项目")
            
            if not filtered:
                logger.warning("⚠️ 未找到匹配项目，流程结束")
                return
            
            # 5. AI 分析（如果启用）
            if self.analyzer:
                logger.info("🤖 步骤 5/6: AI 分析项目信息")
                for project in filtered:
                    self.analyze_project(project)
            else:
                logger.info("⏭️ 步骤 5/6: 跳过 AI 分析")
            
            # 6. 生成报告
            logger.info("📝 步骤 6/6: 生成分析报告")
            stats = {
                'total_crawled': len(announcements),
                'total_matched': len(filtered),
                'high_priority': sum(1 for p in filtered if p['feasibility']['total'] >= 80),
                'medium_priority': sum(1 for p in filtered if 60 <= p['feasibility']['total'] < 80),
                'low_priority': sum(1 for p in filtered if p['feasibility']['total'] < 60)
            }
            report = self.reporter.generate_daily_report(filtered, stats)
            
            # 推送通知
            logger.info("📤 推送通知")
            self.notification_manager.send_report(report, filtered)
            
            # 显示爬取统计
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
    
    def filter_announcements(self, announcements):
        """筛选公告"""
        filtered = []
        
        for ann in announcements:
            # 关键词匹配
            match_results = self.keyword_matcher.match(ann)
            if not match_results:
                continue
            
            # 获取最佳匹配方向
            best_direction_id = max(match_results.keys(), key=lambda k: match_results[k]['score'])
            best_direction = match_results[best_direction_id]
            
            # 地域匹配
            location_result = self.location_matcher.match(
                ann, 
                best_direction_id,
                self.config['business_directions'][best_direction_id]
            )
            
            if not location_result['matched']:
                logger.info(f"⏭️ 跳过（地域不符）: {ann['title']}")
                continue
            
            # 去重
            if self.deduplicator.is_duplicate(ann):
                logger.info(f"⏭️ 跳过（重复）: {ann['title']}")
                continue
            
            # 计算可行性评分
            feasibility = self.scorer.calculate(ann, match_results, location_result)
            
            # 保存到数据库
            self.db.save_announcement(ann)
            self.db.save_filtered_project(ann['id'], match_results, feasibility)
            
            # 添加到结果
            filtered.append({
                'announcement': ann,
                'matched_directions': [best_direction],
                'feasibility': feasibility
            })
            
            logger.success(f"✅ 通过筛选: {ann['title']} (评分: {feasibility['total']})")
        
        return filtered
    
    def analyze_project(self, project):
        """分析项目"""
        ann = project['announcement']
        
        # 准备内容
        content = f"{ann['title']}\n\n{ann.get('content', '')}"
        
        # AI 提取
        extracted = self.analyzer.extract(content[:12000])  # 限制长度
        
        if extracted:
            project['analysis'] = extracted
            self.db.save_analysis_result(ann['id'], extracted, 0.8)
    
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
