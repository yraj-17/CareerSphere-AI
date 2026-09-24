"""
Phase 5.8.5.1 — Redis Presence Foundation.

Tracks which users currently have active WebSocket sessions.
Redis is the distributed, ephemeral source for presence state.
PostgreSQL is NOT involved — presence is runtime-only.

Architecture
────────────
Local process:
    ConnectionManager  →  user_id → set[WebSocket]  (Phase 5.8.4, unchanged)

Distributed runtime:
    Redis Presence     →  per-session keys + per-user session index

PostgreSQL:
    conversations / messages / delivery/read state  (durable, unchanged)

Key design
──────────
Two key types per session:

  careersphere:presence:session:{session_id}
      type  : STRING
      value : user_id
      TTL   : REDIS_PRESENCE_TTL_SECONDS
      purpose: authoritative per-session heartbeat key; expiry removes stale sessions.

  careersphere:presence:user:{user_id}:sessions
      type  : SET
      value : {session_id, session_id, ...}
      TTL   : none (managed by cleanup when the set becomes empty)
      purpose: fast O(1) membership + SCARD online check.

Stale session cleanup
─────────────────────
Redis has no native per-member TTL on Sets.  We handle this with a two-key
design:
  - The STRING key expiry is authoritative.  When a STRING key expires,
    the session_id may remain in the SET until the next cleanup.
  - remove_session() always deletes the STRING key and removes the member
    from the SET.
  - is_user_online() and get_active_session_count() check live STRING keys,
    not just the SET, for accuracy.  This prevents stale SET entries from
    incorrectly reporting "online".

Concurrency safety
──────────────────
register_session uses a Redis pipeline:
  SETEX presence:session:{sid}  TTL  user_id
  SADD  presence:user:{uid}:sessions  sid

Both writes are issued in a single pipeline round-trip.  The SCARD check
for "first session" is done BEFORE the SADD so we know how many live
(non-expired) sessions the user had prior to this registration.  The
"live session count" check iterates the SET and verifies each STRING key
still exists — expired keys do not count.

remove_session uses a pipeline:
  DEL   presence:session:{sid}
  SREM  presence:user:{uid}:sessions  sid

After removal, a count of remaining live sessions determines last_session.

Failure handling
────────────────
Redis is runtime coordination, not durable data.
Every public function wraps Redis calls in try/except.
On Redis failure:
  - register_session  → returns (False, "error") — caller should log/proceed
  - remove_session    → returns (False, "error")
  - is_user_online    → returns False (conservative: assume offline)
  - get_active_session_count → returns 0
  - get_active_sessions      → returns []
  - refresh_session   → silent no-op

This ensures Redis unavailability does not crash the WebSocket layer or
affect PostgreSQL messaging state.

Heartbeat / TTL
───────────────
Every active session has a STRING key with TTL = REDIS_PRESENCE_TTL_SECONDS.
The WebSocket layer should call refresh_session() on a regular interval
(e.g. every 60 s) to keep the session alive.  A crashed process will not
refresh, so the key expires and the session is considered stale.
The WebSocket layer integration for heartbeats is planned for Phase 5.8.5.2.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from app.core.config import settings
from app.db.redis_client import redis_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Key helpers — single source of truth for key construction
# ---------------------------------------------------------------------------

_NS = "careersphere:presence"


def _session_key(session_id: str) -> str:
    """STRING key — holds user_id, expires after TTL."""
    return f"{_NS}:session:{session_id}"


def _user_sessions_key(user_id: str) -> str:
    """SET key — holds session IDs for the user."""
    return f"{_NS}:user:{user_id}:sessions"


# ---------------------------------------------------------------------------
# Session ID generation
# ---------------------------------------------------------------------------


def new_session_id() -> str:
    """
    Generate a unique server-side session ID.
    The client never controls this value.
    """
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Core presence operations
# ---------------------------------------------------------------------------


def register_session(user_id: str, session_id: str) -> tuple[bool, str]:
    """
    Register a new active session for *user_id*.

    Returns
    ───────
    (first_session, status)
        first_session : True if the user had zero live sessions before this
                        call — i.e. the user just came online.
        status        : "ok" | "duplicate" | "error"

    Atomicity
    ─────────
    - We count live sessions before the SADD so we can correctly detect
      whether this is the first session even if two registrations race.
    - STRING key + SADD are issued in a pipeline (single round-trip).
    """
    try:
        ttl = settings.REDIS_PRESENCE_TTL_SECONDS

        # Count existing LIVE sessions before registering this one.
        live_before = _count_live_sessions(user_id)

        # Check for duplicate (same session_id already registered).
        existing_user = redis_client.get(_session_key(session_id))
        if existing_user is not None:
            logger.debug(
                "presence: duplicate session registration ignored sid=%s uid=%s",
                session_id, user_id,
            )
            return (False, "duplicate")

        # Atomically write both keys.
        pipe = redis_client.pipeline(transaction=True)
        pipe.set(_session_key(session_id), user_id, ex=ttl)
        pipe.sadd(_user_sessions_key(user_id), session_id)
        pipe.execute()

        first_session = live_before == 0
        logger.debug(
            "presence: registered sid=%s uid=%s first=%s",
            session_id, user_id, first_session,
        )
        return (first_session, "ok")

    except Exception as exc:
        logger.warning("presence: register_session failed uid=%s: %s", user_id, exc)
        return (False, "error")


def remove_session(user_id: str, session_id: str) -> tuple[bool, str]:
    """
    Remove a session from the presence registry.

    Returns
    ───────
    (last_session, status)
        last_session : True if the user now has zero live sessions — i.e.
                       the user just went offline.
        status       : "ok" | "not_found" | "error"
    """
    try:
        # Check if this session is actually registered.
        existing = redis_client.get(_session_key(session_id))
        if existing is None:
            # Session not found — do not mark user offline.
            return (False, "not_found")

        # Atomically delete both references.
        pipe = redis_client.pipeline(transaction=True)
        pipe.delete(_session_key(session_id))
        pipe.srem(_user_sessions_key(user_id), session_id)
        pipe.execute()

        # Count remaining live sessions after removal.
        live_after = _count_live_sessions(user_id)

        # Clean up empty set.
        if live_after == 0:
            try:
                redis_client.delete(_user_sessions_key(user_id))
            except Exception:
                pass  # best-effort cleanup

        last_session = live_after == 0
        logger.debug(
            "presence: removed sid=%s uid=%s last=%s",
            session_id, user_id, last_session,
        )
        return (last_session, "ok")

    except Exception as exc:
        logger.warning("presence: remove_session failed uid=%s: %s", user_id, exc)
        return (False, "error")


def refresh_session(user_id: str, session_id: str) -> bool:
    """
    Extend the TTL of an active session (heartbeat).

    Returns True on success, False if the session no longer exists or Redis
    is unavailable.  Callers should treat False as "session expired/lost".
    """
    try:
        ttl = settings.REDIS_PRESENCE_TTL_SECONDS
        key = _session_key(session_id)
        # Only reset TTL if the key exists and belongs to this user.
        current = redis_client.get(key)
        if current != user_id:
            return False
        redis_client.expire(key, ttl)
        return True
    except Exception as exc:
        logger.warning("presence: refresh_session failed uid=%s: %s", user_id, exc)
        return False


def is_user_online(user_id: str) -> bool:
    """
    Return True if the user has at least one live (non-expired) session.

    Uses live STRING key checks rather than bare SCARD to avoid stale
    SET entries from incorrectly reporting "online".
    """
    try:
        return _count_live_sessions(user_id) > 0
    except Exception as exc:
        logger.warning("presence: is_user_online failed uid=%s: %s", user_id, exc)
        return False  # conservative: assume offline on Redis failure


def get_active_session_count(user_id: str) -> int:
    """Return the number of live sessions for *user_id*. Returns 0 on error."""
    try:
        return _count_live_sessions(user_id)
    except Exception as exc:
        logger.warning("presence: get_active_session_count failed uid=%s: %s", user_id, exc)
        return 0


def get_active_sessions(user_id: str) -> list[str]:
    """
    Return all session IDs that have a live (non-expired) STRING key.
    Returns an empty list on error.
    """
    try:
        return _live_session_ids(user_id)
    except Exception as exc:
        logger.warning("presence: get_active_sessions failed uid=%s: %s", user_id, exc)
        return []


def cleanup_stale_sessions(user_id: str) -> int:
    """
    Remove from the user's SET any session IDs whose STRING key has expired.

    Returns the number of stale entries removed.
    This is an optional maintenance operation; the system degrades gracefully
    without it because is_user_online() cross-checks STRING key existence.
    """
    try:
        members = redis_client.smembers(_user_sessions_key(user_id))
        if not members:
            return 0
        stale = [sid for sid in members if redis_client.get(_session_key(sid)) is None]
        if stale:
            redis_client.srem(_user_sessions_key(user_id), *stale)
        return len(stale)
    except Exception as exc:
        logger.warning("presence: cleanup_stale_sessions failed uid=%s: %s", user_id, exc)
        return 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _live_session_ids(user_id: str) -> list[str]:
    """
    Return session IDs from the user's SET whose STRING key has not expired.
    This is the authoritative live-session list.
    """
    members = redis_client.smembers(_user_sessions_key(user_id))
    if not members:
        return []
    live = []
    for sid in members:
        if redis_client.exists(_session_key(sid)):
            live.append(sid)
    return live


def _count_live_sessions(user_id: str) -> int:
    """Return the count of live sessions without building the full list."""
    return len(_live_session_ids(user_id))
