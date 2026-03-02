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

        # 持久化 app.log：供实验室 Live Terminal 读取（固定路径）
        app_log = Path(__file__).resolve().parent / "data" / "app.log"
        app_log.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(app_log),
            format=log_config['format'],
            level=file_level,
            encoding='utf-8',
        )
    
    def init_components(self):
        """初始化所有组件"""
        logger.info("🔧 正在初始化组件...")
        
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
    
    def run_pipeline(self, force_mode: bool = False, mute_notify: bool = False):
        """执行完整流程（列表页增量爬取 + 本地关键词筛选）
        
        Args:
            force_mode: 强制无视去重（实验室干跑测试用）
            mute_notify: 静音模式，不推送企微，仅控制台打印
        Returns:
            dict: 统计信息 {total_crawled, total_matched, recommended, ...}，异常时返回空 dict
        """
        stats = {}
        logger.info("=" * 60)
        lab_tag = " [实验室干跑]" if (force_mode or mute_notify) else ""
        logger.info(f"🚀 TenderCopilot 开始运行（列表页增量爬取 + 本地筛选）{lab_tag}")
        if force_mode:
            logger.info("  ⚙️ 强制无视去重：已启用")
        if mute_notify:
            logger.info("  🔇 静音模式：企微推送已拦截")
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
                max_consecutive = crawl_config.get('max_consecutive_exists', 15)  # 连续重复熔断阈值
                max_total_items = crawl_config.get('max_total_items', 1000)  # 单次硬性抓取上限
                warn_threshold = crawl_config.get('warn_threshold', 200)  # 警告阈值
                
                all_announcements = self.spider.fetch_announcements(
                    max_pages=max_pages,
                    db_manager=self.db,
                    max_consecutive_exists=max_consecutive,
                    max_total_items=max_total_items,
                    warn_threshold=warn_threshold,
                    skip_db_dedup=force_mode,
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
                logger.info("=" * 44)
                logger.info("本次未抓取到新数据，系统已熔断或暂无更新。")
                logger.info("=" * 44)
                stats = {"total_crawled": 0, "total_matched": 0, "recommended": 0, "message": "未爬取到新公告"}
                return stats

            # 首尾详情探测：抓取最新/最旧两条的详情页以提取精确时间（HH:mm）
            earliest_str, latest_str = self._get_precise_pub_date_range(all_announcements)
            
            # 步骤4: 本地关键词筛选+地域检查
            logger.info("🔍 步骤 4/7: 本地关键词筛选+地域检查")
            logger.info(f"  📋 待筛选: {len(all_announcements)} 条公告")
            logger.info(f"  🔑 关键词: {', '.join(keywords[:3])}... 等{len(keywords)}个")
            filtered = self.filter_announcements(all_announcements, force_mode=force_mode)
            logger.info(f"✅ 筛选出 {len(filtered)} 个匹配项目（匹配率: {len(filtered)/len(all_announcements)*100:.1f}%）")
            
            # 步骤5: 深度分析（只分析通过初筛的项目）
            logger.info("🤖 步骤 5/7: 深度分析（内容+AI+附件）")
            self.deep_analyze_projects(filtered)
            
            # 步骤6: 分析结果分层（推荐+备选）
            push_threshold = self.config.get('scoring', {}).get('push_threshold', 65)
            logger.info("🎯 步骤 6/7: 结果分层（推荐项目 + 备选项目）")
            recommended = [p for p in filtered if p.feasibility['total'] >= push_threshold]
            alternatives = [p for p in filtered if p.feasibility['total'] < push_threshold]

            logger.info(f"  ✅ 推荐项目: {len(recommended)} 个（评分≥{push_threshold}分）")
            if len(recommended) > 0:
                excellent = sum(1 for p in recommended if p.feasibility['total'] >= 80)
                good = len(recommended) - excellent
                if excellent > 0:
                    logger.info(f"     - 优秀: {excellent} 个（≥80分）")
                if good > 0:
                    logger.info(f"     - 良好: {good} 个（{push_threshold}-79分）")

            if alternatives:
                logger.info(f"  📌 备选项目: {len(alternatives)} 个（评分<{push_threshold}分，可人工复核）")
            
            # 步骤7: 生成报告并推送（包含所有项目）
            logger.info("📝 步骤 7/7: 生成报告并推送通知")
            stats = {
                'total_crawled': len(all_announcements),
                'total_matched': len(filtered),
                'recommended': len(recommended),
                'excellent': sum(1 for p in recommended if p.feasibility['total'] >= 80),
                'good': sum(1 for p in recommended if push_threshold <= p.feasibility['total'] < 80),
                'alternatives': len(alternatives),
                'push_threshold': push_threshold,
            }
            
            # 生成包含所有项目的报告（不含时间区间，推送渠道不包含）
            report = self.reporter.generate_daily_report(filtered, stats)
            # 保存到 .md 时插入精确时间区间（仅本地报告，不推送企微）
            self.reporter._save_report(report, earliest_str=earliest_str, latest_str=latest_str)
            
            # 推送通知（静音模式下仅打印，推送内容不含时间区间）
            if mute_notify:
                logger.info("📤 [静音] 拦截企微推送，报告内容如下：")
                logger.info("-" * 40)
                logger.info(report[:3000] + ("..." if len(report) > 3000 else ""))
                logger.info("-" * 40)
            else:
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

            # 本次抓取战报：数量 + 精确数据时间区间（HH:mm）
            logger.info("=" * 44)
            logger.info("================ 本次抓取战报 ================")
            logger.info(f"✅ 新增抓取数量: {len(all_announcements)} 条")
            if earliest_str and latest_str:
                logger.info(f"📅 数据时间区间: {earliest_str} 至 {latest_str}")
            else:
                logger.info("📅 数据时间区间: (部分公告无有效发布日期)")
            logger.info("=" * 44)

            logger.success("✅ 流程执行完成")
            return stats
            
        except Exception as e:
            logger.error(f"❌ 流程执行失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            stats = {"error": str(e)}
        finally:
            if self.spider:
                self.spider.close()
        return stats
    
    def _extract_precise_time_from_content(self, text: str):
        """从 content_raw 或网页源码中正则提取精确时间 YYYY-MM-DD HH:mm。

        支持格式：YYYY-MM-DD HH:mm、YYYY-MM-DD HH:mm:ss、YYYY年MM月DD日 HH:mm 等。
        """
        import re
        from datetime import datetime
        if not text or not str(text).strip():
            return None
        text = str(text)
        patterns = [
            (r'(\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?)', ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M']),
            (r'(\d{4}年\d{1,2}月\d{1,2}日\s+\d{1,2}:\d{2}(?::\d{2})?)', None),
        ]
        for pat, fmts in patterns:
            m = re.search(pat, text)
            if m:
                raw = m.group(1).strip()
                if fmts:
                    for fmt in fmts:
                        try:
                            dt = datetime.strptime(raw[:19], fmt)
                            return dt.strftime('%Y-%m-%d %H:%M')
                        except ValueError:
                            continue
                if re.match(r'\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}', raw):
                    return raw[:16] if len(raw) >= 16 else raw
                if '年' in raw:
                    nums = re.findall(r'\d+', raw)
                    if len(nums) >= 5:
                        try:
                            return f"{nums[0]}-{nums[1].zfill(2)}-{nums[2].zfill(2)} {nums[3].zfill(2)}:{nums[4].zfill(2)}"
                        except (IndexError, ValueError):
                            pass
        return None

    def _get_precise_pub_date_range(self, announcements) -> tuple:
        """获取精确到 HH:mm 的发布日期区间。通过抓取首尾两条详情页提取。"""
        if not announcements or len(announcements) < 1:
            return '', ''
        first_item = announcements[0]
        last_item = announcements[-1] if len(announcements) > 1 else first_item

        latest_str = None
        earliest_str = None

        if self.spider:
            try:
                logger.info("  📅 获取首尾详情以提取精确时间...")
                self.spider.fetch_detail(first_item)
                content_first = getattr(first_item, 'content_raw', '') or (first_item.get('content_raw', '') if hasattr(first_item, 'get') else '')
                latest_str = self._extract_precise_time_from_content(content_first)
                if first_item is not last_item:
                    self.spider.fetch_detail(last_item)
                    content_last = getattr(last_item, 'content_raw', '') or (last_item.get('content_raw', '') if hasattr(last_item, 'get') else '')
                    earliest_str = self._extract_precise_time_from_content(content_last)
                else:
                    earliest_str = latest_str
            except Exception as e:
                logger.warning(f"  ⚠️ 首尾详情时间提取失败: {e}，回退到列表日期")

        if not latest_str or not earliest_str:
            return self._get_pub_date_range(announcements)
        return earliest_str, latest_str

    def _get_pub_date_range(self, announcements):
        """提取公告列表的发布日期区间（最早～最晚）

        Args:
            announcements: 公告列表（TenderItem 或 dict）

        Returns:
            tuple: (earliest_str, latest_str)，无有效日期时返回 ('', '')
        """
        from src.utils import DateParser

        parsed = []
        for ann in announcements:
            raw = ann.get('publish_date', '') or ann.get('pub_date', '') if hasattr(ann, 'get') else (getattr(ann, 'publish_date', '') or getattr(ann, 'pub_date', ''))
            if not raw:
                continue
            dt = DateParser.parse(str(raw).strip())
            if dt:
                parsed.append(dt)

        if not parsed:
            return '', ''
        earliest = min(parsed)
        latest = max(parsed)
        has_time = any(d.hour != 0 or d.minute != 0 for d in parsed)
        fmt = '%Y-%m-%d %H:%M' if has_time else '%Y-%m-%d'
        return earliest.strftime(fmt), latest.strftime(fmt)

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
    
    def filter_announcements(self, announcements, force_mode: bool = False):
        """初步筛选公告（双轨制：策略 A 新机会 / 策略 B 智能追踪）"""
        return self.filter_manager.process(announcements, force_mode=force_mode)
    
    def _analyze_single_project(self, project_info):
        """分析单个项目（可并发执行）
        
        Args:
            project_info: (index, total, project) 元组
            
        Returns:
            更新后的 project 字典
        """
        i, total, project = project_info
        direction_id = project.matched_direction_id
        direction_config = self.config['business_directions'][direction_id]
        deep_analysis_enabled = self.config.get('deep_analysis', {}).get('enabled', True)
        
        logger.info(f"  📊 [{i}/{total}] 分析: {(project.title or '')[:40]}...")
        
        try:
            # 1. 获取详情内容
            detail_content = ''
            if not project.content_raw:
                try:
                    self.spider.fetch_detail(project)
                    detail_content = project.content_raw
                except Exception as e:
                    logger.warning(f"     ⚠️ 获取详情失败: {e}")
            else:
                detail_content = project.content_raw
            
            # 2. 内容相关度分析
            content_analysis = None
            if deep_analysis_enabled and self.config.get('deep_analysis', {}).get('analyze_content', True):
                try:
                    content_analysis = self.content_analyzer.analyze_relevance(
                        project,
                        direction_config,
                        detail_content
                    )
                    logger.debug(f"     内容相关度: {content_analysis['score']}/100")
                except Exception as e:
                    logger.warning(f"     ⚠️ 内容分析失败: {e}")
            
            # 3. AI提取结构化信息（精准 4 要素 + 评分，直接赋给 project）
            ai_extracted = None
            if self.analyzer and deep_analysis_enabled and self.config.get('deep_analysis', {}).get('extract_ai', True):
                try:
                    content = f"{project.title}\n\n{detail_content}"
                    ai_extracted = self.analyzer.extract(content[:12000], item=project)
                    logger.debug(f"     AI提取: 完成")
                except Exception as e:
                    logger.warning(f"     ⚠️ AI提取失败: {e}")
            
            # 4. 附件分析
            attachment_analysis = None
            if deep_analysis_enabled and self.config.get('deep_analysis', {}).get('analyze_attachments', True):
                attachments = project.attachments or []
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
                project,
                project.match_results,
                project.location_result,
                content_analysis=content_analysis,
                ai_extracted=ai_extracted,
                attachment_analysis=attachment_analysis,
                direction_id=direction_id
            )
            
            # 保存结果到 TenderItem
            project.feasibility = feasibility
            project.content_analysis = content_analysis
            project.ai_extracted = ai_extracted
            project.attachment_analysis = attachment_analysis
            
            # 保存到数据库
            self.db.save_filtered_project(project.project_id, project.match_results, feasibility)
            if ai_extracted is not None:
                # 确保 AI 核心字段被正确打包（优先用 item 属性，兜底用 ai_extracted）
                to_save = dict(ai_extracted)
                for key, default in [
                    ("confidentiality_req", "未知"),
                    ("project_summary", "未知"),
                    ("doc_deadline", "未知"),
                    ("bid_deadline", "未知"),
                    ("budget_info", "未公布"),
                    ("bid_location", "未知"),
                    ("contact_info", "未知"),
                    ("doc_claim_method", "未知"),
                    ("bid_method", "未知"),
                ]:
                    val = getattr(project, key, None) or to_save.get(key)
                    to_save[key] = (val or "").strip() or default
                to_save["has_attachments"] = getattr(project, "has_attachments", False)
                self.db.save_analysis_result(project.project_id, to_save, 0.8)

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
                    refs = extract_project_refs_from_content(project.content_raw or "")
                    if refs:
                        project_code, project_name = refs[0][0] or "", refs[0][1] or ""
                if project_code or project_name:
                    n = self.db.add_interested_project(
                        project_code=project_code,
                        project_name=project_name,
                        source_announcement_id=project.project_id,
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
            # 兜底护盾：强行塞入默认 feasibility
            project.feasibility = {
                'total': 60,
                'level': '及格',
                'reason': 'AI分析失败或超时，给予默认及格分以保证流程继续',
                'breakdown': {},
                'passes_filter': True,
                'time_score_details': {},
                'score_breakdown': [{"rule": "AI分析失败，默认及格分", "points": 60}],
            }
            return project
    
    def deep_analyze_projects(self, projects):
        """深度分析项目（串行版：避免 DrissionPage 多线程 Tab 抢占）

        DrissionPage 操控单例浏览器，多线程下极易发生 Tab 抢占与 DOM 未渲染即提取，
        导致详情页 content_raw 为空。改为单线程 for 循环串行抓取，确保稳定。

        Args:
            projects: 项目列表
        """
        if not projects:
            return

        logger.info(f"串行分析 {len(projects)} 个项目（详情页单线程抓取，避免 Tab 抢占）")
        for i, project in enumerate(projects, 1):
            self._analyze_single_project((i, len(projects), project))
        logger.info(f"✅ 深度分析完成：{len(projects)} 个项目")
    
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
