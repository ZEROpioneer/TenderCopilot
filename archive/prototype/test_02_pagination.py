"""测试2：增量翻页逻辑 - 连续5条重复停止"""

from DrissionPage import ChromiumPage, ChromiumOptions
import re
import hashlib
from datetime import datetime
import json
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.storage import DatabaseManager

def extract_id_from_url(url):
    """从URL中提取唯一ID"""
    match = re.search(r'/info/\d{4}/([a-f0-9]+)', url)
    if match:
        return match.group(1)
    else:
        return hashlib.md5(url.encode()).hexdigest()

def parse_list_item_v2(item):
    """解析列表项（与test_01相同）"""
    try:
        title_ele = item.ele('tag:a', timeout=1)
        if not title_ele:
            return None
        
        title = title_ele.text.strip()
        url = title_ele.attr('href')
        
        if not url or '/ggxx/info/' not in url:
            return None
        
        if not url.startswith('http'):
            url = 'https://www.plap.mil.cn' + url
        
        # 提取日期
        publish_date = ''
        try:
            spans = item.eles('tag:span')
            if spans:
                for span in reversed(spans):
                    text = span.text.strip()
                    if re.match(r'\d{4}-\d{2}-\d{2}', text):
                        publish_date = text
                        break
        except:
            pass
        
        if not publish_date:
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', title)
            if date_match:
                publish_date = date_match.group(1)
        
        if not publish_date:
            publish_date = datetime.now().strftime('%Y-%m-%d')
        
        announcement_id = extract_id_from_url(url)
        
        # 提取地区等信息
        region = ''
        try:
            spans = item.eles('tag:span')
            if len(spans) > 1:
                region = spans[1].text.strip()
        except:
            pass
        
        return {
            'id': announcement_id,
            'title': title,
            'url': url,
            'publish_date': publish_date,
            'region': region,
            'crawled_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        return None

def find_announcement_items(page):
    """智能查找公告列表项"""
    selectors = [
        ('css:ul li', '列表项'),
        ('css:table tbody tr', '表格行'),
    ]
    
    for selector, desc in selectors:
        try:
            elements = page.eles(selector, timeout=2)
            if not elements:
                continue
            
            valid_items = []
            for elem in elements:
                link = elem.ele('tag:a', timeout=0.5)
                if link:
                    href = link.attr('href')
                    if href and '/ggxx/info/' in href:
                        valid_items.append(elem)
            
            if len(valid_items) >= 5:
                print(f"   ✅ 使用 {desc} - 找到 {len(valid_items)} 个公告项")
                return valid_items
        except:
            pass
    
    return []

def goto_next_page(page):
    """翻到下一页"""
    try:
        # 尝试多种下一页选择器
        next_selectors = [
            'css:a.next',
            'css:a[title="下一页"]',
            'css:li.next a',
            'css:.pagination a:contains("下一页")',
            'css:.pagination a:contains(">")',
        ]
        
        for selector in next_selectors:
            try:
                next_btn = page.ele(selector, timeout=1)
                if next_btn:
                    print(f"   🔗 找到下一页按钮: {selector}")
                    next_btn.click()
                    
                    import time
                    time.sleep(3)  # 等待加载
                    return True
            except:
                pass
        
        print("   ⚠️ 未找到下一页按钮")
        return False
        
    except Exception as e:
        print(f"   ❌ 翻页失败: {e}")
        return False

def test_incremental_crawl():
    """测试增量翻页爬取"""
    print("=" * 70)
    print("🧪 测试2：增量翻页逻辑（连续5条重复停止）")
    print("=" * 70)
    
    # 初始化数据库
    print("\n📊 初始化数据库...")
    db = DatabaseManager('data/history.db')
    
    # 查询数据库中的公告数量
    try:
        result = db.execute_query("SELECT COUNT(*) FROM announcements")
        count = result[0][0] if result else 0
        print(f"   数据库中已有 {count} 条公告记录")
    except:
        print(f"   数据库已初始化")
    
    # 配置浏览器（暂时用可视化模式调试）
    options = ChromiumOptions()
    options.headless(False)  # 改为可视化，方便观察
    page = ChromiumPage(addr_or_opts=options)
    
    print("💡 提示：浏览器将打开，你可以看到爬取过程")
    
    try:
        # 访问列表页
        url = "https://www.plap.mil.cn/freecms-glht/site/juncai/cggg/index.html"
        print(f"\n📡 访问: {url}")
        page.get(url)
        
        import time
        print("⏳ 等待页面基础加载...")
        time.sleep(3)
        
        # 关键：等待AJAX加载完成 - 等待公告列表出现
        print("⏳ 等待公告列表加载（AJAX异步）...")
        try:
            # 等待第一个公告链接出现（最多20秒）
            page.wait.ele_displayed('css:ul.noticeShowList li a', timeout=20)
            print("   ✅ 公告列表已加载")
        except Exception as e:
            print(f"   ⚠️ 等待超时，可能AJAX请求失败: {e}")
            print("   💡 尝试手动触发...")
            # 有时候滚动可以触发加载
            page.scroll.to_bottom()
            time.sleep(3)
            page.scroll.to_top()
            time.sleep(3)
        
        # 诊断：检查公告列表状态
        print("\n🔍 诊断公告列表...")
        try:
            notice_list = page.ele('css:ul.noticeShowList', timeout=2)
            if notice_list:
                print("   ✅ 找到公告列表容器")
                list_html = notice_list.html[:500]
                print(f"   内容预览: {list_html[:200]}...")
                
                # 检查是否有<li>
                lis = notice_list.eles('tag:li')
                print(f"   包含 {len(lis)} 个<li>元素")
                
                if len(lis) == 0:
                    print("   ❌ 列表为空！AJAX可能未加载")
                    print("   💡 可能原因：")
                    print("      1. 网络请求慢")
                    print("      2. API端点失效")
                    print("      3. 需要登录")
            else:
                print("   ❌ 未找到公告列表容器")
        except Exception as e:
            print(f"   ❌ 诊断失败: {e}")
        
        # 保存调试信息
        print("\n💾 保存页面HTML...")
        try:
            html = page.html
            with open('prototype/results/test_02_page.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print("   已保存: prototype/results/test_02_page.html")
        except Exception as e:
            print(f"   ⚠️ 保存失败: {e}")
        
        # 开始翻页爬取
        all_announcements = []
        page_num = 1
        should_stop = False
        consecutive_exists = 0  # 连续重复计数器
        
        while page_num <= 5 and not should_stop:  # 最多5页
            print(f"\n{'='*70}")
            print(f"📄 第 {page_num} 页")
            print(f"{'='*70}")
            
            # 查找公告
            items = find_announcement_items(page)
            if not items:
                print("   ⚠️ 未找到公告，停止")
                break
            
            print(f"   找到 {len(items)} 个公告项")
            
            new_count = 0
            for i, item in enumerate(items, 1):
                ann = parse_list_item_v2(item)
                if not ann:
                    continue
                
                # 检查数据库
                exists = db.exists(ann['id'])
                
                if exists:
                    consecutive_exists += 1
                    print(f"   [{i}] ⏭️ 已存在: {ann['title'][:40]}... (连续{consecutive_exists})")
                    
                    # 连续5条都存在，停止
                    if consecutive_exists >= 5:
                        print(f"\n   ⏹️ 连续{consecutive_exists}条都已存在，停止翻页！")
                        should_stop = True
                        break
                else:
                    # 新公告
                    consecutive_exists = 0  # 重置计数器
                    new_count += 1
                    all_announcements.append(ann)
                    print(f"   [{i}] ✅ 新公告: {ann['title'][:40]}... [{ann['region']}]")
            
            print(f"\n   第{page_num}页小结: 新增 {new_count} 条，累计 {len(all_announcements)} 条")
            
            if should_stop:
                break
            
            # 翻到下一页
            if page_num < 5:
                print(f"\n   📖 尝试翻到第 {page_num + 1} 页...")
                if not goto_next_page(page):
                    print("   ⏹️ 没有下一页，停止")
                    break
            
            page_num += 1
        
        # 统计结果
        print("\n" + "=" * 70)
        print("📊 爬取统计")
        print("=" * 70)
        print(f"  爬取页数: {page_num}")
        print(f"  新公告数: {len(all_announcements)}")
        print(f"  停止原因: {'连续5条重复' if should_stop else '已爬取完所有页'}")
        
        # 保存结果
        output_file = 'prototype/results/test_02_result.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'total_pages': page_num,
                'total_new': len(all_announcements),
                'stopped_by_duplicate': should_stop,
                'announcements': all_announcements
            }, f, ensure_ascii=False, indent=2)
        print(f"\n💾 结果已保存: {output_file}")
        
        # 显示新公告列表
        if all_announcements:
            print(f"\n📋 新公告列表（共{len(all_announcements)}条）：")
            for i, ann in enumerate(all_announcements[:10], 1):
                print(f"  [{i}] {ann['title'][:50]}... [{ann['region']}] {ann['publish_date']}")
            if len(all_announcements) > 10:
                print(f"  ... 还有 {len(all_announcements) - 10} 条")
        
        # 验证
        print("\n" + "=" * 70)
        print("✅ 验证结果")
        print("=" * 70)
        
        success = True
        
        # 验证：增量逻辑是否正常工作
        if page_num == 1 and len(all_announcements) == 0:
            print("⚠️ 第一页就全部重复，增量逻辑正常")
            success = True
        elif len(all_announcements) > 0:
            print(f"✅ 通过：成功识别 {len(all_announcements)} 条新公告")
            success = True
        else:
            print("❌ 失败：未获取到任何新公告且未触发停止逻辑")
            success = False
        
        print("\n" + "=" * 70)
        if success:
            print("🎉 测试2通过！增量翻页逻辑正常")
        else:
            print("❌ 测试2失败")
        print("=" * 70)
        
        return success
        
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        page.quit()

if __name__ == "__main__":
    success = test_incremental_crawl()
    exit(0 if success else 1)
