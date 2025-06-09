import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect("stock_analysis.db")
cursor = conn.cursor()
cursor.execute('''
    INSERT INTO users (username, password_hash)
    VALUES (?, ?)
''', ('testuser', generate_password_hash('testpassword')))
conn.commit()
conn.close()
print("Test user created: username=testuser, password=testpassword")

