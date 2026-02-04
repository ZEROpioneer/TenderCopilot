"""测试军队采购网的 URL"""

from DrissionPage import ChromiumPage, ChromiumOptions
import time
from pathlib import Path

def test_urls():
    """测试不同的 URL"""
    # 配置浏览器（使用可视化模式）
    options = ChromiumOptions()
    options.headless(False)
    
    page = ChromiumPage(addr_or_opts=options)
    
    # 要测试的 URL 列表
    test_urls = [
        ("首页", "https://www.plap.mil.cn"),
        ("采购公告分类页", "https://www.plap.mil.cn/portal/category/10101"),
        ("采购公告列表", "https://www.plap.mil.cn/portal/list"),
        ("公告页", "https://www.plap.mil.cn/announcement"),
        ("门户", "https://www.plap.mil.cn/portal"),
    ]
    
    debug_dir = Path("data/debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    print("🔍 开始测试 URL...\n")
    print("=" * 80)
    
    for name, url in test_urls:
        print(f"\n测试: {name}")
        print(f"URL: {url}")
        
        try:
            page.get(url)
            time.sleep(3)
            
            # 检查状态
            title = page.title
            
            # 检查是否是 404 页面
            if "404" in title or "Not Found" in page.html[:500]:
                status = "❌ 404 Not Found"
                accessible = False
            else:
                status = "✅ 可访问"
                accessible = True
                
                # 保存截图
                screenshot_path = debug_dir / f"{name.replace(' ', '_')}.png"
                page.get_screenshot(path=str(screenshot_path))
                
                # 保存 HTML
                html_path = debug_dir / f"{name.replace(' ', '_')}.html"
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(page.html)
                
                # 统计页面元素
                link_count = len(page.eles('tag:a', timeout=1))
                
                print(f"状态: {status}")
                print(f"标题: {title}")
                print(f"链接数: {link_count}")
                print(f"截图: {screenshot_path}")
                print(f"HTML: {html_path}")
            
            if not accessible:
                print(f"状态: {status}")
            
            results.append({
                'name': name,
                'url': url,
                'accessible': accessible,
                'title': title if accessible else 'N/A'
            })
            
        except Exception as e:
            print(f"状态: ❌ 错误 - {e}")
            results.append({
                'name': name,
                'url': url,
                'accessible': False,
                'error': str(e)
            })
        
        print("-" * 80)
    
    # 总结
    print("\n" + "=" * 80)
    print("📊 测试总结:\n")
    
    accessible_urls = [r for r in results if r['accessible']]
    
    if accessible_urls:
        print("✅ 可访问的 URL:")
        for r in accessible_urls:
            print(f"  - {r['name']}: {r['url']}")
        print(f"\n💡 建议使用第一个可访问的 URL 作为起始页")
        print(f"📂 请查看 data/debug/ 目录下的截图和 HTML 文件")
    else:
        print("❌ 没有找到可访问的 URL")
        print("\n可能的原因:")
        print("  1. 网站需要特殊的访问权限")
        print("  2. 网站域名或结构已变更")
        print("  3. 需要 VPN 或特定网络环境")
        print("  4. 网站检测到自动化工具")
    
    print("\n按 Enter 键关闭...")
    input()
    
    page.quit()


if __name__ == "__main__":
    test_urls()
