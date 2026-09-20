"""
Local database initialization helper.

Usage from the backend directory:
    python init_db.py

This applies Alembic migrations to DATABASE_URL, defaulting to backend/data/namm.db.
It does not drop or rewrite existing tables.
"""

from app.db.init_db import run_migrations


if __name__ == "__main__":
    run_migrations("alembic.ini")
    print("Database migrations applied successfully.")
