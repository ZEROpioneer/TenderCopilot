"""测试配置文件加载"""

import yaml
from pathlib import Path

def test_config_loading():
    """测试所有配置文件是否能正常加载"""
    print("🧪 开始测试配置文件加载...\n")
    
    configs = {
        'settings': 'config/settings.yaml',
        'business_directions': 'config/business_directions.yaml',
        'search_keywords': 'config/search_keywords.yaml',
        'filter_settings': 'config/filter_settings.yaml',
        'notifications': 'config/notifications.yaml'
    }
    
    results = {}
    
    for name, path in configs.items():
        try:
            file_path = Path(path)
            if not file_path.exists():
                results[name] = f"❌ 文件不存在: {path}"
                continue
            
            with open(path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            if config:
                results[name] = f"✅ 加载成功 ({len(config)} 个配置项)"
            else:
                results[name] = "⚠️ 文件为空"
                
        except Exception as e:
            results[name] = f"❌ 加载失败: {e}"
    
    # 打印结果
    print("📋 配置文件加载结果:\n")
    for name, result in results.items():
        print(f"  {name:25s} {result}")
    
    # 检查关键配置
    print("\n🔍 关键配置检查:\n")
    
    # 检查搜索关键词
    try:
        with open('config/search_keywords.yaml', 'r', encoding='utf-8') as f:
            search_config = yaml.safe_load(f)
        
        keywords_count = sum(
            len(kws) if isinstance(kws, list) else 0 
            for kws in search_config.get('search_keywords', {}).values()
        )
        print(f"  搜索关键词数量: {keywords_count} 个")
        
        strategy = search_config.get('crawl_strategy', {})
        print(f"  增量爬取: {'✅ 启用' if strategy.get('use_incremental') else '❌ 未启用'}")
        print(f"  数据库去重: {'✅ 启用' if strategy.get('enable_db_dedup') else '❌ 未启用'}")
        print(f"  每关键词上限: {strategy.get('max_per_keyword', '未配置')} 条")
        
    except Exception as e:
        print(f"  ⚠️ 搜索配置检查失败: {e}")
    
    # 检查地域策略
    print("\n  地域策略:")
    try:
        with open('config/business_directions.yaml', 'r', encoding='utf-8') as f:
            business_config = yaml.safe_load(f)
        
        for direction_id, direction in business_config.get('business_directions', {}).items():
            name = direction.get('name', direction_id)
            location_required = direction.get('location_required', False)
            location_bonus = direction.get('location_bonus', False)
            
            if location_required:
                priority = direction.get('location_priority', {})
                print(f"    {name}: 必须 {priority.get('province', '?')} (优先 {priority.get('city', '?')})")
            elif location_bonus:
                print(f"    {name}: 不限制，靠近辽宁省加分")
            else:
                print(f"    {name}: 不限制")
                
    except Exception as e:
        print(f"    ⚠️ 地域策略检查失败: {e}")
    
    print("\n✅ 配置文件测试完成！\n")

if __name__ == "__main__":
    test_config_loading()
