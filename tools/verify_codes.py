"""
验证地区代码和公告类型代码

此脚本帮助你验证配置文件中的代码映射是否正确
"""

import sys
from pathlib import Path
import io

# 设置标准输出编码为 UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

def verify_codes():
    """验证编码映射"""
    print("=" * 80)
    print("🔍 编码映射验证工具")
    print("=" * 80)
    print()
    
    # 加载配置
    with open('config/filter_settings.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 验证地区代码
    print("📍 地区代码映射")
    print("-" * 80)
    region_codes = config.get('region_codes', {})
    
    print(f"共配置 {len(region_codes)} 个地区代码\n")
    
    # 显示优先地区
    priority_regions = config.get('filters', {}).get('regions', {}).get('priority', [])
    if priority_regions:
        print("✅ 优先地区及其代码：")
        for region in priority_regions:
            name = region['name']
            code = region_codes.get(name, '❌ 未找到')
            print(f"  {name}: {code}")
            
            if region.get('include_cities') and region.get('cities'):
                print(f"    └── 下属城市：")
                for city in region['cities']:
                    city_code = region_codes.get(city, '❌ 未找到')
                    print(f"        {city}: {city_code}")
        print()
    
    # 显示其他关注地区
    included_regions = config.get('filters', {}).get('regions', {}).get('included', [])
    if included_regions:
        print("✅ 其他关注地区及其代码：")
        for name in included_regions:
            code = region_codes.get(name, '❌ 未找到')
            print(f"  {name}: {code}")
        print()
    
    # 验证公告类型代码
    print("=" * 80)
    print("📋 公告类型代码映射")
    print("-" * 80)
    notice_type_codes = config.get('notice_type_codes', {})
    
    print(f"共配置 {len(notice_type_codes)} 个公告类型代码\n")
    
    # 显示配置的公告类型
    configured_types = config.get('filters', {}).get('notice_types', {}).get('types', [])
    if configured_types:
        print("✅ 已启用的公告类型及其代码：")
        for notice_type in configured_types:
            code = notice_type_codes.get(notice_type, '❌ 未找到')
            print(f"  {notice_type}: {code}")
        print()
    
    # 显示所有可用类型
    print("📋 所有可用的公告类型：")
    for notice_type, code in notice_type_codes.items():
        status = "✓ 已启用" if notice_type in configured_types else "  未启用"
        print(f"  {status} | {notice_type}: {code}")
    print()
    
    # 检查问题
    print("=" * 80)
    print("🔍 问题检查")
    print("-" * 80)
    
    issues_found = False
    
    # 检查地区代码
    for region in priority_regions:
        name = region['name']
        if name not in region_codes:
            print(f"⚠️ 优先地区缺少代码: {name}")
            issues_found = True
        
        if region.get('include_cities') and region.get('cities'):
            for city in region['cities']:
                if city not in region_codes:
                    print(f"⚠️ 城市缺少代码: {city}")
                    issues_found = True
    
    for name in included_regions:
        if name not in region_codes:
            print(f"⚠️ 关注地区缺少代码: {name}")
            issues_found = True
    
    # 检查公告类型代码
    for notice_type in configured_types:
        if notice_type not in notice_type_codes:
            print(f"⚠️ 公告类型缺少代码: {notice_type}")
            issues_found = True
    
    if not issues_found:
        print("✅ 未发现配置问题")
    
    print()
    
    # 使用说明
    print("=" * 80)
    print("💡 如何验证代码是否正确")
    print("=" * 80)
    print()
    print("方法 1：使用浏览器开发者工具")
    print("  1. 访问 https://www.plap.mil.cn/freecms-glht/site/juncai/cggg/index.html")
    print("  2. 打开开发者工具 (F12)")
    print("  3. 切换到 Network 标签")
    print("  4. 在页面上选择不同的地区和公告类型")
    print("  5. 查看 XHR/Fetch 请求中的参数")
    print("  6. 对比实际参数与配置文件中的代码")
    print()
    print("方法 2：运行 API 端点测试")
    print("  1. 确保找到了正确的 API 端点")
    print("  2. 运行: python tools/test_api_endpoints.py")
    print("  3. 查看请求和响应，确认代码格式")
    print()
    print("方法 3：查看页面 HTML 源代码")
    print("  1. 在页面上右键 -> 查看页面源代码")
    print("  2. 搜索下拉选择框的 <select> 标签")
    print("  3. 查看 <option> 标签的 value 属性")
    print("  4. 这些 value 就是实际的代码")
    print()
    print("=" * 80)


if __name__ == "__main__":
    verify_codes()
