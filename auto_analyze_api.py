"""自动分析军队采购网 API"""

from DrissionPage import ChromiumPage, ChromiumOptions
import time
from pathlib import Path
import json

def analyze_api():
    """分析采购大厅的 API 调用"""
    # 配置浏览器 - 启用开发者工具
    options = ChromiumOptions()
    options.headless(False)  # 使用可视模式便于调试
    
    page = ChromiumPage(addr_or_opts=options)
    
    debug_dir = Path("data/debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    print("🔍 分析军队采购网 API...")
    print("=" * 80)
    
    try:
        # 访问采购大厅
        url = "https://www.plap.mil.cn/freecms-glht/site/juncai/cggg/index.html"
        print(f"\n📡 访问: {url}")
        page.get(url)
        time.sleep(5)  # 等待页面完全加载和 API 调用
        
        print(f"✅ 页面标题: {page.title}")
        
        # 保存页面
        screenshot_path = debug_dir / "api_analysis.png"
        page.get_screenshot(path=str(screenshot_path))
        print(f"📸 截图: {screenshot_path}")
        
        html_path = debug_dir / "api_page.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(page.html)
        print(f"💾 HTML: {html_path}")
        
        # 查找页面中的 script 标签，寻找 API 调用
        print("\n🔍 查找页面中的 JavaScript API 调用...")
        scripts = page.eles('tag:script', timeout=2)
        
        api_patterns = []
        for script in scripts:
            content = script.html
            # 查找常见的 API 调用模式
            if 'ajax' in content.lower() or 'fetch' in content.lower() or 'axios' in content.lower():
                # 查找 URL 模式
                import re
                urls = re.findall(r'["\']([/\w\-\.]+\.do)["\']', content)
                urls += re.findall(r'["\']([/\w\-\.]+/api/[/\w\-\.]+)["\']', content)
                urls += re.findall(r'url\s*:\s*["\']([^"\']+)["\']', content)
                
                if urls:
                    for u in urls:
                        if u not in api_patterns:
                            api_patterns.append(u)
                            print(f"  📡 发现 API 路径: {u}")
        
        # 分析表单提交
        print("\n🔍 查找表单和数据提交...")
        forms = page.eles('tag:form', timeout=2)
        print(f"  找到 {len(forms)} 个表单")
        
        for i, form in enumerate(forms, 1):
            action = form.attr('action')
            method = form.attr('method')
            if action:
                print(f"  表单 {i}: {method} -> {action}")
        
        # 查找分页和筛选控件
        print("\n🔍 查找分页和筛选控件...")
        
        # 查找日期选择器
        date_inputs = page.eles('css:input[type="date"]', timeout=1)
        date_inputs += page.eles('css:input[placeholder*="日期"]', timeout=1)
        date_inputs += page.eles('css:input[placeholder*="时间"]', timeout=1)
        if date_inputs:
            print(f"  📅 找到 {len(date_inputs)} 个日期输入框")
        
        # 查找下拉选择器（地区、类型等）
        selects = page.eles('tag:select', timeout=1)
        if selects:
            print(f"  📋 找到 {len(selects)} 个下拉选择框")
            for i, select in enumerate(selects[:5], 1):
                name = select.attr('name') or select.attr('id')
                options = select.eles('tag:option', timeout=0.5)
                print(f"    选择框 {i} ({name}): {len(options)} 个选项")
                if len(options) > 0 and len(options) < 10:
                    for opt in options:
                        print(f"      - {opt.text.strip()} (value: {opt.attr('value')})")
        
        # 分析 URL 参数
        print("\n🔍 分析当前页面 URL 参数...")
        current_url = page.url
        print(f"  当前 URL: {current_url}")
        
        if '?' in current_url:
            params = current_url.split('?')[1]
            print(f"  URL 参数: {params}")
        
        # 总结
        print("\n" + "=" * 80)
        print("📊 分析结果总结:\n")
        
        if api_patterns:
            print("✅ 发现的 API 端点:")
            for pattern in api_patterns:
                print(f"  - {pattern}")
        else:
            print("⚠️ 未在 JavaScript 中发现明显的 API 调用")
            print("💡 可能的原因:")
            print("  1. API 调用被混淆或加密")
            print("  2. 使用了外部 JS 文件")
            print("  3. 页面使用传统的表单提交")
        
        print("\n💡 建议:")
        print("  1. 打开浏览器开发者工具 (F12)")
        print("  2. 切换到 Network 标签")
        print("  3. 筛选 XHR/Fetch 请求")
        print("  4. 查看公告列表加载时的网络请求")
        print("  5. 记录真实的 API 端点和参数")
        
        print("\n⏸️ 浏览器将保持打开，请手动检查 Network 面板...")
        print("检查完成后按 Enter 继续...")
        input()
        
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        page.quit()
        print("🔚 浏览器已关闭")


if __name__ == "__main__":
    analyze_api()
