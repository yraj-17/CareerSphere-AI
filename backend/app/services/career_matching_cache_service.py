"""Redis cache helpers for final career matching responses."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Optional

from app.core.config import settings
from app.db.models import Profile
from app.services.cache_service import get_cache_client

logger = logging.getLogger(__name__)

_PREFIX = "careersphere:career_matching"


def _safe_list(values) -> list[str]:
    return sorted(str(value or "").strip().lower() for value in values if str(value or "").strip())


def _json_list(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item).strip()]
    except Exception:
        pass
    return [part.strip() for part in raw.split(",") if part.strip()]


def matching_input_fingerprint(profile: Profile) -> str:
    pref = profile.career_preferences
    payload: dict[str, Any] = {
        "profile": {
            "headline": profile.headline,
            "location": profile.location,
        },
        "skills": _safe_list([skill.normalized_name or skill.name for skill in profile.skills]),
        "projects": [
            {
                "name": project.name,
                "description": project.description,
                "technologies": _safe_list([tech.normalized_name or tech.name for tech in project.technologies]),
            }
            for project in sorted(profile.projects, key=lambda item: item.id or item.name or "")
        ],
        "experience": [
            {
                "company": exp.company,
                "job_title": exp.job_title,
                "employment_type": exp.employment_type,
                "start_date": exp.start_date.isoformat() if exp.start_date else None,
                "end_date": exp.end_date.isoformat() if exp.end_date else None,
                "currently_working": exp.currently_working,
            }
            for exp in sorted(profile.experience, key=lambda item: item.id or item.job_title or "")
        ],
        "preferences": {
            "target_job_role": pref.target_job_role if pref else None,
            "preferred_industry": pref.preferred_industry if pref else None,
            "preferred_work_type": pref.preferred_work_type if pref else None,
            "preferred_locations": _safe_list(_json_list(pref.preferred_locations if pref else None)),
            "career_interests": _safe_list(_json_list(pref.career_interests if pref else None)),
        },
        "opportunity_dataset": "curated-v1",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]


def career_matching_cache_key(user_id: str, profile: Profile) -> str:
    return f"{_PREFIX}:{user_id}:{matching_input_fingerprint(profile)}"


def get_cached_career_matching(key: str) -> Optional[dict[str, Any]]:
    try:
        raw = get_cache_client().get(key)
        if not raw:
            return None
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None
        return parsed
    except Exception as exc:
        logger.warning("[CareerMatchingCache] Cache get failed: %s", exc)
        return None


def set_cached_career_matching(key: str, payload: dict[str, Any]) -> None:
    try:
        get_cache_client().set(
            key,
            json.dumps(payload, sort_keys=True, default=str),
            ex=settings.CAREER_MATCHING_CACHE_TTL_SECONDS,
        )
    except Exception as exc:
        logger.warning("[CareerMatchingCache] Cache set failed: %s", exc)


def invalidate_career_matching_cache(user_id: str) -> None:
    pattern = f"{_PREFIX}:{user_id}:*"
    try:
        client = get_cache_client()
        keys = list(client.scan_iter(pattern))
        if keys:
            client.delete(*keys)
    except Exception as exc:
        logger.warning("[CareerMatchingCache] Cache invalidation failed: %s", exc)
