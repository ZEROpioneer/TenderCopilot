"""调试爬虫 - 查看页面结构"""

from DrissionPage import ChromiumPage, ChromiumOptions
from pathlib import Path
import time

def debug_plap_site():
    """调试军队采购网页面结构"""
    print("🔍 开始调试军队采购网...")
    
    # 配置浏览器
    options = ChromiumOptions()
    options.headless(False)  # 使用可视化模式便于调试
    
    page = ChromiumPage(addr_or_opts=options)
    
    try:
        # 访问网站
        url = "https://www.plap.mil.cn/portal/category/10101"
        print(f"📡 访问: {url}")
        page.get(url)
        
        # 等待页面加载
        time.sleep(3)
        print("⏳ 页面加载完成")
        
        # 保存截图
        screenshot_dir = Path("data/debug")
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = screenshot_dir / "page_screenshot.png"
        page.get_screenshot(path=str(screenshot_path))
        print(f"📸 截图已保存: {screenshot_path}")
        
        # 保存 HTML 源码
        html_path = screenshot_dir / "page_source.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(page.html)
        print(f"💾 HTML 源码已保存: {html_path}")
        
        # 尝试查找常见的列表容器
        print("\n🔎 尝试查找页面元素...")
        
        selectors = [
            ('css:ul', 'ul 列表'),
            ('css:table', 'table 表格'),
            ('css:.list', '.list 类'),
            ('css:.content', '.content 类'),
            ('css:.main', '.main 类'),
            ('tag:tr', 'tr 表格行'),
            ('tag:li', 'li 列表项'),
            ('tag:a', 'a 链接'),
            ('css:[class*="list"]', '包含list的类'),
            ('css:[class*="item"]', '包含item的类'),
            ('css:[class*="notice"]', '包含notice的类'),
            ('css:[class*="announce"]', '包含announce的类'),
        ]
        
        results = []
        for selector, desc in selectors:
            try:
                elements = page.eles(selector, timeout=1)
                count = len(elements)
                if count > 0:
                    results.append((desc, selector, count))
                    print(f"  ✅ {desc} ({selector}): 找到 {count} 个元素")
                    
                    # 如果是链接，显示前 3 个的文本
                    if selector == 'tag:a' and count > 0:
                        for i, elem in enumerate(elements[:5]):
                            text = elem.text.strip()
                            if text:
                                print(f"      链接 {i+1}: {text[:50]}...")
            except Exception as e:
                print(f"  ❌ {desc} ({selector}): {e}")
        
        # 分析页面结构
        print("\n📊 页面结构分析:")
        print(f"  - 页面标题: {page.title}")
        print(f"  - 页面 URL: {page.url}")
        
        # 查找主要内容区域
        try:
            body = page.ele('tag:body')
            if body:
                # 获取所有具有 class 的元素
                elements_with_class = page.eles('xpath://*[@class]', timeout=2)
                class_names = set()
                for elem in elements_with_class[:50]:  # 只看前50个
                    classes = elem.attr('class')
                    if classes:
                        for cls in classes.split():
                            class_names.add(cls)
                
                print(f"\n🏷️ 发现的 CSS 类名 (前50个):")
                for cls in sorted(class_names)[:30]:
                    print(f"  - .{cls}")
        except Exception as e:
            print(f"  ❌ 分析类名失败: {e}")
        
        # 等待用户查看
        print("\n✨ 调试信息已生成!")
        print(f"📂 请查看 {screenshot_dir} 目录下的文件")
        print("\n🔍 建议:")
        print("  1. 打开截图查看页面结构")
        print("  2. 打开 HTML 源码搜索关键词（如'公告'、'采购'、'招标'）")
        print("  3. 根据上述找到的元素，修改爬虫选择器")
        
        input("\n按 Enter 键关闭浏览器...")
        
    except Exception as e:
        print(f"❌ 调试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        page.quit()
        print("🔚 浏览器已关闭")


if __name__ == "__main__":
    debug_plap_site()
