"""Authenticated global presence WebSocket endpoint.

Unlike the conversation WebSocket, this connection is scoped to the signed-in
session rather than a messaging page. It keeps one Redis presence session alive
while the user navigates through the dashboard and streams presence changes for
the user's accepted connections.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import SessionLocal
from app.services import connection_service
from app.services import presence_service as presence
from app.services.presence_fanout import publish_user_offline, publish_user_online
from app.services.websocket_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Presence WebSocket"])


def _event(event_type: str, data: dict) -> str:
    return json.dumps({"type": event_type, "data": data})


def _resolve_user(user_id: str) -> Optional[User]:
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()


def _get_accepted_connection_ids(user_id: str) -> list[str]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            return []
        connections = connection_service.get_accepted_connections(db, user)
        return [
            connection.receiver_id
            if connection.requester_id == user_id
            else connection.requester_id
            for connection in connections
        ]
    finally:
        db.close()


def _online_connection_ids(user_id: str) -> list[str]:
    return [
        connection_id
        for connection_id in _get_accepted_connection_ids(user_id)
        # Redis is the distributed source of truth, while the local manager
        # covers an active socket whose Redis registration/refresh briefly
        # failed. This prevents the first active user from appearing offline
        # merely because another user connected later.
        if manager.is_connected(connection_id) or presence.is_user_online(connection_id)
    ]


async def _refresh_session_loop(user_id: str, session_id: str) -> None:
    interval = settings.REDIS_PRESENCE_REFRESH_INTERVAL_SECONDS
    while True:
        await asyncio.sleep(interval)
        if not presence.refresh_session(user_id, session_id):
            return


async def _broadcast_local_presence(event_type: str, user_id: str) -> None:
    await manager.send_to_all(
        event_type,
        {"user_id": user_id},
        exclude_user_id=user_id,
    )


@router.websocket("/presence/ws")
async def websocket_presence(
    websocket: WebSocket,
    token: Optional[str] = None,
) -> None:
    """Keep an authenticated user's global dashboard presence alive."""
    payload = decode_access_token(token) if token else None
    if payload is None:
        await websocket.close(code=4001, reason="Invalid or missing authentication token.")
        return

    user_id = payload.get("sub")
    if not user_id or _resolve_user(user_id) is None:
        await websocket.close(code=4001, reason="Authenticated user not found.")
        return

    await websocket.accept()

    session_id = presence.new_session_id()
    redis_first_session = False
    try:
        redis_first_session, status = presence.register_session(user_id, session_id)
        if status == "error":
            logger.warning(
                "presence ws: Redis registration failed uid=%s sid=%s; continuing locally",
                user_id,
                session_id,
            )
    except Exception as exc:
        logger.warning("presence ws: unexpected registration failure uid=%s: %s", user_id, exc)

    first_local_socket = manager.connect(user_id, websocket)
    refresh_task: Optional[asyncio.Task] = None
    try:
        refresh_task = asyncio.create_task(
            _refresh_session_loop(user_id, session_id),
            name=f"presence-session-refresh-{session_id[:8]}",
        )
    except Exception as exc:
        logger.warning("presence ws: failed to start refresh task uid=%s: %s", user_id, exc)

    try:
        await websocket.send_text(
            _event("presence_snapshot", {"user_ids": _online_connection_ids(user_id)})
        )

        if first_local_socket:
            await _broadcast_local_presence("user_online", user_id)

        if redis_first_session:
            asyncio.ensure_future(publish_user_online(user_id))

        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("presence ws: connection ended uid=%s: %s", user_id, exc)
    finally:
        if refresh_task is not None and not refresh_task.done():
            refresh_task.cancel()
            try:
                await refresh_task
            except (asyncio.CancelledError, Exception):
                pass

        last_local_socket = manager.disconnect(user_id, websocket)
        redis_last_session = False
        try:
            redis_last_session, _status = presence.remove_session(user_id, session_id)
        except Exception as exc:
            logger.warning("presence ws: unexpected removal failure uid=%s: %s", user_id, exc)

        if redis_last_session:
            asyncio.ensure_future(publish_user_offline(user_id))

        if redis_last_session or last_local_socket:
            await _broadcast_local_presence("user_offline", user_id)
