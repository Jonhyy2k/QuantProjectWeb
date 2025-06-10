# init_db.py

# We import the 'app' and 'db' objects from our main server file
from server import app, db

# The 'with app.app_context()' is important. It makes sure that our app's configuration
# (like the database URL) is loaded before we try to interact with the database.
with app.app_context():
    print("Creating database tables...")
    # This single command reads all the classes that inherit from db.Model
    # and creates the corresponding tables in your PostgreSQL database.
    db.create_all()
    print("Database tables created successfully.")