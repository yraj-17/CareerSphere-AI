"""Job synchronisation: persistence, duplicates, updates, withdrawal, expiry, run logging.

Uses the dev PostgreSQL database with a dedicated ``pytest-jobs`` source that the
Career Matching pipeline never loads (it only reads real provider keys). Only
rows created by these tests are removed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.models import JobSyncRun, Opportunity
from app.db.session import Base, SessionLocal, engine
from app.services import job_sync_service as sync
from app.services.job_providers import FetchResult, JobProvider, NormalizedJob, ProviderError

TEST_PROVIDER = "pytest-jobs"


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.query(Opportunity).filter(Opportunity.source == TEST_PROVIDER).delete(synchronize_session=False)
        session.query(JobSyncRun).filter(JobSyncRun.provider == TEST_PROVIDER).delete(synchronize_session=False)
        session.commit()
        session.close()


@pytest.fixture()
def board() -> str:
    return f"board-{uuid.uuid4().hex[:8]}"


def _job(board: str, ext: str, **overrides) -> NormalizedJob:
    values = dict(
        provider=TEST_PROVIDER, source_board=board, external_id=ext,
        title="Software Engineer - Backend (Python)", company="Acme",
        description="Python, PostgreSQL and Docker. 1-3 years of experience.",
        job_url=f"https://jobs.example.org/{ext}", application_url=f"https://jobs.example.org/{ext}/apply",
        location="Pune, India", country="India", work_mode="hybrid", employment_type="full_time",
        posted_at=datetime(2026, 10, 1, tzinfo=timezone.utc), attribution="Listed on Acme's board",
    )
    values.update(overrides)
    return NormalizedJob(**values)


def _sync(db, board, jobs, complete=True):
    result = sync.SourceSyncResult(provider=TEST_PROVIDER, source_board=board, status="running")
    sync.upsert_jobs(db, TEST_PROVIDER, board, jobs, complete, result)
    db.commit()
    return result


def _rows(db, board):
    return {row.external_id: row for row in db.query(Opportunity).filter(Opportunity.source_board == board).all()}


def test_insert_persists_normalised_listing(db, board):
    result = _sync(db, board, [_job(board, "1")])
    assert (result.inserted, result.updated, result.kept) == (1, 0, 1)
    row = _rows(db, board)["1"]
    assert row.title == "Software Engineer - Backend (Python)"
    assert row.application_url == "https://jobs.example.org/1/apply" and row.job_url == "https://jobs.example.org/1"
    assert row.target_role == "Backend Engineer"
    assert row.experience_min_years == 1 and row.experience_max_years == 3
    assert row.is_active and row.first_seen_at is not None and row.last_seen_at is not None
    assert row.salary_min is None and row.salary_max is None  # never invented
    assert {s.normalized_name for s in row.required_skills} >= {"python", "postgresql", "docker"}
    assert row.source_attribution == "Listed on Acme's board"


def test_duplicates_in_one_response_and_across_syncs_are_prevented(db, board):
    _sync(db, board, [_job(board, "1"), _job(board, "1")])
    second = _sync(db, board, [_job(board, "1")])
    assert len(_rows(db, board)) == 1
    assert (second.inserted, second.unchanged) == (0, 1)


def test_provider_update_updates_existing_record(db, board):
    _sync(db, board, [_job(board, "1")])
    first_seen = next(iter(_rows(db, board).values())).first_seen_at
    result = _sync(db, board, [_job(board, "1", title="Senior Backend Engineer", description="Golang and Kafka")])
    assert result.updated == 1
    db.expire_all()
    row = next(iter(_rows(db, board).values()))
    assert row.title == "Senior Backend Engineer" and row.experience_level == "Senior"
    assert {s.normalized_name for s in row.required_skills} == {"go", "kafka"}
    assert row.first_seen_at == first_seen


def test_withdrawn_listing_is_deactivated_after_complete_fetch(db, board):
    _sync(db, board, [_job(board, "1"), _job(board, "2")])
    result = _sync(db, board, [_job(board, "1")], complete=True)
    assert result.deactivated == 1
    db.expire_all()
    rows = _rows(db, board)
    assert rows["1"].is_active is True
    assert rows["2"].is_active is False and rows["2"].inactive_reason == "withdrawn"


def test_partial_fetch_never_deactivates(db, board):
    _sync(db, board, [_job(board, "1"), _job(board, "2")])
    result = _sync(db, board, [_job(board, "1")], complete=False)
    assert result.deactivated == 0
    db.expire_all()
    assert all(r.is_active for r in _rows(db, board).values())


def test_complete_fetch_with_zero_records_deactivates_board(db, board):
    _sync(db, board, [_job(board, "1")])
    result = _sync(db, board, [], complete=True)
    assert result.deactivated == 1


def test_reappearing_listing_is_reactivated(db, board):
    _sync(db, board, [_job(board, "1")])
    _sync(db, board, [], complete=True)
    _sync(db, board, [_job(board, "1")])
    db.expire_all()
    row = next(iter(_rows(db, board).values()))
    assert row.is_active and row.inactive_reason is None


def test_expired_listing_is_stored_inactive(db, board):
    past = datetime.now(timezone.utc) - timedelta(days=1)
    _sync(db, board, [_job(board, "1", expires_at=past)])
    row = next(iter(_rows(db, board).values()))
    assert row.is_active is False and row.inactive_reason == "expired"


def test_invalid_listings_are_skipped(db, board):
    result = _sync(db, board, [_job(board, "1", application_url=None, job_url=None), _job(board, "2", title="")])
    assert result.invalid == 2 and result.inserted == 0


def test_unseen_listing_becomes_stale(db, board, monkeypatch):
    monkeypatch.setattr(sync, "PROVIDER_KEYS", (*sync.PROVIDER_KEYS, TEST_PROVIDER))
    _sync(db, board, [_job(board, "1")])
    row = next(iter(_rows(db, board).values()))
    row.last_seen_at = datetime.now(timezone.utc) - timedelta(days=sync.UNSEEN_STALE_DAYS + 1)
    db.commit()
    sync.expire_stale_listings(db)
    db.expire_all()
    row = next(iter(_rows(db, board).values()))
    assert row.is_active is False and row.inactive_reason == "stale"


class _FakeProvider(JobProvider):
    provider = TEST_PROVIDER

    def __init__(self, board, jobs=None, error=None):
        super().__init__(source_board=board)
        self.jobs, self.error = jobs or [], error

    def fetch(self) -> FetchResult:
        if self.error:
            raise self.error
        return FetchResult(jobs=self.jobs, fetched=len(self.jobs), complete=True)


def test_sync_source_logs_success_run(db, board):
    result = sync.sync_source(db, _FakeProvider(board, [_job(board, "1")]), trigger="manual")
    assert result.status == "success" and result.inserted == 1
    run = db.query(JobSyncRun).filter(JobSyncRun.source_board == board).one()
    assert run.status == "success" and run.trigger == "manual" and run.inserted_count == 1 and run.finished_at


def test_provider_error_is_logged_and_does_not_touch_listings(db, board):
    sync.sync_source(db, _FakeProvider(board, [_job(board, "1")]))
    result = sync.sync_source(db, _FakeProvider(board, error=ProviderError("pytest-jobs: HTTP 500")))
    assert result.status == "error" and "HTTP 500" in result.error
    db.expire_all()
    assert all(r.is_active for r in _rows(db, board).values())  # a failed fetch never deactivates
    runs = db.query(JobSyncRun).filter(JobSyncRun.source_board == board).order_by(JobSyncRun.started_at).all()
    assert [r.status for r in runs] == ["success", "error"] and runs[-1].error_message


def test_unexpected_exception_is_reported_not_hidden(db, board):
    result = sync.sync_source(db, _FakeProvider(board, error=RuntimeError("bug")))
    assert result.status == "error" and "unexpected error" in result.error


def test_run_full_sync_respects_lock(monkeypatch):
    monkeypatch.setattr(sync, "_acquire_lock", lambda: False)
    summary = sync.run_full_sync(trigger="manual")
    assert summary.started is False and "already running" in summary.reason


def test_listing_identity_is_board_scoped_for_company_boards():
    job = _job("acme", "123")
    job.provider = "greenhouse"
    assert sync.listing_identity(job) == "acme:123"
    job.provider = "adzuna"
    assert sync.listing_identity(job) == "123"


def test_withdrawn_listing_disappears_from_career_matching(db, board):
    """End to end on the isolated test DB: a listing withdrawn by its board is no longer matched."""
    from app.services.career_matching_pipeline_service import load_active_listings

    provider = "lever"  # a real provider key — safe here because tests run on the *_test database
    jobs = [_job(board, "keep", provider=provider), _job(board, "gone", provider=provider)]
    result = sync.SourceSyncResult(provider=provider, source_board=board, status="running")
    sync.upsert_jobs(db, provider, board, jobs, True, result)
    db.commit()
    try:
        active = {o.external_id for o in load_active_listings(db) if o.source_board == board}
        assert active == {f"{board}:keep", f"{board}:gone"}
        result = sync.SourceSyncResult(provider=provider, source_board=board, status="running")
        sync.upsert_jobs(db, provider, board, [jobs[0]], True, result)  # board no longer lists "gone"
        db.commit()
        assert result.deactivated == 1
        db.expire_all()
        active = {o.external_id for o in load_active_listings(db) if o.source_board == board}
        assert active == {f"{board}:keep"}
        gone = db.query(Opportunity).filter(Opportunity.external_id == f"{board}:gone").one()
        assert gone.is_active is False and gone.inactive_reason == "withdrawn"
    finally:
        db.query(Opportunity).filter(Opportunity.source_board == board).delete(synchronize_session=False)
        db.commit()
