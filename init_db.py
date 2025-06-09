import sqlite3
import os

# Database file
DB_FILE = "stock_analysis.db"

def init_db():
    # Connect to SQLite database (creates file if it doesn't exist)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')

    # Create analyses table (if not exists)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            symbol TEXT NOT NULL,
            analysis_data TEXT NOT NULL,  -- JSON string of analysis result
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_action TEXT,  -- New column for Strong Buy/Sell, Buy/Sell
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Add user_action column if it doesn't exist (for existing databases)
    try:
        cursor.execute('ALTER TABLE analyses ADD COLUMN user_action TEXT')
        print("[INFO] Added user_action column to analyses table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("[INFO] user_action column already exists")
        else:
            raise e

    # Create watchlists table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS watchlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            symbol TEXT NOT NULL,
            UNIQUE(user_id, symbol),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Commit and close
    conn.commit()
    conn.close()
    print(f"[INFO] Database initialized at {DB_FILE}")

if __name__ == "__main__":
    init_db()