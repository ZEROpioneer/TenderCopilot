"""探测军队采购网的真实 API 接口"""

from DrissionPage import ChromiumPage, ChromiumOptions
import time
import json
from loguru import logger

def explore_api():
    """探测网站实际使用的 API"""
    logger.info("🔍 开始探测军队采购网 API...")
    
    # 配置浏览器
    options = ChromiumOptions()
    options.headless(False)  # 显示浏览器窗口，方便观察
    
    page = ChromiumPage(addr_or_opts=options)
    
    # 启用网络监听
    page.listen.start('selectInfo')  # 监听包含 'selectInfo' 的请求
    
    try:
        # 访问公告列表页
        url = 'https://www.plap.mil.cn/freecms-glht/site/juncai/cggg/index.html'
        logger.info(f"📄 访问页面: {url}")
        page.get(url)
        
        # 等待页面加载
        time.sleep(5)
        
        logger.info("🔍 尝试触发 API 请求...")
        
        # 尝试点击筛选按钮或翻页，触发 API 请求
        try:
            # 查找并点击查询/翻页按钮
            search_btn = page.ele('text:查询', timeout=2)
            if search_btn:
                logger.info("  点击查询按钮...")
                search_btn.click()
                time.sleep(2)
        except:
            pass
        
        try:
            # 尝试点击下一页
            next_page = page.ele('text:下一页', timeout=2)
            if next_page:
                logger.info("  点击下一页...")
                next_page.click()
                time.sleep(2)
        except:
            pass
        
        # 获取监听到的请求
        logger.info("\n" + "="*60)
        logger.info("📡 监听到的 API 请求:")
        logger.info("="*60)
        
        packets = page.listen.steps()
        
        if packets:
            for i, packet in enumerate(packets, 1):
                try:
                    logger.info(f"\n[请求 {i}]")
                    logger.info(f"  URL: {packet.url}")
                    logger.info(f"  方法: {packet.method}")
                    
                    # 显示请求参数
                    if hasattr(packet, 'postData'):
                        logger.info(f"  POST 数据: {packet.postData}")
                    
                    # 显示响应
                    response = packet.response
                    if response:
                        logger.info(f"  状态码: {response.status_code}")
                        
                        # 尝试解析 JSON 响应
                        try:
                            body = response.body
                            if body:
                                data = json.loads(body)
                                logger.info(f"  响应数据结构: {list(data.keys())}")
                                # 显示前2条数据示例
                                if 'data' in data:
                                    logger.info(f"  data 字段: {type(data['data'])}")
                                    if isinstance(data['data'], dict):
                                        logger.info(f"  data 子字段: {list(data['data'].keys())}")
                        except:
                            pass
                    
                    logger.info("-" * 60)
                    
                except Exception as e:
                    logger.warning(f"  解析请求失败: {e}")
        else:
            logger.warning("⚠️ 未监听到任何 API 请求")
            logger.info("\n💡 建议:")
            logger.info("  1. 在浏览器中手动操作（点击查询、翻页等）")
            logger.info("  2. 打开浏览器开发者工具 (F12) -> Network 标签")
            logger.info("  3. 观察 XHR/Fetch 请求")
        
        logger.info("\n" + "="*60)
        logger.info("⏳ 浏览器将保持打开 30 秒，请手动操作并观察...")
        logger.info("="*60)
        time.sleep(30)
        
    except Exception as e:
        logger.error(f"❌ 探测失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    finally:
        page.quit()
        logger.info("✅ 探测完成")


if __name__ == '__main__':
    explore_api()
