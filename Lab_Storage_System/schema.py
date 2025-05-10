import sqlite3

def init_db():
    conn = sqlite3.connect('storage.db')
    cursor = conn.cursor()

    cursor.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password_hash TEXT,
        role TEXT CHECK(role IN ('material_lab_manager', 'head_rd', 'lab_engineer', 'guest'))
    );

    CREATE TABLE IF NOT EXISTS equipment (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE,
        last_maintenance DATE,
        next_maintenance DATE,
        maintenance_interval INTEGER,
        report_path TEXT,
        description TEXT,  -- Added description column
        completed INTEGER DEFAULT 0  -- Added completed column
    );

    CREATE TABLE IF NOT EXISTS tests (
        id INTEGER PRIMARY KEY,
        equipment_id INTEGER,
        test_date DATE,
        result TEXT,
        FOREIGN KEY (equipment_id) REFERENCES equipment(id)
    );

    CREATE TABLE IF NOT EXISTS specifications (
        id INTEGER PRIMARY KEY,
        equipment_id INTEGER UNIQUE,
        model TEXT,
        manufacturer TEXT,
        calibration_date DATE,
        report_path TEXT,
        FOREIGN KEY (equipment_id) REFERENCES equipment(id)
    );

    CREATE TABLE IF NOT EXISTS quotations (
        id INTEGER PRIMARY KEY,
        customer TEXT,
        service TEXT,
        price REAL,
        date DATE
    );
    ''')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized!")