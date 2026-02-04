"""分析采购大厅页面结构"""

from DrissionPage import ChromiumPage, ChromiumOptions
import time
from pathlib import Path

def analyze_page():
    """分析采购大厅页面"""
    # 配置浏览器
    options = ChromiumOptions()
    options.headless(False)  # 可视化模式
    
    page = ChromiumPage(addr_or_opts=options)
    
    debug_dir = Path("data/debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    print("🔍 分析采购大厅页面结构...")
    print("=" * 80)
    
    try:
        # 访问采购大厅
        url = "https://www.plap.mil.cn/freecms-glht/site/juncai/cggg/index.html"
        print(f"\n📡 访问: {url}")
        page.get(url)
        time.sleep(3)
        
        print(f"✅ 页面标题: {page.title}")
        
        # 保存页面信息
        screenshot_path = debug_dir / "cggg_page.png"
        page.get_screenshot(path=str(screenshot_path))
        print(f"📸 截图: {screenshot_path}")
        
        html_path = debug_dir / "cggg_page.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(page.html)
        print(f"💾 HTML: {html_path}")
        
        # 分析页面结构
        print("\n" + "=" * 80)
        print("📊 页面结构分析:\n")
        
        # 1. 查找表格
        print("1️⃣ 查找表格元素...")
        tables = page.eles('tag:table', timeout=2)
        print(f"   找到 {len(tables)} 个 table 元素")
        
        # 2. 查找列表
        print("\n2️⃣ 查找列表元素...")
        uls = page.eles('tag:ul', timeout=2)
        print(f"   找到 {len(uls)} 个 ul 元素")
        
        # 3. 查找所有链接
        print("\n3️⃣ 查找公告链接...")
        all_links = page.eles('tag:a', timeout=2)
        print(f"   页面共有 {len(all_links)} 个链接")
        
        # 找出看起来像公告的链接
        announcement_links = []
        for link in all_links:
            text = link.text.strip()
            href = link.attr('href')
            
            # 过滤掉导航链接等
            if href and 'ggxx/info' in href and len(text) > 10:
                announcement_links.append({
                    'text': text,
                    'href': href
                })
        
        print(f"   找到 {len(announcement_links)} 个可能的公告链接")
        
        if announcement_links:
            print("\n   前5个公告示例:")
            for i, link in enumerate(announcement_links[:5], 1):
                print(f"   {i}. {link['text'][:60]}...")
                print(f"      URL: {link['href']}")
        
        # 4. 分析公告项的父元素
        print("\n4️⃣ 分析公告项的容器结构...")
        if announcement_links:
            # 获取第一个公告链接的父元素
            first_link_text = announcement_links[0]['text']
            try:
                first_link_ele = page.ele(f'text={first_link_text[:30]}', timeout=2)
                if first_link_ele:
                    # 获取父元素
                    parent = first_link_ele.parent()
                    print(f"   父元素标签: {parent.tag}")
                    print(f"   父元素 class: {parent.attr('class')}")
                    
                    # 获取祖父元素
                    grandparent = parent.parent()
                    print(f"   祖父元素标签: {grandparent.tag}")
                    print(f"   祖父元素 class: {grandparent.attr('class')}")
                    
                    # 尝试找到所有同级元素
                    if grandparent.tag == 'tr':
                        tbody = grandparent.parent()
                        all_rows = tbody.eles('tag:tr')
                        print(f"\n   ✅ 发现表格结构！共 {len(all_rows)} 行")
                        
                        # 分析表格列
                        if len(all_rows) > 0:
                            first_row = all_rows[0]
                            cells = first_row.eles('tag:td')
                            print(f"   表格列数: {len(cells)}")
                            
                            if len(cells) > 0:
                                print("\n   表格结构分析:")
                                for i, cell in enumerate(cells, 1):
                                    print(f"     列 {i}: {cell.text[:50]}...")
                    elif grandparent.tag == 'li':
                        ul = grandparent.parent()
                        all_items = ul.eles('tag:li')
                        print(f"\n   ✅ 发现列表结构！共 {len(all_items)} 项")
                    
            except Exception as e:
                print(f"   ⚠️ 分析容器失败: {e}")
        
        # 5. 查找特定的 CSS 类
        print("\n5️⃣ 查找常见的 CSS 类...")
        common_classes = [
            'list', 'item', 'row', 'announcement', 'notice',
            'table', 'content', 'main', 'cggg', 'result'
        ]
        
        for cls in common_classes:
            elements = page.eles(f'css:[class*="{cls}"]', timeout=1)
            if elements:
                print(f"   .{cls}* : 找到 {len(elements)} 个元素")
        
        print("\n" + "=" * 80)
        print("💡 建议:")
        print("   1. 查看生成的截图和 HTML 文件")
        print("   2. 根据上述分析结果调整爬虫选择器")
        print("   3. 如果是表格结构，使用 'tag:tr' 选择器")
        print("   4. 如果是列表结构，使用 'tag:li' 选择器")
        
        print("\n按 Enter 关闭...")
        input()
        
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        page.quit()
        print("🔚 浏览器已关闭")


if __name__ == "__main__":
    analyze_page()
