"""
Phase 5.8.3 — Redis Pub/Sub Manager.

Infrastructure-only transport layer.  This module provides:

  - publish()          — publish a structured event to a Redis channel
  - subscribe()        — subscribe to one or more channels
  - unsubscribe()      — remove subscriptions
  - start_listener()   — launch a background asyncio task that forwards
                          incoming events to a registered handler
  - stop_listener()    — shut down the background listener cleanly
  - PubSubEvent        — typed event envelope

No business logic lives here.  The manager is intentionally generic so
that Phases 5.8.4 (cross-instance fanout) and 5.8.5 (distributed
online/offline events) can layer their logic on top without touching
this module.

Architecture
────────────
FastAPI Instance A                   FastAPI Instance B
    │                                     │
    │  publish(channel, event)            │
    │         │                           │
    ▼         ▼                           ▼
        Redis Pub/Sub channel
              │
    ┌─────────┴─────────┐
    │                   │
 Listener A          Listener B
    │                   │
  handler(event)    handler(event)

Async design
────────────
The manager uses redis.asyncio (bundled with redis-py ≥ 4.2).  A separate
async Redis connection is created for the Pub/Sub listener because Redis
requires a dedicated connection while subscribed.

publish() uses a lightweight async connection pool so it can be called from
within an existing asyncio event loop (e.g. a WebSocket handler) without
blocking.

Channel naming
──────────────
All channels are prefixed careersphere:pubsub: (consistent with the
careersphere:presence: prefix from Phase 5.8.1).  Use the Channels
constants rather than raw strings throughout the application.

Event structure
───────────────
{
    "event_type": "<string>",       # e.g. "new_message", "user_online"
    "event_id":   "<uuid4>",        # unique per event
    "timestamp":  "<ISO 8601 UTC>", # when the event was published
    "source":     "<instance_id>",  # which FastAPI worker published it
    "payload":    {}                # event-specific data (future phases)
}

Failure handling
────────────────
- publish() returns False and logs on Redis failure; caller decides impact.
- start_listener() / stop_listener() never raise; errors are logged.
- Malformed incoming events are logged and skipped; the listener continues.
- Redis unavailability during the listener loop causes a clean exit with
  a logged warning; no uncontrolled retry loop is created.

Instance identification
───────────────────────
settings.INSTANCE_ID is used as the event 'source'.  If left blank in
the environment it is auto-populated with a UUID4 at import time so every
worker has a stable, non-sensitive identifier for the lifetime of the
process.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Instance ID — resolved once at import time
# ---------------------------------------------------------------------------

_INSTANCE_ID: str = settings.INSTANCE_ID or str(uuid.uuid4())

# ---------------------------------------------------------------------------
# Channel naming — single source of truth
# ---------------------------------------------------------------------------

_CHANNEL_NS = "careersphere:pubsub"


class Channels:
    """
    Centralised channel-name constants.

    Consumers must use these rather than hard-coding strings so that a
    single rename propagates everywhere.

    Phase 5.8.4 will add:  MESSAGING  = careersphere:pubsub:messaging
    Phase 5.8.5 will add:  PRESENCE   = careersphere:pubsub:presence
    """

    #: Generic broadcast channel — used for integration tests and future use.
    BROADCAST: str = f"{_CHANNEL_NS}:broadcast"

    @staticmethod
    def messaging(conversation_id: str) -> str:
        """Per-conversation channel for cross-instance message fanout (Phase 5.8.4)."""
        return f"{_CHANNEL_NS}:messaging:{conversation_id}"

    @staticmethod
    def presence() -> str:
        """Global presence channel for online/offline events (Phase 5.8.5)."""
        return f"{_CHANNEL_NS}:presence"

    @staticmethod
    def custom(suffix: str) -> str:
        """Escape hatch for any other channel needed by future phases."""
        return f"{_CHANNEL_NS}:{suffix}"


# ---------------------------------------------------------------------------
# Event envelope
# ---------------------------------------------------------------------------


class PubSubEvent:
    """
    Typed wrapper for a Pub/Sub event.

    Attributes
    ──────────
    event_type  : application-level event name (e.g. "new_message")
    event_id    : UUID4 string — unique per event
    timestamp   : ISO 8601 UTC string
    source      : INSTANCE_ID of the publishing worker
    payload     : arbitrary dict; interpretation left to the consumer
    """

    __slots__ = ("event_type", "event_id", "timestamp", "source", "payload")

    def __init__(
        self,
        event_type: str,
        payload: Optional[dict] = None,
        *,
        event_id: Optional[str] = None,
        timestamp: Optional[str] = None,
        source: Optional[str] = None,
    ) -> None:
        self.event_type = event_type
        self.event_id = event_id or str(uuid.uuid4())
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.source = source or _INSTANCE_ID
        self.payload = payload or {}

    # ── Serialisation ────────────────────────────────────────────────────────

    def to_json(self) -> str:
        return json.dumps({
            "event_type": self.event_type,
            "event_id":   self.event_id,
            "timestamp":  self.timestamp,
            "source":     self.source,
            "payload":    self.payload,
        })

    @classmethod
    def from_json(cls, raw: str) -> "PubSubEvent":
        """
        Deserialise a JSON string into a PubSubEvent.

        Raises:
            ValueError  — if the JSON is malformed or missing required fields.
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError("Event payload must be a JSON object.")

        event_type = data.get("event_type")
        if not event_type or not isinstance(event_type, str):
            raise ValueError("Missing or invalid 'event_type' field.")

        return cls(
            event_type=event_type,
            payload=data.get("payload", {}),
            event_id=data.get("event_id"),
            timestamp=data.get("timestamp"),
            source=data.get("source"),
        )

    def __repr__(self) -> str:
        return (
            f"PubSubEvent(type={self.event_type!r} "
            f"id={self.event_id[:8]}… "
            f"src={self.source[:8]}…)"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PubSubEvent):
            return NotImplemented
        return self.event_id == other.event_id


# ---------------------------------------------------------------------------
# EventHandler type alias
# ---------------------------------------------------------------------------

#: Signature: async handler(channel: str, event: PubSubEvent) -> None
EventHandler = Callable[[str, PubSubEvent], Awaitable[None]]


# ---------------------------------------------------------------------------
# Redis Pub/Sub Manager
# ---------------------------------------------------------------------------


class RedisPubSubManager:
    """
    Async Redis Pub/Sub manager.

    Lifecycle
    ─────────
    Typically called from the FastAPI lifespan context:

        await manager.start_listener(channels, handler)
        ...application runs...
        await manager.stop_listener()

    For fire-and-forget publish from synchronous contexts, the module-level
    ``publish()`` convenience function is provided.

    Thread safety
    ─────────────
    All operations are async and intended to run inside the asyncio event
    loop managed by uvicorn.  Do NOT call these from synchronous threads.
    """

    def __init__(self) -> None:
        self._redis_url: str = settings.REDIS_URL
        # Dedicated async client for the subscriber (held for the session).
        self._sub_client: Optional[aioredis.Redis] = None
        self._pubsub: Optional[aioredis.client.PubSub] = None
        self._listener_task: Optional[asyncio.Task] = None
        self._handler: Optional[EventHandler] = None
        self._subscribed_channels: set[str] = set()
        self._running: bool = False

    # ── Publish ──────────────────────────────────────────────────────────────

    async def publish(self, channel: str, event: PubSubEvent) -> bool:
        """
        Publish *event* to *channel*.

        Creates a short-lived async Redis connection per call (connection
        pooling is handled transparently by redis.asyncio).

        Returns True on success, False on any Redis failure.

        M4 (Phase 5.8.6): ``socket_connect_timeout`` is set to 2 s here
        (reduced from 5 s) so that a Redis outage adds at most ~2 s of
        latency per message rather than 5 s.  The subscriber connections
        retain the longer 5 s timeout because a slow initial subscription
        setup is less harmful than per-message publish latency.
        """
        payload = event.to_json()
        try:
            async with aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
            ) as r:
                await r.publish(channel, payload)
            logger.debug(
                "pubsub: published event_type=%s channel=%s event_id=%s",
                event.event_type, channel, event.event_id,
            )
            return True
        except Exception as exc:
            logger.warning(
                "pubsub: publish failed channel=%s event_type=%s: %s",
                channel, event.event_type, exc,
            )
            return False

    # ── Subscribe / Unsubscribe ───────────────────────────────────────────────

    async def subscribe(self, *channels: str) -> bool:
        """
        Subscribe the dedicated subscriber client to *channels*.

        The subscriber client is created lazily on first call.
        Returns True on success, False on Redis failure.
        """
        if not channels:
            return True
        try:
            await self._ensure_sub_client()
            await self._pubsub.subscribe(*channels)
            self._subscribed_channels.update(channels)
            logger.debug("pubsub: subscribed to %s", channels)
            return True
        except Exception as exc:
            logger.warning("pubsub: subscribe failed channels=%s: %s", channels, exc)
            return False

    async def unsubscribe(self, *channels: str) -> bool:
        """
        Unsubscribe from *channels*.  If called with no arguments, unsubscribes
        from all currently subscribed channels.

        Returns True on success, False on Redis failure.
        """
        if self._pubsub is None:
            return True
        try:
            if channels:
                await self._pubsub.unsubscribe(*channels)
                self._subscribed_channels.difference_update(channels)
            else:
                await self._pubsub.unsubscribe()
                self._subscribed_channels.clear()
            logger.debug("pubsub: unsubscribed from %s", channels or "all")
            return True
        except Exception as exc:
            logger.warning("pubsub: unsubscribe failed: %s", exc)
            return False

    # ── Listener lifecycle ────────────────────────────────────────────────────

    async def start_listener(
        self,
        channels: list[str],
        handler: EventHandler,
    ) -> bool:
        """
        Subscribe to *channels* and launch a background asyncio task that
        calls *handler(channel, event)* for each incoming message.

        The task runs until ``stop_listener()`` is called or Redis becomes
        permanently unavailable.

        Returns True if the listener started successfully, False otherwise.

        It is safe to call start_listener() only once per process.
        """
        if self._running:
            logger.warning("pubsub: start_listener called but listener already running.")
            return True

        self._handler = handler
        ok = await self.subscribe(*channels)
        if not ok:
            return False

        self._running = True
        self._listener_task = asyncio.create_task(
            self._listen_loop(),
            name="redis-pubsub-listener",
        )
        logger.info(
            "pubsub: listener started on channels=%s instance=%s",
            channels, _INSTANCE_ID,
        )
        return True

    async def stop_listener(self) -> None:
        """
        Gracefully stop the background listener and release all Redis resources.

        Safe to call even if the listener was never started or has already stopped.
        """
        self._running = False

        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.debug("pubsub: listener task cleanup: %s", exc)
        self._listener_task = None

        await self._close_sub_client()
        logger.info("pubsub: listener stopped instance=%s", _INSTANCE_ID)

    # ── Internal helpers ─────────────────────────────────────────────────────

    async def _ensure_sub_client(self) -> None:
        """Create the subscriber Redis client and PubSub object if not yet done."""
        if self._sub_client is None:
            self._sub_client = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            self._pubsub = self._sub_client.pubsub(ignore_subscribe_messages=True)

    async def _close_sub_client(self) -> None:
        """Unsubscribe and close the subscriber Redis connection."""
        if self._pubsub is not None:
            try:
                await self._pubsub.unsubscribe()
                await self._pubsub.aclose()
            except Exception as exc:
                logger.debug("pubsub: error closing pubsub: %s", exc)
            self._pubsub = None

        if self._sub_client is not None:
            try:
                await self._sub_client.aclose()
            except Exception as exc:
                logger.debug("pubsub: error closing sub client: %s", exc)
            self._sub_client = None

        self._subscribed_channels.clear()

    async def _listen_loop(self) -> None:
        """
        Core receive loop.  Runs as a background asyncio task.

        - Reads messages from the PubSub connection.
        - Deserialises each message into a PubSubEvent.
        - Calls the registered handler.
        - Skips malformed messages with a warning.
        - Exits cleanly when self._running becomes False or the task is cancelled.

        M2 (Phase 5.8.6.1): ``self._running`` is reset to ``False`` in the
        ``finally`` block so that callers can reliably detect that the loop
        has exited, regardless of whether the exit was intentional (cancelled
        by ``stop_listener()``) or caused by a Redis error.  This also allows
        higher-level wrappers (e.g. ``presence_fanout``) to observe the
        stopped state and trigger a reconnect.
        """
        logger.debug("pubsub: listen loop started")
        try:
            while self._running:
                if self._pubsub is None:
                    break
                try:
                    message = await asyncio.wait_for(
                        self._pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    # No message within 1 s — check _running and loop again.
                    continue
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning(
                        "pubsub: error reading message from Redis: %s — stopping listener",
                        exc,
                    )
                    break

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
                        "pubsub: skipping malformed event on channel=%s: %s",
                        channel, exc,
                    )
                    continue

                if self._handler is not None:
                    try:
                        await self._handler(channel, event)
                    except Exception as exc:
                        logger.warning(
                            "pubsub: handler raised for event_type=%s: %s",
                            event.event_type, exc,
                        )

        except asyncio.CancelledError:
            logger.debug("pubsub: listen loop cancelled")
            raise
        except Exception as exc:
            logger.error("pubsub: unexpected error in listen loop: %s", exc)
        finally:
            # M2: always reset _running so the stopped state is observable.
            # stop_listener() already sets this to False before cancellation,
            # so this is a no-op on clean shutdown and a correctness fix on
            # unexpected exit.
            self._running = False
            logger.debug("pubsub: listen loop exited")

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        """True if the listener background task is active."""
        return self._running and (
            self._listener_task is not None and not self._listener_task.done()
        )

    @property
    def subscribed_channels(self) -> frozenset[str]:
        """Read-only set of currently subscribed channels."""
        return frozenset(self._subscribed_channels)

    @property
    def instance_id(self) -> str:
        """The instance identifier used in published events."""
        return _INSTANCE_ID


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

#: Global manager instance shared across the FastAPI process.
#: Phases 5.8.4 and 5.8.5 import this directly.
pubsub_manager = RedisPubSubManager()


# ---------------------------------------------------------------------------
# Convenience functions (thin wrappers over the singleton)
# ---------------------------------------------------------------------------


async def publish(channel: str, event: PubSubEvent) -> bool:
    """Publish *event* to *channel* using the module-level singleton manager."""
    return await pubsub_manager.publish(channel, event)


def get_instance_id() -> str:
    """Return the stable instance identifier for this process."""
    return _INSTANCE_ID
