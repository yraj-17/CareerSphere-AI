"""
Phase 5.8.4 — WebSocket Connection Manager.

Process-local registry of active WebSocket connections.

Design
──────
A single user may have multiple active sockets simultaneously (laptop tab,
mobile browser, etc.).  The registry therefore maps:

    user_id  →  set[WebSocket]

Connecting adds one socket to the set; disconnecting removes exactly that
socket — leaving the others intact.

Online/offline lifecycle
────────────────────────
- "user online" = the user transitions from 0 → 1 active sockets.
- "user offline" = the user transitions from 1 → 0 active sockets.

This is process-local.  Distributed presence (Redis pub/sub) is out of
scope for Phase 5.8.4 and will be addressed in Phase 5.8.5.

Thread safety
─────────────
FastAPI runs WebSocket handlers in the same asyncio event loop.  Python's
asyncio is single-threaded within the loop, so the plain dict/set operations
here are safe without locks.  If uvicorn is ever started with multiple
workers, each worker maintains its own independent registry (per the
Phase 5.8.5 distributed-presence caveat).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


def _make_event(event_type: str, data: dict) -> str:
    """Serialize a server→client event to a JSON string."""
    return json.dumps({"type": event_type, "data": data})


class ConnectionManager:
    """
    Process-local registry of active WebSocket connections.

    Each user can have multiple simultaneous sockets (multi-tab / multi-device).
    Connects and disconnects are O(1) set operations.
    """

    def __init__(self) -> None:
        # user_id → set of active WebSocket connections for that user
        self._connections: dict[str, set[WebSocket]] = {}

    # ── Registration ─────────────────────────────────────────────────────────

    def connect(self, user_id: str, websocket: WebSocket) -> bool:
        """
        Register *websocket* for *user_id*.

        Returns True if this is the user's FIRST active socket
        (i.e. the user just came online from this process's perspective).
        """
        if user_id not in self._connections:
            self._connections[user_id] = set()
        was_offline = len(self._connections[user_id]) == 0
        self._connections[user_id].add(websocket)
        return was_offline

    def disconnect(self, user_id: str, websocket: WebSocket) -> bool:
        """
        Remove *websocket* from the registry.

        Returns True if this was the user's LAST active socket
        (i.e. the user just went offline from this process's perspective).
        """
        sockets = self._connections.get(user_id)
        if not sockets:
            return False
        sockets.discard(websocket)
        if not sockets:
            del self._connections[user_id]
            return True   # last socket removed — user offline
        return False

    # ── Presence ─────────────────────────────────────────────────────────────

    def is_connected(self, user_id: str) -> bool:
        """Return True if the user has at least one active socket."""
        return bool(self._connections.get(user_id))

    def active_socket_count(self, user_id: str) -> int:
        """Return the number of active sockets for this user (0 if offline)."""
        return len(self._connections.get(user_id, set()))

    # ── Delivery ─────────────────────────────────────────────────────────────

    async def send_to_user(self, user_id: str, event_type: str, data: dict) -> int:
        """
        Send an event to all active sockets for *user_id*.

        Returns the number of sockets the event was successfully sent to.
        Stale sockets that raise during send are silently removed.
        """
        sockets = list(self._connections.get(user_id, set()))
        if not sockets:
            return 0

        payload = _make_event(event_type, data)
        delivered = 0
        stale: list[WebSocket] = []

        for ws in sockets:
            try:
                await ws.send_text(payload)
                delivered += 1
            except Exception:
                stale.append(ws)

        # Clean up sockets that are no longer usable.
        for ws in stale:
            self._connections.get(user_id, set()).discard(ws)
        if user_id in self._connections and not self._connections[user_id]:
            del self._connections[user_id]

        return delivered

    async def send_to_conversation(
        self,
        conversation_id: str,
        participant_ids: list[str],
        event_type: str,
        data: dict,
        exclude_user_id: str | None = None,
    ) -> None:
        """
        Broadcast an event to all active sockets of every participant in
        *participant_ids*, optionally excluding *exclude_user_id*.

        ``conversation_id`` is included in the data dict as a convenience if
        it isn't already present — the caller may override it.
        """
        if "conversation_id" not in data:
            data = {**data, "conversation_id": conversation_id}

        for uid in participant_ids:
            if uid == exclude_user_id:
                continue
            await self.send_to_user(uid, event_type, data)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

# A single global manager is shared across all WebSocket connections within
# this process.  It is intentionally process-local for Phase 5.8.4.
manager = ConnectionManager()
