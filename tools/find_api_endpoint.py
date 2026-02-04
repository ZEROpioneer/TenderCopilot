"""
手动查找军队采购网 API 端点的工具

使用方法：
1. 运行此脚本
2. 浏览器会自动打开军队采购网
3. 手动打开开发者工具 (F12)
4. 切换到 Network 标签
5. 筛选 XHR/Fetch 请求
6. 在页面上进行筛选操作（选择日期、地区等）
7. 观察 Network 面板中出现的请求
8. 找到获取公告列表的请求并记录：
   - 请求 URL
   - 请求方法 (GET/POST)
   - 请求参数
   - 响应格式
"""

from DrissionPage import ChromiumPage, ChromiumOptions
import time
from pathlib import Path

def find_api():
    """查找 API 端点"""
    print("=" * 80)
    print("🔍 军队采购网 API 端点查找工具")
    print("=" * 80)
    print()
    print("📋 使用步骤：")
    print("  1. 浏览器会自动打开军队采购网公告页面")
    print("  2. 按 F12 打开开发者工具")
    print("  3. 切换到 'Network' (网络) 标签")
    print("  4. 筛选 'Fetch/XHR' 类型的请求")
    print("  5. 在页面上进行筛选操作（选择日期、地区、公告类型等）")
    print("  6. 观察 Network 面板中新出现的请求")
    print("  7. 找到获取公告列表的请求（通常包含 list、select、query 等关键词）")
    print("  8. 记录以下信息：")
    print("     - Request URL (请求地址)")
    print("     - Request Method (GET 或 POST)")
    print("     - Request Headers (特别是 Content-Type)")
    print("     - Form Data / Query Parameters (请求参数)")
    print("     - Response (响应数据格式)")
    print()
    print("=" * 80)
    
    # 配置浏览器
    options = ChromiumOptions()
    options.headless(False)  # 必须使用可视模式
    
    page = ChromiumPage(addr_or_opts=options)
    
    debug_dir = Path("data/debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # 访问公告页面
        url = "https://www.plap.mil.cn/freecms-glht/site/juncai/cggg/index.html"
        print(f"📡 正在打开: {url}")
        page.get(url)
        time.sleep(3)
        
        print("✅ 页面已加载")
        print()
        print("⏸️ 浏览器将保持打开状态...")
        print()
        print("💡 提示：")
        print("  - 在页面上尝试不同的筛选条件")
        print("  - 注意观察 Network 面板中的 XHR/Fetch 请求")
        print("  - 点击请求可以查看详细信息")
        print("  - 找到 API 后，记录下来并更新配置文件")
        print()
        print("🔍 常见的 API 端点模式：")
        print("  - /api/notice/list")
        print("  - /rest/v1/notice/select")
        print("  - /freecms/api/notice")
        print("  - *.do (Struts 框架)")
        print("  - /portal/query")
        print()
        print("📝 找到 API 后，更新以下文件：")
        print("  1. config/filter_settings.yaml")
        print("     api:")
        print("       endpoint: \"/你找到的API路径\"")
        print()
        print("  2. src/spider/api_client.py")
        print("     根据实际的参数名称和响应格式调整代码")
        print()
        print("=" * 80)
        print()
        print("完成查找后，按 Enter 退出...")
        input()
        
        # 保存最后的页面状态
        screenshot_path = debug_dir / "api_search_final.png"
        page.get_screenshot(path=str(screenshot_path))
        print(f"📸 截图已保存: {screenshot_path}")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        page.quit()
        print("🔚 浏览器已关闭")
        print()
        print("=" * 80)
        print("📚 参考资料：")
        print("  如果你找到了正确的 API 端点，请记录以下信息：")
        print()
        print("  1. API URL: ______________________________________")
        print("  2. Method: [ ] GET  [ ] POST")
        print("  3. 参数格式:")
        print("     - 日期参数名: __________  格式: __________")
        print("     - 地区参数名: __________  格式: __________")
        print("     - 类型参数名: __________  格式: __________")
        print("     - 分页参数名: __________  格式: __________")
        print("  4. 响应格式:")
        print("     - 数据路径: data.list / data.records / records / 其他: __________")
        print()
        print("然后更新代码中的相应配置。")
        print("=" * 80)


if __name__ == "__main__":
    find_api()
