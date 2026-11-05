"""
Test-database isolation for the backend suite.

The suite must never write to the development or production database. This
module is imported by ``tests/conftest.py`` *before any app module*, so the
application's settings and SQLAlchemy engine are created against a dedicated
test database:

* ``TEST_DATABASE_URL`` (environment or ``.env``) if set, otherwise the
  development ``DATABASE_URL`` with ``_test`` appended to the database name.
* The URL is refused unless the database name ends with ``_test``, differs from
  the development database, and the host is local (``localhost``/``127.0.0.1``/
  ``::1``/``postgres``, or listed in ``TEST_DATABASE_ALLOWED_HOSTS``).
* Redis uses a separate logical database (``TEST_REDIS_URL`` or db 15), and the
  background job-sync scheduler is disabled.

``read_only_dev_engine()`` gives a connection to the development database that
PostgreSQL itself refuses to write through, used only to *prove* that real
imported job listings are unchanged by the suite.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1", "postgres"}
DEV_URL_ENV = "CAREERSPHERE_DEV_DATABASE_URL"
PROVIDER_KEYS = ("greenhouse", "lever", "ashby", "adzuna", "remotive")


class UnsafeTestDatabaseError(RuntimeError):
    """The configured test database could be a real (dev/production) database."""


def _env_value(name: str) -> Optional[str]:
    if os.environ.get(name):
        return os.environ[name]
    for env_file in (BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"):
        if env_file.exists():
            value = dotenv_values(env_file).get(name)
            if value:
                return value
    return None


def _normalize_without_settings(url: str) -> URL:
    # Importing app.core.config would instantiate Settings with the dev URL, so
    # the driver normalisation is repeated here.
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    elif url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    return make_url(url)


def derive_test_url(dev_url: str) -> str:
    dev = _normalize_without_settings(dev_url)
    return dev.set(database=f"{dev.database}_test").render_as_string(hide_password=False)


def validate_test_database_url(test_url: str, dev_url: Optional[str]) -> URL:
    """Raise UnsafeTestDatabaseError unless ``test_url`` is a dedicated local test database."""
    url = _normalize_without_settings(test_url)
    if not url.drivername.startswith("postgresql"):
        raise UnsafeTestDatabaseError(f"Test database must be PostgreSQL, got {url.drivername!r}.")
    name = url.database or ""
    if not name.endswith("_test"):
        raise UnsafeTestDatabaseError(f"Refusing to run tests against database {name!r}: its name must end with '_test'.")
    if dev_url:
        dev = _normalize_without_settings(dev_url)
        if (dev.host, dev.port, dev.database) == (url.host, url.port, url.database) or dev.database == name:
            raise UnsafeTestDatabaseError(f"Test database {name!r} is the development database.")
    extra = {h.strip() for h in (_env_value("TEST_DATABASE_ALLOWED_HOSTS") or "").split(",") if h.strip()}
    if (url.host or "localhost") not in DEFAULT_ALLOWED_HOSTS | extra:
        raise UnsafeTestDatabaseError(
            f"Refusing to run tests against non-local host {url.host!r}. "
            "Add it to TEST_DATABASE_ALLOWED_HOSTS only if it is a disposable test server.")
    return url


def _ensure_database_exists(url: URL) -> None:
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database}).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin.dispose()


def configure_test_environment() -> URL:
    """Point the app at the test database. Must run before any ``app`` import."""
    if "app.core.config" in sys.modules or "app.db.session" in sys.modules:
        raise UnsafeTestDatabaseError("App settings were imported before the test database was configured.")

    dev_url = _env_value("DATABASE_URL")
    test_url = _env_value("TEST_DATABASE_URL") or (derive_test_url(dev_url) if dev_url else None)
    if not test_url:
        raise UnsafeTestDatabaseError("Set TEST_DATABASE_URL (or DATABASE_URL to derive '<name>_test').")
    url = validate_test_database_url(test_url, dev_url)
    _ensure_database_exists(url)

    rendered = url.render_as_string(hide_password=False)
    if dev_url:
        os.environ[DEV_URL_ENV] = dev_url
    os.environ["DATABASE_URL"] = rendered
    redis_url = _env_value("TEST_REDIS_URL")
    if not redis_url:
        base = (_env_value("REDIS_URL") or "redis://localhost:6379/0").rsplit("/", 1)[0]
        redis_url = f"{base}/15"
    os.environ["REDIS_URL"] = redis_url
    os.environ["JOB_SYNC_ENABLED"] = "false"
    return url


def migrate_test_database() -> None:
    """Bring the test database to the current schema (no data).

    Mirrors ``init_db.py``: the historical migrations do not replay cleanly on an
    empty database, so a fresh (or half-built) test database gets
    ``create_all`` + ``stamp head``; an already-stamped one is upgraded.
    """
    from alembic import command
    from alembic.config import Config

    from app.db import models  # noqa: F401 — register every table
    from app.db.session import Base, engine

    current = assert_engine_is_test_database()  # never reset anything but a *_test database
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    with engine.connect() as conn:
        stamped = conn.execute(text("SELECT to_regclass('public.alembic_version') IS NOT NULL")).scalar() and \
            conn.execute(text("SELECT count(*) FROM alembic_version")).scalar()
    if stamped:
        command.upgrade(cfg, "head")
        return
    with engine.begin() as conn:
        assert current.endswith("_test")
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(bind=engine)
    command.stamp(cfg, "head")


def assert_engine_is_test_database() -> str:
    from app.db.session import engine

    with engine.connect() as conn:
        current = conn.execute(text("SELECT current_database()")).scalar()
    if not current or not current.endswith("_test"):
        raise UnsafeTestDatabaseError(f"Engine is connected to {current!r}, not a *_test database.")
    return current


def read_only_dev_engine():
    """Engine for the development database on which PostgreSQL rejects all writes."""
    dev_url = os.environ.get(DEV_URL_ENV)
    if not dev_url:
        return None
    return create_engine(
        _normalize_without_settings(dev_url),
        connect_args={"options": "-c default_transaction_read_only=on"},
        pool_pre_ping=True,
    )


def real_listing_fingerprint(engine) -> Optional[dict]:
    """Count + checksum of real imported listings (every column that sync can change)."""
    if engine is None:
        return None
    sql = text(
        """
        SELECT count(*) AS total,
               count(*) FILTER (WHERE is_active) AS active,
               coalesce(md5(string_agg(id || '|' || coalesce(is_active::text, '') || '|' || updated_at::text
                                       || '|' || coalesce(last_seen_at::text, ''), ',' ORDER BY id)), '') AS checksum
        FROM opportunities WHERE source = ANY(:providers)
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"providers": list(PROVIDER_KEYS)}).mappings().one()
        sync_runs = conn.execute(text("SELECT count(*) FROM job_sync_runs")).scalar()
    return {"total": row["total"], "active": row["active"], "checksum": row["checksum"], "sync_runs": sync_runs}
