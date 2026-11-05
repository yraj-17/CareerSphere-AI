"""Career Matching API + pipeline: auth, admin endpoints, distinct empty states, pagination.

Listings here are in-memory test fixtures; the pipeline's loaders are patched so
no fixture can ever be stored or served as production data.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.db.models import CareerPreference, Opportunity, OpportunityRequiredSkill, Profile, ProfileSkill, User
from app.main import app
from app.schemas.career_matching_api import CareerMatchingAPIResponse
from app.services import career_matching_pipeline_service as pipeline
from app.services.career_matching_service import MatchFilters
from app.services.job_sync_service import SyncSummary

USER = User(id="user-abc", username="tester", email="tester@example.com", first_name="T", last_name="U")
ADMIN = User(id="admin-1", username="admin", email="Admin@Example.com", first_name="A", last_name="D")


@pytest.fixture()
def client():
    app.dependency_overrides[get_db] = lambda: iter([None])
    yield TestClient(app)
    app.dependency_overrides.clear()


def _as(user: User):
    app.dependency_overrides[get_current_user] = lambda: user


# ── Authentication / authorisation ───────────────────────────────────────────

def test_unauthenticated_request_is_rejected():
    app.dependency_overrides.clear()
    response = TestClient(app).get("/api/career-matching/me")
    assert response.status_code == 401


def test_user_comes_from_jwt_and_filters_are_forwarded(client):
    _as(USER)
    captured = {}

    async def fake(db, user, include_ai, filters, page, page_size):
        captured.update(user=user, include_ai=include_ai, filters=filters, page=page, page_size=page_size)
        return CareerMatchingAPIResponse(status="no_profile")

    with patch("app.api.career_matching.run_career_matching_pipeline", new=fake):
        response = client.get("/api/career-matching/me", params={
            "work_mode": "remote", "location": " Pune ", "employment_type": "full_time", "experience": "entry",
            "page": 2, "page_size": 5, "user_id": "someone-else"})
    assert response.status_code == 200
    assert captured["user"].id == "user-abc"  # user_id query param is ignored
    assert captured["filters"] == MatchFilters(location="Pune", work_mode="remote", employment_type="full_time", experience="entry")
    assert (captured["page"], captured["page_size"], captured["include_ai"]) == (2, 5, False)


def test_invalid_filter_values_are_rejected(client):
    _as(USER)
    assert client.get("/api/career-matching/me", params={"work_mode": "moon"}).status_code == 422
    assert client.get("/api/career-matching/me", params={"page_size": 500}).status_code == 422


def test_pipeline_failure_returns_503_not_empty_results(client):
    _as(USER)
    with patch("app.api.career_matching.run_career_matching_pipeline", new=AsyncMock(side_effect=RuntimeError("db down"))):
        response = client.get("/api/career-matching/me")
    assert response.status_code == 503
    assert "results" not in response.json()


def test_admin_endpoints_reject_regular_users(client, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "admin@example.com")
    _as(USER)
    assert client.get("/api/career-matching/providers/status").status_code == 403
    assert client.post("/api/career-matching/admin/sync").status_code == 403


def test_admin_endpoints_closed_when_no_admins_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "")
    _as(ADMIN)
    assert client.get("/api/career-matching/providers/status").status_code == 403


def test_provider_status_for_admin_never_contains_secrets(client, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "admin@example.com")
    monkeypatch.setattr(settings, "ADZUNA_APP_KEY", "super-secret-key")
    _as(ADMIN)
    status = {
        "sync_enabled": True, "sync_interval_minutes": 360, "sync_running": False, "total_active_listings": 3,
        "providers": [{"provider": "adzuna", "enabled": True, "sources": ["python developer"], "attribution": "Jobs by Adzuna",
                       "note": None, "active_listings": 3, "last_run_at": None, "last_run_status": "success",
                       "last_successful_sync_at": datetime(2026, 11, 5, tzinfo=timezone.utc), "last_error_at": None,
                       "last_error": None, "failing_sources": []}],
    }
    with patch("app.api.career_matching.provider_status", return_value=status):
        response = client.get("/api/career-matching/providers/status")
    assert response.status_code == 200
    assert response.json()["total_active_listings"] == 3
    assert "super-secret-key" not in response.text


def test_admin_can_trigger_sync(client, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "admin@example.com")
    _as(ADMIN)
    with patch("app.api.career_matching.is_sync_running", return_value=False), \
         patch("app.api.career_matching.run_full_sync", return_value=SyncSummary(started=True)) as run:
        response = client.post("/api/career-matching/admin/sync", params={"provider": "lever"})
    assert response.status_code == 202 and response.json()["status"] == "started"
    run.assert_called_once_with("manual", "lever")


def test_sync_trigger_reports_already_running(client, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "admin@example.com")
    _as(ADMIN)
    with patch("app.api.career_matching.is_sync_running", return_value=True):
        response = client.post("/api/career-matching/admin/sync")
    assert response.json()["status"] == "already_running"


# ── Pipeline states ──────────────────────────────────────────────────────────

def _profile(target="Backend Engineer", skills=("Python", "PostgreSQL")) -> Profile:
    profile = Profile(id="profile-1", user_id=USER.id, location="Pune, India")
    profile.skills = [ProfileSkill(name=s, normalized_name=s.lower()) for s in skills]
    profile.projects, profile.experience, profile.education = [], [], []
    profile.career_preferences = CareerPreference(target_job_role=target, preferred_work_type="Flexible",
                                                  preferred_locations=json.dumps(["Pune"]))
    return profile


def _listing(i: int, title="Backend Engineer") -> Opportunity:
    opp = Opportunity(id=f"opp-{i:03d}", title=f"{title} - Team {chr(64 + i)}", company=f"Company {i}", description="Python services",
                      opportunity_type="job", target_role="Backend Engineer", location="Pune, India", is_remote=False,
                      work_mode="hybrid", employment_type="full_time", source="lever", source_board="acme",
                      source_attribution="Listed on Acme's Lever job board", is_active=True,
                      job_url=f"https://jobs.lever.co/acme/{i}", application_url=f"https://jobs.lever.co/acme/{i}/apply",
                      published_at=datetime(2026, 11, 1, tzinfo=timezone.utc))
    opp.required_skills = [OpportunityRequiredSkill(name="Python", normalized_name="python")]
    opp.preferred_skills = []
    return opp


def _availability(active=10, providers=("lever",), errors=(), last_success=datetime(2026, 11, 5, tzinfo=timezone.utc), running=False):
    return {"active_listings": active, "configured_providers": list(providers), "providers_with_errors": list(errors),
            "last_successful_sync_at": last_success, "sync_running": running}


def _run(profile, availability=None, listings=(), filters=None, page=1, page_size=10):
    with patch.object(pipeline, "load_profile_for_career_matching", return_value=profile), \
         patch.object(pipeline, "listing_availability", return_value=availability or _availability()), \
         patch.object(pipeline, "load_active_listings", return_value=list(listings)), \
         patch.object(pipeline, "get_cached_career_matching", return_value=None), \
         patch.object(pipeline, "set_cached_career_matching"), \
         patch.object(pipeline, "get_dataset_version", return_value="v"):
        return asyncio.run(pipeline.run_career_matching_pipeline(None, USER, filters=filters, page=page, page_size=page_size))


def test_no_profile_state():
    assert _run(None).status == "no_profile"


def test_incomplete_profile_state():
    response = _run(_profile(target=None, skills=()))
    assert response.status == "incomplete_profile"
    assert set(response.missing_profile_fields) == {"target_job_role", "skills"}


def test_no_providers_configured_state():
    response = _run(_profile(), _availability(active=0, providers=()))
    assert response.status == "no_jobs_available" and "No job providers are configured" in response.message


def test_provider_error_state_is_distinct():
    response = _run(_profile(), _availability(active=0, errors=("lever",)))
    assert response.status == "provider_error" and "lever" in response.message


def test_importing_state_when_never_synced():
    response = _run(_profile(), _availability(active=0, last_success=None, running=True))
    assert response.status == "no_jobs_available" and "being imported" in response.message


def test_zero_listings_after_successful_sync_is_not_an_error():
    response = _run(_profile(), _availability(active=0))
    assert response.status == "no_jobs_available" and response.status != "provider_error"


def test_no_relevant_matches_state_has_reason_and_suggestions():
    response = _run(_profile(), listings=[_listing(1, title="Account Executive")])
    assert response.status == "no_relevant_matches"
    assert response.excluded_counts.get("low_relevance") == 1 and response.suggestions


def test_success_paginates_and_returns_original_links():
    listings = [_listing(i) for i in range(1, 24)]
    first = _run(_profile(), listings=listings, page=1, page_size=10)
    third = _run(_profile(), listings=listings, page=3, page_size=10)
    assert first.status == "success" and first.total_matches == 23 and first.total_pages == 3
    assert len(first.results) == 10 and len(third.results) == 3
    assert not {r.opportunity_id for r in first.results} & {r.opportunity_id for r in third.results}
    job = first.results[0]
    assert job.application_url.startswith("https://jobs.lever.co/acme/") and job.application_url.endswith("/apply")
    assert job.source == "lever" and job.source_label == "Lever" and job.attribution
    assert job.explanation and job.match_reasons and 0 < job.match_score <= 100
    assert job.salary_min is None and job.salary_text is None


def test_filters_reported_and_options_offered():
    response = _run(_profile(), listings=[_listing(1)], filters=MatchFilters(work_mode="remote"))
    assert response.status == "no_relevant_matches"
    assert response.applied_filters.work_mode == "remote"
    assert response.filter_options.locations == ["Pune"]
    assert any("filters" in tip for tip in response.suggestions)


def test_ai_annotations_never_change_scores_or_order():
    listings = [_listing(i) for i in range(1, 4)]
    base = _run(_profile(), listings=listings)

    async def fake_annotate(profile, run, page_results):
        for item in page_results:
            item.rerank_reason = "AI note"
        return "success", "success"

    with patch.object(pipeline, "_annotate_with_ai", new=fake_annotate), \
         patch.object(pipeline, "load_profile_for_career_matching", return_value=_profile()), \
         patch.object(pipeline, "listing_availability", return_value=_availability()), \
         patch.object(pipeline, "load_active_listings", return_value=listings), \
         patch.object(pipeline, "get_cached_career_matching", return_value=None), \
         patch.object(pipeline, "set_cached_career_matching"), \
         patch.object(pipeline, "get_dataset_version", return_value="v"):
        with_ai = asyncio.run(pipeline.run_career_matching_pipeline(None, USER, include_ai=True))
    assert [(r.opportunity_id, r.match_score) for r in with_ai.results] == [(r.opportunity_id, r.match_score) for r in base.results]
    assert all(r.rerank_reason == "AI note" for r in with_ai.results)
    assert with_ai.gemini_status == "success"


def test_ai_failure_keeps_deterministic_results():
    listings = [_listing(1)]
    with patch.object(pipeline, "_annotate_with_ai", new=AsyncMock(side_effect=RuntimeError("gemini down"))), \
         patch.object(pipeline, "load_profile_for_career_matching", return_value=_profile()), \
         patch.object(pipeline, "listing_availability", return_value=_availability()), \
         patch.object(pipeline, "load_active_listings", return_value=listings), \
         patch.object(pipeline, "get_cached_career_matching", return_value=None), \
         patch.object(pipeline, "set_cached_career_matching"), \
         patch.object(pipeline, "get_dataset_version", return_value="v"):
        response = asyncio.run(pipeline.run_career_matching_pipeline(None, USER, include_ai=True))
    assert response.status == "success" and len(response.results) == 1
    assert response.gemini_status == "unavailable" and response.qwen_status == "unavailable"
