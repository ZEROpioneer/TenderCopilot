"""军队采购网爬虫"""

from DrissionPage import ChromiumPage, ChromiumOptions
from loguru import logger
import time
import random
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Any


class PLAPSpider:
    """军队采购网爬虫"""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.base_url = config['target_sites']['plap']['base_url']
        self.list_url = config['target_sites']['plap']['announcement_list_url']
        
        # 配置浏览器选项
        self.options = ChromiumOptions()
        if config['spider']['headless']:
            self.options.headless(True)
        
        # 设置 User Agent
        user_agent = config['spider'].get('user_agent')
        if user_agent:
            self.options.set_user_agent(user_agent)
        
        # 等待时间配置（性能优化）
        spider_config = config.get('spider', {})
        self.wait_ajax_load = spider_config.get('wait_ajax_load', 0.5)
        self.wait_page_refresh = spider_config.get('wait_page_refresh', 1)
        self.wait_between_pages = spider_config.get('wait_between_pages', 2)
        self.wait_retry = spider_config.get('retry_delay', 2)
        
        self.page = None
    
    def init_browser(self):
        """初始化浏览器"""
        try:
            # 使用配置好的选项初始化浏览器
            self.page = ChromiumPage(addr_or_opts=self.options)
            logger.info("✅ 浏览器初始化成功")
            return True
        except Exception as e:
            logger.error(f"❌ 浏览器初始化失败: {e}")
            return False
    
    def _load_page_with_retry(self, url, max_retries=3):
        """加载页面并等待AJAX完成（带重试机制）
        
        Args:
            url: 目标URL
            max_retries: 最大重试次数
            
        Returns:
            bool: 是否成功加载
        """
        for retry in range(max_retries):
            if retry > 0:
                logger.info(f"   🔄 第 {retry + 1} 次尝试...")
            
            try:
                self.page.get(url)
            except Exception as e:
                logger.warning(f"   ❌ 页面访问失败: {e}")
                if retry < max_retries - 1:
                    time.sleep(self.wait_retry)
                    continue
                return False
            
            logger.debug("   ⏳ 等待页面基础加载...")
            time.sleep(self.wait_page_refresh)
            
            # 等待AJAX加载完成 - 等待公告列表出现
            logger.debug("   ⏳ 等待公告列表加载（AJAX异步）...")
            try:
                # 等待第一个公告链接出现（最多20秒）
                self.page.wait.ele_displayed('css:ul.noticeShowList li a', timeout=20)
                logger.debug("   ✅ 公告列表已加载")
            except Exception as e:
                logger.warning(f"   ⚠️ 等待超时: {e}")
                logger.info("   💡 尝试手动触发...")
                try:
                    self.page.scroll.to_bottom()
                    time.sleep(self.wait_ajax_load)
                    self.page.scroll.to_top()
                    time.sleep(self.wait_ajax_load)
                except:
                    pass
            
            # 诊断：检查公告列表状态
            try:
                notice_list = self.page.ele('css:ul.noticeShowList', timeout=2)
                if notice_list:
                    lis = notice_list.eles('tag:li')
                    logger.debug(f"   📊 公告列表包含 {len(lis)} 个元素")
                    
                    if len(lis) == 0:
                        logger.warning("   ❌ 列表为空！AJAX未加载")
                        if retry < max_retries - 1:
                            logger.info(f"   💡 将在{self.wait_retry}秒后重试...")
                            time.sleep(self.wait_retry)
                            continue
                        return False
                    else:
                        logger.debug("   ✅ 列表有内容")
                        return True
                else:
                    logger.warning("   ❌ 未找到公告列表容器")
                    if retry < max_retries - 1:
                        time.sleep(2)
                        continue
                    return False
            except Exception as e:
                logger.warning(f"   ❌ 诊断失败: {e}")
                if retry < max_retries - 1:
                    time.sleep(self.wait_retry)
                    continue
                return False
        
        logger.error(f"❌ 尝试{max_retries}次后仍然失败")
        return False
    
    def fetch_announcements(self, max_pages=None, db_manager=None, max_consecutive_exists=5, max_total_items=300, warn_threshold=200):
        """爬取招标公告列表（多页增量版本）
        
        停止策略（按优先级）：
        1. 连续重复停止（主要机制）：连续N条都已存在，说明已爬到历史数据
        2. 保护性上限（安全机制）：爬取总数达到上限，防止异常情况无限爬取
        3. 警告阈值：爬取数量超过阈值时发出提醒
        
        Args:
            max_pages: 最多爬取页数（None=不限制，推荐）
            db_manager: 数据库管理器（用于去重检查）
            max_consecutive_exists: 连续多少条重复后停止（默认5）
            max_total_items: 保护性上限，单次最多爬取条数（默认300）
            warn_threshold: 警告阈值，超过后发出提醒（默认200）
            
        Returns:
            公告列表
        """
        logger.info(f"🔍 开始爬取招标公告: {self.list_url}")
        if max_pages:
            logger.info(f"   页数限制: {max_pages} 页")
        else:
            logger.info(f"   页数限制: 无限制（直到连续重复停止）")
        if db_manager:
            logger.info(f"   增量策略: 连续{max_consecutive_exists}条重复停止")
        logger.info(f"   保护上限: 最多{max_total_items}条（警告阈值: {warn_threshold}条）")
        
        if not self.page:
            if not self.init_browser():
                return []
        
        all_announcements = []
        consecutive_exists = 0
        
        try:
            # ✅ 使用重试机制加载页面
            page_loaded = self._load_page_with_retry(self.list_url, max_retries=3)
            
            if not page_loaded:
                logger.error("❌ 页面加载失败（已重试3次）")
                return []
            
            # 保存调试信息
            self._save_debug_info()
            
            # 多页爬取
            page_num = 1
            should_stop = False
            warned = False  # 是否已发出警告
            
            # 如果 max_pages 为 None，设置为一个很大的数字
            effective_max_pages = max_pages if max_pages else 9999
            
            while page_num <= effective_max_pages and not should_stop:
                logger.info(f"📄 第 {page_num} 页...")
                
                # 智能查找公告列表项
                items = self._find_announcement_items()
                
                if not items:
                    logger.warning(f"   ⚠️ 未找到公告列表项，停止")
                    break
                
                logger.debug(f"   找到 {len(items)} 个公告项")
                
                page_new = 0
                page_duplicate = 0
                
                # 解析本页公告
                for item in items:
                    try:
                        announcement = self._parse_list_item(item)
                        if not announcement:
                            continue
                        
                        # 数据库去重检查
                        if db_manager and db_manager.exists(announcement['id']):
                            consecutive_exists += 1
                            page_duplicate += 1
                            
                            # 连续重复达到阈值，停止爬取
                            if consecutive_exists >= max_consecutive_exists:
                                logger.info(f"   ⏹️ 连续{consecutive_exists}条重复，停止爬取")
                                should_stop = True
                                break
                        else:
                            consecutive_exists = 0  # 重置计数器
                            page_new += 1
                            all_announcements.append(announcement)
                            logger.debug(f"   ✅ [{len(all_announcements)}] {announcement['title'][:50]}...")
                        
                    except Exception as e:
                        logger.warning(f"   ⚠️ 解析公告项失败: {e}")
                        continue
                
                logger.debug(f"   本页统计: 新增 {page_new} 条，重复 {page_duplicate} 条")
                logger.debug(f"   累计爬取: {len(all_announcements)} 条新公告")
                
                # 检查停止条件
                if should_stop:
                    logger.info(f"   🛑 达到连续重复停止条件")
                    break
                
                # 检查保护性上限
                if len(all_announcements) >= max_total_items:
                    logger.warning(f"   🛑 达到保护性上限（{max_total_items}条），停止爬取")
                    logger.warning(f"   ⚠️ 这可能表示系统配置需要调整（连续重复阈值或去重机制）")
                    break
                
                # 检查警告阈值
                if len(all_announcements) >= warn_threshold and not warned:
                    logger.warning(f"   ⚠️ 已爬取{len(all_announcements)}条，超过警告阈值（{warn_threshold}）")
                    logger.warning(f"   ⚠️ 仍在继续爬取，直到连续{max_consecutive_exists}条重复...")
                    warned = True
                
                # 尝试翻页
                if page_num < effective_max_pages:
                    logger.info(f"   📖 尝试翻到第 {page_num + 1} 页...")
                    if self._goto_next_page():
                        page_num += 1
                    else:
                        logger.info("   ⏹️ 没有下一页")
                        break
                else:
                    # 只有设置了 max_pages 时才会触发这个分支
                    if max_pages:
                        logger.info(f"   ⏹️ 达到最大页数限制（{max_pages}页）")
                    break
            
            logger.success(f"✅ 爬取完成：共爬取 {page_num} 页，获得 {len(all_announcements)} 条新公告")
            
        except Exception as e:
            logger.error(f"❌ 爬取失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return all_announcements
    
    def _find_announcement_items(self):
        """智能查找公告列表项（优先使用验证成功的选择器）"""
        # ✅ 优先策略：使用验证成功的选择器
        selectors = [
            ('css:ul.noticeShowList li', '公告列表项（主选择器）'),
            ('css:table tbody tr', '表格行'),
            ('css:table tr', '表格行（无tbody）'),
            ('css:ul li', '列表项（通用）'),
        ]
        
        for selector, desc in selectors:
            try:
                items = self.page.eles(selector, timeout=1)
                if not items:
                    continue
                
                # 过滤出包含公告链接的项
                valid_items = []
                for item in items:
                    links = item.eles('tag:a')
                    if links:
                        link = links[0]
                        href = link.attr('href') or ''
                        # 只保留包含公告路径的链接
                        if '/ggxx/info/' in href:
                            valid_items.append(item)
                
                if len(valid_items) >= 5:  # 至少要有5个有效项
                    logger.debug(f"   ✅ 使用 {desc} - 找到 {len(valid_items)} 个公告项")
                    return valid_items
                elif len(valid_items) > 0:
                    logger.debug(f"   ⚠️ {desc} 只找到 {len(valid_items)} 个，继续尝试...")
            except Exception as e:
                logger.debug(f"   {desc} 失败: {e}")
                continue
        
        logger.warning("⚠️ 所有选择器都未找到足够的公告项")
        return []
    
    def _save_debug_info(self):
        """保存调试信息"""
        try:
            from pathlib import Path
            debug_dir = Path("data/debug")
            debug_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存HTML源码
            html_path = debug_dir / "page_source.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(self.page.html)
            logger.info(f"💾 HTML源码已保存: {html_path}")
            
            # 保存截图
            try:
                screenshot_path = debug_dir / "page_screenshot.png"
                self.page.get_screenshot(path=str(screenshot_path))
                logger.info(f"📸 页面截图已保存: {screenshot_path}")
            except Exception as e:
                logger.warning(f"⚠️ 保存截图失败: {e}")
                
        except Exception as e:
            logger.warning(f"⚠️ 保存调试信息失败: {e}")
    
    def _parse_list_item(self, item):
        """解析列表项（已验证的v2版本 - 正确提取地域和日期）"""
        try:
            # 提取标题链接
            links = item.eles('tag:a')
            if not links:
                return None
            
            link = links[0]
            href = link.attr('href') or ''
            title = link.text.strip()
            
            # 过滤掉非公告链接
            if not href or '/ggxx/info/' not in href:
                return None
            
            # 补全URL
            if href.startswith('/'):
                url = self.base_url + href
            else:
                url = href
            
            # 提取ID（从URL中提取32位hex）
            import re
            id_match = re.search(r'/([a-f0-9]{32})\.html', href)
            announcement_id = id_match.group(1) if id_match else href.split('/')[-1].split('.')[0]
            
            # ✅ 关键修复：使用验证成功的地域提取逻辑
            # HTML结构：<li><a>...</a><span>类型</span><span>地域</span><span>日期</span></li>
            spans = item.eles('tag:span')
            notice_type = '未知公告类型'
            location = '未知'
            date_text = '未知'
            
            try:
                if len(spans) >= 3:
                    # 标准情况：spans[0]=类型, spans[1]=地域, spans[2]=日期
                    notice_type = spans[0].text.strip() or notice_type
                    location = spans[1].text.strip() or location
                    date_text = spans[2].text.strip() or date_text
                elif len(spans) == 2:
                    # 2个span：可能是类型+日期 或 地域+日期
                    first = spans[0].text.strip()
                    second = spans[1].text.strip()
                    if re.match(r'\d{4}-\d{2}-\d{2}$', second):
                        # 视作：类型/地域 + 日期
                        date_text = second
                        # 尝试从第一列中识别“公告”字样作为类型
                        if '公告' in first or '公示' in first:
                            notice_type = first
                        else:
                            location = first
                    else:
                        # 视作：地域 + 其他信息
                        location = first
                        date_text = second
                elif len(spans) == 1:
                    # 只有1个span：可能是日期或类型
                    span_text = spans[0].text.strip()
                    if re.match(r'\d{4}-\d{2}-\d{2}$', span_text):
                        date_text = span_text
                    elif '公告' in span_text or '公示' in span_text:
                        notice_type = span_text
                    else:
                        location = span_text
            except Exception:
                # 解析异常时保留默认值，避免中断
                pass
            
            # 如果日期不是标准格式，尝试提取
            if not re.match(r'\d{4}-\d{2}-\d{2}$', date_text):
                # 从标题提取日期
                date_in_title = re.search(r'(\d{4}-\d{2}-\d{2})', title)
                if date_in_title:
                    date_text = date_in_title.group(1)
                else:
                    # 使用当前日期
                    date_text = datetime.now().strftime('%Y-%m-%d')
            
            return {
                'id': announcement_id,
                'title': title,
                'url': url,
                'pub_date': date_text,
                'publish_date': date_text,  # 统一字段名
                'notice_type_raw': notice_type,
                'location': location,
                'summary': '',
                'crawled_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.debug(f"解析列表项失败: {e}")
            return None
    
    def fetch_detail(self, url):
        """爬取公告详情"""
        logger.debug(f"  🔍 爬取详情: {url[:60]}...")
        
        try:
            self.page.get(url)
            time.sleep(self.wait_page_refresh)  # 可配置的等待时间
            
            # 智能提取内容 - 尝试多种选择器
            content = ''
            selectors = [
                'css:.content',
                'css:.detail',
                'css:.detail-content',
                'css:.article',
                'css:.main-content',
                'css:[class*="content"]',
                'css:[class*="detail"]',
                'css:article',
                'tag:article',
            ]
            
            for selector in selectors:
                try:
                    content_ele = self.page.ele(selector, timeout=0.5)
                    if content_ele:
                        # 获取文本内容（去除HTML标签）
                        content = content_ele.text
                        if len(content) > 50:  # 确保有实质内容
                            logger.debug(f"  ✅ 使用选择器: {selector}, 内容长度: {len(content)}")
                            break
                except:
                    continue
            
            # 如果所有选择器都失败，尝试获取body的文本
            if not content or len(content) < 50:
                try:
                    body = self.page.ele('tag:body', timeout=1)
                    if body:
                        content = body.text
                        logger.debug(f"  ⚠️ 使用body文本, 内容长度: {len(content)}")
                except:
                    logger.warning(f"  ⚠️ 无法提取详情内容")
            
            # 提取附件
            attachments = self._extract_attachments()
            
            return {
                'content': content,
                'attachments': attachments
            }
            
        except Exception as e:
            logger.warning(f"  ❌ 爬取详情失败: {e}")
            return {'content': '', 'attachments': []}
    
    def _extract_attachments(self):
        """提取附件链接"""
        attachments = []
        
        try:
            attachment_links = self.page.eles('tag:a')
            
            for link in attachment_links:
                href = link.attr('href')
                text = link.text.strip()
                
                # 判断是否为附件
                if href and any(ext in href.lower() for ext in ['.pdf', '.doc', '.docx']):
                    # 补全URL
                    if not href.startswith('http'):
                        href = self.base_url + href
                    
                    attachments.append({
                        'name': text or '附件',
                        'url': href
                    })
        except Exception as e:
            logger.debug(f"提取附件失败: {e}")
        
        return attachments
    
    def _generate_id(self, title, date):
        """生成唯一ID"""
        text = f"{title}_{date}"
        return hashlib.md5(text.encode()).hexdigest()
    
    def _random_delay(self):
        """随机延迟"""
        delay_range = self.config['spider'].get('request_delay_range', [2, 5])
        delay = random.uniform(delay_range[0], delay_range[1])
        time.sleep(delay)
    
    def search_by_keyword(
        self,
        keyword: str,
        last_crawl_time: datetime,
        db_manager,
        max_results: int = 200
    ):
        """使用网站搜索框搜索关键词（支持增量爬取）
        
        Args:
            keyword: 搜索关键词
            last_crawl_time: 上次爬取时间
            db_manager: 数据库管理器（用于去重）
            max_results: 最多返回结果数（保护性上限）
            
        Returns:
            公告列表（已去重）
        """
        logger.info(f"🔍 搜索关键词: '{keyword}'")
        logger.info(f"   时间范围: {last_crawl_time.strftime('%Y-%m-%d %H:%M')} → 现在")
        
        if not self.page:
            if not self.init_browser():
                return []
        
        announcements = []
        
        try:
            # 访问列表页
            self.page.get(self.list_url)
            time.sleep(self.wait_page_refresh)
            
            # 查找搜索框并输入关键词
            search_success = self._perform_search(keyword)
            if not search_success:
                logger.warning(f"⚠️ 未找到搜索框或搜索失败")
                return []
            
            # 解析搜索结果（支持翻页）
            page_num = 1
            found_old_announcement = False
            
            while page_num <= 10 and not found_old_announcement:  # 最多爬10页
                logger.info(f"   📄 解析第 {page_num} 页...")
                
                # 等待页面加载
                time.sleep(self.wait_page_refresh)
                
                # 查找公告列表项
                items = self._find_announcement_items()
                if not items:
                    logger.info(f"   ⚠️ 第 {page_num} 页没有找到公告，停止")
                    break
                
                page_count = 0
                for item in items:
                    if len(announcements) >= max_results:
                        logger.info(f"   ⚠️ 已达到最大结果数 {max_results}，停止")
                        found_old_announcement = True
                        break
                    
                    try:
                        announcement = self._parse_list_item(item)
                        if not announcement:
                            continue
                        
                        # 检查时间：如果早于上次爬取时间，停止
                        pub_date = self._parse_date(announcement['pub_date'])
                        if pub_date and pub_date <= last_crawl_time:
                            logger.info(f"   ⏰ 发现旧公告（{announcement['pub_date']}），停止爬取")
                            found_old_announcement = True
                            break
                        
                        # 数据库去重
                        if db_manager.exists(announcement['id']):
                            logger.debug(f"   ⏭️ 跳过重复: {announcement['title'][:30]}...")
                            continue
                        
                        announcements.append(announcement)
                        page_count += 1
                        logger.info(f"   ✅ [{len(announcements)}] {announcement['title'][:50]}...")
                        
                    except Exception as e:
                        logger.warning(f"   ⚠️ 解析公告项失败: {e}")
                        continue
                
                logger.info(f"   第 {page_num} 页: 获取 {page_count} 条新公告")
                
                if found_old_announcement:
                    break
                
                # 尝试翻页
                if not self._goto_next_page():
                    logger.info(f"   ⏹️ 没有下一页，停止")
                    break
                
                page_num += 1
            
            logger.success(f"✅ 关键词 '{keyword}' 搜索完成，获取 {len(announcements)} 条新公告")
            
        except Exception as e:
            logger.error(f"❌ 搜索失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return announcements
    
    def _perform_search(self, keyword: str) -> bool:
        """执行搜索操作
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            True: 搜索成功
            False: 搜索失败
        """
        try:
            # 尝试多种搜索框选择器（优先级从高到低）
            search_selectors = [
                ('css:input[name="key"]', '按name="key"查找（主搜索框）'),
                ('css:input[name="identity"]', '按name="identity"查找（标题搜索框）'),
                ('css:input[id="title"]', '按id="title"查找'),
                ('css:input[id="art-title"]', '按id="art-title"查找'),
                ('css:input[type="text"][placeholder*="查询"]', '按placeholder包含"查询"'),
                ('css:input[type="text"][placeholder*="标题"]', '按placeholder包含"标题"'),
                ('css:input[type="text"][name*="search"]', '按name查找'),
                ('css:.search-input', '按class查找'),
                ('css:#searchInput', '按ID查找'),
            ]
            
            search_box = None
            for selector, desc in search_selectors:
                try:
                    box = self.page.ele(selector, timeout=1)
                    if box:
                        # 排除下拉选择框
                        placeholder = box.attr('placeholder') or ''
                        if '直接选择' in placeholder or '下拉' in placeholder:
                            logger.debug(f"   ⏭️  跳过下拉框: {placeholder}")
                            continue
                        
                        search_box = box
                        logger.info(f"   ✅ 找到搜索框: {desc}")
                        logger.debug(f"      placeholder='{placeholder}'")
                        break
                except:
                    continue
            
            if not search_box:
                logger.warning("   ⚠️ 未找到搜索框")
                return False
            
            # 清空并输入关键词
            search_box.clear()
            search_box.input(keyword)
            time.sleep(self.wait_ajax_load)
            
            # 查找并点击搜索按钮
            submit_button = None
            button_selectors = [
                ('css:button[type="submit"]', '提交按钮'),
                ('css:button.search-btn', '搜索按钮（class）'),
                ('css:.search-button', '搜索按钮（class）'),
                ('css:input[type="submit"]', '提交输入框'),
            ]
            
            for selector, desc in button_selectors:
                try:
                    submit_button = self.page.ele(selector, timeout=1)
                    if submit_button:
                        logger.info(f"   ✅ 找到搜索按钮: {desc}")
                        break
                except:
                    continue
            
            if submit_button:
                submit_button.click()
            else:
                # 如果没找到按钮，尝试回车
                logger.info("   ⚠️ 未找到搜索按钮，尝试回车")
                search_box.input('\n')
            
            time.sleep(self.wait_page_refresh)  # 等待搜索结果加载
            logger.info("   ✅ 搜索提交成功")
            return True
            
        except Exception as e:
            logger.error(f"   ❌ 执行搜索失败: {e}")
            return False
    
    def _goto_next_page(self) -> bool:
        """跳转到下一页（智能等待版本）
        
        注意：军队采购网使用<li>元素实现分页，不是<a>链接
        
        Returns:
            True: 成功翻页
            False: 没有下一页或翻页失败
        """
        try:
            logger.debug("   🔍 正在查找翻页按钮...")
            
            # ✅ 正确的选择器：查找<li>元素（不是<a>）
            next_selectors = [
                ('xpath://div[@id="pagination"]//li[text()=">"]', '下一页(>)'),
                ('css:#pagination li:has-text(">")', '下一页CSS'),
            ]
            
            next_btn = None
            for selector, desc in next_selectors:
                try:
                    btn = self.page.ele(selector, timeout=1)
                    if btn:
                        # 检查是否被禁用
                        btn_class = btn.attr('class') or ''
                        if 'disabled' in btn_class:
                            logger.debug(f"   ⚠️ 按钮已禁用（最后一页）")
                            return False
                        
                        next_btn = btn
                        logger.debug(f"   🔗 找到 {desc}")
                        break
                except:
                    continue
            
            if not next_btn:
                logger.debug("   ⚠️ 未找到下一页按钮")
                return False
            
            # ✅ 智能翻页等待：记录翻页前第一条公告标题
            old_first_title = None
            try:
                old_first_item = self.page.ele('css:ul.noticeShowList li:nth-child(1) a', timeout=2)
                if old_first_item:
                    old_first_title = old_first_item.text
                    logger.debug(f"   📋 翻页前第一条: {old_first_title[:30]}...")
            except:
                pass
            
            # 点击翻页
            logger.debug("   ✅ 准备点击翻页...")
            next_btn.click()
            
            # ✅ 关键：等待公告列表真正刷新（标题变化）
            logger.debug("   ⏳ 等待AJAX刷新公告列表...")
            max_wait = 10  # 最多等待10秒
            waited = 0
            refreshed = False
            
            while waited < max_wait:
                time.sleep(1)
                waited += 1
                
                try:
                    new_first_item = self.page.ele('css:ul.noticeShowList li:nth-child(1) a', timeout=1)
                    if new_first_item:
                        new_first_title = new_first_item.text
                        
                        # 检查标题是否变化
                        if new_first_title and new_first_title != old_first_title:
                            logger.debug(f"   ✅ 列表已刷新（等待{waited}秒）")
                            logger.debug(f"   📋 翻页后第一条: {new_first_title[:30]}...")
                            refreshed = True
                            break
                except:
                    pass
            
            if not refreshed:
                logger.warning(f"   ⚠️ 等待{max_wait}秒后仍未检测到列表刷新")
                # 即使未检测到刷新也继续（可能是页面结构变化）
            
            # 额外等待确保完全加载
            time.sleep(self.wait_ajax_load)
            return True
            
        except Exception as e:
            logger.debug(f"   ❌ 翻页失败: {e}")
            return False
    
    def _parse_date(self, date_str: str) -> datetime:
        """解析日期字符串
        
        Args:
            date_str: 日期字符串（如 "2024-01-15" 或 "2024-01-15 10:30"）
            
        Returns:
            datetime对象，解析失败返回None
        """
        try:
            # 尝试多种日期格式
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except:
                    continue
            return None
        except:
            return None
    
    def fetch_by_filters(
        self,
        date_range=None,
        notice_types=None,
        regions=None,
        max_results=50,
        use_api=True
    ):
        """使用筛选条件爬取公告
        
        Args:
            date_range: 日期范围 (start_date, end_date)
            notice_types: 公告类型列表
            regions: 地区列表
            max_results: 最大结果数
            use_api: 是否使用 API（推荐）
            
        Returns:
            公告列表
        """
        logger.info("🎯 开始使用筛选条件爬取公告")
        
        if use_api:
            # 使用 API 客户端（推荐方式）
            from .api_client import PLAPApiClient
            
            try:
                api_client = PLAPApiClient(self.config)
                announcements = api_client.fetch_announcements(
                    date_range=date_range,
                    notice_types=notice_types,
                    regions=regions,
                    max_results=max_results
                )
                api_client.close()
                
                # 如果 API 返回空结果，尝试降级
                if not announcements:
                    logger.warning("⚠️ API 返回空结果，切换到传统爬取模式")
                    use_api = False
                else:
                    return announcements
                    
            except Exception as e:
                logger.error(f"❌ API 爬取失败: {e}")
                logger.warning("⚠️ 切换到传统爬取模式")
                use_api = False
        
        # 降级到传统爬取方式
        logger.info("🔄 使用传统爬取模式")
        return self.fetch_announcements()
    
    def close(self) -> None:
        """关闭浏览器"""
        if self.page:
            try:
                self.page.quit()
                logger.info("🔚 浏览器已关闭")
            except Exception as e:
                logger.warning(f"关闭浏览器时出错: {e}")
            finally:
                self.page = None
    
    def __enter__(self) -> 'PLAPSpider':
        """上下文管理器入口
        
        使用示例:
            with PLAPSpider(config) as spider:
                announcements = spider.fetch_announcements()
        
        Returns:
            self: PLAPSpider 实例
        """
        self.init_browser()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """上下文管理器退出
        
        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常追踪
            
        Returns:
            False: 不抑制异常，让异常继续传播
        """
        self.close()
        return False  # 不抑制异常
