"""测试模块导入"""

def test_imports():
    """测试所有新增模块是否能正常导入"""
    print("🧪 开始测试模块导入...\n")
    
    modules = [
        # 原有模块
        ('数据库管理', 'src.database.storage', 'DatabaseManager'),
        ('爬虫模块', 'src.spider.plap_spider', 'PLAPSpider'),
        ('爬取追踪器', 'src.spider.crawl_tracker', 'CrawlTracker'),
        ('附件处理', 'src.spider.attachment_handler', 'AttachmentHandler'),
        ('关键词匹配', 'src.filter.keyword_matcher', 'KeywordMatcher'),
        ('地域匹配', 'src.filter.location_matcher', 'LocationMatcher'),
        ('去重器', 'src.filter.deduplicator', 'Deduplicator'),
        ('信息提取', 'src.analyzer.info_extractor', 'InfoExtractor'),
        ('可行性评分', 'src.analyzer.feasibility_scorer', 'FeasibilityScorer'),
        
        # 新增模块
        ('内容分析器', 'src.analyzer.content_analyzer', 'ContentAnalyzer'),
        ('附件分析器', 'src.analyzer.attachment_analyzer', 'AttachmentAnalyzer'),
    ]
    
    results = []
    
    for name, module_path, class_name in modules:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            results.append((name, '✅ 导入成功'))
        except ImportError as e:
            results.append((name, f'❌ 导入失败: {e}'))
        except AttributeError as e:
            results.append((name, f'❌ 类不存在: {e}'))
        except Exception as e:
            results.append((name, f'❌ 未知错误: {e}'))
    
    # 打印结果
    print("📋 模块导入结果:\n")
    for name, result in results:
        print(f"  {name:15s} {result}")
    
    # 统计
    success_count = sum(1 for _, r in results if '✅' in r)
    total_count = len(results)
    
    print(f"\n📊 成功率: {success_count}/{total_count} ({success_count/total_count*100:.1f}%)")
    
    if success_count == total_count:
        print("✅ 所有模块导入成功！\n")
    else:
        print("⚠️ 部分模块导入失败，请检查！\n")

if __name__ == "__main__":
    test_imports()
