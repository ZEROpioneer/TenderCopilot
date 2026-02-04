"""查找军队采购网的公告列表页"""

from DrissionPage import ChromiumPage, ChromiumOptions
import time
from pathlib import Path

def find_announcement_list():
    """查找公告列表页"""
    # 配置浏览器（可视化模式便于观察）
    options = ChromiumOptions()
    options.headless(False)
    
    page = ChromiumPage(addr_or_opts=options)
    
    debug_dir = Path("data/debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    print("🔍 开始查找军队采购网公告列表页...\n")
    
    try:
        # 1. 访问首页
        print("📡 访问首页: https://www.plap.mil.cn/")
        page.get("https://www.plap.mil.cn/")
        time.sleep(3)
        
        print(f"✅ 首页标题: {page.title}")
        
        # 保存首页截图
        screenshot_path = debug_dir / "homepage.png"
        page.get_screenshot(path=str(screenshot_path))
        print(f"📸 首页截图: {screenshot_path}")
        
        # 2. 查找包含"公告"、"采购"、"招标"等关键词的链接
        print("\n🔍 查找相关链接...\n")
        
        all_links = page.eles('tag:a', timeout=3)
        relevant_links = []
        
        keywords = ['公告', '采购', '招标', '信息', '通知', '列表']
        
        for link in all_links:
            text = link.text.strip()
            href = link.attr('href')
            
            if not href:
                continue
            
            # 检查链接文本或 URL 是否包含关键词
            if any(keyword in text for keyword in keywords) or any(keyword in href for keyword in keywords):
                # 补全 URL
                if href.startswith('/'):
                    href = 'https://www.plap.mil.cn' + href
                elif not href.startswith('http'):
                    continue
                
                relevant_links.append({
                    'text': text,
                    'href': href
                })
                print(f"  📌 {text[:30]:<30} -> {href}")
        
        if not relevant_links:
            print("⚠️ 首页未找到明显的公告列表链接")
            print("💡 尝试常见的路径...")
            
            # 尝试常见路径
            possible_paths = [
                "/ggxx",  # 公告信息
                "/freecms/site/juncai/ggxx",
                "/portal/list",
                "/list",
                "/announcement",
                "/notice",
            ]
            
            for path in possible_paths:
                url = f"https://www.plap.mil.cn{path}"
                print(f"\n🔍 测试: {url}")
                
                try:
                    page.get(url)
                    time.sleep(2)
                    
                    if "404" not in page.html[:1000]:
                        print(f"✅ 可访问！")
                        print(f"   标题: {page.title}")
                        
                        # 检查是否有公告链接
                        links = page.eles('tag:a', timeout=2)
                        notice_links = []
                        for l in links[:20]:
                            t = l.text.strip()
                            if len(t) > 10 and any(k in t for k in ['采购', '招标', '公告']):
                                notice_links.append(t[:50])
                        
                        if notice_links:
                            print(f"   找到 {len(notice_links)} 个可能的公告链接:")
                            for nl in notice_links[:5]:
                                print(f"     - {nl}...")
                            
                            # 保存这个页面
                            name = path.replace('/', '_')
                            screenshot_path = debug_dir / f"list_page{name}.png"
                            page.get_screenshot(path=str(screenshot_path))
                            
                            html_path = debug_dir / f"list_page{name}.html"
                            with open(html_path, 'w', encoding='utf-8') as f:
                                f.write(page.html)
                            
                            print(f"   📸 截图: {screenshot_path}")
                            print(f"   💾 HTML: {html_path}")
                            
                            relevant_links.append({
                                'text': f'列表页: {path}',
                                'href': url
                            })
                    else:
                        print(f"❌ 404 Not Found")
                        
                except Exception as e:
                    print(f"❌ 错误: {e}")
        
        # 3. 总结
        print("\n" + "=" * 80)
        print("📊 总结:\n")
        
        if relevant_links:
            print("✅ 找到以下可能的公告列表页:\n")
            for i, link in enumerate(relevant_links, 1):
                print(f"{i}. {link['text']}")
                print(f"   URL: {link['href']}\n")
            
            print(f"💡 建议:")
            print(f"   1. 查看 data/debug/ 目录下的截图")
            print(f"   2. 选择一个合适的 URL 更新到 config/settings.yaml")
            print(f"   3. 修改 announcement_list_url 配置项")
        else:
            print("❌ 未找到明显的公告列表页")
            print("\n💡 建议:")
            print("   1. 手动浏览 https://www.plap.mil.cn/")
            print("   2. 找到公告列表页")
            print("   3. 复制 URL 到配置文件")
        
        print("\n按 Enter 关闭浏览器...")
        input()
        
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        page.quit()
        print("🔚 浏览器已关闭")


if __name__ == "__main__":
    find_announcement_list()
