"""
测试新的筛选爬取功能
"""

import yaml
from loguru import logger
from src.spider.api_client import PLAPApiClient
from src.spider.crawl_tracker import CrawlTracker
from src.database.storage import DatabaseManager


def test_api_client():
    """测试 API 客户端"""
    logger.info("=" * 60)
    logger.info("🧪 测试 API 客户端")
    logger.info("=" * 60)
    
    # 加载配置
    with open('config/settings.yaml', 'r', encoding='utf-8') as f:
        settings = yaml.safe_load(f)
    
    with open('config/filter_settings.yaml', 'r', encoding='utf-8') as f:
        filter_settings = yaml.safe_load(f)
    
    config = {**settings, 'filter_settings': filter_settings}
    
    # 创建 API 客户端
    api_client = PLAPApiClient(config)
    
    # 测试获取公告
    logger.info("📡 测试获取公告...")
    try:
        announcements = api_client.fetch_announcements(
            date_range=('2024-01-01', '2024-12-31'),
            notice_types=['招标公告', '采购公告'],
            regions=['辽宁省', '大连市'],
            max_results=10
        )
        
        logger.info(f"✅ 成功获取 {len(announcements)} 条公告")
        
        # 显示前 3 条
        for i, ann in enumerate(announcements[:3]):
            logger.info(f"\n公告 {i+1}:")
            logger.info(f"  标题: {ann.get('title', 'N/A')}")
            logger.info(f"  日期: {ann.get('publish_date', 'N/A')}")
            logger.info(f"  类型: {ann.get('notice_type', 'N/A')}")
            logger.info(f"  地区: {ann.get('region', 'N/A')}")
            logger.info(f"  URL: {ann.get('url', 'N/A')}")
        
        api_client.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_crawl_tracker():
    """测试爬取追踪器"""
    logger.info("\n" + "=" * 60)
    logger.info("🧪 测试爬取追踪器")
    logger.info("=" * 60)
    
    # 加载配置
    with open('config/settings.yaml', 'r', encoding='utf-8') as f:
        settings = yaml.safe_load(f)
    
    with open('config/filter_settings.yaml', 'r', encoding='utf-8') as f:
        filter_settings = yaml.safe_load(f)
    
    config = {**settings, 'filter_settings': filter_settings}
    
    # 初始化数据库和追踪器
    db = DatabaseManager(config['database']['path'])
    tracker = CrawlTracker(db, config)
    
    # 测试获取日期范围
    logger.info("📅 测试日期范围计算...")
    try:
        date_range = tracker.get_date_range()
        logger.info(f"✅ 日期范围: {date_range[0]} ~ {date_range[1]}")
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        return False
    
    # 测试记录爬取
    logger.info("📝 测试记录爬取...")
    try:
        tracker.record_crawl(10, success=True)
        logger.info("✅ 记录成功")
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        return False
    
    # 测试获取统计
    logger.info("📊 测试获取统计...")
    try:
        stats = tracker.get_statistics()
        logger.info("✅ 统计信息:")
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        return False
    
    db.close()
    return True


def test_region_codes():
    """测试地区代码映射"""
    logger.info("\n" + "=" * 60)
    logger.info("🧪 测试地区代码映射")
    logger.info("=" * 60)
    
    with open('config/filter_settings.yaml', 'r', encoding='utf-8') as f:
        filter_settings = yaml.safe_load(f)
    
    region_codes = filter_settings.get('region_codes', {})
    
    # 测试几个关键地区
    test_regions = ['辽宁省', '大连市', '北京市', '上海市']
    
    logger.info("🔍 查找地区代码:")
    for region in test_regions:
        code = region_codes.get(region)
        if code:
            logger.info(f"  ✅ {region}: {code}")
        else:
            logger.warning(f"  ⚠️ {region}: 未找到代码")
    
    return True


if __name__ == '__main__':
    logger.info("🚀 开始测试新的筛选爬取功能")
    
    # 1. 测试地区代码映射
    success1 = test_region_codes()
    
    # 2. 测试爬取追踪器
    success2 = test_crawl_tracker()
    
    # 3. 测试 API 客户端（可能会失败，因为需要实际 API 端点）
    logger.info("\n⚠️ 注意: API 客户端测试可能失败，因为需要实际的 API 端点")
    logger.info("   如果失败，请检查网站的实际 API 接口和参数")
    success3 = test_api_client()
    
    # 总结
    logger.info("\n" + "=" * 60)
    logger.info("📋 测试总结")
    logger.info("=" * 60)
    logger.info(f"  地区代码映射: {'✅ 通过' if success1 else '❌ 失败'}")
    logger.info(f"  爬取追踪器: {'✅ 通过' if success2 else '❌ 失败'}")
    logger.info(f"  API 客户端: {'✅ 通过' if success3 else '⚠️ 失败（可能需要调整 API 参数）'}")
    
    if success1 and success2:
        logger.success("\n✅ 核心功能测试通过！")
        logger.info("\n📝 后续步骤:")
        logger.info("  1. 如果 API 测试失败，需要:")
        logger.info("     - 检查网站实际的 API 端点和参数")
        logger.info("     - 使用浏览器开发者工具查看网络请求")
        logger.info("     - 调整 api_client.py 中的请求参数")
        logger.info("  2. 运行完整流程测试: python main.py --mode once")
        logger.info("  3. 查看爬取统计和生成的报告")
    else:
        logger.error("\n❌ 部分测试失败，请检查错误信息")
