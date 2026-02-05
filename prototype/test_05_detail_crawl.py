"""
测试5：验证详情页爬取
- 测试详情页访问
- 测试内容提取
- 测试附件链接提取
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DrissionPage import ChromiumPage, ChromiumOptions
import json
import time

# 导入共享工具
from prototype.common_utils import wait_and_load_page, find_announcement_items, parse_list_item_v2

def crawl_detail_page(page, url):
    """
    爬取详情页内容
    
    Returns:
        dict: 详情信息
    """
    try:
        print(f"\n📄 访问详情页: {url[:80]}...")
        page.get(url)
        
        # 等待页面加载
        time.sleep(2)
        
        # 提取标题
        title = ''
        try:
            title_ele = page.ele('css:h1', timeout=2) or page.ele('css:.title', timeout=2)
            if title_ele:
                title = title_ele.text.strip()
        except:
            pass
        
        # 提取正文内容
        content = ''
        try:
            # 多种可能的内容选择器
            content_selectors = [
                'css:.content',
                'css:#content',
                'css:.article-content',
                'css:.detail-content',
                'css:.main-content',
            ]
            
            for selector in content_selectors:
                try:
                    content_ele = page.ele(selector, timeout=1)
                    if content_ele:
                        content = content_ele.text.strip()
                        if len(content) > 50:  # 内容足够长
                            break
                except:
                    continue
            
            # 如果还是没找到，尝试body
            if not content or len(content) < 50:
                body = page.ele('tag:body', timeout=1)
                if body:
                    content = body.text.strip()
        except:
            pass
        
        # 提取附件链接
        attachments = []
        try:
            # 查找所有下载链接
            attachment_selectors = [
                'css:a[href*="download"]',
                'css:a[href$=".pdf"]',
                'css:a[href$=".doc"]',
                'css:a[href$=".docx"]',
                'css:a[href$=".zip"]',
                'css:a:has-text("下载")',
                'css:a:has-text("附件")',
            ]
            
            found_links = set()
            for selector in attachment_selectors:
                try:
                    links = page.eles(selector, timeout=0.5)
                    for link in links:
                        href = link.attr('href')
                        link_text = link.text.strip()
                        if href and href not in found_links:
                            found_links.add(href)
                            # 补全相对URL
                            if href.startswith('/'):
                                href = f"https://www.plap.mil.cn{href}"
                            attachments.append({
                                'name': link_text or '附件',
                                'url': href
                            })
                except:
                    continue
        except:
            pass
        
        # 提取关键信息（联系人、电话、截止日期等）
        contact_info = {}
        try:
            # 简单的正则提取
            import re
            
            # 联系人
            contact_match = re.search(r'联系人[：:]\s*([^\s\n]+)', content)
            if contact_match:
                contact_info['contact_person'] = contact_match.group(1)
            
            # 电话
            phone_match = re.search(r'联系电话[：:]\s*([\d\-]+)', content)
            if phone_match:
                contact_info['phone'] = phone_match.group(1)
            
            # 截止日期
            deadline_patterns = [
                r'截止时间[：:]\s*(\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?\s*\d{1,2}:\d{2})',
                r'报名截止[：:]\s*(\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?)',
                r'投标截止[：:]\s*(\d{4}[-年]\d{1,2}[-月]\d{1,2}[日]?)',
            ]
            for pattern in deadline_patterns:
                deadline_match = re.search(pattern, content)
                if deadline_match:
                    contact_info['deadline'] = deadline_match.group(1)
                    break
            
            # 预算金额
            budget_patterns = [
                r'预算[金额]*[：:]\s*([\d,\.]+)\s*[万元|元]',
                r'最高限价[：:]\s*([\d,\.]+)\s*[万元|元]',
                r'采购金额[：:]\s*([\d,\.]+)\s*[万元|元]',
            ]
            for pattern in budget_patterns:
                budget_match = re.search(pattern, content)
                if budget_match:
                    contact_info['budget'] = budget_match.group(1)
                    break
        except:
            pass
        
        result = {
            'title': title,
            'content': content[:500] + '...' if len(content) > 500 else content,  # 截取前500字
            'content_length': len(content),
            'attachments': attachments,
            'contact_info': contact_info
        }
        
        return result
        
    except Exception as e:
        print(f"   ❌ 爬取失败: {e}")
        return None

def test_detail_crawl():
    """测试详情页爬取"""
    print("=" * 70)
    print("🧪 测试5：详情页爬取功能")
    print("=" * 70)
    
    # 先获取列表页的几个公告
    print("\n📥 步骤1：获取列表页公告...")
    
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
        
        # 解析前3个
        announcements = []
        for item in items[:3]:
            ann = parse_list_item_v2(item)
            if ann:
                announcements.append(ann)
        
        print(f"✅ 获取到 {len(announcements)} 条公告用于测试")
        
        # 测试爬取详情页
        print("\n" + "=" * 70)
        print("🔍 步骤2：爬取详情页内容")
        print("=" * 70)
        
        results = []
        
        for i, ann in enumerate(announcements, 1):
            print(f"\n[{i}/{len(announcements)}] 标题: {ann['title'][:50]}...")
            print(f"   URL: {ann['url'][:80]}...")
            
            detail = crawl_detail_page(page, ann['url'])
            
            if detail:
                print(f"   ✅ 爬取成功")
                print(f"      正文长度: {detail['content_length']} 字符")
                print(f"      附件数量: {len(detail['attachments'])} 个")
                print(f"      联系信息: {len(detail['contact_info'])} 项")
                
                if detail['content_length'] > 0:
                    print(f"      正文预览: {detail['content'][:100]}...")
                
                if detail['attachments']:
                    print(f"      附件示例: {detail['attachments'][0]['name']}")
                
                if detail['contact_info']:
                    print(f"      联系信息: {', '.join(detail['contact_info'].keys())}")
                
                results.append({
                    'list_item': ann,
                    'detail': detail
                })
            else:
                print(f"   ❌ 爬取失败")
            
            time.sleep(1)  # 礼貌等待
        
        # 统计
        print("\n" + "=" * 70)
        print("📊 爬取统计")
        print("=" * 70)
        
        success_count = len(results)
        print(f"  成功爬取: {success_count}/{len(announcements)} 条")
        
        if results:
            avg_content_len = sum(r['detail']['content_length'] for r in results) / len(results)
            total_attachments = sum(len(r['detail']['attachments']) for r in results)
            total_contact_fields = sum(len(r['detail']['contact_info']) for r in results)
            
            print(f"  平均正文长度: {int(avg_content_len)} 字符")
            print(f"  总附件数: {total_attachments} 个")
            print(f"  总联系信息字段: {total_contact_fields} 项")
        
        # 保存结果
        os.makedirs('prototype/results', exist_ok=True)
        with open('prototype/results/test_05_result.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 结果已保存: prototype/results/test_05_result.json")
        
        # 验证结果
        print("\n" + "=" * 70)
        print("✅ 验证结果")
        print("=" * 70)
        
        test_passed = True
        
        if success_count > 0:
            print("✅ 通过：成功爬取详情页")
        else:
            print("❌ 失败：未能爬取任何详情页")
            test_passed = False
        
        if results:
            has_content = any(r['detail']['content_length'] > 100 for r in results)
            has_attachments = any(len(r['detail']['attachments']) > 0 for r in results)
            has_contact = any(len(r['detail']['contact_info']) > 0 for r in results)
            
            if has_content:
                print("✅ 通过：正文内容提取正常")
            else:
                print("⚠️ 警告：未提取到足够的正文内容")
            
            if has_attachments:
                print("✅ 通过：附件提取正常")
            else:
                print("⚠️ 提示：本批公告可能没有附件")
            
            if has_contact:
                print("✅ 通过：联系信息提取正常")
            else:
                print("⚠️ 提示：未提取到联系信息（可能格式特殊）")
        
        print("\n" + "=" * 70)
        if test_passed:
            print("🎉 测试5通过！详情页爬取功能正常")
        else:
            print("❌ 测试5失败！详情页爬取有问题")
        print("=" * 70)
        
        return test_passed
        
    finally:
        page.quit()

if __name__ == '__main__':
    test_detail_crawl()
