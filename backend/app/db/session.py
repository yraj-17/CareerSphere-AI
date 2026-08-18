import os
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

Base = declarative_base()


def get_engine():
    db_url = settings.DATABASE_URL
    try:
        if db_url.startswith("postgresql"):
            test_engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
            )
            # Test connection
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("[Database] Successfully connected to PostgreSQL database.")
            return test_engine
        else:
            return create_engine(
                db_url,
                connect_args={"check_same_thread": False} if "sqlite" in db_url else {}
            )
    except Exception as e:
        print(f"[Database Notice] Could not connect to PostgreSQL: {e}")
        print("[Database Notice] Falling back to local SQLite database (careersphere.db) for development.")
        print("[Database Notice] To use PostgreSQL, update DATABASE_URL in backend/.env with your PostgreSQL credentials.")
        fallback_url = "sqlite:///./careersphere.db"
        return create_engine(fallback_url, connect_args={"check_same_thread": False})


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator:
    """Dependency that yields a SQLAlchemy database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
