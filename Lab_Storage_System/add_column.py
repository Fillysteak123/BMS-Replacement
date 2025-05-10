import sqlite3

conn = sqlite3.connect('storage.db')
cursor = conn.cursor()

# Check if the column exists
cursor.execute("PRAGMA table_info(equipment)")
columns = [col[1] for col in cursor.fetchall()]

if "equipment_num" not in columns:
    cursor.execute("ALTER TABLE equipment ADD COLUMN equipment_num TEXT;")
    print("Added column 'equipment_num'.")

conn.commit()
conn.close()
