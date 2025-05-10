import sqlite3
import bcrypt

def create_user(username, password, role):
    try:
        conn = sqlite3.connect('storage.db')
        cursor = conn.cursor()

        # Hash the password
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        cursor.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                       (username, hashed_pw, role))

        conn.commit()
        conn.close()
        print(f"User '{username}' created successfully.")
    except sqlite3.Error as e:
        print(f"Error creating user: {e}")

if __name__ == "__main__":
    # Example usage:
    create_user("Renata", "renata", "material_lab_manager")
    create_user("Wesley", "wespassword", "lab_engineer")
    create_user("Zach", "zachpassword", "lab_engineer")
    create_user("guest", "guestpassword", "guest")
    create_user("head", "headpassword", "head_rd")