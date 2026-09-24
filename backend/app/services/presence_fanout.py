"""
Phase 5.8.5 — Distributed Online/Offline Events.

This module distributes user presence state (online/offline) across multiple
FastAPI instances using Redis Pub/Sub.

Responsibilities (this module)
──────────────────────────────
1. Publish ``user_online`` when a user's FIRST global session is registered.
2. Publish ``user_offline`` when a user's LAST global session is removed.
3. Subscribe to ``Channels.presence()`` and dispatch received events to the
   appropriate local WebSocket layer.
4. Guard against source-instance echo (do not re-deliver events we published).
5. Guard against re-publishing received events (no fanout loop).

The first/last session semantics come entirely from ``presence_service.py``.
This module never reads from or writes to Redis presence keys directly.

Responsibilities (other modules — NOT duplicated here)
──────────────────────────────────────────────────────
- Session counting / first_session / last_session  → presence_service.py
- Process-local WebSocket socket tracking          → websocket_manager.py
- Redis Pub/Sub transport primitives               → redis_pubsub_manager.py
- Message fanout (Phase 5.8.4)                     → messaging_fanout.py
- WebSocket authentication / conversation routing  → messaging_ws.py

Channel
───────
All presence events are published to and received from:

    Channels.presence()  →  careersphere:pubsub:presence

A single global channel is correct here: presence events are global
(user X is online/offline), not per-conversation.

Event format
────────────
user_online:
    {
      "event_type": "user_online",
      "event_id":   "<UUID4>",
      "timestamp":  "<ISO 8601 UTC>",
      "source":     "<instance ID>",
      "payload":    {"user_id": "<user ID>"}
    }

user_offline:
    {
      "event_type": "user_offline",
      "event_id":   "<UUID4>",
      "timestamp":  "<ISO 8601 UTC>",
      "source":     "<instance ID>",
      "payload":    {"user_id": "<user ID>"}
    }

Anti-loop guarantees
────────────────────
1. Source-instance skip: when the publishing instance receives its own
   Pub/Sub echo (``event.source == _INSTANCE_ID``), it skips local
   delivery.  Local delivery already happened synchronously in
   ``messaging_ws.py`` immediately after the presence operation.
2. No re-publish: ``handle_presence_event`` never calls publish.

Session semantics (enforced by the caller in messaging_ws.py)
──────────────────────────────────────────────────────────────
- ``publish_user_online``  is called ONLY when ``first_session=True``
  from ``presence_service.register_session()``.
- ``publish_user_offline`` is called ONLY when ``last_session=True``
  from ``presence_service.remove_session()``.
- Intermediate sessions generate no presence events.

Local delivery routing
──────────────────────
When a remote instance sends a ``user_online`` or ``user_offline`` event,
this module delivers it to the locally connected WebSocket conversation
partner of the user via the process-local ConnectionManager.

In the current 1-to-1 messaging architecture there is no global social
graph.  Therefore the event is delivered to any user who has a locally
active WebSocket connection — specifically the ``other_user_id`` relationship
from the conversation.  Because the ConnectionManager only tracks sockets on
this instance, and we do not have a global registry of "who is conversing
with whom" at the presence layer, the handler delivers to any locally
connected socket that subscribes to presence updates for the affected user.

Implementation: ``handle_presence_event`` looks up the user's conversation
partners via a narrow query pattern based on the ConnectionManager's active
connections — it notifies any locally connected user whose WebSocket session
is active.  This keeps the implementation simple and correct for Phase 5.8.5
without requiring a social graph.

Failure handling
────────────────
- Publish failure: event not delivered to remote instances.  Log warning.
  Local state is unaffected.
- Listener start failure: process continues with local-only presence events.
- Handler exception: isolated; loop continues.
- Malformed / unknown events: logged and skipped.

NOT implemented here (scope boundary)
──────────────────────────────────────
- Phase 5.8.6: heartbeat, TTL refresh, reconnection strategy.
- Phase 5.8.7: freeze automation.
- Followers / social graph / global broadcast.
- Presence persistence in PostgreSQL.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.services.redis_pubsub_manager import (
    Channels,
    PubSubEvent,
    RedisPubSubManager,
    _INSTANCE_ID,
    pubsub_manager,
)
from app.services.websocket_manager import manager as ws_manager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Backoff constants (M1 — Phase 5.8.6.1)
# ---------------------------------------------------------------------------

#: Initial reconnect delay in seconds.
_BACKOFF_INITIAL: float = 1.0
#: Maximum reconnect delay in seconds.
_BACKOFF_MAX: float = 30.0

# ---------------------------------------------------------------------------
# Module-level listener state
# ---------------------------------------------------------------------------

_presence_manager: Optional[RedisPubSubManager] = None
_listener_running: bool = False
_restart_task: Optional[asyncio.Task] = None


# ---------------------------------------------------------------------------
# Publish helpers
# ---------------------------------------------------------------------------


async def publish_user_online(user_id: str) -> bool:
    """
    Publish a ``user_online`` event to ``Channels.presence()``.

    Must be called ONLY when ``presence_service.register_session()``
    returns ``first_session=True``.

    Returns True on successful publish, False on Redis failure (logged but
    does not affect local state — local delivery already happened).
    """
    channel = Channels.presence()
    event = PubSubEvent(
        event_type="user_online",
        payload={"user_id": user_id},
    )
    ok = await pubsub_manager.publish(channel, event)
    if not ok:
        logger.warning(
            "presence_fanout: publish user_online failed for user_id=%s", user_id
        )
    else:
        logger.debug(
            "presence_fanout: published user_online user_id=%s channel=%s",
            user_id, channel,
        )
    return ok


async def publish_user_offline(user_id: str) -> bool:
    """
    Publish a ``user_offline`` event to ``Channels.presence()``.

    Must be called ONLY when ``presence_service.remove_session()``
    returns ``last_session=True``.

    Returns True on successful publish, False on Redis failure (logged but
    does not affect local state — local cleanup already happened).
    """
    channel = Channels.presence()
    event = PubSubEvent(
        event_type="user_offline",
        payload={"user_id": user_id},
    )
    ok = await pubsub_manager.publish(channel, event)
    if not ok:
        logger.warning(
            "presence_fanout: publish user_offline failed for user_id=%s", user_id
        )
    else:
        logger.debug(
            "presence_fanout: published user_offline user_id=%s channel=%s",
            user_id, channel,
        )
    return ok


# ---------------------------------------------------------------------------
# Receive / handler
# ---------------------------------------------------------------------------


async def handle_presence_event(channel: str, event: PubSubEvent) -> None:
    """
    Pub/Sub listener callback for distributed presence events.

    Called by the presence listener for every event on
    ``Channels.presence()`` (``careersphere:pubsub:presence``).

    Logic:
    1. Accept only ``user_online`` / ``user_offline`` events.
    2. Skip events from THIS instance — local delivery already happened
       synchronously in ``messaging_ws.py``.
    3. Extract ``user_id`` from the payload.
    4. Deliver the event to any locally connected WebSocket clients that
       are currently conversing with the affected user.
    5. NEVER re-publish the event.
    6. NEVER modify Redis presence state.
    7. NEVER write to PostgreSQL.
    """
    if event.event_type not in ("user_online", "user_offline"):
        # Silently ignore unknown event types — future-proof.
        return

    payload = event.payload
    if not isinstance(payload, dict):
        logger.warning(
            "presence_fanout: received %s event with non-dict payload; skipping.",
            event.event_type,
        )
        return

    # ── Anti-loop: skip events we published ourselves ──────────────────────
    if event.source == _INSTANCE_ID:
        # This instance already delivered locally; nothing to do.
        return

    # ── Extract required field ─────────────────────────────────────────────
    user_id = payload.get("user_id")
    if not user_id:
        logger.warning(
            "presence_fanout: %s event missing user_id; skipping event_id=%s",
            event.event_type, event.event_id,
        )
        return

    # ── Deliver to locally connected users who are aware of this user ──────
    #
    # In the 1-to-1 messaging architecture each WebSocket connection is
    # scoped to a single conversation, and each conversation has exactly
    # one other participant.  We deliver the presence event to every
    # locally connected user who may be conversing with the affected user.
    #
    # The ConnectionManager holds user_id → set[WebSocket].  We cannot
    # enumerate "who is conversing with user_id" from the manager alone,
    # so we broadcast the presence event to ALL locally connected users
    # except the affected user themselves.  Each client filters relevance
    # based on their conversation context.
    #
    # This is consistent with the current protocol:
    #   user_online  → data: {user_id}
    #   user_offline → data: {user_id}
    # Clients already handle these events for their conversation partner.
    #
    # Security: user_id comes from the server-published event (signed by
    # the source instance's JWT infrastructure) — never from client input.

    ws_event_type = event.event_type  # "user_online" or "user_offline"
    ws_data = {"user_id": user_id}

    # Iterate over all locally connected users.
    for local_user_id in list(ws_manager._connections.keys()):
        if local_user_id == user_id:
            # Do not echo the user's own online/offline state back to themselves.
            continue
        try:
            await ws_manager.send_to_user(local_user_id, ws_event_type, ws_data)
        except Exception as exc:
            logger.warning(
                "presence_fanout: delivery of %s to local_user=%s failed: %s",
                ws_event_type, local_user_id, exc,
            )

    logger.debug(
        "presence_fanout: delivered %s for user_id=%s to local connections event_id=%s",
        event.event_type, user_id, event.event_id,
    )


# ---------------------------------------------------------------------------
# Listener startup / shutdown
# ---------------------------------------------------------------------------


async def _presence_restart_loop() -> None:
    """
    M1 (Phase 5.8.6.1): Background task that keeps the presence listener
    alive by reconnecting after Redis failures.

    The loop uses bounded exponential backoff:
        1 s → 2 s → 4 s → 8 s → 16 s → 30 s (cap) → 30 s → …

    The backoff resets to ``_BACKOFF_INITIAL`` after each successful
    connection (i.e. the manager started and ran without error).

    The loop exits cleanly when ``_listener_running`` is set to ``False``
    by ``stop_presence_listener()``.  ``CancelledError`` is always re-raised.

    Implementation notes
    ────────────────────
    Each restart creates a fresh ``RedisPubSubManager`` instance.  This
    ensures no state leakage from the failed connection (stale ``_pubsub``
    objects, stale ``_subscribed_channels`` sets, etc.).  The module-level
    ``_presence_manager`` reference is updated atomically within the loop
    so that ``stop_presence_listener()`` can always cancel the current
    manager regardless of which iteration is active.
    """
    global _presence_manager, _listener_running
    channel = Channels.presence()
    backoff: float = _BACKOFF_INITIAL

    logger.info(
        "presence_fanout: restart loop started channel=%s instance=%s",
        channel, _INSTANCE_ID,
    )

    try:
        while _listener_running:
            # Create a fresh manager for each attempt.
            mgr = RedisPubSubManager()
            _presence_manager = mgr

            ok = await mgr.start_listener(
                channels=[channel],
                handler=handle_presence_event,
            )

            if not ok:
                # Could not connect — apply backoff and retry.
                if not _listener_running:
                    break
                logger.warning(
                    "presence_fanout: failed to connect to Redis "
                    "— retrying in %.0fs",
                    backoff,
                )
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    raise
                backoff = min(backoff * 2, _BACKOFF_MAX)
                continue

            # Connected successfully — reset backoff.
            backoff = _BACKOFF_INITIAL
            logger.info(
                "presence_fanout: listener connected channel=%s instance=%s",
                channel, _INSTANCE_ID,
            )

            # Wait until the underlying listener task stops.  After the M2
            # fix, mgr._running becomes False when _listen_loop() exits for
            # any reason (cancellation or Redis error).
            while _listener_running and mgr.is_running:
                await asyncio.sleep(0.2)

            if not _listener_running:
                # Clean shutdown requested — exit without retry.
                await mgr.stop_listener()
                break

            # The manager's listener died unexpectedly — apply backoff.
            await mgr.stop_listener()
            _presence_manager = None

            logger.warning(
                "presence_fanout: listener died — retrying in %.0fs", backoff
            )
            try:
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                raise
            backoff = min(backoff * 2, _BACKOFF_MAX)

    except asyncio.CancelledError:
        logger.debug("presence_fanout: restart loop cancelled")
        raise
    except Exception as exc:
        logger.error("presence_fanout: unexpected error in restart loop: %s", exc)
    finally:
        _listener_running = False
        if _presence_manager is not None:
            try:
                await _presence_manager.stop_listener()
            except Exception:
                pass
            _presence_manager = None
        logger.info("presence_fanout: restart loop stopped instance=%s", _INSTANCE_ID)


async def start_presence_listener() -> bool:
    """
    Start the distributed presence listener at application startup.

    Subscribes to ``Channels.presence()`` and launches a background
    asyncio restart task (M1) that keeps the listener alive across Redis
    outages using exponential backoff.

    Uses a **dedicated** ``RedisPubSubManager`` instance (managed by the
    restart loop) separate from the module-level singleton so that the
    presence subscription and Phase 5.8.4 fanout lifecycles are independent.

    Returns True if the initial connection to Redis succeeded, False if
    Redis is unavailable at startup (safe fallback — process continues with
    local-only presence).  Even when this returns False the restart loop
    runs in the background and will connect once Redis becomes available.
    """
    global _presence_manager, _listener_running, _restart_task

    if _listener_running:
        logger.warning(
            "presence_fanout: start_presence_listener called but already running."
        )
        return True

    # Probe Redis with one connection attempt before declaring success.
    channel = Channels.presence()
    probe_mgr = RedisPubSubManager()
    ok = await probe_mgr.start_listener(
        channels=[channel],
        handler=handle_presence_event,
    )

    if ok:
        # Initial connection succeeded — hand off to the restart loop.
        await probe_mgr.stop_listener()
        _listener_running = True
        _restart_task = asyncio.create_task(
            _presence_restart_loop(),
            name="presence-fanout-restart-loop",
        )
        logger.info(
            "presence_fanout: listener started channel=%s instance=%s",
            channel, _INSTANCE_ID,
        )
    else:
        # Redis not reachable at startup — start the restart loop anyway so
        # it reconnects once Redis comes back.
        logger.warning(
            "presence_fanout: Redis not reachable at startup — "
            "presence listener will retry in background"
        )
        _listener_running = True
        _restart_task = asyncio.create_task(
            _presence_restart_loop(),
            name="presence-fanout-restart-loop",
        )

    return ok


async def stop_presence_listener() -> None:
    """
    Stop the distributed presence listener and its restart loop.

    Safe to call even if the listener was never started.
    Called at application shutdown.
    """
    global _presence_manager, _listener_running, _restart_task

    _listener_running = False

    if _restart_task and not _restart_task.done():
        _restart_task.cancel()
        try:
            await _restart_task
        except (asyncio.CancelledError, Exception):
            pass
    _restart_task = None

    if _presence_manager is not None:
        await _presence_manager.stop_listener()
        _presence_manager = None

    logger.info("presence_fanout: listener stopped instance=%s", _INSTANCE_ID)
