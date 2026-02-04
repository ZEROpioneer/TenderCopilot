"""
军队采购网 API 客户端
直接调用网站的 REST API 接口获取筛选后的公告数据
"""

import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import requests
from loguru import logger


class PLAPApiClient:
    """军队采购网 API 客户端"""
    
    def __init__(self, config: Dict):
        """初始化 API 客户端
        
        Args:
            config: 配置字典，包含 filter_settings
        """
        self.config = config
        self.filter_config = config.get('filter_settings', {})
        
        # API 配置
        api_config = self.filter_config.get('api', {})
        self.base_url = api_config.get('base_url', 'https://www.plap.mil.cn')
        self.endpoint = api_config.get('endpoint', '/rest/v1/notice/selectInfoMoreChannel.do')
        self.timeout = api_config.get('timeout', 30)
        
        # 请求头
        self.headers = {
            'User-Agent': config['spider'].get('user_agent', 
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': f'{self.base_url}/freecms-glht/site/juncai/cggg/index.html'
        }
        
        # 会话
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        logger.info("✅ API 客户端初始化成功")
    
    def fetch_announcements(
        self,
        date_range: Optional[tuple] = None,
        notice_types: Optional[List[str]] = None,
        regions: Optional[List[str]] = None,
        max_results: int = 50
    ) -> List[Dict]:
        """使用 API 获取筛选后的公告列表
        
        Args:
            date_range: 日期范围 (start_date, end_date)，格式 'YYYY-MM-DD'
            notice_types: 公告类型列表
            regions: 地区列表
            max_results: 最大结果数
            
        Returns:
            公告列表
        """
        logger.info("📡 使用 API 获取公告列表")
        
        # 构建筛选条件
        filters = self._build_filters(date_range, notice_types, regions)
        
        # 分页配置
        pagination = self.filter_config.get('crawl_strategy', {}).get('pagination', {})
        page_size = pagination.get('page_size', 50)
        max_pages = pagination.get('max_pages', 10)
        
        all_announcements = []
        page = 1
        
        while page <= max_pages and len(all_announcements) < max_results:
            logger.info(f"  📄 正在获取第 {page} 页...")
            
            # 添加分页参数
            filters['pageNo'] = page
            filters['pageSize'] = page_size
            
            try:
                # 发送请求
                results = self._request_api(filters)
                
                if not results:
                    logger.info(f"  ℹ️ 第 {page} 页无数据，停止翻页")
                    break
                
                # 解析结果
                parsed = self._parse_api_response(results)
                all_announcements.extend(parsed)
                
                logger.info(f"  ✅ 第 {page} 页获取 {len(parsed)} 条公告")
                
                # 如果返回数量少于页大小，说明已到最后一页
                if len(parsed) < page_size:
                    logger.info(f"  ℹ️ 已到最后一页")
                    break
                
                page += 1
                
                # 请求延迟
                delay = random.uniform(*self.config['spider']['request_delay_range'])
                time.sleep(delay)
                
            except Exception as e:
                logger.error(f"  ❌ 第 {page} 页获取失败: {e}")
                break
        
        # 限制结果数量
        if len(all_announcements) > max_results:
            all_announcements = all_announcements[:max_results]
        
        logger.info(f"✅ API 共获取 {len(all_announcements)} 条公告")
        return all_announcements
    
    def _build_filters(
        self,
        date_range: Optional[tuple],
        notice_types: Optional[List[str]],
        regions: Optional[List[str]]
    ) -> Dict[str, Any]:
        """构建 API 请求的筛选参数
        
        Args:
            date_range: 日期范围
            notice_types: 公告类型列表
            regions: 地区列表
            
        Returns:
            API 请求参数字典
        """
        params = {}
        
        # 日期范围
        if date_range:
            start_date, end_date = date_range
            params['startDate'] = start_date
            params['endDate'] = end_date
            logger.info(f"  📅 日期范围: {start_date} ~ {end_date}")
        
        # 公告类型
        if notice_types:
            # 转换为类型代码
            type_codes = self._get_notice_type_codes(notice_types)
            if type_codes:
                params['noticeType'] = ','.join(type_codes)
                logger.info(f"  📋 公告类型: {', '.join(notice_types)}")
        
        # 地区
        if regions:
            # 转换为地区代码
            region_codes = self._get_region_codes(regions)
            if region_codes:
                params['region'] = ','.join(region_codes)
                logger.info(f"  📍 地区: {', '.join(regions)}")
        
        return params
    
    def _request_api(self, params: Dict[str, Any]) -> Optional[Dict]:
        """发送 API 请求
        
        Args:
            params: 请求参数
            
        Returns:
            API 响应数据，失败返回 None
        """
        url = f"{self.base_url}{self.endpoint}"
        
        try:
            response = self.session.post(
                url,
                data=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ API 请求失败: {e}")
            return None
        except ValueError as e:
            logger.error(f"❌ JSON 解析失败: {e}")
            return None
    
    def _parse_api_response(self, data: Dict) -> List[Dict]:
        """解析 API 响应数据
        
        Args:
            data: API 响应数据
            
        Returns:
            公告列表
        """
        announcements = []
        
        try:
            # 根据实际 API 响应结构调整
            # 常见的结构: {"code": 200, "data": {"list": [...]}}
            if 'data' in data:
                items = data['data'].get('list', []) or data['data'].get('records', [])
            elif 'list' in data:
                items = data['list']
            elif 'records' in data:
                items = data['records']
            else:
                items = data if isinstance(data, list) else []
            
            for item in items:
                try:
                    announcement = self._parse_announcement_item(item)
                    if announcement:
                        announcements.append(announcement)
                except Exception as e:
                    logger.warning(f"⚠️ 解析公告项失败: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"❌ 解析 API 响应失败: {e}")
        
        return announcements
    
    def _parse_announcement_item(self, item: Dict) -> Optional[Dict]:
        """解析单个公告项
        
        Args:
            item: API 返回的公告项
            
        Returns:
            标准化的公告字典
        """
        try:
            # 根据实际 API 字段调整
            announcement = {
                'title': item.get('title', '').strip(),
                'url': self._build_detail_url(item),
                'publish_date': item.get('publishDate', item.get('createTime', '')),
                'notice_type': item.get('noticeType', item.get('type', '')),
                'region': item.get('region', item.get('area', '')),
                'source': '军队采购网',
                'id': item.get('id', ''),
                'summary': item.get('summary', item.get('abstract', '')),
            }
            
            # 数据质量控制
            if not self._validate_announcement(announcement):
                return None
            
            return announcement
            
        except Exception as e:
            logger.warning(f"⚠️ 解析公告项失败: {e}")
            return None
    
    def _build_detail_url(self, item: Dict) -> str:
        """构建详情页 URL
        
        Args:
            item: 公告项
            
        Returns:
            详情页 URL
        """
        # 方法 1: 直接从 item 中获取
        if 'url' in item:
            url = item['url']
            if url.startswith('http'):
                return url
            else:
                return f"{self.base_url}{url}"
        
        # 方法 2: 根据 ID 构建
        if 'id' in item:
            return f"{self.base_url}/ggxx/info/{item['id']}.html"
        
        # 方法 3: 根据链接字段构建
        link = item.get('link', item.get('href', ''))
        if link:
            if link.startswith('http'):
                return link
            else:
                return f"{self.base_url}{link}"
        
        return ''
    
    def _validate_announcement(self, announcement: Dict) -> bool:
        """验证公告数据质量
        
        Args:
            announcement: 公告字典
            
        Returns:
            是否通过验证
        """
        quality_config = self.filter_config.get('quality_control', {})
        
        # 检查必填字段
        if not announcement.get('title'):
            return False
        
        # 检查标题长度
        min_length = quality_config.get('min_title_length', 10)
        if len(announcement['title']) < min_length:
            logger.debug(f"⏭️ 标题过短: {announcement['title']}")
            return False
        
        # 过滤测试公告
        if quality_config.get('filter_test_announcements', True):
            title = announcement['title'].lower()
            test_keywords = quality_config.get('test_keywords', [])
            for keyword in test_keywords:
                if keyword.lower() in title:
                    logger.debug(f"⏭️ 测试公告: {announcement['title']}")
                    return False
        
        return True
    
    def _get_notice_type_codes(self, notice_types: List[str]) -> List[str]:
        """获取公告类型代码
        
        Args:
            notice_types: 公告类型名称列表
            
        Returns:
            类型代码列表
        """
        type_codes_map = self.filter_config.get('notice_type_codes', {})
        codes = []
        
        for notice_type in notice_types:
            code = type_codes_map.get(notice_type)
            if code:
                codes.append(code)
            else:
                logger.warning(f"⚠️ 未找到公告类型代码: {notice_type}")
        
        return codes
    
    def _get_region_codes(self, regions: List[str]) -> List[str]:
        """获取地区代码
        
        Args:
            regions: 地区名称列表
            
        Returns:
            地区代码列表
        """
        region_codes_map = self.filter_config.get('region_codes', {})
        codes = []
        
        for region in regions:
            code = region_codes_map.get(region)
            if code:
                codes.append(code)
            else:
                logger.warning(f"⚠️ 未找到地区代码: {region}")
        
        return codes
    
    def close(self):
        """关闭会话"""
        if self.session:
            self.session.close()
            logger.info("🔒 API 客户端已关闭")
