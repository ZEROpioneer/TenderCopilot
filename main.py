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
        
        # 合并配置
        config = {**settings}
        config['business_directions'] = business['business_directions']
        config['global_exclude'] = business['global_exclude']
        config.update(notifications)
        
        # 处理环境变量
        api_key_config = config['analyzer'].get('api_key', '')
        if '${GEMINI_API_KEY}' in api_key_config:
            config['analyzer']['api_key'] = os.getenv('GEMINI_API_KEY', '')
        elif '${OPENAI_API_KEY}' in api_key_config:
            config['analyzer']['api_key'] = os.getenv('OPENAI_API_KEY', '')
        
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
            
            # 1. 爬取公告列表
            logger.info("📥 步骤 1/6: 爬取招标公告列表")
            announcements = self.spider.fetch_announcements()
            logger.info(f"✅ 爬取到 {len(announcements)} 条公告")
            
            if not announcements:
                logger.warning("⚠️ 未爬取到任何公告，流程结束")
                return
            
            # 2. 获取公告详情（可选：只获取前N个以加快速度）
            logger.info("📄 步骤 2/6: 获取公告详情内容")
            max_details = self.config['spider'].get('max_fetch_details', 50)
            for i, ann in enumerate(announcements[:max_details]):
                try:
                    logger.info(f"  [{i+1}/{min(len(announcements), max_details)}] 获取: {ann['title'][:40]}...")
                    detail = self.spider.fetch_detail(ann['url'])
                    if detail:
                        ann['content'] = detail.get('content', '')
                        ann['attachments'] = detail.get('attachments', [])
                except Exception as e:
                    logger.warning(f"  ⚠️ 获取详情失败: {e}")
                    continue
            
            # 3. 筛选项目
            logger.info("🔍 步骤 3/6: 筛选匹配项目")
            logger.info(f"💡 开始关键词匹配（业务方向：文化氛围、数字史馆、仿真训练、院线电影）")
            filtered = self.filter_announcements(announcements)
            logger.info(f"✅ 筛选出 {len(filtered)} 个匹配项目")
            
            if not filtered:
                logger.warning("⚠️ 未找到匹配项目，流程结束")
                return
            
            # 4. AI 分析（如果启用）
            if self.analyzer:
                logger.info("🤖 步骤 4/6: AI 分析项目信息")
                for project in filtered:
                    self.analyze_project(project)
            else:
                logger.info("⏭️ 步骤 4/6: 跳过 AI 分析")
            
            # 5. 生成报告
            logger.info("📝 步骤 5/6: 生成分析报告")
            stats = {
                'total_crawled': len(announcements),
                'total_matched': len(filtered),
                'high_priority': sum(1 for p in filtered if p['feasibility']['total'] >= 80),
                'medium_priority': sum(1 for p in filtered if 60 <= p['feasibility']['total'] < 80),
                'low_priority': sum(1 for p in filtered if p['feasibility']['total'] < 60)
            }
            report = self.reporter.generate_daily_report(filtered, stats)
            
            # 6. 推送通知
            logger.info("📤 步骤 6/6: 推送通知")
            self.notification_manager.send_report(report, filtered)
            
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
