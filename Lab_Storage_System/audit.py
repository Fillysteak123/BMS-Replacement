# audit.py
import sqlite3
from datetime import datetime

DB_NAME = "storage.db"

class AuditLogger:
    def __init__(self, user_id):
        self.user_id = user_id

    def log(self, action, details=""):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute(
            'INSERT INTO audit_log (user_id, action, details) VALUES (?, ?, ?)',
            (self.user_id, action, details)
        )
        conn.commit()
        conn.close()
