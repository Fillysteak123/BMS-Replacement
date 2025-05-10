# db.py
import sqlite3
from PySide6.QtWidgets import QMessageBox

DB_NAME = "storage.db"

def db_query(query, params=(), fetchone=False):
    try:
        conn = sqlite3.connect('storage.db')
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchone() if fetchone else cursor.fetchall()
        conn.commit()
        return result
    except sqlite3.Error as e:
        print(f"Database Error: {e}")
        return []  # ← this is the important fix!
    finally:
        conn.close()


def execute_sql(sql_command):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(sql_command)
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        _show_error(f"SQL Error: {e}")

def check_and_add_column():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(equipment)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]

        if "equipment_num" not in column_names:
            execute_sql('ALTER TABLE equipment ADD COLUMN equipment_num TEXT;')
    except sqlite3.Error as e:
        _show_error(f"SQL Error: {e}")

def _show_error(message):
    try:
        # Try using QMessageBox for GUI
        QMessageBox.critical(None, "Database Error", message)
    except Exception:
        # Fallback for CLI
        print(f"[DB ERROR] {message}")
