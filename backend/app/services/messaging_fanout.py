"""
Phase 5.8.4 — Cross-Instance Message Fanout.

This module is the *only* place that bridges the Redis Pub/Sub transport
layer with the local ConnectionManager for messaging events.

Responsibilities (this module)
──────────────────────────────
1. Subscribe to ALL per-conversation channels with a single Redis pattern
   subscription ``careersphere:pubsub:messaging:*`` so every instance
   receives events for every active conversation without per-connection
   subscription management.
2. Build and publish a ``new_message`` event to
   ``Channels.messaging(conversation_id)`` after a message has been
   persisted to PostgreSQL.
3. Receive events from Redis and deliver them to locally connected
   WebSocket clients that are the intended recipient.

Channel strategy
────────────────
Publish:   ``Channels.messaging(conversation_id)``
           → ``careersphere:pubsub:messaging:<conversation_id>``

Subscribe: ``careersphere:pubsub:messaging:*`` (PSUBSCRIBE pattern)
           → receives events for ALL conversation channels in one
             subscription; routing is done in the handler via recipient_id.

This avoids per-connection subscribe/unsubscribe management while still
using the correct per-conversation channel name for publishing, satisfying
the architectural requirement that ``Channels.messaging(conversation_id)``
is the canonical channel for cross-instance fanout.

Responsibilities (other modules — NOT duplicated here)
──────────────────────────────────────────────────────
- PostgreSQL persistence         → messaging_service.py
- WebSocket authorization        → messaging_ws.py
- Process-local socket delivery  → websocket_manager.py (ConnectionManager)
- Pub/Sub transport              → redis_pubsub_manager.py
- Presence/session tracking      → presence_service.py

Anti-loop guarantee
────────────────────
The handler inspects ``event.source``.  If ``source == _INSTANCE_ID`` the
publishing instance itself receives the event and **skips** delivery,
because the WebSocket endpoint already delivered the message locally in
``_handle_message()`` immediately after PostgreSQL persistence.

No event is ever re-published.  No message is ever persisted twice.

Failure handling (Phase 5.8.4 level)
─────────────────────────────────────
- Listener start failure: process continues with local-only delivery.
- Publish failure: PostgreSQL message already persisted; fire-and-forget.
- Handler exception: isolated; the listener loop continues.
- Malformed event: logged; skipped.

NOT implemented here (scope boundary)
──────────────────────────────────────
- Phase 5.8.5: distributed user_online / user_offline events.
- Phase 5.8.6: heartbeat, TTL refresh, advanced failure recovery.
- Delivery/read receipt fanout (future refinement).
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings
from app.services.redis_pubsub_manager import (
    Channels,
    PubSubEvent,
    _INSTANCE_ID,
    _CHANNEL_NS,
    pubsub_manager,
)
from app.services.websocket_manager import manager as ws_manager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level listener state (private)
# ---------------------------------------------------------------------------

#: Pattern that matches all per-conversation messaging channels.
#: Used with Redis PSUBSCRIBE to receive events for every conversation
#: in a single subscription, without per-connection lifecycle management.
_MESSAGING_PATTERN: str = f"{_CHANNEL_NS}:messaging:*"

_listener_task: Optional[asyncio.Task] = None
_listener_running: bool = False


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------


async def publish_new_message(
    message_id: str,
    conversation_id: str,
    sender_id: str,
    recipient_id: str,
    content: str,
    created_at: str,
) -> bool:
    """
    Publish a ``new_message`` event to the per-conversation Redis channel
    after the message has been persisted to PostgreSQL.

    Publishes to ``Channels.messaging(conversation_id)`` so that remote
    instances subscribed via the pattern listener can deliver the event
    to their locally connected participants.

    Must be called AFTER ``messaging_service.send_direct_message()`` returns
    successfully so that PostgreSQL is the source of truth.

    Returns True on successful publish, False on Redis failure (which is
    logged but does not affect the already-persisted message).

    Security note:
        - ``sender_id`` and ``recipient_id`` always come from server-side
          data (the authenticated user and conversation participant),
          never from client input.
        - ``content`` is the already-trimmed value returned by the service.
        - No JWT, password, or secret is included.
    """
    channel = Channels.messaging(conversation_id)
    event = PubSubEvent(
        event_type="new_message",
        payload={
            "message_id":      message_id,
            "conversation_id": conversation_id,
            "sender_id":       sender_id,
            "recipient_id":    recipient_id,
            "content":         content,
            "created_at":      created_at,
        },
    )

    ok = await pubsub_manager.publish(channel, event)
    if not ok:
        logger.warning(
            "fanout: publish failed for message_id=%s conversation_id=%s",
            message_id, conversation_id,
        )
    return ok


# ---------------------------------------------------------------------------
# Subscription lifecycle helpers (for test use and explicit control)
# ---------------------------------------------------------------------------


async def subscribe_conversation(conversation_id: str) -> bool:
    """
    Record interest in cross-instance events for ``conversation_id``.

    In the production listener, the PSUBSCRIBE pattern already covers all
    per-conversation channels, so this function is a logical no-op at
    runtime.  It is provided so that:
      - WebSocket endpoints can declare intent without coupling to the
        implementation of the listener.
      - Tests can verify that the correct channel name is derived.

    Returns True always (the pattern subscription is managed at startup).
    """
    channel = Channels.messaging(conversation_id)
    logger.debug("fanout: subscribe_conversation acknowledged channel=%s", channel)
    return True


async def unsubscribe_conversation(conversation_id: str) -> bool:
    """
    Release interest in cross-instance events for ``conversation_id``.

    Like subscribe_conversation, this is a logical no-op in production
    because the PSUBSCRIBE pattern handles all conversations centrally.
    Provided for symmetry and test coverage.

    Returns True always.
    """
    channel = Channels.messaging(conversation_id)
    logger.debug("fanout: unsubscribe_conversation acknowledged channel=%s", channel)
    return True


# ---------------------------------------------------------------------------
# Receive / handler
# ---------------------------------------------------------------------------


async def handle_fanout_event(channel: str, event: PubSubEvent) -> None:
    """
    Pub/Sub listener callback for cross-instance message fanout.

    Called by the pattern listener for every event on any
    ``careersphere:pubsub:messaging:<conversation_id>`` channel.

    Logic:
    1. Accept only ``new_message`` events; ignore others (future-proof).
    2. Skip events originating from THIS instance — local delivery already
       happened synchronously in ``_handle_message()``.
    3. Extract ``recipient_id`` from the payload.
    4. If the recipient has active sockets on this instance, deliver the
       ``new_message`` event through the local ConnectionManager.
    5. Never re-publish the event (anti-loop guarantee).
    6. Never write to PostgreSQL (message is already persisted).
    """
    if event.event_type != "new_message":
        return

    payload = event.payload
    if not isinstance(payload, dict):
        logger.warning("fanout: received new_message event with non-dict payload; skipping.")
        return

    # ── Anti-loop: skip events we published ourselves ──────────────────────
    if event.source == _INSTANCE_ID:
        return

    # ── Extract required fields ────────────────────────────────────────────
    recipient_id = payload.get("recipient_id")
    if not recipient_id:
        logger.warning(
            "fanout: new_message event missing recipient_id; skipping event_id=%s",
            event.event_id,
        )
        return

    ws_data = {
        "id":              payload.get("message_id", ""),
        "conversation_id": payload.get("conversation_id", ""),
        "sender_id":       payload.get("sender_id", ""),
        "content":         payload.get("content", ""),
        "created_at":      payload.get("created_at"),
        "delivered_at":    None,
        "read_at":         None,
    }

    # ── Deliver to locally connected recipient ─────────────────────────────
    if ws_manager.is_connected(recipient_id):
        delivered = await ws_manager.send_to_user(recipient_id, "new_message", ws_data)

        if delivered:
            await ws_manager.send_to_user(
                recipient_id,
                "notification",
                {
                    "notification_type": "new_message",
                    "conversation_id":   payload.get("conversation_id", ""),
                    "sender_id":         payload.get("sender_id", ""),
                    "message_id":        payload.get("message_id", ""),
                },
            )
            logger.debug(
                "fanout: delivered new_message to recipient=%s event_id=%s",
                recipient_id, event.event_id,
            )


# ---------------------------------------------------------------------------
# Backoff constants (M1 — Phase 5.8.6.1)
# ---------------------------------------------------------------------------

#: Initial reconnect delay in seconds.
_BACKOFF_INITIAL: float = 1.0
#: Maximum reconnect delay in seconds (caps exponential growth).
_BACKOFF_MAX: float = 30.0


# ---------------------------------------------------------------------------
# Pattern listener (private)
# ---------------------------------------------------------------------------


async def _single_connect_and_listen() -> None:
    """
    Open ONE Redis PSUBSCRIBE connection and read events until failure or
    ``_listener_running`` becomes False.

    Raises on connection / subscription failure so the outer retry loop can
    apply backoff.  Exits normally (no raise) when ``_listener_running``
    becomes False, which signals a clean shutdown request.
    """
    async with aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=5,
    ) as redis_client:
        async with redis_client.pubsub(ignore_subscribe_messages=True) as pubsub:
            await pubsub.psubscribe(_MESSAGING_PATTERN)
            logger.info("fanout: pattern subscribed to %s", _MESSAGING_PATTERN)

            while _listener_running:
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    # Redis read error — propagate so the outer loop retries.
                    raise RuntimeError(
                        f"fanout: error reading from Redis: {exc}"
                    ) from exc

                if message is None:
                    continue

                channel = message.get("channel", "")
                raw_data = message.get("data", "")

                if not isinstance(raw_data, str) or not raw_data:
                    continue

                try:
                    event = PubSubEvent.from_json(raw_data)
                except ValueError as exc:
                    logger.warning(
                        "fanout: skipping malformed event on channel=%s: %s",
                        channel, exc,
                    )
                    continue

                try:
                    await handle_fanout_event(channel, event)
                except Exception as exc:
                    logger.warning(
                        "fanout: handler raised for event_type=%s: %s",
                        event.event_type, exc,
                    )


async def _pattern_listen_loop() -> None:
    """
    Background asyncio task: subscribe to ALL per-conversation channels via
    Redis PSUBSCRIBE and dispatch events to ``handle_fanout_event``.

    M1 (Phase 5.8.6.1): wraps the single-connection loop in an exponential-
    backoff retry so that a temporary Redis outage is recovered automatically
    once Redis becomes available again.

    Backoff schedule (bounded):
        1 s → 2 s → 4 s → 8 s → 16 s → 30 s (cap) → 30 s → …

    The backoff resets to ``_BACKOFF_INITIAL`` after each successful
    connection (i.e. a connection that received at least one poll cycle
    without error).

    The loop exits cleanly when ``_listener_running`` is set to ``False``
    by ``stop_fanout_listener()``.  A ``CancelledError`` (task cancellation
    from ``stop_fanout_listener()``) is always re-raised so asyncio can clean
    up the task.
    """
    global _listener_running
    logger.info(
        "fanout: pattern listener starting pattern=%s instance=%s",
        _MESSAGING_PATTERN, _INSTANCE_ID,
    )
    backoff: float = _BACKOFF_INITIAL

    try:
        while _listener_running:
            try:
                await _single_connect_and_listen()
                # Reached here either because _listener_running → False (clean
                # shutdown) or because the connection was closed cleanly.
                backoff = _BACKOFF_INITIAL  # reset on clean exit
                if not _listener_running:
                    break
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if not _listener_running:
                    # Shutdown was requested concurrently — exit without retry.
                    break
                logger.warning(
                    "fanout: Redis connection lost (%s) — retrying in %.0fs",
                    exc, backoff,
                )
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    raise
                backoff = min(backoff * 2, _BACKOFF_MAX)

    except asyncio.CancelledError:
        logger.debug("fanout: pattern listener task cancelled")
        raise
    except Exception as exc:
        logger.error("fanout: unexpected error in pattern listener: %s", exc)
    finally:
        _listener_running = False
        logger.info("fanout: pattern listener stopped instance=%s", _INSTANCE_ID)


# ---------------------------------------------------------------------------
# Listener startup / shutdown
# ---------------------------------------------------------------------------


async def start_fanout_listener() -> bool:
    """
    Start the cross-instance fanout listener at application startup.

    Subscribes to the Redis pattern ``careersphere:pubsub:messaging:*``
    so that events published to ANY ``Channels.messaging(conversation_id)``
    channel are received by this instance.

    If the listener task dies due to a Redis outage, the M1 backoff-retry
    loop inside ``_pattern_listen_loop()`` will automatically reconnect
    once Redis becomes available again.

    Returns True if the listener started successfully, False if Redis is
    unavailable (safe fallback — process continues with local-only delivery).
    """
    global _listener_task, _listener_running

    if _listener_running:
        logger.warning("fanout: start_fanout_listener called but listener already running.")
        return True

    # Probe Redis before starting the listener task.
    probe_channel = Channels.custom("fanout:startup-probe")
    probe_event = PubSubEvent(event_type="startup_probe", payload={})
    redis_ok = await pubsub_manager.publish(probe_channel, probe_event)
    if not redis_ok:
        logger.warning(
            "fanout: Redis not reachable at startup — cross-instance fanout disabled"
        )
        return False

    _listener_running = True
    _listener_task = asyncio.create_task(
        _pattern_listen_loop(),
        name="fanout-pattern-listener",
    )
    logger.info(
        "fanout: listener started pattern=%s instance=%s",
        _MESSAGING_PATTERN, _INSTANCE_ID,
    )
    return True


async def stop_fanout_listener() -> None:
    """
    Stop the fanout listener background task.

    Called at application shutdown (or in tests that need to clean up).
    Safe to call even if the listener was never started.
    """
    global _listener_task, _listener_running

    _listener_running = False

    if _listener_task and not _listener_task.done():
        _listener_task.cancel()
        try:
            await _listener_task
        except (asyncio.CancelledError, Exception):
            pass
    _listener_task = None
    logger.info("fanout: listener stopped instance=%s", _INSTANCE_ID)
