"""
诊断翻页功能
- 查找所有可能的翻页元素
- 保存页面HTML用于分析
- 测试翻页点击
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DrissionPage import ChromiumPage, ChromiumOptions
import time

# 导入共享工具
from prototype.common_utils import wait_and_load_page

def debug_pagination():
    """诊断翻页功能"""
    print("=" * 70)
    print("🔍 翻页功能诊断")
    print("=" * 70)
    
    options = ChromiumOptions()
    options.headless(False)  # 可见模式，方便观察
    page = ChromiumPage(options)
    
    try:
        url = "https://www.plap.mil.cn/freecms-glht/site/juncai/cggg/index.html"
        success = wait_and_load_page(page, url)
        
        if not success:
            print("❌ 页面加载失败")
            return
        
        print("\n" + "=" * 70)
        print("🔍 查找所有分页相关元素")
        print("=" * 70)
        
        # 1. 查找所有包含"下一页"文本的元素
        print("\n1️⃣ 查找包含'下一页'文本的元素...")
        try:
            next_elements = page.eles('xpath://a[contains(text(), "下一页")]')
            if next_elements:
                print(f"   ✅ 找到 {len(next_elements)} 个")
                for i, elem in enumerate(next_elements[:3], 1):
                    print(f"      [{i}] class={elem.attr('class')}, id={elem.attr('id')}")
                    print(f"          href={elem.attr('href')}")
            else:
                print("   ❌ 未找到")
        except:
            print("   ❌ 查找失败")
        
        # 2. 查找所有包含">"的链接
        print("\n2️⃣ 查找包含'>'文本的链接...")
        try:
            next_elements = page.eles('xpath://a[contains(text(), ">")]')
            if next_elements:
                print(f"   ✅ 找到 {len(next_elements)} 个")
                for i, elem in enumerate(next_elements[:3], 1):
                    print(f"      [{i}] class={elem.attr('class')}, id={elem.attr('id')}")
            else:
                print("   ❌ 未找到")
        except:
            print("   ❌ 查找失败")
        
        # 3. 查找layui分页
        print("\n3️⃣ 查找layui分页元素...")
        try:
            layui_next = page.eles('css:.layui-laypage-next')
            if layui_next:
                print(f"   ✅ 找到 {len(layui_next)} 个layui-laypage-next")
                for i, elem in enumerate(layui_next, 1):
                    print(f"      [{i}] class={elem.attr('class')}")
                    print(f"          disabled={elem.attr('disabled')}")
                    print(f"          text={elem.text}")
            else:
                print("   ❌ 未找到")
        except:
            print("   ❌ 查找失败")
        
        # 4. 查找分页容器
        print("\n4️⃣ 查找分页容器...")
        pagination_selectors = [
            'css:.pagination',
            'css:.layui-laypage',
            'css:[id*="page"]',
            'css:[class*="page"]',
        ]
        
        for selector in pagination_selectors:
            try:
                containers = page.eles(selector)
                if containers:
                    print(f"   ✅ {selector} 找到 {len(containers)} 个")
                    for i, container in enumerate(containers[:2], 1):
                        print(f"      [{i}] class={container.attr('class')}, id={container.attr('id')}")
                        # 显示容器内的链接
                        links = container.eles('tag:a')
                        if links:
                            print(f"          包含 {len(links)} 个链接")
                            for j, link in enumerate(links[:5], 1):
                                link_text = link.text.strip()
                                print(f"            [{j}] {link_text} (class={link.attr('class')})")
            except:
                pass
        
        # 5. 查找所有页码链接
        print("\n5️⃣ 查找页码链接（数字1-10）...")
        try:
            for num in range(1, 11):
                page_links = page.eles(f'xpath://a[text()="{num}"]')
                if page_links:
                    print(f"   ✅ 找到页码 {num} ({len(page_links)}个)")
                    if num == 2:  # 详细显示页码2的信息
                        link = page_links[0]
                        print(f"      class={link.attr('class')}")
                        print(f"      href={link.attr('href')}")
                        print(f"      onclick={link.attr('onclick')}")
        except:
            print("   ❌ 查找失败")
        
        # 6. 保存页面HTML
        print("\n" + "=" * 70)
        print("💾 保存页面HTML用于分析")
        print("=" * 70)
        
        try:
            html = page.html
            os.makedirs('prototype/results', exist_ok=True)
            with open('prototype/results/pagination_debug.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print("   ✅ 已保存: prototype/results/pagination_debug.html")
            print("   💡 可以用编辑器打开查找分页相关代码")
        except Exception as e:
            print(f"   ❌ 保存失败: {e}")
        
        # 7. 尝试找到第2页链接并点击
        print("\n" + "=" * 70)
        print("🧪 尝试点击第2页")
        print("=" * 70)
        
        print("\n方法1: 查找<li>元素（不是<a>链接！）...")
        try:
            # 正确的选择器：查找#pagination下的<li>元素，文本为"2"
            page2_selectors = [
                ('css:#pagination li:has-text("2")', 'CSS has-text'),
                ('xpath://div[@id="pagination"]//li[text()="2"]', 'XPath text'),
            ]
            
            page2_elem = None
            for selector, desc in page2_selectors:
                try:
                    elem = page.ele(selector, timeout=2)
                    if elem:
                        # 确保不是当前激活页（class="active"）
                        elem_class = elem.attr('class') or ''
                        if 'active' not in elem_class:
                            page2_elem = elem
                            print(f"   ✅ 找到页码2元素 ({desc})")
                            print(f"      selector: {selector}")
                            print(f"      class: {elem_class}")
                            break
                except:
                    pass
            
            if page2_elem:
                print("\n   💡 提示：将在5秒后点击第2页...")
                print("      观察浏览器是否跳转到第2页")
                time.sleep(5)
                
                page2_elem.click()
                print("   ✅ 已点击")
                
                print("\n   ⏳ 等待5秒加载第2页...")
                time.sleep(5)
                
                # 检查是否成功翻页
                print("\n   🔍 检查是否成功翻页...")
                current_url = page.url
                print(f"      当前URL: {current_url}")
                
                # 查找当前页码（应该是class="active"的li）
                try:
                    active_page = page.ele('css:#pagination li.active', timeout=2)
                    if active_page:
                        print(f"      ✅ 当前页码: {active_page.text}")
                    else:
                        print("      ⚠️ 未找到当前页码标记")
                except:
                    print("      ⚠️ 无法确定当前页码")
                
                # 检查公告列表是否变化
                try:
                    items = page.eles('css:ul.noticeShowList li')
                    if items:
                        print(f"      📋 公告列表: {len(items)} 条")
                        # 显示第一条标题
                        first_item = items[0]
                        title_elem = first_item.ele('tag:a', timeout=1)
                        if title_elem:
                            title = title_elem.text.strip()[:50]
                            print(f"      第一条: {title}...")
                except:
                    pass
                
                # 保存第2页HTML
                try:
                    html2 = page.html
                    with open('prototype/results/pagination_page2.html', 'w', encoding='utf-8') as f:
                        f.write(html2)
                    print("      ✅ 已保存第2页HTML: prototype/results/pagination_page2.html")
                except:
                    pass
                
            else:
                print("   ❌ 未找到页码2元素")
        except Exception as e:
            print(f"   ❌ 失败: {e}")
        
        print("\n" + "=" * 70)
        print("✅ 诊断完成")
        print("=" * 70)
        print("\n💡 建议:")
        print("   1. 检查控制台输出，查看找到了哪些分页元素")
        print("   2. 打开 prototype/results/pagination_debug.html 搜索'分页'、'page'")
        print("   3. 观察浏览器是否成功跳转到第2页")
        
        # 保持浏览器打开10秒，方便观察
        print("\n💡 浏览器将在10秒后关闭...")
        time.sleep(10)
        
    finally:
        page.quit()

if __name__ == '__main__':
    debug_pagination()
