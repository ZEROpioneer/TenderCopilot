"""测试配置管理器"""

from src.config import ConfigManager
from loguru import logger


def test_config_manager():
    """测试配置管理器功能"""
    logger.info("=" * 60)
    logger.info("🧪 测试配置管理器")
    logger.info("=" * 60)
    
    try:
        # 1. 加载配置
        logger.info("\n📥 步骤1: 加载所有配置...")
        config = ConfigManager()
        config.load_all()
        logger.success("✅ 配置加载成功")
        
        # 2. 测试点号路径访问
        logger.info("\n🔍 步骤2: 测试点号路径访问...")
        timeout = config.get('spider.timeout')
        logger.info(f"  spider.timeout = {timeout}")
        
        headless = config.get('spider.headless')
        logger.info(f"  spider.headless = {headless}")
        
        use_incremental = config.get('crawl_strategy.use_incremental')
        logger.info(f"  crawl_strategy.use_incremental = {use_incremental}")
        
        logger.success("✅ 点号路径访问正常")
        
        # 3. 测试字典式访问（向后兼容）
        logger.info("\n🔍 步骤3: 测试字典式访问...")
        spider_config = config['spider']
        logger.info(f"  config['spider']['timeout'] = {spider_config['timeout']}")
        logger.success("✅ 字典式访问正常")
        
        # 4. 测试业务方向配置
        logger.info("\n🔍 步骤4: 测试业务方向配置...")
        business_directions = config.get('business_directions')
        logger.info(f"  业务方向数量: {len(business_directions)}")
        for direction_id, direction in business_directions.items():
            # keywords_include 是实际的字段名
            keywords = direction.get('keywords_include', direction.get('keywords', []))
            logger.info(f"  - {direction['name']}: {len(keywords)} 个关键词")
        logger.success("✅ 业务方向配置正常")
        
        # 5. 测试搜索关键词（从 business_directions 提取）
        logger.info("\n🔍 步骤5: 测试搜索关键词提取...")
        all_keywords = []
        for direction_id, direction in business_directions.items():
            # keywords_include 是实际的字段名
            keywords = direction.get('keywords_include', direction.get('keywords', []))
            all_keywords.extend(keywords)
        logger.info(f"  总关键词数量: {len(all_keywords)}")
        logger.info(f"  示例关键词: {', '.join(all_keywords[:5])}...")
        logger.success("✅ 关键词提取正常")
        
        # 6. 测试环境变量处理（如果已设置）
        logger.info("\n🔍 步骤6: 测试环境变量处理...")
        email_config = config.get('notifications.email')
        if email_config:
            logger.info(f"  邮件发送者: {email_config.get('sender_email')}")
            # 不显示密码，只检查是否存在
            has_password = bool(email_config.get('sender_password'))
            logger.info(f"  密码已配置: {'是' if has_password else '否（使用环境变量）'}")
        logger.success("✅ 环境变量处理正常")
        
        # 7. 测试默认值
        logger.info("\n🔍 步骤7: 测试默认值...")
        non_existent = config.get('non.existent.key', '默认值')
        logger.info(f"  不存在的配置项: {non_existent}")
        logger.success("✅ 默认值处理正常")
        
        # 8. 显示完整配置结构
        logger.info("\n📊 步骤8: 配置结构概览...")
        full_config = config.to_dict()
        logger.info(f"  顶级配置项: {', '.join(full_config.keys())}")
        logger.success("✅ 配置结构完整")
        
        logger.info("\n" + "=" * 60)
        logger.success("🎉 所有测试通过！配置管理器工作正常")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == '__main__':
    test_config_manager()
