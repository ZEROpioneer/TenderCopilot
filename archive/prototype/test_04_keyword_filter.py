"""
测试4：验证关键词筛选功能
- 测试业务方向关键词匹配
- 测试地域加分策略
- 验证综合评分计算
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DrissionPage import ChromiumPage, ChromiumOptions
import json
import yaml

# 导入共享工具
from prototype.common_utils import wait_and_load_page, find_announcement_items, parse_list_item_v2

def load_business_directions():
    """加载业务方向配置"""
    with open('config/business_directions.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 转换为列表格式
    dirs = []
    for key, value in config['business_directions'].items():
        dirs.append({
            'name': value['name'],
            'keywords': value.get('keywords_include', []),
            'location_required': value.get('location_required', False),
            'location_bonus': value.get('location_bonus', False)
        })
    return dirs

def match_keywords(title, keywords):
    """匹配关键词"""
    matched = []
    for kw in keywords:
        if kw in title:
            matched.append(kw)
    return matched

def calculate_location_score(location, category_name):
    """
    计算地域评分
    - 文化氛围类：辽宁省优先，大连市最优
    - 其他类：辽宁省周边加分（权重较低）
    """
    location = location or ''
    
    # 文化氛围类特殊规则
    if '文化氛围' in category_name:
        if '大连' in location:
            return 20  # 最优
        elif '辽宁' in location:
            return 15  # 优先
        else:
            return 0  # 不匹配
    
    # 其他三类：周边省份低权重加分
    else:
        if '辽宁' in location:
            return 10  # 本省加分
        # 周边省份（低权重）
        nearby_provinces = ['吉林', '黑龙江', '内蒙古', '河北', '山东']
        for province in nearby_provinces:
            if province in location:
                return 3  # 低权重加分
        return 0

def calculate_comprehensive_score(announcement, business_dirs):
    """计算综合评分"""
    title = announcement.get('title', '')
    location = announcement.get('location', '')
    
    best_match = {
        'category': '未匹配',
        'matched_keywords': [],
        'keyword_score': 0,
        'location_score': 0,
        'total_score': 0
    }
    
    for category in business_dirs:
        cat_name = category['name']
        keywords = category.get('keywords', [])
        
        # 关键词匹配
        matched_kws = match_keywords(title, keywords)
        
        if matched_kws:
            # 关键词评分：每个关键词5分
            kw_score = len(matched_kws) * 5
            
            # 地域评分
            loc_score = calculate_location_score(location, cat_name)
            
            # 总分
            total = kw_score + loc_score
            
            # 保留最高分
            if total > best_match['total_score']:
                best_match = {
                    'category': cat_name,
                    'matched_keywords': matched_kws,
                    'keyword_score': kw_score,
                    'location_score': loc_score,
                    'total_score': total
                }
    
    return best_match

def fetch_first_page():
    """获取第一页公告"""
    options = ChromiumOptions()
    options.headless(False)
    
    page = ChromiumPage(options)
    
    try:
        url = "https://www.plap.mil.cn/freecms-glht/site/juncai/cggg/index.html"
        
        # 使用共享的页面加载函数
        success = wait_and_load_page(page, url)
        
        if not success:
            print("   ❌ 页面加载失败")
            return []
        
        # 查找公告
        items = find_announcement_items(page)
        if not items:
            print("   ⚠️ 未找到公告项")
            return []
        
        print(f"   找到 {len(items)} 个公告项\n")
        
        # 解析
        announcements = []
        for item in items:
            ann = parse_list_item_v2(item)
            if ann:
                announcements.append(ann)
        
        return announcements
        
    finally:
        page.quit()

def test_keyword_filter():
    """测试关键词筛选"""
    print("=" * 70)
    print("🧪 测试4：关键词筛选功能")
    print("=" * 70)
    
    # 加载业务方向配置
    print("\n📋 步骤1：加载业务方向配置...")
    business_dirs = load_business_directions()
    
    print(f"   共 {len(business_dirs)} 个业务方向：")
    for cat in business_dirs:
        kw_count = len(cat.get('keywords', []))
        print(f"     - {cat['name']}: {kw_count} 个关键词")
    
    # 获取公告
    print("\n📥 步骤2：获取第一页公告...")
    announcements = fetch_first_page()
    
    if not announcements:
        print("❌ 未获取到公告，测试失败")
        return False
    
    print(f"✅ 获取到 {len(announcements)} 条公告")
    
    # 关键词筛选
    print("\n" + "=" * 70)
    print("🔍 步骤3：关键词匹配与评分")
    print("=" * 70)
    
    matched_announcements = []
    
    for ann in announcements:
        score_info = calculate_comprehensive_score(ann, business_dirs)
        
        if score_info['total_score'] > 0:
            ann['score_info'] = score_info
            matched_announcements.append(ann)
    
    print(f"\n匹配结果: {len(matched_announcements)}/{len(announcements)} 条符合业务方向")
    
    if matched_announcements:
        # 按分数排序
        matched_announcements.sort(key=lambda x: x['score_info']['total_score'], reverse=True)
        
        print("\n" + "=" * 70)
        print("📊 匹配的公告（按评分排序）")
        print("=" * 70)
        
        for i, ann in enumerate(matched_announcements, 1):
            score = ann['score_info']
            title = ann['title'][:50] + '...' if len(ann['title']) > 50 else ann['title']
            
            print(f"\n[{i}] {title}")
            print(f"    📍 地域: {ann['location']}")
            print(f"    🏷️  业务类别: {score['category']}")
            print(f"    🔑 匹配关键词: {', '.join(score['matched_keywords'])}")
            print(f"    📊 评分: 总分 {score['total_score']} = 关键词 {score['keyword_score']} + 地域 {score['location_score']}")
        
        # 统计各业务类别
        print("\n" + "=" * 70)
        print("📈 业务类别分布")
        print("=" * 70)
        
        category_stats = {}
        for ann in matched_announcements:
            cat = ann['score_info']['category']
            category_stats[cat] = category_stats.get(cat, 0) + 1
        
        for cat, count in sorted(category_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"  {cat}: {count} 条")
        
        # 地域分布
        print("\n" + "=" * 70)
        print("🗺️  地域分布（匹配项）")
        print("=" * 70)
        
        location_stats = {}
        for ann in matched_announcements:
            loc = ann['location']
            location_stats[loc] = location_stats.get(loc, 0) + 1
        
        for loc, count in sorted(location_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"  {loc}: {count} 条")
        
        # 验证地域加分策略
        print("\n" + "=" * 70)
        print("✅ 验证地域加分策略")
        print("=" * 70)
        
        liaoning_culture = [ann for ann in matched_announcements 
                           if '文化氛围' in ann['score_info']['category']
                           and '辽宁' in ann['location']]
        
        nearby_other = [ann for ann in matched_announcements
                       if '文化氛围' not in ann['score_info']['category']
                       and ann['score_info']['location_score'] > 0]
        
        print(f"  文化氛围类 + 辽宁省: {len(liaoning_culture)} 条")
        print(f"  其他类 + 周边省份加分: {len(nearby_other)} 条")
        
        if liaoning_culture:
            print("\n  文化氛围类（辽宁）示例:")
            for ann in liaoning_culture[:2]:
                print(f"    - {ann['title'][:40]}... [地域分: {ann['score_info']['location_score']}]")
        
        if nearby_other:
            print("\n  其他类（周边加分）示例:")
            for ann in nearby_other[:2]:
                print(f"    - {ann['title'][:40]}... [{ann['location']}] [地域分: {ann['score_info']['location_score']}]")
    
    else:
        print("\n⚠️ 未找到匹配的公告")
    
    # 保存结果
    result = {
        'total': len(announcements),
        'matched': len(matched_announcements),
        'category_distribution': category_stats if matched_announcements else {},
        'location_distribution': location_stats if matched_announcements else {},
        'top_5_matches': [
            {
                'title': ann['title'],
                'location': ann['location'],
                'category': ann['score_info']['category'],
                'keywords': ann['score_info']['matched_keywords'],
                'score': ann['score_info']['total_score']
            }
            for ann in matched_announcements[:5]
        ] if matched_announcements else []
    }
    
    os.makedirs('prototype/results', exist_ok=True)
    with open('prototype/results/test_04_result.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 结果已保存: prototype/results/test_04_result.json")
    
    # 验证结果
    print("\n" + "=" * 70)
    print("✅ 验证结果")
    print("=" * 70)
    
    success = True
    
    if len(matched_announcements) > 0:
        print("✅ 通过：成功匹配到相关公告")
    else:
        print("⚠️ 警告：未匹配到公告（可能是今天没有相关项目）")
        success = False
    
    # 验证评分机制
    if matched_announcements:
        has_keyword_score = any(ann['score_info']['keyword_score'] > 0 for ann in matched_announcements)
        has_location_score = any(ann['score_info']['location_score'] > 0 for ann in matched_announcements)
        
        if has_keyword_score:
            print("✅ 通过：关键词评分机制正常")
        else:
            print("❌ 失败：关键词评分异常")
            success = False
        
        if has_location_score:
            print("✅ 通过：地域评分机制正常")
        else:
            print("⚠️ 提示：本次无地域加分（可能都不在辽宁及周边）")
    
    print("\n" + "=" * 70)
    if success:
        print("🎉 测试4通过！关键词筛选功能正常")
    else:
        print("⚠️ 测试4部分通过（筛选逻辑正常，但未匹配到相关公告）")
    print("=" * 70)
    
    return success

if __name__ == '__main__':
    test_keyword_filter()
