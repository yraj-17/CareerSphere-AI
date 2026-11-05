"""
Real job-listing synchronisation.

For every configured source (provider + board/feed):
  fetch → normalise/validate → insert new → update changed → touch unchanged
  → deactivate withdrawn listings (only after a *complete* fetch) → log a JobSyncRun.
After all sources: expire listings past their deadline or not seen recently.

Scheduling reuses the existing infrastructure: an asyncio task in the FastAPI
lifespan plus a Redis lock so only one API instance syncs at a time. There is no
RQ/Celery in this project, so none is introduced.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.data.job_taxonomy import (
    LEVEL_NAMES,
    TAXONOMY_VERSION,
    classify_role,
    extract_skills,
    level_from_title,
    level_from_years,
    parse_experience_years,
    skill_display_name,
)
from app.db.models import JobSyncRun, Opportunity, OpportunityRequiredSkill
from app.db.session import SessionLocal
from app.services.job_providers import (
    JobProvider,
    NormalizedJob,
    ProviderError,
    build_providers,
    configured_providers,
)
from app.services.job_providers.remotive import MIN_INTERVAL_HOURS as REMOTIVE_MIN_INTERVAL_HOURS

logger = logging.getLogger(__name__)

PROVIDER_KEYS = ("greenhouse", "lever", "ashby", "adzuna", "remotive")
COMPANY_BOARD_PROVIDERS = {"greenhouse", "lever", "ashby"}
# A listing that has not been seen by any successful fetch for this long is
# treated as stale (conservative expiry for sources without a reliable status).
UNSEEN_STALE_DAYS = 7

LOCK_KEY = "careersphere:job_sync:lock"
DATASET_VERSION_KEY = "careersphere:job_dataset_version"
LOCK_TTL_SECONDS = 60 * 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# Derivation (deterministic, never invents missing data)
# ─────────────────────────────────────────────────────────────────────────────

def listing_identity(job: NormalizedJob) -> str:
    """Provider-scoped external id. Company-board ids are namespaced by board."""
    if job.provider in COMPANY_BOARD_PROVIDERS and job.source_board:
        return f"{job.source_board}:{job.external_id}"[:255]
    return job.external_id[:255]


@dataclass
class DerivedFields:
    target_role: str
    experience_level: Optional[str]
    experience_min_years: Optional[int]
    experience_max_years: Optional[int]
    skills: list[str]
    opportunity_type: str


def derive_fields(job: NormalizedJob) -> DerivedFields:
    families = classify_role(job.title)
    min_years, max_years = parse_experience_years(job.description)
    level = level_from_title(job.title)
    if level is None:
        level = level_from_years(min_years)
    tag_text = " ".join(job.provider_tags)
    skills = extract_skills(f"{job.title}\n{job.description}\n{tag_text}")
    return DerivedFields(
        target_role=families[0] if families else (job.department or "Other")[:160],
        experience_level=LEVEL_NAMES.get(level) if level is not None else None,
        experience_min_years=min_years,
        experience_max_years=max_years,
        skills=skills,
        opportunity_type="internship" if job.employment_type == "internship" else "job",
    )


def content_hash(job: NormalizedJob) -> str:
    payload = {
        k: getattr(job, k)
        for k in ("title", "company", "description", "job_url", "application_url", "location", "country", "work_mode",
                  "employment_type", "salary_min", "salary_max", "salary_currency", "salary_period", "salary_text",
                  "posted_at", "source_updated_at", "expires_at", "department")
    }
    # Derived fields (skills, role family, level) depend on the taxonomy, so a
    # taxonomy change makes the next sync re-derive every stored listing.
    payload["taxonomy_version"] = TAXONOMY_VERSION
    encoded = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _is_expired(expires_at: Optional[datetime], now: datetime) -> bool:
    expires_at = _aware(expires_at)
    return bool(expires_at and expires_at < now)


def _apply(opportunity: Opportunity, job: NormalizedJob, derived: DerivedFields, digest: str) -> None:
    opportunity.title = job.title[:200]
    opportunity.company = job.company[:200]
    opportunity.description = job.description or ""
    opportunity.opportunity_type = derived.opportunity_type
    opportunity.target_role = derived.target_role[:160]
    opportunity.location = (job.location or None) and job.location[:160]
    opportunity.is_remote = job.work_mode == "remote"
    opportunity.experience_level = derived.experience_level
    opportunity.industry = None
    opportunity.salary_min = job.salary_min
    opportunity.salary_max = job.salary_max
    opportunity.application_url = (job.application_url or job.job_url or "")[:500] or None
    opportunity.job_url = (job.job_url or job.application_url or "")[:1000] or None
    opportunity.published_at = job.posted_at
    opportunity.expires_at = job.expires_at
    opportunity.source_board = job.source_board[:120] if job.source_board else None
    opportunity.source_attribution = (job.attribution or "")[:300] or None
    opportunity.country = job.country
    opportunity.work_mode = job.work_mode
    opportunity.employment_type = job.employment_type
    opportunity.experience_min_years = derived.experience_min_years
    opportunity.experience_max_years = derived.experience_max_years
    opportunity.salary_currency = job.salary_currency
    opportunity.salary_period = job.salary_period
    opportunity.salary_text = job.salary_text
    opportunity.source_updated_at = job.source_updated_at
    opportunity.content_hash = digest

    wanted = {skill_id: skill_display_name(skill_id)[:80] for skill_id in derived.skills}
    existing = {skill.normalized_name: skill for skill in opportunity.required_skills}
    for skill_id, skill in existing.items():
        if skill_id not in wanted:
            opportunity.required_skills.remove(skill)
    for skill_id, name in wanted.items():
        if skill_id not in existing:
            opportunity.required_skills.append(OpportunityRequiredSkill(name=name, normalized_name=skill_id[:80]))


# ─────────────────────────────────────────────────────────────────────────────
# Per-source synchronisation
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SourceSyncResult:
    provider: str
    source_board: Optional[str]
    status: str
    fetched: int = 0
    kept: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    deactivated: int = 0
    invalid: int = 0
    error: Optional[str] = None


def upsert_jobs(db: Session, provider: str, source_board: Optional[str], jobs: list[NormalizedJob],
                complete: bool, result: SourceSyncResult, now: Optional[datetime] = None) -> None:
    now = now or _now()
    unique: dict[str, NormalizedJob] = {}
    for job in jobs:
        errors = job.validation_errors()
        if errors:
            result.invalid += 1
            logger.info("[JobSync] Skipping invalid %s listing %r: %s", provider, job.external_id, ", ".join(errors))
            continue
        unique.setdefault(listing_identity(job), job)  # duplicates inside one response collapse
    result.kept = len(unique)

    existing_rows = (
        db.query(Opportunity)
        .options(selectinload(Opportunity.required_skills))
        .filter(Opportunity.source == provider, Opportunity.external_id.in_(list(unique)))
        .all()
    ) if unique else []
    by_identity = {row.external_id: row for row in existing_rows}

    for identity, job in unique.items():
        digest = content_hash(job)
        row = by_identity.get(identity)
        expired = _is_expired(job.expires_at, now)
        if row is None:
            row = Opportunity(source=provider, external_id=identity, first_seen_at=now, required_skills=[], preferred_skills=[])
            _apply(row, job, derive_fields(job), digest)
            db.add(row)
            result.inserted += 1
        elif row.content_hash != digest:
            _apply(row, job, derive_fields(job), digest)
            result.updated += 1
        else:
            result.unchanged += 1
        row.last_seen_at = now
        row.is_active = not expired
        row.inactive_reason = "expired" if expired else None

    if complete and source_board is not None:
        # Withdrawn: present before, absent from a complete listing of the same board.
        query = db.query(Opportunity).filter(
            Opportunity.source == provider,
            Opportunity.source_board == source_board,
            Opportunity.is_active.is_(True),
        )
        if unique:
            query = query.filter(~Opportunity.external_id.in_(list(unique)))
        result.deactivated = query.update(
            {Opportunity.is_active: False, Opportunity.inactive_reason: "withdrawn"}, synchronize_session=False
        )


def _recent_success(db: Session, provider: str, source_board: Optional[str], hours: float) -> bool:
    cutoff = _now() - timedelta(hours=hours)
    return db.query(JobSyncRun.id).filter(
        JobSyncRun.provider == provider,
        JobSyncRun.source_board == source_board,
        JobSyncRun.status == "success",
        JobSyncRun.finished_at >= cutoff,
    ).first() is not None


def sync_source(db: Session, source: JobProvider, trigger: str = "scheduled") -> SourceSyncResult:
    result = SourceSyncResult(provider=source.provider, source_board=source.source_board, status="running")
    run = JobSyncRun(provider=source.provider, source_board=source.source_board, trigger=trigger, status="running",
                     started_at=_now(), fetched_count=0, kept_count=0, inserted_count=0, updated_count=0,
                     unchanged_count=0, deactivated_count=0, invalid_count=0)
    db.add(run)
    db.commit()
    try:
        fetched = source.fetch()
        result.fetched = fetched.fetched
        upsert_jobs(db, source.provider, source.source_board, fetched.jobs, fetched.complete, result)
        result.status = "success"
    except ProviderError as exc:
        db.rollback()
        result.status, result.error = "error", str(exc)[:500]
    except Exception as exc:  # unexpected bug in normalisation/persistence — never hidden
        db.rollback()
        logger.exception("[JobSync] Unexpected failure syncing %s", source.source_key)
        result.status, result.error = "error", f"{source.source_key}: unexpected error ({type(exc).__name__})"
    finally:
        source.close()

    run = db.merge(run)
    run.status = result.status
    run.finished_at = _now()
    run.fetched_count, run.kept_count = result.fetched, result.kept
    run.inserted_count, run.updated_count, run.unchanged_count = result.inserted, result.updated, result.unchanged
    run.deactivated_count, run.invalid_count = result.deactivated, result.invalid
    run.error_message = result.error
    db.commit()
    log = logger.warning if result.status == "error" else logger.info
    log("[JobSync] %s: status=%s fetched=%d kept=%d inserted=%d updated=%d unchanged=%d deactivated=%d invalid=%d%s",
        source.source_key, result.status, result.fetched, result.kept, result.inserted, result.updated,
        result.unchanged, result.deactivated, result.invalid, f" error={result.error}" if result.error else "")
    return result


def expire_stale_listings(db: Session, now: Optional[datetime] = None) -> dict[str, int]:
    """Deactivate listings past their deadline, too old (aggregators), or unseen for a week."""
    now = now or _now()
    expired = db.query(Opportunity).filter(
        Opportunity.is_active.is_(True), Opportunity.expires_at.isnot(None), Opportunity.expires_at < now,
    ).update({Opportunity.is_active: False, Opportunity.inactive_reason: "expired"}, synchronize_session=False)

    max_age = now - timedelta(days=settings.JOB_LISTING_MAX_AGE_DAYS)
    too_old = db.query(Opportunity).filter(
        Opportunity.is_active.is_(True), Opportunity.source.in_(["adzuna", "remotive"]),
        Opportunity.published_at.isnot(None), Opportunity.published_at < max_age,
    ).update({Opportunity.is_active: False, Opportunity.inactive_reason: "stale"}, synchronize_session=False)

    unseen = db.query(Opportunity).filter(
        Opportunity.is_active.is_(True), Opportunity.source.in_(PROVIDER_KEYS),
        Opportunity.last_seen_at < now - timedelta(days=UNSEEN_STALE_DAYS),
    ).update({Opportunity.is_active: False, Opportunity.inactive_reason: "stale"}, synchronize_session=False)
    db.commit()
    return {"expired": expired, "too_old": too_old, "unseen": unseen}


# ─────────────────────────────────────────────────────────────────────────────
# Full run, lock, dataset version
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SyncSummary:
    started: bool
    reason: Optional[str] = None
    sources: list[SourceSyncResult] = field(default_factory=list)
    expiry: dict[str, int] = field(default_factory=dict)


def _redis():
    from app.db.redis_client import redis_client

    return redis_client


def _acquire_lock() -> Optional[bool]:
    """True = acquired, False = held elsewhere, None = Redis unavailable."""
    try:
        return bool(_redis().set(LOCK_KEY, _now().isoformat(), nx=True, ex=LOCK_TTL_SECONDS))
    except Exception as exc:
        logger.warning("[JobSync] Redis lock unavailable (%s); continuing without a lock.", exc)
        return None


def _release_lock() -> None:
    try:
        _redis().delete(LOCK_KEY)
    except Exception:
        pass


def is_sync_running() -> bool:
    try:
        return bool(_redis().exists(LOCK_KEY))
    except Exception:
        return False


def bump_dataset_version() -> None:
    try:
        _redis().set(DATASET_VERSION_KEY, _now().isoformat())
    except Exception as exc:
        logger.warning("[JobSync] Could not bump dataset version: %s", exc)


def get_dataset_version() -> str:
    try:
        return str(_redis().get(DATASET_VERSION_KEY) or "0")
    except Exception:
        return "0"


def run_full_sync(trigger: str = "scheduled", only: Optional[str] = None, db: Optional[Session] = None) -> SyncSummary:
    lock = _acquire_lock()
    if lock is False:
        return SyncSummary(started=False, reason="A job synchronisation is already running.")
    owns_session = db is None
    db = db or SessionLocal()
    summary = SyncSummary(started=True)
    try:
        sources = build_providers(only=only)
        if not sources:
            summary.reason = "No job providers are configured."
        for source in sources:
            if source.provider == "remotive" and _recent_success(db, "remotive", source.source_board, REMOTIVE_MIN_INTERVAL_HOURS):
                continue  # honour Remotive's "max ~4 requests a day"
            summary.sources.append(sync_source(db, source, trigger=trigger))
        summary.expiry = expire_stale_listings(db)
        changed = any(r.inserted or r.updated or r.deactivated for r in summary.sources) or any(summary.expiry.values())
        if changed:
            bump_dataset_version()
        return summary
    finally:
        if owns_session:
            db.close()
        if lock:
            _release_lock()


# ─────────────────────────────────────────────────────────────────────────────
# Status (never includes credentials)
# ─────────────────────────────────────────────────────────────────────────────

def active_listing_counts(db: Session) -> dict[str, int]:
    rows = db.query(Opportunity.source, func.count(Opportunity.id)).filter(
        Opportunity.is_active.is_(True), Opportunity.source.in_(PROVIDER_KEYS)
    ).group_by(Opportunity.source).all()
    return {source: count for source, count in rows}


def provider_status(db: Session) -> dict:
    counts = active_listing_counts(db)
    providers = []
    for config in configured_providers():
        last_success = db.query(func.max(JobSyncRun.finished_at)).filter(
            JobSyncRun.provider == config.provider, JobSyncRun.status == "success").scalar()
        last_error = db.query(JobSyncRun).filter(
            JobSyncRun.provider == config.provider, JobSyncRun.status == "error"
        ).order_by(JobSyncRun.started_at.desc()).first()
        last_run = db.query(JobSyncRun).filter(JobSyncRun.provider == config.provider).order_by(JobSyncRun.started_at.desc()).first()
        failing_sources = []
        for source in config.sources:
            latest = db.query(JobSyncRun).filter(JobSyncRun.provider == config.provider, JobSyncRun.source_board == source) \
                .order_by(JobSyncRun.started_at.desc()).first()
            if latest is not None and latest.status == "error":
                failing_sources.append(source)
        providers.append({
            "provider": config.provider,
            "enabled": config.enabled,
            "sources": list(config.sources),
            "attribution": config.attribution,
            "note": config.note or None,
            "active_listings": counts.get(config.provider, 0),
            "last_run_at": last_run.started_at if last_run else None,
            "last_run_status": last_run.status if last_run else None,
            "last_successful_sync_at": last_success,
            "last_error_at": last_error.started_at if last_error else None,
            "last_error": last_error.error_message if last_error else None,
            "failing_sources": failing_sources,
        })
    return {
        "sync_enabled": settings.JOB_SYNC_ENABLED,
        "sync_interval_minutes": settings.JOB_SYNC_INTERVAL_MINUTES,
        "sync_running": is_sync_running(),
        "total_active_listings": sum(counts.values()),
        "providers": providers,
    }


def listing_availability(db: Session) -> dict:
    """Small summary used by Career Matching to explain empty states."""
    counts = active_listing_counts(db)
    enabled = [c.provider for c in configured_providers() if c.enabled]
    last_success = db.query(func.max(JobSyncRun.finished_at)).filter(JobSyncRun.status == "success").scalar()
    recent_errors: list[str] = []
    for provider in enabled:
        latest = db.query(JobSyncRun).filter(JobSyncRun.provider == provider).order_by(JobSyncRun.started_at.desc()).first()
        if latest is not None and latest.status == "error":
            recent_errors.append(provider)
    return {
        "active_listings": sum(counts.values()),
        "configured_providers": enabled,
        "providers_with_errors": recent_errors,
        "last_successful_sync_at": last_success,
        "sync_running": is_sync_running(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Scheduler (asyncio task in the API process)
# ─────────────────────────────────────────────────────────────────────────────

_scheduler_task: Optional[asyncio.Task] = None


def _sync_due(db: Session) -> bool:
    last = db.query(func.max(JobSyncRun.started_at)).scalar()
    last = _aware(last)
    return last is None or last < _now() - timedelta(minutes=settings.JOB_SYNC_INTERVAL_MINUTES)


async def _scheduler_loop() -> None:
    await asyncio.sleep(15)  # let the API finish starting
    first = True
    while True:
        try:
            def _due() -> bool:
                with SessionLocal() as db:
                    return _sync_due(db)

            if (first and settings.JOB_SYNC_ON_STARTUP or not first) and await asyncio.to_thread(_due):
                summary = await asyncio.to_thread(run_full_sync, "startup" if first else "scheduled")
                if summary.started:
                    logger.info("[JobSync] Scheduled sync finished: %d sources.", len(summary.sources))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("[JobSync] Scheduled sync failed")
        first = False
        # Re-check regularly; _sync_due() decides whether the interval has elapsed.
        await asyncio.sleep(min(15, max(5, settings.JOB_SYNC_INTERVAL_MINUTES)) * 60)


def start_job_sync_scheduler() -> bool:
    global _scheduler_task
    if not settings.JOB_SYNC_ENABLED or _scheduler_task is not None:
        return False
    _scheduler_task = asyncio.get_running_loop().create_task(_scheduler_loop())
    return True


async def stop_job_sync_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task is None:
        return
    _scheduler_task.cancel()
    try:
        await _scheduler_task
    except (asyncio.CancelledError, Exception):
        pass
    _scheduler_task = None
