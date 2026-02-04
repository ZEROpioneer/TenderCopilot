"""数据库存储管理"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from loguru import logger


class DatabaseManager:
    """SQLite 数据库管理器"""
    
    def __init__(self, db_path='data/history.db'):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None
        self.init_database()
    
    def init_database(self):
        """初始化数据库表"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        cursor = self.conn.cursor()
        
        # 创建公告表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS announcements (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT,
                pub_date DATE,
                url TEXT UNIQUE,
                location TEXT,
                budget TEXT,
                deadline DATETIME,
                contact TEXT,
                attachments TEXT,
                status TEXT DEFAULT 'discovered',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建筛选项目表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS filtered_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                announcement_id TEXT,
                matched_directions TEXT,
                feasibility_score REAL,
                feasibility_level TEXT,
                status TEXT DEFAULT 'filtered',
                filtered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (announcement_id) REFERENCES announcements(id)
            )
        """)
        
        # 创建分析结果表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                announcement_id TEXT,
                extracted_info TEXT,
                confidence_score REAL,
                analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (announcement_id) REFERENCES announcements(id)
            )
        """)
        
        # 创建通知日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                announcement_id TEXT,
                channel TEXT,
                status TEXT,
                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                error_message TEXT,
                FOREIGN KEY (announcement_id) REFERENCES announcements(id)
            )
        """)
        
        # 创建任务日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_name TEXT,
                status TEXT,
                start_time DATETIME,
                end_time DATETIME,
                duration_seconds REAL,
                crawled_count INTEGER,
                matched_count INTEGER,
                error_message TEXT
            )
        """)
        
        self.conn.commit()
        logger.info("✅ 数据库初始化完成")
    
    def save_announcement(self, announcement):
        """保存公告"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO announcements 
                (id, title, content, pub_date, url, location, budget, deadline, contact, attachments, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                announcement['id'],
                announcement['title'],
                announcement.get('content'),
                announcement.get('pub_date'),
                announcement.get('url'),
                announcement.get('location'),
                announcement.get('budget'),
                announcement.get('deadline'),
                announcement.get('contact'),
                json.dumps(announcement.get('attachments', []))
            ))
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"❌ 保存公告失败: {e}")
            return False
    
    def save_filtered_project(self, announcement_id, match_results, feasibility):
        """保存筛选项目"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO filtered_projects 
                (announcement_id, matched_directions, feasibility_score, feasibility_level)
                VALUES (?, ?, ?, ?)
            """, (
                announcement_id,
                json.dumps(match_results),
                feasibility['total'],
                feasibility['level']
            ))
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"❌ 保存筛选项目失败: {e}")
            return False
    
    def save_analysis_result(self, announcement_id, extracted_info, confidence_score):
        """保存分析结果"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO analysis_results 
                (announcement_id, extracted_info, confidence_score, analyzed_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                announcement_id,
                json.dumps(extracted_info),
                confidence_score
            ))
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"❌ 保存分析结果失败: {e}")
            return False
    
    def exists(self, announcement_id):
        """检查公告是否存在"""
        cursor = self.conn.cursor()
        result = cursor.execute(
            "SELECT id FROM announcements WHERE id = ?", 
            (announcement_id,)
        ).fetchone()
        return result is not None
    
    def log_notification(self, announcement_id, channel, status, error_message=None):
        """记录通知日志"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO notification_logs 
            (announcement_id, channel, status, error_message)
            VALUES (?, ?, ?, ?)
        """, (announcement_id, channel, status, error_message))
        self.conn.commit()
    
    def log_task(self, task_name, status, start_time, end_time, stats=None, error_message=None):
        """记录任务日志"""
        cursor = self.conn.cursor()
        
        duration = (end_time - start_time).total_seconds()
        
        cursor.execute("""
            INSERT INTO task_logs 
            (task_name, status, start_time, end_time, duration_seconds, crawled_count, matched_count, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task_name,
            status,
            start_time,
            end_time,
            duration,
            stats.get('crawled', 0) if stats else 0,
            stats.get('matched', 0) if stats else 0,
            error_message
        ))
        self.conn.commit()
    
    def get_recent_projects(self, days=7, status=None):
        """查询最近的项目"""
        cursor = self.conn.cursor()
        
        query = """
            SELECT a.*, f.feasibility_score, f.feasibility_level
            FROM announcements a
            LEFT JOIN filtered_projects f ON a.id = f.announcement_id
            WHERE a.created_at >= datetime('now', '-{} days')
        """.format(days)
        
        if status:
            query += f" AND a.status = '{status}'"
        
        query += " ORDER BY a.created_at DESC"
        
        results = cursor.execute(query).fetchall()
        return [dict(row) for row in results]
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info("🔒 数据库连接已关闭")
