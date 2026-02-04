"""军队采购网爬虫"""

from DrissionPage import ChromiumPage, ChromiumOptions
from loguru import logger
import time
import random
import hashlib
from datetime import datetime


class PLAPSpider:
    """军队采购网爬虫"""
    
    def __init__(self, config):
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
    
    def fetch_announcements(self, max_pages=3):
        """爬取招标公告列表"""
        logger.info(f"🔍 开始爬取招标公告: {self.list_url}")
        
        if not self.page:
            if not self.init_browser():
                return []
        
        announcements = []
        
        try:
            # 访问列表页
            self.page.get(self.list_url)
            time.sleep(3)  # 增加等待时间
            
            # 保存调试信息
            self._save_debug_info()
            
            # 智能查找公告列表项
            items = self._find_announcement_items()
            
            if not items:
                logger.warning("⚠️ 未找到任何公告列表项")
                logger.info("💡 请查看 data/debug/ 目录下的调试文件")
                return []
            
            logger.info(f"📄 找到 {len(items)} 个公告项")
            
            for item in items[:50]:  # 限制数量
                try:
                    announcement = self._parse_list_item(item)
                    if announcement:
                        announcements.append(announcement)
                        logger.info(f"📄 发现公告: {announcement['title']}")
                except Exception as e:
                    logger.warning(f"⚠️ 解析公告项失败: {e}")
                    continue
                
                # 随机延迟
                self._random_delay()
            
            logger.success(f"✅ 爬取完成，共 {len(announcements)} 条公告")
            
        except Exception as e:
            logger.error(f"❌ 爬取失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return announcements
    
    def _find_announcement_items(self):
        """智能查找公告列表项"""
        logger.info("🔍 开始智能查找公告项...")
        
        # 策略1: 尝试查找表格行或列表项
        selectors = [
            ('css:table tbody tr', '表格行'),
            ('css:table tr', '表格行（无tbody）'),
            ('css:ul li', '列表项'),
            ('css:.result-list tr', '结果列表表格行'),
            ('css:.result-list li', '结果列表项'),
            ('css:[class*="list"] tr', '包含list的表格行'),
            ('css:[class*="result"] tr', '包含result的表格行'),
        ]
        
        for selector, desc in selectors:
            try:
                items = self.page.eles(selector, timeout=1)
                if not items:
                    continue
                
                # 过滤出包含公告链接的项
                valid_items = []
                for item in items:
                    link = item.ele('tag:a', timeout=0.5)
                    if link:
                        href = link.attr('href')
                        # 只保留包含公告路径的链接
                        if href and '/ggxx/info/' in href:
                            valid_items.append(item)
                
                if len(valid_items) >= 5:  # 至少要有5个有效项
                    logger.info(f"✅ 使用选择器成功: {selector} ({desc}) - 找到 {len(valid_items)} 个公告项")
                    return valid_items
                elif len(valid_items) > 0:
                    logger.info(f"⚠️ {desc} 只找到 {len(valid_items)} 个公告项，继续尝试...")
            except Exception as e:
                logger.debug(f"  {desc} 选择器失败: {e}")
                continue
        
        # 策略2: 直接查找所有公告链接，并将它们作为"项"
        logger.info("🔍 策略2: 直接查找公告链接...")
        try:
            all_links = self.page.eles('tag:a', timeout=2)
            logger.info(f"📝 页面共有 {len(all_links)} 个链接")
            
            # 过滤出公告链接
            announcement_links = []
            for link in all_links:
                href = link.attr('href')
                text = link.text.strip()
                
                # 只保留公告链接
                if href and '/ggxx/info/' in href and len(text) > 10:
                    announcement_links.append(link)
            
            if len(announcement_links) > 0:
                logger.info(f"✅ 找到 {len(announcement_links)} 个公告链接")
                
                # 显示前5个示例
                logger.info("📋 前5个公告示例:")
                for i, link in enumerate(announcement_links[:5], 1):
                    text = link.text.strip()
                    logger.info(f"  {i}. {text[:60]}...")
                
                return announcement_links
            else:
                logger.warning("⚠️ 未找到任何公告链接（包含 /ggxx/info/ 路径）")
                
                # 输出所有链接供调试
                logger.info("📝 页面所有链接（前20个）:")
                for i, link in enumerate(all_links[:20], 1):
                    text = link.text.strip()
                    href = link.attr('href')
                    if text:
                        logger.info(f"  {i}. {text[:50]} -> {href}")
                
                return []
            
        except Exception as e:
            logger.error(f"❌ 查找链接失败: {e}")
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
        """解析列表项"""
        try:
            # 提取标题链接
            title_ele = item.ele('tag:a', timeout=1)
            if not title_ele:
                return None
            
            title = title_ele.text.strip()
            url = title_ele.attr('href')
            
            # 过滤掉非公告链接
            if not url or '/ggxx/info/' not in url:
                return None
            
            # 补全URL
            if url and not url.startswith('http'):
                url = self.base_url + url
            
            # 提取日期 - 尝试多种方式
            date_text = ''
            try:
                # 方式1: 查找包含日期的单元格
                date_ele = item.ele('css:.date', timeout=0.5)
                if date_ele:
                    date_text = date_ele.text.strip()
            except:
                pass
            
            if not date_text:
                try:
                    # 方式2: 如果是表格行，获取最后一列（通常是日期）
                    if item.tag == 'tr':
                        cells = item.eles('tag:td', timeout=0.5)
                        if len(cells) > 0:
                            # 通常日期在最后一列
                            date_text = cells[-1].text.strip()
                except:
                    pass
            
            if not date_text:
                try:
                    # 方式3: 从标题文本中提取日期（如果标题包含日期）
                    import re
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', title)
                    if date_match:
                        date_text = date_match.group(1)
                except:
                    pass
            
            # 如果还是没有日期，使用当前日期
            if not date_text or len(date_text) < 8:
                date_text = datetime.now().strftime('%Y-%m-%d')
            
            # 提取摘要（如果有）
            summary = ''
            try:
                if item.tag == 'tr':
                    cells = item.eles('tag:td', timeout=0.5)
                    # 摘要通常在第二列或第三列
                    if len(cells) > 1:
                        for cell in cells[1:-1]:  # 跳过第一列（标题）和最后一列（日期）
                            text = cell.text.strip()
                            if text and len(text) > 5 and text != title:
                                summary = text
                                break
            except:
                pass
            
            # 生成唯一ID
            announcement_id = self._generate_id(title, date_text)
            
            return {
                'id': announcement_id,
                'title': title,
                'url': url,
                'pub_date': date_text,
                'summary': summary,
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
            time.sleep(1)  # 减少等待时间以加快速度
            
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
            time.sleep(2)
            
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
                time.sleep(2)
                
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
            # 尝试多种搜索框选择器
            search_selectors = [
                ('css:input[type="text"][name*="search"]', '按name查找'),
                ('css:input[type="text"][placeholder*="搜索"]', '按placeholder查找'),
                ('css:input[type="text"][placeholder*="关键"]', '按placeholder查找'),
                ('css:.search-input', '按class查找'),
                ('css:#searchInput', '按ID查找'),
                ('css:input[type="text"]', '通用文本输入框'),
            ]
            
            search_box = None
            for selector, desc in search_selectors:
                try:
                    search_box = self.page.ele(selector, timeout=1)
                    if search_box:
                        logger.info(f"   ✅ 找到搜索框: {desc}")
                        break
                except:
                    continue
            
            if not search_box:
                logger.warning("   ⚠️ 未找到搜索框")
                return False
            
            # 清空并输入关键词
            search_box.clear()
            search_box.input(keyword)
            time.sleep(0.5)
            
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
            
            time.sleep(2)  # 等待搜索结果加载
            logger.info("   ✅ 搜索提交成功")
            return True
            
        except Exception as e:
            logger.error(f"   ❌ 执行搜索失败: {e}")
            return False
    
    def _goto_next_page(self) -> bool:
        """跳转到下一页
        
        Returns:
            True: 成功翻页
            False: 没有下一页或翻页失败
        """
        try:
            # 尝试多种下一页选择器
            next_selectors = [
                ('css:a.next', '下一页链接（class=next）'),
                ('css:a[title="下一页"]', '下一页链接（title）'),
                ('css:a:contains("下一页")', '下一页链接（文本）'),
                ('css:a:contains(">")', '下一页链接（>符号）'),
                ('css:.pagination a:last-child', '分页最后一个链接'),
            ]
            
            for selector, desc in next_selectors:
                try:
                    next_btn = self.page.ele(selector, timeout=1)
                    if next_btn:
                        # 检查是否被禁用
                        if 'disabled' in next_btn.attr('class'):
                            return False
                        
                        logger.debug(f"   ✅ 找到下一页按钮: {desc}")
                        next_btn.click()
                        time.sleep(2)
                        return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            logger.debug(f"   翻页失败: {e}")
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
    
    def close(self):
        """关闭浏览器"""
        if self.page:
            self.page.quit()
            logger.info("🔚 浏览器已关闭")
