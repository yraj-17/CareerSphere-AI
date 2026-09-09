from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

Base = declarative_base()


def get_engine():
    """Create and validate the PostgreSQL engine. Raises on connection failure."""
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,   # cheaply validates connections before use
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,    # recycle connections every 30 min
    )
    # Fail fast on startup if PostgreSQL is unreachable
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("[Database] Connected to PostgreSQL successfully.")
    return engine


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator:
    """FastAPI dependency — yields a SQLAlchemy session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
