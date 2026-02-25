"""检查数据库中的记录"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.storage import DatabaseManager

db = DatabaseManager()

print("\n=== 数据库中最近存储的5条公告 ===\n")
rows = db.execute_query('SELECT title, location, pub_date FROM announcements ORDER BY id DESC LIMIT 5')

if rows:
    for i, row in enumerate(rows, 1):
        title = row[0][:60] + '...' if len(row[0]) > 60 else row[0]
        print(f"{i}. {title}")
        print(f"   地域: {row[1]}, 日期: {row[2]}\n")
else:
    print("数据库为空")

print(f"\n总计公告数: {db.execute_query('SELECT COUNT(*) FROM announcements')[0][0]}")
