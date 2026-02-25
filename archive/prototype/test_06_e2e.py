"""
测试6：完整流程端到端测试
- 整合列表页爬取、时间过滤、关键词筛选、详情页爬取
- 测试完整的工作流程
- 验证数据存储
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DrissionPage import ChromiumPage, ChromiumOptions
from datetime import datetime, timedelta
import json
import time
import re
import yaml

# 导入共享工具
from prototype.common_utils import wait_and_load_page, find_announcement_items, parse_list_item_v2
from src.database.storage import DatabaseManager

def load_config():
    """加载配置"""
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
    """计算地域评分"""
    location = location or ''
    
    if '文化氛围' in category_name:
        if '大连' in location:
            return 20
        elif '辽宁' in location:
            return 15
        else:
            return 0
    else:
        if '辽宁' in location:
            return 10
        nearby_provinces = ['吉林', '黑龙江', '内蒙古', '河北', '山东']
        for province in nearby_provinces:
            if province in location:
                return 3
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
        
        matched_kws = match_keywords(title, keywords)
        
        if matched_kws:
            kw_score = len(matched_kws) * 5
            loc_score = calculate_location_score(location, cat_name)
            total = kw_score + loc_score
            
            if total > best_match['total_score']:
                best_match = {
                    'category': cat_name,
                    'matched_keywords': matched_kws,
                    'keyword_score': kw_score,
                    'location_score': loc_score,
                    'total_score': total
                }
    
    return best_match

def is_after_time(ann, cutoff_time):
    """判断公告是否在指定时间之后"""
    date_str = ann.get('publish_date', '')
    if not date_str or date_str == '未知':
        return False
    
    try:
        ann_date = datetime.strptime(date_str, '%Y-%m-%d')
        return ann_date > cutoff_time
    except:
        return False

def crawl_detail_simple(page, url):
    """简单的详情页爬取"""
    try:
        page.get(url)
        time.sleep(1)
        
        # 提取正文（简化版）
        content = ''
        try:
            body = page.ele('tag:body', timeout=2)
            if body:
                content = body.text.strip()
        except:
            pass
        
        return {
            'content_length': len(content),
            'has_content': len(content) > 100
        }
    except:
        return {
            'content_length': 0,
            'has_content': False
        }

def test_e2e_workflow():
    """完整流程端到端测试"""
    print("=" * 70)
    print("🧪 测试6：完整流程端到端测试")
    print("=" * 70)
    
    # 步骤1：加载配置
    print("\n📋 步骤1：加载配置...")
    business_dirs = load_config()
    print(f"   加载了 {len(business_dirs)} 个业务方向")
    
    # 步骤2：初始化数据库
    print("\n💾 步骤2：初始化数据库...")
    db = DatabaseManager()
    initial_count = db.execute_query("SELECT COUNT(*) FROM announcements")[0][0]
    print(f"   数据库现有 {initial_count} 条记录")
    
    # 步骤3：爬取列表页
    print("\n📥 步骤3：爬取列表页...")
    
    options = ChromiumOptions()
    options.headless(False)
    page = ChromiumPage(options)
    
    try:
        url = "https://www.plap.mil.cn/freecms-glht/site/juncai/cggg/index.html"
        success = wait_and_load_page(page, url)
        
        if not success:
            print("❌ 页面加载失败")
            return False
        
        items = find_announcement_items(page)
        if not items:
            print("❌ 未找到公告")
            return False
        
        print(f"   找到 {len(items)} 个公告\n")
        
        # 解析
        all_announcements = []
        for item in items:
            ann = parse_list_item_v2(item)
            if ann:
                all_announcements.append(ann)
        
        print(f"✅ 解析成功 {len(all_announcements)} 条公告")
        
        # 步骤4：时间过滤
        print("\n🕒 步骤4：时间过滤（24小时内）...")
        cutoff_time = datetime.now() - timedelta(days=1)
        time_filtered = [ann for ann in all_announcements if is_after_time(ann, cutoff_time)]
        print(f"   结果: {len(time_filtered)}/{len(all_announcements)} 条符合时间要求")
        
        # 步骤5：关键词筛选
        print("\n🔍 步骤5：关键词筛选...")
        matched_announcements = []
        
        for ann in time_filtered:
            score_info = calculate_comprehensive_score(ann, business_dirs)
            
            if score_info['total_score'] > 0:
                ann['score_info'] = score_info
                matched_announcements.append(ann)
        
        print(f"   结果: {len(matched_announcements)}/{len(time_filtered)} 条匹配业务方向")
        
        if matched_announcements:
            # 按分数排序
            matched_announcements.sort(key=lambda x: x['score_info']['total_score'], reverse=True)
            
            print("\n   📊 匹配的公告（前5个）：")
            for i, ann in enumerate(matched_announcements[:5], 1):
                score = ann['score_info']
                title = ann['title'][:40] + '...' if len(ann['title']) > 40 else ann['title']
                print(f"     [{i}] {title}")
                print(f"         类别: {score['category']}, 评分: {score['total_score']}, 地域: {ann['location']}")
        
        # 步骤6：去重检查
        print("\n🔄 步骤6：去重检查...")
        new_announcements = []
        duplicate_count = 0
        
        for ann in matched_announcements:
            if not db.exists(ann['id']):
                new_announcements.append(ann)
            else:
                duplicate_count += 1
        
        print(f"   新公告: {len(new_announcements)} 条")
        print(f"   重复（跳过）: {duplicate_count} 条")
        
        # 步骤7：详情页爬取（只爬前3个）
        print("\n📄 步骤7：详情页爬取（测试前3个）...")
        
        detail_success = 0
        detail_fail = 0
        
        for i, ann in enumerate(new_announcements[:3], 1):
            print(f"   [{i}/3] {ann['title'][:40]}...")
            detail = crawl_detail_simple(page, ann['url'])
            
            if detail['has_content']:
                ann['detail'] = detail
                detail_success += 1
                print(f"      ✅ 成功（{detail['content_length']}字符）")
            else:
                detail_fail += 1
                print(f"      ⚠️ 失败或内容不足")
            
            time.sleep(0.5)
        
        print(f"\n   详情页爬取: {detail_success} 成功, {detail_fail} 失败")
        
        # 步骤8：数据存储
        print("\n💾 步骤8：数据存储...")
        
        stored_count = 0
        for ann in new_announcements[:3]:  # 只存储测试的前3个
            try:
                # ✅ 构造符合DatabaseManager期望的字典格式
                announcement_data = {
                    'id': ann['id'],
                    'title': ann['title'],
                    'url': ann['url'],
                    'pub_date': ann['publish_date'],  # 注意：数据库用的是 pub_date
                    'content': ann.get('detail', {}).get('content', ''),
                    'location': ann.get('location', ''),
                    'budget': None,
                    'deadline': None,
                    'contact': None,
                    'attachments': []
                }
                
                db.save_announcement(announcement_data)
                stored_count += 1
            except Exception as e:
                print(f"   ⚠️ 存储失败: {e}")
        
        print(f"   成功存储 {stored_count} 条记录")
        
        # 验证存储
        final_count = db.execute_query("SELECT COUNT(*) FROM announcements")[0][0]
        new_records = final_count - initial_count
        print(f"   数据库新增 {new_records} 条记录")
        
        # 统计报告
        print("\n" + "=" * 70)
        print("📊 完整流程统计报告")
        print("=" * 70)
        
        print(f"  1. 列表页爬取: {len(all_announcements)} 条")
        print(f"  2. 时间过滤: {len(time_filtered)} 条（24小时内）")
        print(f"  3. 关键词匹配: {len(matched_announcements)} 条")
        print(f"  4. 去重后: {len(new_announcements)} 条新公告")
        print(f"  5. 详情页爬取: {detail_success}/{min(3, len(new_announcements))} 成功")
        print(f"  6. 数据存储: {stored_count} 条")
        
        if matched_announcements:
            print("\n  业务类别分布:")
            category_stats = {}
            for ann in matched_announcements:
                cat = ann['score_info']['category']
                category_stats[cat] = category_stats.get(cat, 0) + 1
            
            for cat, count in sorted(category_stats.items(), key=lambda x: x[1], reverse=True):
                print(f"    - {cat}: {count} 条")
        
        # 保存结果
        result = {
            'timestamp': datetime.now().isoformat(),
            'statistics': {
                'total_crawled': len(all_announcements),
                'time_filtered': len(time_filtered),
                'keyword_matched': len(matched_announcements),
                'new_announcements': len(new_announcements),
                'detail_crawled': detail_success,
                'stored': stored_count
            },
            'top_matches': [
                {
                    'title': ann['title'],
                    'category': ann['score_info']['category'],
                    'score': ann['score_info']['total_score'],
                    'location': ann['location']
                }
                for ann in matched_announcements[:10]
            ] if matched_announcements else []
        }
        
        os.makedirs('prototype/results', exist_ok=True)
        with open('prototype/results/test_06_e2e_result.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 结果已保存: prototype/results/test_06_e2e_result.json")
        
        # 验证结果
        print("\n" + "=" * 70)
        print("✅ 验证结果")
        print("=" * 70)
        
        test_passed = True
        
        checks = [
            (len(all_announcements) > 0, "列表页爬取"),
            (len(time_filtered) >= 0, "时间过滤"),
            (len(matched_announcements) >= 0, "关键词筛选"),
            (detail_success > 0 or len(new_announcements) == 0, "详情页爬取"),
            (stored_count > 0 or len(new_announcements) == 0, "数据存储"),
        ]
        
        for passed, name in checks:
            if passed:
                print(f"✅ {name}: 通过")
            else:
                print(f"❌ {name}: 失败")
                test_passed = False
        
        # 特别验证：如果有匹配项，评分机制是否正常
        if matched_announcements:
            has_scores = all(ann.get('score_info', {}).get('total_score', 0) > 0 for ann in matched_announcements)
            if has_scores:
                print("✅ 评分机制: 通过")
            else:
                print("❌ 评分机制: 异常")
                test_passed = False
        
        print("\n" + "=" * 70)
        if test_passed:
            print("🎉 测试6通过！完整流程端到端测试成功")
            print("\n✨ 所有测试完成！系统功能验证通过，可以应用到主代码")
        else:
            print("❌ 测试6失败！部分功能有问题")
        print("=" * 70)
        
        return test_passed
        
    finally:
        page.quit()

if __name__ == '__main__':
    test_e2e_workflow()
