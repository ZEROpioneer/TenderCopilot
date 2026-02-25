"""
测试不同的 API 端点

使用方法：
1. 如果你找到了新的 API 端点，将其添加到 possible_endpoints 列表
2. 运行此脚本测试哪些端点可用
3. 找到可用的端点后，更新 config/filter_settings.yaml
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from loguru import logger
from src.spider.api_client import PLAPApiClient


def test_endpoints():
    """测试多个可能的 API 端点"""
    print("=" * 80)
    print("🧪 API 端点测试工具")
    print("=" * 80)
    print()
    
    # 加载配置
    with open('config/settings.yaml', 'r', encoding='utf-8') as f:
        settings = yaml.safe_load(f)
    
    with open('config/business_directions.yaml', 'r', encoding='utf-8') as f:
        business = yaml.safe_load(f)
    
    with open('config/filter_settings.yaml', 'r', encoding='utf-8') as f:
        filter_settings = yaml.safe_load(f)
    
    config = {**settings}
    config['business_directions'] = business['business_directions']
    config['global_exclude'] = business['global_exclude']
    config['filter_settings'] = filter_settings
    
    # 可能的 API 端点列表
    possible_endpoints = [
        "/rest/v1/notice/selectInfoMoreChannel.do",  # 当前配置（已知失效）
        "/freecms/api/notice/list.do",
        "/api/notice/selectList.do",
        "/api/notice/list.do",
        "/portal/notice/query.do",
        "/rest/notice/select.do",
        "/freecms/rest/notice/list.do",
        "/site/juncai/cggg/list.do",
    ]
    
    print("📋 将测试以下端点：")
    for i, endpoint in enumerate(possible_endpoints, 1):
        print(f"  {i}. {endpoint}")
    print()
    print("⏳ 开始测试...")
    print()
    
    # 创建 API 客户端
    api_client = PLAPApiClient(config)
    
    successful_endpoints = []
    
    for endpoint in possible_endpoints:
        print(f"🧪 测试: {endpoint}")
        print("-" * 80)
        
        # 测试端点
        success = api_client.test_endpoint(endpoint)
        
        if success:
            successful_endpoints.append(endpoint)
        
        print()
    
    # 关闭客户端
    api_client.close()
    
    # 总结
    print("=" * 80)
    print("📊 测试结果总结")
    print("=" * 80)
    print()
    
    if successful_endpoints:
        print(f"✅ 找到 {len(successful_endpoints)} 个可用端点：")
        for endpoint in successful_endpoints:
            print(f"  ✓ {endpoint}")
        print()
        print("💡 下一步：")
        print(f"  1. 选择一个端点更新到 config/filter_settings.yaml")
        print(f"     api:")
        print(f"       endpoint: \"{successful_endpoints[0]}\"")
        print()
        print(f"  2. 运行测试验证功能是否正常：")
        print(f"     python main.py --mode once")
    else:
        print("❌ 未找到可用的 API 端点")
        print()
        print("💡 建议：")
        print("  1. 运行手动查找工具: python tools/find_api_endpoint.py")
        print("  2. 使用浏览器开发者工具查找真实的 API 地址")
        print("  3. 或者使用传统网页爬取模式（系统会自动降级）")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    test_endpoints()
