"""
Initialize CareerSphere AI infrastructure:
  1. PostgreSQL tables (via SQLAlchemy metadata)
  2. Alembic version stamp (so migrations stay in sync)
  3. Qdrant default collections
  4. MinIO application bucket
"""
import sys

from alembic import command
from alembic.config import Config

from app.db.session import engine, Base
from app.db.models import User, MediaObject  # noqa: F401
from app.services.qdrant_service import ensure_default_collections, ping_qdrant
from app.services.storage_service import ensure_bucket, ping_minio


def init_db() -> None:
    print("Initializing PostgreSQL tables...")
    Base.metadata.create_all(bind=engine)
    print("  -> users, media_objects ready.")

    # Keep Alembic revision history aligned when bootstrapping via create_all
    try:
        cfg = Config("alembic.ini")
        command.stamp(cfg, "head")
        print("  -> Alembic stamped at head.")
    except Exception as exc:
        print(f"  -> WARNING: could not stamp Alembic ({exc})")


def init_qdrant() -> None:
    print("Initializing Qdrant collections...")
    if not ping_qdrant():
        raise RuntimeError("Qdrant is not reachable. Start it with: docker compose up -d qdrant")
    ensure_default_collections()


def init_minio() -> None:
    print("Initializing MinIO bucket...")
    if not ping_minio():
        raise RuntimeError("MinIO is not reachable. Start it with: docker compose up -d minio")
    ensure_bucket()


def main() -> None:
    try:
        init_db()
        init_qdrant()
        init_minio()
        print("Infrastructure initialized successfully.")
    except Exception as exc:
        print(f"Initialization failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
