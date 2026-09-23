"""
Phase 5.8.4 — WebSocket Real-Time Messaging Endpoint.
Phase 5.8.5.2 — Redis Session/Connection Tracking integrated.
Phase 5.8.5   — Distributed Online/Offline Events integrated.

Architecture
────────────
    Client (Native WebSocket)
        │
        │  ws://<host>/api/messaging/ws/<conversation_id>?token=<JWT>
        ▼
    FastAPI WebSocket endpoint  (this file)
        │
        ├── JWT authentication      → user identity from token, never client-supplied
        ├── Conversation auth       → must exist + caller must be participant
        ├── Connection enforcement  → accepted connection required (via service)
        ├── session_id generated    → server-side UUID4, client never controls it
        ├── Redis presence          → register_session() / remove_session()
        ├── Connection Manager      → tracks actual WebSocket objects (process-local)
        ├── Distributed presence    → publish_user_online / publish_user_offline
        ├── Event routing           → dispatches incoming client events
        │
        ▼
    messaging_service.py  (authoritative for all persistence and authorization)
        │
        ▼
    PostgreSQL

Session lifecycle
─────────────────
After websocket.accept():
  1. session_id = presence_service.new_session_id()         # server-generated UUID4
  2. first_session, _ = presence_service.register_session() # Redis presence
  3. manager.connect(user_id, websocket)                    # local socket registry
  4. if first_session: publish_user_online()                # distributed event
  5. if is_first_socket: local user_online to partner       # local notification

On disconnect (finally block):
  1. manager.disconnect(user_id, websocket)                 # local cleanup
  2. last_session, _ = presence_service.remove_session()    # Redis cleanup
  3. if last_session: publish_user_offline()                # distributed event
  4. if is_last_socket: local user_offline to partner       # local notification

Failure policy:
  - Redis register fails      → log, continue with local-only
  - Distributed publish fails → log, local delivery already happened
  - Redis remove fails        → logged by presence_service
  - ConnectionManager never raises (pure dict/set operations)

Security rules
──────────────
- Token is extracted from the `?token=` query parameter.  This is the
  standard approach for WebSocket authentication since browsers cannot
  send custom headers with the native WebSocket API.
- The authenticated user is resolved server-side from the JWT.
- `sender_id` / `user_id` from client messages are NEVER trusted.
- session_id is generated server-side; the client never provides it.
- The WebSocket connection is only accepted after all authorization
  checks pass.  Unauthorized handshakes are closed before `accept()`.

DB session policy
─────────────────
- A new SessionLocal session is created for each individual operation
  (message, read, delivered) and closed immediately afterwards.
- No session is held open for the lifetime of the connection.

Event protocol
──────────────
Client → Server:
  {"type": "message",       "data": {"content": "..."}}
  {"type": "typing_start",  "data": {}}
  {"type": "typing_stop",   "data": {}}
  {"type": "message_read",  "data": {}}

Server → Client:
  {"type": "new_message",           "data": {id, conversation_id, sender_id, content, created_at, delivered_at, read_at}}
  {"type": "message_delivered",     "data": {conversation_id, user_id}}
  {"type": "message_read",          "data": {conversation_id, user_id}}
  {"type": "user_typing",           "data": {conversation_id, user_id}}
  {"type": "user_stopped_typing",   "data": {conversation_id, user_id}}
  {"type": "user_online",           "data": {user_id}}
  {"type": "user_offline",          "data": {user_id}}
  {"type": "notification",          "data": {notification_type, conversation_id, sender_id, message_id}}
  {"type": "error",                 "data": {code, message}}
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from app.core.security import decode_access_token
from app.db.models import DirectConversationParticipant, User
from app.db.session import SessionLocal
from app.services import messaging_service as svc
from app.services import presence_service as presence
from app.services.websocket_manager import manager
from app.services.messaging_fanout import (
    publish_new_message,
    subscribe_conversation,
    unsubscribe_conversation,
)
from app.services.presence_fanout import (
    publish_user_online,
    publish_user_offline,
)

logger = logging.getLogger(__name__)

# WebSocket routes are added directly to a separate APIRouter so that they
# appear in the app without polluting the REST messaging router.
router = APIRouter(tags=["Messaging WebSocket"])


# ---------------------------------------------------------------------------
# Authentication helper
# ---------------------------------------------------------------------------


def _ws_authenticate(token: Optional[str]) -> Optional[dict]:
    """
    Validate the JWT from the WebSocket query parameter.

    Returns the decoded payload (containing 'sub' = user_id) or None.
    """
    if not token:
        return None
    return decode_access_token(token)


def _resolve_user(user_id: str) -> Optional[User]:
    """Load the User from the database using a fresh short-lived session."""
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()


def _get_other_participant_id(conversation_id: str, current_user_id: str) -> Optional[str]:
    """
    Return the ID of the other participant in the conversation.
    Returns None if not found or if the conversation is malformed.
    """
    db = SessionLocal()
    try:
        rows = (
            db.query(DirectConversationParticipant.user_id)
            .filter(DirectConversationParticipant.conversation_id == conversation_id)
            .all()
        )
        for (uid,) in rows:
            if uid != current_user_id:
                return uid
        return None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Error / event helpers
# ---------------------------------------------------------------------------


def _error_event(code: str, message: str) -> str:
    return json.dumps({"type": "error", "data": {"code": code, "message": message}})


def _event(event_type: str, data: dict) -> str:
    return json.dumps({"type": event_type, "data": data})


def _message_data(msg) -> dict:
    """Serialize a DirectMessage ORM object to a safe dict for wire transport."""
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "sender_id": msg.sender_id,
        "content": msg.content,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        "delivered_at": msg.delivered_at.isoformat() if msg.delivered_at else None,
        "read_at": msg.read_at.isoformat() if msg.read_at else None,
    }


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------


async def _handle_message(
    ws: WebSocket,
    conversation_id: str,
    current_user: User,
    other_user_id: str,
    data: dict,
) -> None:
    """
    Handle a 'message' event from the client.

    Phase 5.8.4 flow:
    1. Validate content.
    2. Persist via messaging_service (PostgreSQL — source of truth).
    3. Deliver locally to both participants via ConnectionManager.
    4. Fan out via Redis so other FastAPI instances can deliver to
       their locally connected recipients.
    5. If recipient is locally online, mark delivered and notify sender.

    The cross-instance fanout (step 4) is fire-and-forget after PostgreSQL
    persistence.  A publish failure does not affect the already-persisted
    message — it is logged and the local delivery already happened.
    """
    content = data.get("content", "")
    if not isinstance(content, str) or not content.strip():
        await ws.send_text(_error_event("invalid_message", "Message content cannot be empty."))
        return

    # ── Step 2: Persist (PostgreSQL first) ───────────────────────────────
    db = SessionLocal()
    try:
        msg = svc.send_direct_message(db, conversation_id, current_user, content)
    except Exception as exc:
        detail = getattr(exc, "detail", str(exc))
        await ws.send_text(_error_event("message_failed", str(detail)))
        return
    finally:
        db.close()

    msg_payload = _message_data(msg)

    # ── Step 3: Local delivery to both participants ───────────────────────
    # Deliver to sender (always on this instance — their socket is here).
    await manager.send_to_user(current_user.id, "new_message", msg_payload)
    # Attempt local delivery to recipient (may be on another instance).
    await manager.send_to_user(other_user_id, "new_message", msg_payload)

    # Lightweight notification for the recipient.
    await manager.send_to_user(
        other_user_id,
        "notification",
        {
            "notification_type": "new_message",
            "conversation_id": conversation_id,
            "sender_id": current_user.id,
            "message_id": msg.id,
        },
    )

    # ── Step 4: Cross-instance fanout via Redis ───────────────────────────
    # Publish AFTER PostgreSQL persistence and local delivery.
    # Other instances receive this and deliver to their local recipients.
    # This instance skips its own event (anti-loop check in fanout handler).
    await publish_new_message(
        message_id=msg.id,
        conversation_id=conversation_id,
        sender_id=current_user.id,
        recipient_id=other_user_id,
        content=msg.content,  # use the trimmed/persisted value from the service
        created_at=msg.created_at.isoformat() if msg.created_at else "",
    )

    # ── Step 5: Mark delivered if recipient is locally online ─────────────
    if manager.is_connected(other_user_id):
        db2 = SessionLocal()
        try:
            recipient = db2.query(User).filter(User.id == other_user_id).first()
            if recipient:
                svc.mark_messages_delivered(db2, conversation_id, recipient)
        except Exception:
            pass  # delivery mark is best-effort; message is already persisted
        finally:
            db2.close()

        await manager.send_to_user(
            current_user.id,
            "message_delivered",
            {"conversation_id": conversation_id, "user_id": other_user_id},
        )


async def _handle_typing_start(
    conversation_id: str,
    current_user: User,
    other_user_id: str,
) -> None:
    """Forward typing_start as user_typing to the other participant. Not persisted."""
    await manager.send_to_user(
        other_user_id,
        "user_typing",
        {"conversation_id": conversation_id, "user_id": current_user.id},
    )


async def _handle_typing_stop(
    conversation_id: str,
    current_user: User,
    other_user_id: str,
) -> None:
    """Forward typing_stop as user_stopped_typing. Not persisted."""
    await manager.send_to_user(
        other_user_id,
        "user_stopped_typing",
        {"conversation_id": conversation_id, "user_id": current_user.id},
    )


async def _handle_message_read(
    ws: WebSocket,
    conversation_id: str,
    current_user: User,
    other_user_id: str,
) -> None:
    """
    Handle a 'message_read' event.

    1. Call mark_messages_read() — updates PostgreSQL read state.
    2. Notify the other participant.
    """
    db = SessionLocal()
    try:
        svc.mark_messages_read(db, conversation_id, current_user)
    except Exception as exc:
        detail = getattr(exc, "detail", str(exc))
        await ws.send_text(_error_event("read_failed", str(detail)))
        return
    finally:
        db.close()

    await manager.send_to_user(
        other_user_id,
        "message_read",
        {"conversation_id": conversation_id, "user_id": current_user.id},
    )


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/messaging/ws/{conversation_id}")
async def websocket_messaging(
    websocket: WebSocket,
    conversation_id: str,
    token: Optional[str] = None,
) -> None:
    """
    WebSocket endpoint for real-time 1-to-1 messaging.

    Connection URL:
        ws://<host>/api/messaging/ws/<conversation_id>?token=<JWT>

    Authorization flow (all checks occur BEFORE websocket.accept()):
    1. Extract and validate JWT from ?token= query parameter.
    2. Resolve the authenticated user.
    3. Verify the conversation exists and the user is a participant.
    4. Verify both participants have an accepted professional connection.
    5. Only then: websocket.accept()

    This endpoint is intentionally thin — all persistence and authorization
    logic lives in messaging_service.py.
    """
    # ── Step 1: Authenticate ─────────────────────────────────────────────
    payload = _ws_authenticate(token)
    if payload is None:
        await websocket.close(code=4001, reason="Invalid or missing authentication token.")
        return

    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        await websocket.close(code=4001, reason="Invalid token payload.")
        return

    # ── Step 2: Resolve user ─────────────────────────────────────────────
    current_user = _resolve_user(user_id)
    if current_user is None:
        await websocket.close(code=4001, reason="Authenticated user not found.")
        return

    # ── Step 3 & 4: Conversation + participant + connection check ─────────
    db = SessionLocal()
    try:
        # Verify conversation exists and user is a participant.
        # Verify accepted connection — both done inside the service.
        conv = svc.get_direct_conversation_for_user(db, conversation_id, current_user)
        # Determine the other participant.
        participants = (
            db.query(DirectConversationParticipant.user_id)
            .filter(DirectConversationParticipant.conversation_id == conversation_id)
            .all()
        )
        other_user_id_candidates = [uid for (uid,) in participants if uid != current_user.id]
        if not other_user_id_candidates:
            db.close()
            await websocket.close(code=4003, reason="Conversation is malformed.")
            return
        other_user_id = other_user_id_candidates[0]

        # Verify accepted connection is still active.
        from app.services.messaging_service import _require_accepted_connection
        try:
            _require_accepted_connection(db, current_user.id, other_user_id)
        except Exception:
            db.close()
            await websocket.close(code=4003, reason="No accepted connection with the other participant.")
            return
    except Exception as exc:
        db.close()
        detail = getattr(exc, "detail", str(exc))
        code = 4004 if "not found" in str(detail).lower() else 4003
        await websocket.close(code=code, reason=str(detail))
        return
    finally:
        try:
            db.close()
        except Exception:
            pass

    # ── Step 5: Accept the connection ────────────────────────────────────
    await websocket.accept()

    # ── Step 6: Generate session ID + register in Redis + local manager ──
    #
    # Order:
    #   a. Generate a server-side session_id (UUID4; client never supplies it).
    #   b. Register in Redis presence  → distributed session tracking.
    #   c. Register in ConnectionManager → local WebSocket socket tracking.
    #
    # Failure policy (per Phase 5.8.5.1):
    #   - Redis register failure → log warning, continue with local-only.
    #     The connection remains functional; Redis presence will be absent
    #     for this session, which is acceptable for a single-process deployment.
    #   - ConnectionManager.connect() is pure dict/set — it never raises.
    #
    session_id = presence.new_session_id()

    _redis_first_session = False
    try:
        _first, _status = presence.register_session(current_user.id, session_id)
        _redis_first_session = _first
        if _status == "error":
            logger.warning(
                "ws: Redis presence registration failed uid=%s sid=%s — proceeding local-only",
                current_user.id, session_id,
            )
    except Exception as exc:
        logger.warning("ws: unexpected error in presence.register_session: %s", exc)

    # Local socket registration — always succeeds.
    is_first_socket = manager.connect(current_user.id, websocket)

    if is_first_socket:
        # Notify the conversation partner that this user came online (local).
        await manager.send_to_user(
            other_user_id,
            "user_online",
            {"user_id": current_user.id},
        )

    # ── Step 6c: Distributed presence — user came online ─────────────────
    # Publish user_online ONLY if this is the user's first global session
    # (first_session=True from Redis presence).  Intermediate sessions must
    # NOT generate an online event.
    # Fire-and-forget: a publish failure does not affect local state.
    if _redis_first_session:
        try:
            import asyncio as _asyncio
            _asyncio.ensure_future(publish_user_online(current_user.id))
        except Exception as exc:
            logger.warning(
                "ws: schedule publish_user_online failed uid=%s: %s",
                current_user.id, exc,
            )

    # ── Step 6b: Subscribe to the per-conversation fanout channel ────────
    # Registers intent for cross-instance delivery (no-op at runtime;
    # the pattern listener already covers all conversations).
    try:
        await subscribe_conversation(conversation_id)
    except Exception as exc:
        logger.warning(
            "ws: subscribe_conversation failed conv=%s: %s",
            conversation_id, exc,
        )

    # ── Step 7: Message loop ─────────────────────────────────────────────
    try:
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            # Parse the envelope.
            try:
                envelope = json.loads(raw)
                if not isinstance(envelope, dict):
                    raise ValueError("Expected a JSON object.")
            except (json.JSONDecodeError, ValueError):
                await websocket.send_text(
                    _error_event("invalid_json", "Invalid JSON payload.")
                )
                continue

            event_type = envelope.get("type")
            event_data = envelope.get("data", {})

            if not isinstance(event_data, dict):
                event_data = {}

            # Route the event.
            if event_type == "message":
                await _handle_message(
                    websocket, conversation_id, current_user, other_user_id, event_data
                )
            elif event_type == "typing_start":
                await _handle_typing_start(conversation_id, current_user, other_user_id)
            elif event_type == "typing_stop":
                await _handle_typing_stop(conversation_id, current_user, other_user_id)
            elif event_type == "message_read":
                await _handle_message_read(
                    websocket, conversation_id, current_user, other_user_id
                )
            else:
                await websocket.send_text(
                    _error_event(
                        "unsupported_event",
                        f"Unsupported WebSocket event: {event_type!r}.",
                    )
                )

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.exception("Unexpected error in WebSocket message loop: %s", exc)
    finally:
        # ── Cleanup: local disconnect → Redis removal ─────────────────────
        #
        # Order is intentional:
        #   1. Remove from local ConnectionManager first so no new events
        #      are dispatched to a socket that is already closing.
        #   2. Then remove from Redis so distributed presence is updated.
        #
        is_last_socket = manager.disconnect(current_user.id, websocket)

        # Remove the Redis presence session for this socket.
        # presence.remove_session() handles its own exceptions internally
        # and returns (False, "error") on Redis failure — safe to ignore here.
        _redis_last_session = False
        try:
            _last, _status = presence.remove_session(current_user.id, session_id)
            _redis_last_session = _last
        except Exception as exc:
            logger.warning("ws: unexpected error in presence.remove_session: %s", exc)

        # ── Distributed presence — user went offline ──────────────────────
        # Publish user_offline ONLY if this was the user's last global
        # session (last_session=True from Redis presence).  Intermediate
        # disconnects must NOT generate an offline event.
        if _redis_last_session:
            try:
                import asyncio as _asyncio
                _asyncio.ensure_future(publish_user_offline(current_user.id))
            except Exception as exc:
                logger.warning(
                    "ws: schedule publish_user_offline failed uid=%s: %s",
                    current_user.id, exc,
                )

        # Unsubscribe from the per-conversation fanout channel.
        # Registers release of interest (no-op at runtime; the pattern
        # listener continues but will simply not find the recipient connected).
        try:
            await unsubscribe_conversation(conversation_id)
        except Exception as exc:
            logger.warning(
                "ws: unsubscribe_conversation failed conv=%s: %s",
                conversation_id, exc,
            )

        if is_last_socket:
            # Notify the conversation partner that this user went offline (local).
            await manager.send_to_user(
                other_user_id,
                "user_offline",
                {"user_id": current_user.id},
            )
