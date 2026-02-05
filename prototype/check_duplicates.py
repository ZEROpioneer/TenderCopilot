"""检查爬取结果是否有重复"""
import json

with open('prototype/results/test_full_workflow_result.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 从top_matches检查重复（这是8条匹配的）
print("=" * 70)
print("检查匹配的8条公告是否有重复")
print("=" * 70)

matches = data['top_matches']
print(f"\ntop_matches 声称有 {len(matches)} 条")

# 提取标题（前50个字符用于对比）
titles = [m['title'][:80] for m in matches]
unique_titles = set(titles)

print(f"去重后实际有 {len(unique_titles)} 条不同的标题\n")

if len(titles) != len(unique_titles):
    print("⚠️ 发现重复！\n")
    
    # 找出重复的
    from collections import Counter
    title_counts = Counter(titles)
    
    print("重复的公告：")
    for title, count in title_counts.items():
        if count > 1:
            print(f"  [{count}次] {title}...")

else:
    print("✅ 没有重复")

print("\n" + "=" * 70)
print("结论")
print("=" * 70)

if len(titles) != len(unique_titles):
    print("❌ 爬取有重复问题！")
    print(f"   声称8条，实际只有{len(unique_titles)}条不同的")
    print(f"   重复率: {(len(titles) - len(unique_titles)) / len(titles) * 100:.1f}%")
else:
    print("✅ 爬取结果正常，无重复")
