from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings, normalize_database_url

Base = declarative_base()


def get_engine():
    """Create and validate the PostgreSQL engine. Raises on connection failure."""
    database_url = normalize_database_url(settings.DATABASE_URL)
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,
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
