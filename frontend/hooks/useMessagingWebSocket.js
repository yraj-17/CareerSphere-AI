import { useEffect, useRef, useCallback, useState } from 'react';
import { getStoredToken } from '@/lib/auth';

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

// Connection states exposed to the UI
export const WS_STATE = {
  IDLE: 'idle',
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  DISCONNECTED: 'disconnected',
  FAILED: 'failed',
};

/**
 * useMessagingWebSocket
 *
 * Manages a single WebSocket connection for a conversation.
 *
 * @param {string|null} conversationId - Active conversation ID (null = not connected)
 * @param {object}      handlers       - Event callbacks:
 *   onNewMessage(event)       — new_message / notification
 *   onMessageDelivered(event) — message_delivered
 *   onMessageRead(event)      — message_read
 *   onTyping(event)           — typing_start / typing_stop
 *   onUserOnline(userId)      — user_online
 *   onUserOffline(userId)     — user_offline
 *   onError(event)            — error events from server
 *
 * @returns {object} { wsState, sendMessage, sendTypingStart, sendTypingStop, sendMessageRead }
 */
export function useMessagingWebSocket(conversationId, handlers = {}) {
  const [wsState, setWsState] = useState(WS_STATE.IDLE);
  const socketRef = useRef(null);
  const handlersRef = useRef(handlers);
  const typingTimerRef = useRef(null);
  const isTypingRef = useRef(false);
  const activeConvRef = useRef(null);

  // Keep handlers fresh without triggering reconnect
  useEffect(() => {
    handlersRef.current = handlers;
  });

  const closeSocket = useCallback(() => {
    if (socketRef.current) {
      // Prevent onclose from firing reconnect logic after intentional close
      socketRef.current._intentionalClose = true;
      socketRef.current.close(1000, 'conversation changed');
      socketRef.current = null;
    }
    activeConvRef.current = null;
  }, []);

  useEffect(() => {
    if (!conversationId) {
      closeSocket();
      setWsState(WS_STATE.IDLE);
      return;
    }

    // Already connected to this conversation — skip
    if (activeConvRef.current === conversationId && socketRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    closeSocket();

    const token = getStoredToken();
    if (!token) {
      setWsState(WS_STATE.FAILED);
      return;
    }

    setWsState(WS_STATE.CONNECTING);
    activeConvRef.current = conversationId;

    const url = `${WS_BASE}/api/messaging/ws/${conversationId}?token=${token}`;
    const ws = new WebSocket(url);
    ws._intentionalClose = false;
    socketRef.current = ws;

    ws.onopen = () => {
      if (socketRef.current === ws) {
        setWsState(WS_STATE.CONNECTED);
      }
    };

    ws.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch {
        return;
      }

      const { type, data: payload } = data;
      const h = handlersRef.current;

      switch (type) {
        case 'new_message':
          h.onNewMessage?.(payload);
          break;
        case 'notification':
          // notification is a secondary event; forward to same handler
          h.onNewMessage?.(payload, 'notification');
          break;
        case 'message_delivered':
          h.onMessageDelivered?.(payload);
          break;
        case 'message_read':
          h.onMessageRead?.(payload);
          break;
        case 'user_typing':
          h.onTyping?.({ ...payload, isTyping: true });
          break;
        case 'user_stopped_typing':
          h.onTyping?.({ ...payload, isTyping: false });
          break;
        case 'user_online':
          h.onUserOnline?.(payload?.user_id ?? payload);
          break;
        case 'user_offline':
          h.onUserOffline?.(payload?.user_id ?? payload);
          break;
        case 'error':
          h.onError?.(payload);
          break;
        default:
          break;
      }
    };

    ws.onerror = () => {
      if (socketRef.current === ws) {
        setWsState(WS_STATE.FAILED);
      }
    };

    ws.onclose = (e) => {
      if (socketRef.current !== ws) return;
      if (ws._intentionalClose) return;
      setWsState(WS_STATE.DISCONNECTED);
    };

    return () => {
      ws._intentionalClose = true;
      ws.close(1000, 'effect cleanup');
      if (socketRef.current === ws) {
        socketRef.current = null;
      }
    };
  }, [conversationId, closeSocket]);

  // ── Sending helpers ─────────────────────────────────────────────────────────

  const _send = useCallback((payload) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(payload));
      return true;
    }
    return false;
  }, []);

  /** Send a chat message. Backend persists and delivers. */
  const sendMessage = useCallback((content) => {
    return _send({ type: 'message', data: { content } });
  }, [_send]);

  /** Notify backend that the current user started typing (debounced at call site). */
  const sendTypingStart = useCallback(() => {
    if (!isTypingRef.current) {
      isTypingRef.current = true;
      _send({ type: 'typing_start', data: {} });
    }
    // Auto stop typing after 3 s of no new start signals
    clearTimeout(typingTimerRef.current);
    typingTimerRef.current = setTimeout(() => {
      isTypingRef.current = false;
      _send({ type: 'typing_stop', data: {} });
    }, 3000);
  }, [_send]);

  /** Explicitly stop typing (e.g., on send or blur). */
  const sendTypingStop = useCallback(() => {
    clearTimeout(typingTimerRef.current);
    if (isTypingRef.current) {
      isTypingRef.current = false;
      _send({ type: 'typing_stop', data: {} });
    }
  }, [_send]);

  /** Tell the backend the user has read messages in this conversation. */
  const sendMessageRead = useCallback(() => {
    _send({ type: 'message_read', data: {} });
  }, [_send]);

  // Cleanup timers on unmount
  useEffect(() => () => clearTimeout(typingTimerRef.current), []);

  return { wsState, sendMessage, sendTypingStart, sendTypingStop, sendMessageRead };
}
