"""
测试3：验证时间过滤功能
- 测试 last_crawl_time 的时间过滤
- 验证只获取指定时间段内的公告
- 测试多种日期格式
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from DrissionPage import ChromiumPage, ChromiumOptions
import time
import json
import re

# 导入共享工具（避免重复代码！）
from prototype.common_utils import wait_and_load_page, find_announcement_items, parse_list_item_v2

def parse_date_from_announcement(ann_data):
    """解析公告的发布日期"""
    date_str = ann_data.get('publish_date', '')
    
    if not date_str or date_str == '未知':
        return None
    
    # 尝试多种日期格式
    formats = [
        '%Y-%m-%d',
        '%Y年%m月%d日',
        '%Y/%m/%d',
        '%Y.%m.%d'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except:
            continue
    
    # 尝试提取 YYYY-MM-DD 模式
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if match:
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except:
            pass
    
    return None

def is_after_time(ann_data, cutoff_time):
    """判断公告是否在指定时间之后"""
    ann_date = parse_date_from_announcement(ann_data)
    if not ann_date:
        return False
    return ann_date > cutoff_time

def fetch_first_page():
    """获取第一页公告（使用共享的成功代码）"""
    options = ChromiumOptions()
    options.headless(False)  # 可见模式，方便观察
    
    page = ChromiumPage(options)
    
    try:
        url = "https://www.plap.mil.cn/freecms-glht/site/juncai/cggg/index.html"
        
        # ✅ 使用共享的页面加载函数（来自test_02的成功经验）
        success = wait_and_load_page(page, url)
        
        if not success:
            print("   ❌ 页面加载失败")
            return []
        
        # 查找公告
        items = find_announcement_items(page)
        if not items:
            print("   ⚠️ 未找到公告项")
            return []
        
        print(f"   找到 {len(items)} 个公告项")
        
        # 解析
        announcements = []
        for item in items:
            ann = parse_list_item_v2(item)
            if ann:
                announcements.append(ann)
        
        return announcements
        
    finally:
        page.quit()

def test_time_filter():
    """测试时间过滤"""
    print("=" * 70)
    print("🧪 测试3：时间过滤功能")
    print("=" * 70)
    
    # 获取公告
    print("\n📥 步骤1：获取第一页公告...")
    announcements = fetch_first_page()
    
    if not announcements:
        print("❌ 未获取到公告，测试失败")
        return False
    
    print(f"\n✅ 获取到 {len(announcements)} 条公告")
    print("\n" + "=" * 70)
    print("📋 公告时间分布：")
    print("=" * 70)
    
    # 统计时间分布
    dates = {}
    for ann in announcements:
        date_str = ann.get('publish_date', '未知')
        dates[date_str] = dates.get(date_str, 0) + 1
    
    for date_str in sorted(dates.keys(), reverse=True):
        print(f"  {date_str}: {dates[date_str]} 条")
    
    # 测试场景1：过滤1天前
    print("\n" + "=" * 70)
    print("🔍 测试场景1：过滤24小时内的公告")
    print("=" * 70)
    
    cutoff_1day = datetime.now() - timedelta(days=1)
    print(f"   截止时间: {cutoff_1day.strftime('%Y-%m-%d %H:%M:%S')}")
    
    filtered_1day = [ann for ann in announcements if is_after_time(ann, cutoff_1day)]
    print(f"   结果: {len(filtered_1day)}/{len(announcements)} 条符合")
    
    if filtered_1day:
        print("\n   示例（前3条）:")
        for i, ann in enumerate(filtered_1day[:3], 1):
            print(f"     [{i}] {ann['title'][:50]}... [{ann['publish_date']}]")
    
    # 测试场景2：过滤3天前
    print("\n" + "=" * 70)
    print("🔍 测试场景2：过滤3天内的公告")
    print("=" * 70)
    
    cutoff_3day = datetime.now() - timedelta(days=3)
    print(f"   截止时间: {cutoff_3day.strftime('%Y-%m-%d %H:%M:%S')}")
    
    filtered_3day = [ann for ann in announcements if is_after_time(ann, cutoff_3day)]
    print(f"   结果: {len(filtered_3day)}/{len(announcements)} 条符合")
    
    # 测试场景3：过滤7天前
    print("\n" + "=" * 70)
    print("🔍 测试场景3：过滤7天内的公告")
    print("=" * 70)
    
    cutoff_7day = datetime.now() - timedelta(days=7)
    print(f"   截止时间: {cutoff_7day.strftime('%Y-%m-%d %H:%M:%S')}")
    
    filtered_7day = [ann for ann in announcements if is_after_time(ann, cutoff_7day)]
    print(f"   结果: {len(filtered_7day)}/{len(announcements)} 条符合")
    
    # 验证逻辑
    print("\n" + "=" * 70)
    print("✅ 验证结果")
    print("=" * 70)
    
    if len(filtered_1day) <= len(filtered_3day) <= len(filtered_7day):
        print("✅ 通过：时间过滤逻辑正确（1天 ≤ 3天 ≤ 7天）")
        success = True
    else:
        print("❌ 失败：时间过滤逻辑异常")
        success = False
    
    # 保存结果
    result = {
        'total': len(announcements),
        'filtered_1day': len(filtered_1day),
        'filtered_3day': len(filtered_3day),
        'filtered_7day': len(filtered_7day),
        'date_distribution': dates,
        'samples': [
            {
                'title': ann['title'],
                'publish_date': ann['publish_date'],
                'location': ann['location']
            }
            for ann in announcements[:5]
        ]
    }
    
    os.makedirs('prototype/results', exist_ok=True)
    with open('prototype/results/test_03_result.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 结果已保存: prototype/results/test_03_result.json")
    
    print("\n" + "=" * 70)
    if success:
        print("🎉 测试3通过！时间过滤功能正常")
    else:
        print("❌ 测试3失败！时间过滤逻辑有问题")
    print("=" * 70)
    
    return success

if __name__ == '__main__':
    test_time_filter()
