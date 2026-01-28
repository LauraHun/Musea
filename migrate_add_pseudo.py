"""
One-off migration: add pseudo column to users table in musea.db.
Run this if you see "no such column: pseudo" when signing up or logging in.

  python migrate_add_pseudo.py

Safe to run multiple times: it only adds the column if it's missing.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "musea.db")


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found: {DB_PATH}")
        print("Create it first with: python database_setup.py --db musea.db")
        return False

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
    )
    if not cur.fetchone():
        conn.close()
        print("Table 'users' not found. Create the DB with: python database_setup.py --db musea.db")
        return False

    # Check if pseudo column exists
    cur.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cur.fetchall()]
    if "pseudo" in columns:
        print("Column 'pseudo' already exists in users. Nothing to do.")
        conn.close()
        return True

    print("Adding 'pseudo' column to users...")
    cur.execute("ALTER TABLE users ADD COLUMN pseudo TEXT")
    cur.execute("UPDATE users SET pseudo = user_id WHERE pseudo IS NULL OR pseudo = ''")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_pseudo ON users(pseudo)")
    conn.commit()
    conn.close()
    print("Migration done. You can sign up and log in with pseudo now.")
    return True


if __name__ == "__main__":
    migrate()
