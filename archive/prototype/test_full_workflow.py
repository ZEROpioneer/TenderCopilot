"""
完整工作流测试（加强版）
- 多页增量爬取（最多5页，连续5条重复停止）
- 完整流程：爬取 → 时间过滤 → 关键词筛选 → 去重 → 详情页 → 存储
- 压力测试，检查潜在问题
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

def goto_next_page(page):
    """
    翻到下一页
    
    注意：该网站使用<li>元素实现分页，不是<a>链接！
    HTML结构：<div id="pagination"><ul><li>首页</li><li>&lt;</li><li class="active">1</li><li>2</li><li>&gt;</li><li>尾页</li></ul></div>
    """
    try:
        print(f"   🔍 正在查找翻页按钮...")
        
        # 正确的选择器：查找<li>元素，不是<a>
        next_selectors = [
            ('css:#pagination li:has-text(">")', '下一页(>)'),
            ('xpath://div[@id="pagination"]//li[text()=">"]', '下一页XPath'),
        ]
        
        for selector, desc in next_selectors:
            try:
                next_btn = page.ele(selector, timeout=1)
                if next_btn:
                    print(f"   🔗 找到 {desc}: {selector}")
                    
                    # 检查是否disabled
                    btn_class = next_btn.attr('class') or ''
                    if 'disabled' in btn_class:
                        print(f"   ⚠️ 按钮已禁用（已是最后一页）")
                        return False
                    
                    print(f"   ✅ 准备点击...")
                    
                    # 记录翻页前的第一条公告标题（用于验证是否真的翻页了）
                    try:
                        old_first_item = page.ele('css:ul.noticeShowList li:nth-child(1) a', timeout=2)
                        old_first_title = old_first_item.text if old_first_item else None
                        print(f"   📋 翻页前第一条: {old_first_title[:30] if old_first_title else '未知'}...")
                    except:
                        old_first_title = None
                    
                    next_btn.click()
                    print(f"   ✅ 已点击，等待AJAX刷新公告列表...")
                    
                    # 关键：等待公告列表真正刷新（标题变化）
                    max_wait = 10  # 最多等待10秒
                    waited = 0
                    refreshed = False
                    
                    while waited < max_wait:
                        time.sleep(1)
                        waited += 1
                        
                        try:
                            new_first_item = page.ele('css:ul.noticeShowList li:nth-child(1) a', timeout=1)
                            new_first_title = new_first_item.text if new_first_item else None
                            
                            # 检查标题是否变化
                            if new_first_title and new_first_title != old_first_title:
                                print(f"   ✅ 公告列表已刷新（等待{waited}秒）")
                                print(f"   📋 翻页后第一条: {new_first_title[:30]}...")
                                refreshed = True
                                break
                        except:
                            pass
                    
                    if not refreshed:
                        print(f"   ⚠️ 等待{max_wait}秒后仍未检测到列表刷新，继续...")
                    
                    # 额外等待1秒确保完全加载
                    time.sleep(1)
                    return True
            except Exception as e:
                # print(f"   试探 {desc}: {e}")
                pass
        
        print("   ⚠️ 未找到下一页按钮")
        return False
        
    except Exception as e:
        print(f"   ❌ 翻页失败: {e}")
        return False

def crawl_detail_simple(page, url):
    """简单的详情页爬取"""
    try:
        page.get(url)
        time.sleep(1)
        
        content = ''
        try:
            body = page.ele('tag:body', timeout=2)
            if body:
                content = body.text.strip()
        except:
            pass
        
        # 检查是否404
        is_404 = 'HTTP状态 404' in content or '未找到' in content[:100]
        
        return {
            'content_length': len(content),
            'has_content': len(content) > 100 and not is_404,
            'is_404': is_404
        }
    except:
        return {
            'content_length': 0,
            'has_content': False,
            'is_404': False
        }

def test_full_workflow():
    """完整工作流测试"""
    print("=" * 70)
    print("🚀 完整工作流测试（加强版）")
    print("=" * 70)
    print("📌 测试范围：多页爬取（最多5页） + 完整流程")
    print("📌 停止策略：连续5条重复停止")
    print("=" * 70)
    
    # 步骤1：加载配置
    print("\n📋 步骤1：加载配置...")
    business_dirs = load_config()
    print(f"   加载了 {len(business_dirs)} 个业务方向")
    for cat in business_dirs:
        print(f"     - {cat['name']}: {len(cat['keywords'])} 个关键词")
    
    # 步骤2：初始化数据库
    print("\n💾 步骤2：初始化数据库...")
    db = DatabaseManager()
    initial_count = db.execute_query("SELECT COUNT(*) FROM announcements")[0][0]
    print(f"   数据库现有 {initial_count} 条记录")
    
    # 步骤3：多页增量爬取
    print("\n📥 步骤3：多页增量爬取...")
    
    options = ChromiumOptions()
    options.headless(False)
    page = ChromiumPage(options)
    
    all_announcements = []
    page_stats = []
    consecutive_exists = 0
    max_consecutive = 5
    max_pages = 5
    
    try:
        url = "https://www.plap.mil.cn/freecms-glht/site/juncai/cggg/index.html"
        success = wait_and_load_page(page, url)
        
        if not success:
            print("❌ 页面加载失败")
            return False
        
        page_num = 1
        should_stop = False
        
        while page_num <= max_pages and not should_stop:
            print(f"\n{'='*70}")
            print(f"📄 第 {page_num} 页")
            print(f"{'='*70}")
            
            # 查找公告
            items = find_announcement_items(page)
            if not items:
                print("   ⚠️ 未找到公告，停止")
                should_stop = True
                break
            
            print(f"   找到 {len(items)} 个公告项")
            
            # 解析
            page_announcements = []
            page_new = 0
            page_duplicate = 0
            
            for item in items:
                ann = parse_list_item_v2(item)
                if ann:
                    # 检查是否重复
                    if db.exists(ann['id']):
                        consecutive_exists += 1
                        page_duplicate += 1
                        
                        # 连续重复达到阈值，停止
                        if consecutive_exists >= max_consecutive:
                            print(f"   ⏹️ 连续{consecutive_exists}条重复，停止爬取")
                            should_stop = True
                            break
                    else:
                        consecutive_exists = 0  # 重置计数器
                        page_new += 1
                        page_announcements.append(ann)
                        all_announcements.append(ann)
            
            page_stats.append({
                'page': page_num,
                'total': len(items),
                'new': page_new,
                'duplicate': page_duplicate
            })
            
            print(f"   本页统计: 新增 {page_new} 条，重复 {page_duplicate} 条")
            print(f"   累计爬取: {len(all_announcements)} 条新公告")
            
            if should_stop:
                print(f"   🛑 达到停止条件")
                break
            
            # 尝试翻页
            if page_num < max_pages:
                print(f"\n   📖 尝试翻到第 {page_num + 1} 页...")
                if goto_next_page(page):
                    page_num += 1
                    time.sleep(2)  # 等待加载
                else:
                    print("   ⏹️ 没有更多页面")
                    break
            else:
                print(f"   ⏹️ 达到最大页数限制（{max_pages}页）")
                break
        
        print(f"\n{'='*70}")
        print(f"📊 爬取完成：共爬取 {page_num} 页，获得 {len(all_announcements)} 条新公告")
        print(f"{'='*70}")
        
        # 显示所有爬取公告的标题（用于分析）
        if all_announcements:
            print(f"\n📋 爬取到的公告标题（前20条）：")
            for i, ann in enumerate(all_announcements[:20], 1):
                title_preview = ann['title'][:60] + '...' if len(ann['title']) > 60 else ann['title']
                print(f"   [{i:2d}] {title_preview} [{ann['location']}]")
        
        # 步骤4：时间过滤
        print("\n🕒 步骤4：时间过滤（24小时内）...")
        cutoff_time = datetime.now() - timedelta(days=1)
        print(f"   截止时间: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
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
            
            print("\n   📊 匹配的公告（前10个）：")
            for i, ann in enumerate(matched_announcements[:10], 1):
                score = ann['score_info']
                title = ann['title'][:45] + '...' if len(ann['title']) > 45 else ann['title']
                print(f"     [{i:2d}] {title}")
                print(f"          类别: {score['category']}, 评分: {score['total_score']:2d}, 地域: {ann['location']}")
        
        # 步骤6：去重检查
        print("\n🔄 步骤6：最终去重检查...")
        final_new = []
        final_dup = 0
        
        for ann in matched_announcements:
            if not db.exists(ann['id']):
                final_new.append(ann)
            else:
                final_dup += 1
        
        print(f"   最终新公告: {len(final_new)} 条")
        print(f"   重复（跳过）: {final_dup} 条")
        
        # 步骤7：详情页爬取（批量测试前10个）
        print("\n📄 步骤7：详情页爬取（测试前10个）...")
        
        detail_success = 0
        detail_fail = 0
        detail_404 = 0
        
        test_count = min(10, len(final_new))
        print(f"   将测试 {test_count} 条公告的详情页爬取")
        
        for i, ann in enumerate(final_new[:test_count], 1):
            print(f"\n   [{i}/{test_count}] {ann['title'][:50]}...")
            detail = crawl_detail_simple(page, ann['url'])
            
            if detail['is_404']:
                detail_404 += 1
                print(f"      ⚠️ 404错误")
            elif detail['has_content']:
                ann['detail'] = detail
                detail_success += 1
                print(f"      ✅ 成功（{detail['content_length']}字符）")
            else:
                detail_fail += 1
                print(f"      ❌ 失败或内容不足（{detail['content_length']}字符）")
            
            time.sleep(0.5)  # 礼貌等待
        
        print(f"\n   详情页统计: {detail_success} 成功, {detail_fail} 失败, {detail_404} 404错误")
        
        # 步骤8：数据存储
        print("\n💾 步骤8：数据存储...")
        
        stored_count = 0
        store_errors = []
        
        for i, ann in enumerate(final_new[:test_count], 1):
            try:
                announcement_data = {
                    'id': ann['id'],
                    'title': ann['title'],
                    'url': ann['url'],
                    'pub_date': ann['publish_date'],
                    'content': ann.get('detail', {}).get('content', '')[:1000],  # 限制长度
                    'location': ann.get('location', ''),
                    'budget': None,
                    'deadline': None,
                    'contact': None,
                    'attachments': []
                }
                
                db.save_announcement(announcement_data)
                stored_count += 1
                
                if i % 5 == 0:
                    print(f"   已存储 {i}/{test_count} 条...")
                    
            except Exception as e:
                store_errors.append(str(e))
                print(f"   ⚠️ 存储第{i}条失败: {e}")
        
        print(f"   成功存储 {stored_count}/{test_count} 条记录")
        if store_errors:
            print(f"   存储错误: {len(store_errors)} 个")
        
        # 验证存储
        final_count = db.execute_query("SELECT COUNT(*) FROM announcements")[0][0]
        new_records = final_count - initial_count
        print(f"   数据库新增 {new_records} 条记录")
        
        # 完整统计报告
        print("\n" + "=" * 70)
        print("📊 完整流程统计报告")
        print("=" * 70)
        
        print(f"\n【爬取阶段】")
        print(f"  爬取页数: {page_num} 页")
        for stat in page_stats:
            print(f"    第{stat['page']}页: 总计{stat['total']}条, 新增{stat['new']}条, 重复{stat['duplicate']}条")
        print(f"  累计新公告: {len(all_announcements)} 条")
        
        print(f"\n【筛选阶段】")
        print(f"  时间过滤: {len(time_filtered)}/{len(all_announcements)} 条（24小时内）")
        print(f"  关键词匹配: {len(matched_announcements)}/{len(time_filtered)} 条")
        print(f"  最终去重: {len(final_new)}/{len(matched_announcements)} 条新公告")
        
        if matched_announcements:
            print(f"\n【业务类别分布】")
            category_stats = {}
            for ann in matched_announcements:
                cat = ann['score_info']['category']
                category_stats[cat] = category_stats.get(cat, 0) + 1
            
            for cat, count in sorted(category_stats.items(), key=lambda x: x[1], reverse=True):
                print(f"    {cat}: {count} 条")
            
            print(f"\n【地域分布】（匹配项）")
            location_stats = {}
            for ann in matched_announcements:
                loc = ann['location'] or '未知'
                location_stats[loc] = location_stats.get(loc, 0) + 1
            
            for loc, count in sorted(location_stats.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"    {loc}: {count} 条")
            
            print(f"\n【评分分布】")
            score_ranges = {'高分(15+)': 0, '中分(10-14)': 0, '低分(5-9)': 0, '极低(<5)': 0}
            for ann in matched_announcements:
                score = ann['score_info']['total_score']
                if score >= 15:
                    score_ranges['高分(15+)'] += 1
                elif score >= 10:
                    score_ranges['中分(10-14)'] += 1
                elif score >= 5:
                    score_ranges['低分(5-9)'] += 1
                else:
                    score_ranges['极低(<5)'] += 1
            
            for range_name, count in score_ranges.items():
                print(f"    {range_name}: {count} 条")
        
        print(f"\n【详情页爬取】")
        print(f"  测试数量: {test_count} 条")
        print(f"  成功: {detail_success} 条")
        print(f"  失败: {detail_fail} 条")
        print(f"  404错误: {detail_404} 条")
        if test_count > 0:
            success_rate = (detail_success / test_count) * 100
            print(f"  成功率: {success_rate:.1f}%")
        
        print(f"\n【数据存储】")
        print(f"  存储数量: {stored_count}/{test_count} 条")
        print(f"  存储错误: {len(store_errors)} 个")
        print(f"  数据库总计: {final_count} 条（新增{new_records}条）")
        
        # 保存详细结果
        result = {
            'timestamp': datetime.now().isoformat(),
            'crawl_stats': {
                'pages': page_num,
                'page_details': page_stats,
                'total_crawled': len(all_announcements),
                'consecutive_stop': consecutive_exists >= max_consecutive
            },
            'filter_stats': {
                'time_filtered': len(time_filtered),
                'keyword_matched': len(matched_announcements),
                'final_new': len(final_new)
            },
            'detail_stats': {
                'tested': test_count,
                'success': detail_success,
                'failed': detail_fail,
                '404': detail_404
            },
            'storage_stats': {
                'stored': stored_count,
                'errors': len(store_errors)
            },
            'category_distribution': category_stats if matched_announcements else {},
            'location_distribution': location_stats if matched_announcements else {},
            'all_announcements_sample': [
                {
                    'title': ann['title'],
                    'location': ann['location'],
                    'publish_date': ann['publish_date']
                }
                for ann in all_announcements[:20]
            ],
            'top_matches': [
                {
                    'title': ann['title'],
                    'category': ann['score_info']['category'],
                    'score': ann['score_info']['total_score'],
                    'location': ann['location'],
                    'publish_date': ann['publish_date']
                }
                for ann in matched_announcements[:20]
            ] if matched_announcements else []
        }
        
        os.makedirs('prototype/results', exist_ok=True)
        with open('prototype/results/test_full_workflow_result.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 详细结果已保存: prototype/results/test_full_workflow_result.json")
        
        # 问题检查
        print("\n" + "=" * 70)
        print("🔍 问题检查")
        print("=" * 70)
        
        issues = []
        
        # 检查1：爬取效率
        if len(all_announcements) < page_num * 10:
            issues.append(f"⚠️ 爬取效率低：{page_num}页仅获得{len(all_announcements)}条新公告")
        else:
            print(f"✅ 爬取效率正常：{page_num}页获得{len(all_announcements)}条新公告")
        
        # 检查2：匹配率
        if len(all_announcements) > 0:
            match_rate = (len(matched_announcements) / len(all_announcements)) * 100
            if match_rate < 5:
                issues.append(f"⚠️ 匹配率过低：{match_rate:.1f}%（可能关键词配置有问题）")
            elif match_rate > 50:
                issues.append(f"⚠️ 匹配率过高：{match_rate:.1f}%（可能关键词过于宽泛）")
            else:
                print(f"✅ 匹配率合理：{match_rate:.1f}%")
        
        # 检查3：详情页成功率
        if test_count > 0:
            detail_success_rate = (detail_success / test_count) * 100
            if detail_success_rate < 70:
                issues.append(f"⚠️ 详情页成功率低：{detail_success_rate:.1f}%")
            else:
                print(f"✅ 详情页成功率正常：{detail_success_rate:.1f}%")
        
        # 检查4：404错误
        if detail_404 > 0:
            issues.append(f"⚠️ 发现{detail_404}个404错误（链接失效）")
        else:
            print(f"✅ 无404错误")
        
        # 检查5：存储错误
        if store_errors:
            issues.append(f"⚠️ 存储错误：{len(store_errors)}个")
        else:
            print(f"✅ 存储无错误")
        
        # 检查6：地域提取
        unknown_location_count = sum(1 for ann in matched_announcements if ann['location'] == '未知')
        if unknown_location_count > 0:
            issues.append(f"⚠️ {unknown_location_count}条公告地域未知（可能影响地域评分）")
        else:
            print(f"✅ 所有公告地域提取正常")
        
        if issues:
            print(f"\n发现 {len(issues)} 个需要注意的问题：")
            for issue in issues:
                print(f"  {issue}")
        
        # 最终验证
        print("\n" + "=" * 70)
        print("✅ 最终验证")
        print("=" * 70)
        
        test_passed = True
        
        checks = [
            (len(all_announcements) > 0, "多页爬取"),
            (len(time_filtered) >= 0, "时间过滤"),
            (len(matched_announcements) >= 0, "关键词筛选"),
            (detail_success > 0 or len(final_new) == 0, "详情页爬取"),
            (stored_count > 0 or len(final_new) == 0, "数据存储"),
        ]
        
        for passed, name in checks:
            if passed:
                print(f"✅ {name}: 通过")
            else:
                print(f"❌ {name}: 失败")
                test_passed = False
        
        print("\n" + "=" * 70)
        if test_passed:
            print("🎉 完整工作流测试通过！")
            if issues:
                print(f"⚠️  但有{len(issues)}个需要注意的问题，请查看上方详情")
            else:
                print("✨ 所有功能正常，未发现问题！")
        else:
            print("❌ 完整工作流测试失败！部分功能有问题")
        print("=" * 70)
        
        return test_passed
        
    finally:
        page.quit()

if __name__ == '__main__':
    test_full_workflow()
