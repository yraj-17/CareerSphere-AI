"""Redis-backed cache helpers for short-lived availability lookups."""
from typing import Optional

import redis as redis_lib

from app.core.config import settings
from app.db.redis_client import redis_client


def _availability_key(kind: str, value: str) -> str:
    return f"avail:{kind}:{value.lower()}"


def get_cached_availability(kind: str, value: str) -> Optional[str]:
    """Return cached JSON string for username/email availability, or None on miss/error."""
    try:
        return redis_client.get(_availability_key(kind, value))
    except Exception:
        return None


def set_cached_availability(kind: str, value: str, payload_json: str) -> None:
    """Cache username/email availability for AVAILABILITY_CACHE_TTL seconds."""
    try:
        redis_client.set(
            _availability_key(kind, value),
            payload_json,
            ex=settings.AVAILABILITY_CACHE_TTL,
        )
    except Exception:
        # Cache failures must never break auth/availability endpoints
        pass


def invalidate_availability(kind: str, value: str) -> None:
    try:
        redis_client.delete(_availability_key(kind, value))
    except Exception:
        pass


def get_cache_client() -> redis_lib.Redis:
    return redis_client
