"""
共享工具函数 - 避免重复代码
"""

from DrissionPage import ChromiumPage
import time
import re

def wait_and_load_page(page, url, max_retries=3):
    """
    加载页面并等待AJAX完成（带重试机制）
    
    Args:
        page: DrissionPage对象
        url: 目标URL
        max_retries: 最大重试次数
    
    Returns:
        bool: 是否成功加载
    """
    for retry in range(max_retries):
        if retry > 0:
            print(f"\n🔄 第 {retry + 1} 次尝试...")
        
        print(f"📡 访问: {url}")
        try:
            page.get(url)
        except Exception as e:
            print(f"   ❌ 页面访问失败: {e}")
            if retry < max_retries - 1:
                time.sleep(2)
                continue
            return False
        
        print("⏳ 等待页面基础加载...")
        time.sleep(3)
        
        # 关键：等待AJAX加载完成 - 等待公告列表出现
        print("⏳ 等待公告列表加载（AJAX异步）...")
        ajax_loaded = False
        try:
            # 等待第一个公告链接出现（最多20秒）
            page.wait.ele_displayed('css:ul.noticeShowList li a', timeout=20)
            print("   ✅ 公告列表已加载")
            ajax_loaded = True
        except Exception as e:
            print(f"   ⚠️ 等待超时，可能AJAX请求失败: {e}")
            print("   💡 尝试手动触发...")
            # 有时候滚动可以触发加载
            try:
                page.scroll.to_bottom()
                time.sleep(3)
                page.scroll.to_top()
                time.sleep(3)
            except:
                pass
        
        # 诊断：检查公告列表状态
        print("\n🔍 诊断公告列表...")
        try:
            notice_list = page.ele('css:ul.noticeShowList', timeout=2)
            if notice_list:
                print("   ✅ 找到公告列表容器")
                
                # 检查是否有<li>
                lis = notice_list.eles('tag:li')
                print(f"   包含 {len(lis)} 个<li>元素")
                
                if len(lis) == 0:
                    print("   ❌ 列表为空！AJAX可能未加载")
                    
                    # 如果还有重试机会，继续
                    if retry < max_retries - 1:
                        print(f"   💡 将在2秒后重试...")
                        time.sleep(2)
                        continue
                    return False
                else:
                    print("   ✅ 列表有内容，继续处理")
                    return True
            else:
                print("   ❌ 未找到公告列表容器")
                if retry < max_retries - 1:
                    time.sleep(2)
                    continue
                return False
        except Exception as e:
            print(f"   ❌ 诊断失败: {e}")
            if retry < max_retries - 1:
                time.sleep(2)
                continue
            return False
    
    print(f"\n❌ 尝试{max_retries}次后仍然失败")
    return False

def find_announcement_items(page):
    """查找公告项（统一的选择器逻辑）"""
    selectors = [
        ('css:ul.noticeShowList li', '公告列表项'),
    ]
    
    for selector, desc in selectors:
        try:
            items = page.eles(selector)
            # 过滤：必须包含链接
            valid_items = []
            for item in items:
                links = item.eles('tag:a')
                if links:
                    link = links[0]
                    href = link.attr('href') or ''
                    if '/ggxx/info/' in href:
                        valid_items.append(item)
            
            if valid_items:
                print(f"   ✅ 使用 {desc} - 找到 {len(valid_items)} 个有效公告项")
                return valid_items
        except Exception as e:
            print(f"   ⚠️ {desc} 失败: {e}")
            continue
    
    return []

def parse_list_item_v2(item):
    """解析列表项（v2版本 - 改进的日期提取）"""
    from datetime import datetime
    
    try:
        # 提取链接
        links = item.eles('tag:a')
        if not links:
            return None
        
        link = links[0]
        href = link.attr('href') or ''
        title_text = link.text.strip()
        
        if not href or not title_text:
            return None
        
        # 构建完整URL
        if href.startswith('/'):
            full_url = f"https://www.plap.mil.cn{href}"
        else:
            full_url = href
        
        # 提取ID
        id_match = re.search(r'/([a-f0-9]{32})\.html', href)
        ann_id = id_match.group(1) if id_match else href.split('/')[-1].split('.')[0]
        
        # 提取地域和日期（从span）
        spans = item.eles('tag:span')
        location = '未知'
        publish_date = '未知'
        
        # ✅ 使用test_02的成功经验：spans[0]=项目编号, spans[1]=地域, spans[2]=日期
        try:
            if len(spans) >= 3:
                # 标准情况：3个span
                location = spans[1].text.strip()
                publish_date = spans[2].text.strip()
            elif len(spans) == 2:
                # 2个span：可能是地域+日期
                location = spans[0].text.strip()
                publish_date = spans[1].text.strip()
            elif len(spans) == 1:
                # 只有1个span：可能是日期
                span_text = spans[0].text.strip()
                if re.match(r'\d{4}-\d{2}-\d{2}$', span_text):
                    publish_date = span_text
                else:
                    location = span_text
        except:
            pass
        
        # 如果日期不是标准格式，尝试提取
        if not re.match(r'\d{4}-\d{2}-\d{2}$', publish_date):
            # 从标题提取日期
            date_in_title = re.search(r'(\d{4}-\d{2}-\d{2})', title_text)
            if date_in_title:
                publish_date = date_in_title.group(1)
            else:
                # 使用当前日期
                publish_date = datetime.now().strftime('%Y-%m-%d')
        
        return {
            'id': ann_id,
            'title': title_text,
            'url': full_url,
            'publish_date': publish_date,
            'location': location
        }
        
    except Exception as e:
        return None
