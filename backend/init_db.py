"""
Database initialization script for CareerSphere AI.
Creates the database if it doesn't exist and initializes the tables.
"""
import sys
from app.db.session import engine, Base
from app.db.models import User


def init_db():
    print("Initializing CareerSphere AI database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables initialized successfully (users table ready).")
    except Exception as e:
        print(f"Error initializing tables: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    init_db()
