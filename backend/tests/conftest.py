"""
Shared test-session setup.

1. Database isolation (must happen before any ``app`` import): the suite runs
   against a dedicated ``*_test`` PostgreSQL database and Redis db 15, never the
   development database. Unsafe configuration aborts the run — see
   ``tests/db_isolation.py``.
2. The test database is migrated to the Alembic head at session start.
3. Real imported job listings in the development database are fingerprinted
   through a read-only connection at session start and re-checked at the end;
   any change not explained by a provider sync run fails the session.
4. Leftover coding-problem fixtures (slug prefix "test-") are purged.
"""
import pytest

from tests.db_isolation import (
    UnsafeTestDatabaseError,
    assert_engine_is_test_database,
    configure_test_environment,
    migrate_test_database,
    read_only_dev_engine,
    real_listing_fingerprint,
)

try:
    TEST_DATABASE = configure_test_environment()
except UnsafeTestDatabaseError as exc:  # fail safely before anything touches a database
    pytest.exit(f"Unsafe test database configuration: {exc}", returncode=4)

FIXTURE_SLUG_PREFIXES = ("test-js-", "test-sql-", "test-temp-")
_DEV_SNAPSHOT: dict = {}


def pytest_sessionstart(session):
    migrate_test_database()
    try:
        current = assert_engine_is_test_database()
    except UnsafeTestDatabaseError as exc:
        pytest.exit(str(exc), returncode=4)
    print(f"\n[tests] Using isolated test database: {current}")
    try:
        engine = read_only_dev_engine()
        _DEV_SNAPSHOT["engine"] = engine
        _DEV_SNAPSHOT["before"] = real_listing_fingerprint(engine)
    except Exception as exc:  # dev database not reachable: nothing of it can be modified either
        _DEV_SNAPSHOT["before"] = None
        print(f"[tests] Development database not reachable for the isolation check ({type(exc).__name__}).")


def pytest_sessionfinish(session, exitstatus):
    before = _DEV_SNAPSHOT.get("before")
    engine = _DEV_SNAPSHOT.get("engine")
    if not before or engine is None:
        return
    try:
        after = real_listing_fingerprint(engine)
    finally:
        engine.dispose()
    if after == before:
        print(f"\n[tests] Real job listings unchanged: {after['total']} rows ({after['active']} active).")
        return
    if after["sync_runs"] != before["sync_runs"]:
        # A provider sync (e.g. the dev API's scheduler) ran during the session; that is
        # an expected writer of real listings, not the test suite.
        print("\n[tests] Real job listings changed, but a provider sync ran during the session (not caused by tests).")
        return
    print(f"\n[tests] ERROR: real job listings changed during the test session: {before} -> {after}")
    session.exitstatus = 1


def _purge_fixture_problems() -> int:
    from sqlalchemy import or_

    from app.data.coding_bank import all_problems
    from app.db.models import CodingProblem, CodingSubmission, InterviewQuestion
    from app.db.session import SessionLocal

    bank = {spec.slug for spec in all_problems()}
    db = SessionLocal()
    try:
        ids = [
            pid for pid, slug in db.query(CodingProblem.id, CodingProblem.slug)
            .filter(or_(*[CodingProblem.slug.startswith(prefix) for prefix in FIXTURE_SLUG_PREFIXES]))
            .all()
            if slug not in bank  # never touch a curated bank problem
        ]
        if ids:
            db.query(CodingSubmission).filter(CodingSubmission.problem_id.in_(ids)).delete(synchronize_session=False)
            db.query(InterviewQuestion).filter(InterviewQuestion.problem_id.in_(ids)).update(
                {"problem_id": None}, synchronize_session=False
            )
            db.query(CodingProblem).filter(CodingProblem.id.in_(ids)).delete(synchronize_session=False)
            db.commit()
        return len(ids)
    except Exception:  # database unavailable: tests that need it will report that themselves
        db.rollback()
        return 0
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def _no_leftover_fixture_problems():
    _purge_fixture_problems()
    yield
    _purge_fixture_problems()
