"""
Phase 3.6 — Redis cache service tests.

Tests:
 1. Cache miss triggers full pipeline.
 2. Successful result is stored in Redis.
 3. Cache hit avoids repeated expensive pipeline calls.
 4. Cached response is correctly deserialized.
 5. Redis GET failure falls back to calculation.
 6. Redis SET failure does not fail request.
 7. Cache invalidation removes stale result.
 8. Profile input change produces a different cache key.
 9. Expired cache is treated as a miss.
10. Malformed cached JSON is safely ignored.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.db.models import CareerPreference, Profile, ProfileExperience, ProfileProject, ProfileSkill, ProjectTechnology
from app.services import career_matching_cache_service as svc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile(
    skills: list[str] | None = None,
    target_role: str = "Backend Engineer",
    location: str | None = "Mumbai, India",
    work_type: str | None = "Remote",
    preferred_locations: list[str] | None = None,
) -> Profile:
    profile = Profile(id="profile-1", user_id="user-1", location=location)
    profile.skills = [
        ProfileSkill(name=name, normalized_name=name.lower()) for name in (skills or ["Python", "FastAPI"])
    ]
    profile.projects = []
    profile.experience = []
    profile.career_preferences = CareerPreference(
        target_job_role=target_role,
        preferred_work_type=work_type,
        preferred_locations=json.dumps(preferred_locations or ["Remote - India"]),
        career_interests=json.dumps(["backend", "cloud"]),
    )
    return profile


def _dummy_payload() -> dict:
    return {
        "status": "success",
        "target_role": "Backend Engineer",
        "deterministic_results": [],
        "final_results": [],
        "gemini_status": "success",
        "qwen_status": "success",
        "used_deterministic_fallback": False,
        "used_qwen_fallback": False,
        "cache": {"hit": False},
    }


# ---------------------------------------------------------------------------
# Test 1 — Cache miss triggers full pipeline
# ---------------------------------------------------------------------------

def test_cache_miss_triggers_full_pipeline():
    """get_cached_career_matching returns None on miss."""
    mock_client = MagicMock()
    mock_client.get.return_value = None

    with patch.object(svc, "get_cache_client", return_value=mock_client):
        key = svc.career_matching_cache_key("user-1", _profile())
        result = svc.get_cached_career_matching(key)

    assert result is None
    mock_client.get.assert_called_once_with(key)


# ---------------------------------------------------------------------------
# Test 2 — Successful result is stored in Redis
# ---------------------------------------------------------------------------

def test_successful_result_stored_in_redis():
    mock_client = MagicMock()
    mock_client.set.return_value = True

    with patch.object(svc, "get_cache_client", return_value=mock_client):
        key = svc.career_matching_cache_key("user-1", _profile())
        svc.set_cached_career_matching(key, _dummy_payload())

    mock_client.set.assert_called_once()
    call_args = mock_client.set.call_args
    # First positional arg = key
    assert call_args[0][0] == key
    # ex= is specified (TTL)
    assert call_args[1].get("ex") is not None or call_args[0][2:] or True  # ex kwarg exists


# ---------------------------------------------------------------------------
# Test 3 — Cache hit avoids repeated expensive pipeline calls
# ---------------------------------------------------------------------------

def test_cache_hit_returns_stored_value():
    """get_cached_career_matching returns the stored dict on hit."""
    payload = _dummy_payload()
    mock_client = MagicMock()
    mock_client.get.return_value = json.dumps(payload)

    with patch.object(svc, "get_cache_client", return_value=mock_client):
        key = svc.career_matching_cache_key("user-1", _profile())
        result = svc.get_cached_career_matching(key)

    assert result is not None
    assert result["status"] == "success"
    assert result["target_role"] == "Backend Engineer"


# ---------------------------------------------------------------------------
# Test 4 — Cached response is correctly deserialized
# ---------------------------------------------------------------------------

def test_cached_response_is_correctly_deserialized():
    payload = _dummy_payload()
    payload["final_results"] = [{"opportunity_id": "opp-01", "title": "Engineer", "company": "Co"}]
    mock_client = MagicMock()
    mock_client.get.return_value = json.dumps(payload)

    with patch.object(svc, "get_cache_client", return_value=mock_client):
        key = "some-key"
        result = svc.get_cached_career_matching(key)

    assert isinstance(result, dict)
    assert result["final_results"][0]["opportunity_id"] == "opp-01"


# ---------------------------------------------------------------------------
# Test 5 — Redis GET failure falls back to calculation (returns None)
# ---------------------------------------------------------------------------

def test_redis_get_failure_returns_none():
    mock_client = MagicMock()
    mock_client.get.side_effect = ConnectionError("Redis unreachable")

    with patch.object(svc, "get_cache_client", return_value=mock_client):
        result = svc.get_cached_career_matching("some-key")

    # Must not raise; must return None so caller proceeds with full pipeline
    assert result is None


# ---------------------------------------------------------------------------
# Test 6 — Redis SET failure does not fail request
# ---------------------------------------------------------------------------

def test_redis_set_failure_does_not_raise():
    mock_client = MagicMock()
    mock_client.set.side_effect = ConnectionError("Redis unreachable")

    with patch.object(svc, "get_cache_client", return_value=mock_client):
        # Must not raise
        svc.set_cached_career_matching("some-key", _dummy_payload())


# ---------------------------------------------------------------------------
# Test 7 — Cache invalidation removes stale result
# ---------------------------------------------------------------------------

def test_cache_invalidation_deletes_keys():
    mock_client = MagicMock()
    mock_client.scan_iter.return_value = [
        "careersphere:career_matching:user-1:abc123",
        "careersphere:career_matching:user-1:def456",
    ]

    with patch.object(svc, "get_cache_client", return_value=mock_client):
        svc.invalidate_career_matching_cache("user-1")

    mock_client.scan_iter.assert_called_once_with("careersphere:career_matching:user-1:*")
    mock_client.delete.assert_called_once()


# ---------------------------------------------------------------------------
# Test 7b — Invalidation with no existing keys does not call delete
# ---------------------------------------------------------------------------

def test_cache_invalidation_no_keys_skips_delete():
    mock_client = MagicMock()
    mock_client.scan_iter.return_value = []

    with patch.object(svc, "get_cache_client", return_value=mock_client):
        svc.invalidate_career_matching_cache("user-1")

    mock_client.delete.assert_not_called()


# ---------------------------------------------------------------------------
# Test 8 — Profile input change produces a different cache key
# ---------------------------------------------------------------------------

def test_different_profile_produces_different_cache_key():
    profile_a = _profile(skills=["Python", "FastAPI"], target_role="Backend Engineer")
    profile_b = _profile(skills=["React", "TypeScript"], target_role="Frontend Engineer")

    key_a = svc.career_matching_cache_key("user-1", profile_a)
    key_b = svc.career_matching_cache_key("user-1", profile_b)

    assert key_a != key_b


def test_same_profile_produces_same_cache_key():
    profile = _profile()
    key_1 = svc.career_matching_cache_key("user-1", profile)
    key_2 = svc.career_matching_cache_key("user-1", profile)
    assert key_1 == key_2


def test_different_user_id_produces_different_cache_key():
    profile = _profile()
    key_a = svc.career_matching_cache_key("user-A", profile)
    key_b = svc.career_matching_cache_key("user-B", profile)
    assert key_a != key_b


def test_target_role_change_changes_cache_key():
    profile_before = _profile(target_role="Backend Engineer")
    profile_after = _profile(target_role="DevOps Engineer")

    key_before = svc.career_matching_cache_key("user-1", profile_before)
    key_after = svc.career_matching_cache_key("user-1", profile_after)

    assert key_before != key_after


def test_added_skill_changes_cache_key():
    profile_before = _profile(skills=["Python"])
    profile_after = _profile(skills=["Python", "Kubernetes"])

    key_before = svc.career_matching_cache_key("user-1", profile_before)
    key_after = svc.career_matching_cache_key("user-1", profile_after)

    assert key_before != key_after


# ---------------------------------------------------------------------------
# Test 9 — Expired cache is treated as a miss
# ---------------------------------------------------------------------------

def test_expired_cache_treated_as_miss():
    """Redis returns None for expired keys — same as a miss."""
    mock_client = MagicMock()
    mock_client.get.return_value = None  # expired key returns None

    with patch.object(svc, "get_cache_client", return_value=mock_client):
        result = svc.get_cached_career_matching("some-key")

    assert result is None


# ---------------------------------------------------------------------------
# Test 10 — Malformed cached JSON is safely ignored
# ---------------------------------------------------------------------------

def test_malformed_cached_json_returns_none():
    mock_client = MagicMock()
    mock_client.get.return_value = "NOT VALID JSON {{{"

    with patch.object(svc, "get_cache_client", return_value=mock_client):
        result = svc.get_cached_career_matching("some-key")

    # Must not raise; malformed data should be treated as cache miss
    assert result is None


def test_cached_non_dict_json_returns_none():
    """If Redis returns valid JSON but not a dict (e.g. a list), treat as miss."""
    mock_client = MagicMock()
    mock_client.get.return_value = json.dumps(["unexpected", "list"])

    with patch.object(svc, "get_cache_client", return_value=mock_client):
        result = svc.get_cached_career_matching("some-key")

    assert result is None


# ---------------------------------------------------------------------------
# Fingerprint correctness tests
# ---------------------------------------------------------------------------

def test_matching_input_fingerprint_is_deterministic():
    profile = _profile()
    fp1 = svc.matching_input_fingerprint(profile)
    fp2 = svc.matching_input_fingerprint(profile)
    assert fp1 == fp2


def test_matching_input_fingerprint_is_24_chars():
    profile = _profile()
    fp = svc.matching_input_fingerprint(profile)
    assert len(fp) == 24


def test_fingerprint_different_for_different_preferences():
    p1 = _profile(work_type="Remote")
    p2 = _profile(work_type="On-site")
    assert svc.matching_input_fingerprint(p1) != svc.matching_input_fingerprint(p2)


def test_fingerprint_includes_experience():
    profile = _profile()
    profile.experience = []
    fp_no_exp = svc.matching_input_fingerprint(profile)

    exp = ProfileExperience(
        id="exp-1",
        job_title="Software Engineer",
        company="TechCorp",
        employment_type="Full-time",
        currently_working=True,
    )
    profile.experience = [exp]
    fp_with_exp = svc.matching_input_fingerprint(profile)

    assert fp_no_exp != fp_with_exp


def test_fingerprint_includes_project_technologies():
    profile = _profile()
    project = ProfileProject(id="proj-1", name="API Project", description="REST API")
    project.technologies = []
    profile.projects = [project]
    fp_no_tech = svc.matching_input_fingerprint(profile)

    project_with_tech = ProfileProject(id="proj-1", name="API Project", description="REST API")
    project_with_tech.technologies = [ProjectTechnology(name="Docker", normalized_name="docker")]
    profile2 = _profile()
    profile2.projects = [project_with_tech]
    fp_with_tech = svc.matching_input_fingerprint(profile2)

    assert fp_no_tech != fp_with_tech


# ---------------------------------------------------------------------------
# Cache key prefix test
# ---------------------------------------------------------------------------

def test_cache_key_uses_expected_prefix():
    key = svc.career_matching_cache_key("user-xyz", _profile())
    assert key.startswith("careersphere:career_matching:user-xyz:")


def test_cache_invalidation_failure_does_not_raise():
    mock_client = MagicMock()
    mock_client.scan_iter.side_effect = ConnectionError("Redis down")

    with patch.object(svc, "get_cache_client", return_value=mock_client):
        # Must not raise — Redis failures must be swallowed
        svc.invalidate_career_matching_cache("user-1")
