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
        
        # 创建爬取历史表（用于增量爬取）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawl_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crawl_time DATETIME NOT NULL,
                announcement_count INTEGER DEFAULT 0,
                success INTEGER DEFAULT 1,
                start_date TEXT,
                end_date TEXT,
                filters TEXT,
                error_message TEXT
            )
        """)
        
        # 创建高意向项目追踪表（智能追踪：更正/流标等只关注已关注项目）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interested_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_fingerprint TEXT UNIQUE NOT NULL,
                project_code TEXT,
                project_name TEXT,
                source_announcement_id TEXT,
                feasibility_score REAL,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_announcement_id) REFERENCES announcements(id)
            )
        """)
        
        # 创建索引以提高查询性能（优化版）
        logger.debug("创建数据库索引...")
        
        # 公告表索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_announcements_id 
            ON announcements(id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_announcements_pub_date 
            ON announcements(pub_date DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_announcements_location 
            ON announcements(location)
        """)
        
        # 爬取历史表索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_crawl_time 
            ON crawl_history(crawl_time DESC)
        """)
        
        # 筛选项目表索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_filtered_announcement_id 
            ON filtered_projects(announcement_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_filtered_score 
            ON filtered_projects(feasibility_score DESC)
        """)
        
        # 分析结果表索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_analysis_announcement_id 
            ON analysis_results(announcement_id)
        """)
        
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_interested_fingerprint 
            ON interested_projects(project_fingerprint)
        """)
        
        self.conn.commit()
        logger.info("✅ 数据库初始化完成（含 7 个性能索引）")
    
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
    
    def add_interested_project(
        self,
        project_code: str = None,
        project_name: str = None,
        source_announcement_id: str = None,
        feasibility_score: float = None,
    ) -> int:
        """将高意向项目加入追踪名单（评分>=阈值时调用）。
        会为 project_code 和 project_name 各生成指纹，确保更正公告用任一提及方式都能匹配。
        Returns: 新增的指纹数量（0/1/2）
        """
        import hashlib
        added = 0
        seen_fp = set()
        cursor = self.conn.cursor()
        for raw in (project_code, project_name):
            norm = self._normalize_for_fingerprint(raw) if raw else ""
            if not norm or len(norm) < 2:
                continue
            fp = hashlib.sha256(norm.encode('utf-8')).hexdigest()
            if fp in seen_fp:
                continue
            seen_fp.add(fp)
            code_val = raw if (project_code and raw == project_code) else None
            name_val = raw if (project_name and raw == project_name) else None
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO interested_projects 
                    (project_fingerprint, project_code, project_name, source_announcement_id, feasibility_score)
                    VALUES (?, ?, ?, ?, ?)
                """, (fp, code_val, name_val, source_announcement_id, feasibility_score))
                if cursor.rowcount > 0:
                    added += 1
            except Exception as e:
                logger.warning(f"添加追踪指纹时忽略重复: {e}")
        self.conn.commit()
        return added
    
    def is_interested_project(self, project_fingerprint: str) -> bool:
        """检查项目指纹是否在追踪名单中"""
        cursor = self.conn.cursor()
        result = cursor.execute(
            "SELECT 1 FROM interested_projects WHERE project_fingerprint = ?",
            (project_fingerprint,),
        ).fetchone()
        return result is not None
    
    def get_interested_fingerprints_set(self):
        """获取所有追踪中的项目指纹集合（用于批量检查）"""
        cursor = self.conn.cursor()
        rows = cursor.execute(
            "SELECT project_fingerprint FROM interested_projects"
        ).fetchall()
        return {row[0] if hasattr(row, '__getitem__') else row['project_fingerprint'] for row in rows}
    
    @staticmethod
    def _normalize_for_fingerprint(s: str) -> str:
        """清洗字符串用于指纹计算"""
        if not s or not isinstance(s, str):
            return ""
        import re
        s = re.sub(r'\s+', '', s.strip())
        return s
    
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
    
    def execute_query(self, query, params=None):
        """执行数据库查询
        
        Args:
            query: SQL 查询语句
            params: 查询参数
            
        Returns:
            查询结果
        """
        cursor = self.conn.cursor()
        
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # 如果是 SELECT 查询，返回结果
            if query.strip().upper().startswith('SELECT'):
                return cursor.fetchall()
            
            # 否则提交事务
            self.conn.commit()
            return cursor.rowcount
            
        except Exception as e:
            logger.error(f"❌ 执行查询失败: {e}")
            self.conn.rollback()
            raise
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info("🔒 数据库连接已关闭")
