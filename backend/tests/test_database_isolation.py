"""The backend suite runs on a dedicated test database and cannot alter real job listings."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.config import settings
from app.db.models import Opportunity
from app.db.session import SessionLocal, engine
from app.services import job_sync_service as sync
from app.services.job_providers import NormalizedJob
from tests.db_isolation import (
    DEV_URL_ENV,
    UnsafeTestDatabaseError,
    read_only_dev_engine,
    real_listing_fingerprint,
    validate_test_database_url,
)


def test_suite_uses_dedicated_test_database():
    with engine.connect() as conn:
        current = conn.execute(text("SELECT current_database()")).scalar()
    assert current.endswith("_test")
    assert settings.DATABASE_URL.split("/")[-1].split("?")[0] == current
    dev_url = os.environ.get(DEV_URL_ENV)
    if dev_url:
        assert dev_url.split("/")[-1].split("?")[0] != current


def test_redis_and_scheduler_are_isolated_for_tests():
    assert settings.REDIS_URL.rstrip("/").endswith("/15") or os.environ.get("TEST_REDIS_URL")
    assert settings.JOB_SYNC_ENABLED is False


@pytest.mark.parametrize("url", [
    "postgresql+psycopg://u:p@localhost:5432/careersphere_db",          # the dev database
    "postgresql+psycopg://u:p@localhost:5432/careersphere",             # no _test suffix
    "postgresql+psycopg://u:p@db.prod.example.com:5432/careersphere_test",  # remote host
    "sqlite:///tmp_test",                                               # not PostgreSQL
])
def test_guard_rejects_unauthorized_databases(url):
    with pytest.raises(UnsafeTestDatabaseError):
        validate_test_database_url(url, "postgresql+psycopg://u:p@localhost:5432/careersphere_db")


def test_guard_rejects_test_url_equal_to_dev_url():
    same = "postgresql+psycopg://u:p@localhost:5432/careersphere_test"
    with pytest.raises(UnsafeTestDatabaseError):
        validate_test_database_url(same, same)


def test_guard_accepts_local_test_database():
    url = validate_test_database_url("postgresql://u:p@127.0.0.1:5432/careersphere_db_test",
                                     "postgresql://u:p@127.0.0.1:5432/careersphere_db")
    assert url.database == "careersphere_db_test"


@pytest.fixture()
def dev_engine():
    eng = read_only_dev_engine()
    if eng is None:
        pytest.skip("Development DATABASE_URL not available")
    try:
        real_listing_fingerprint(eng)
    except Exception:
        eng.dispose()
        pytest.skip("Development database not reachable")
    yield eng
    eng.dispose()


def test_dev_connection_used_for_verification_cannot_write(dev_engine):
    with dev_engine.connect() as conn, pytest.raises(DBAPIError, match="read-only"):
        conn.execute(text("UPDATE opportunities SET is_active = is_active WHERE false"))


def test_destructive_job_operations_never_touch_real_listings(dev_engine):
    before = real_listing_fingerprint(dev_engine)
    db = SessionLocal()
    try:
        # Worst case in the test database: import a listing under a real provider key,
        # withdraw every listing of a real board, expire everything, then delete all rows.
        job = NormalizedJob(provider="greenhouse", source_board="isolation-proof", external_id="1", title="Backend Engineer",
                            company="Isolation Proof", description="Python", job_url="https://jobs.example.org/1",
                            application_url="https://jobs.example.org/1")
        result = sync.SourceSyncResult(provider="greenhouse", source_board="isolation-proof", status="running")
        sync.upsert_jobs(db, "greenhouse", "isolation-proof", [job], True, result)
        db.commit()
        sync.upsert_jobs(db, "lever", "cred", [], True, sync.SourceSyncResult("lever", "cred", "running"))
        sync.expire_stale_listings(db, now=datetime.now(timezone.utc) + timedelta(days=3650))
        db.query(Opportunity).delete(synchronize_session=False)
        db.commit()
    finally:
        db.rollback()
        db.close()
    after = real_listing_fingerprint(dev_engine)
    assert after["total"] == before["total"] and after["checksum"] == before["checksum"]
