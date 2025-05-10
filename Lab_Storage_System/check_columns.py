import sqlite3

conn = sqlite3.connect('storage.db')
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(equipment)")
for row in cursor.fetchall():
    print(row)
conn.close()
