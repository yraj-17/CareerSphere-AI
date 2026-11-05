'use client';

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useAuth } from '@/context/AuthContext';
import { getStoredToken } from '@/lib/auth';

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

const DEFAULT_CONTEXT = {
  onlineUsers: new Set(),
  markOnline: () => {},
  markOffline: () => {},
};

const PresenceContext = createContext(DEFAULT_CONTEXT);

function normalizeUserId(userId) {
  if (userId === null || userId === undefined || userId === '') return null;
  return String(userId);
}

export function PresenceProvider({ children }) {
  const { user, token, isAuthenticated } = useAuth();
  const [onlineUsers, setOnlineUsers] = useState(() => new Set());
  const socketRef = useRef(null);

  const markOnline = useCallback((userId) => {
    const normalizedId = normalizeUserId(userId);
    if (!normalizedId || normalizedId === normalizeUserId(user?.id)) return;

    setOnlineUsers((previous) => {
      if (previous.has(normalizedId)) return previous;
      const next = new Set(previous);
      next.add(normalizedId);
      return next;
    });
  }, [user?.id]);

  const markOffline = useCallback((userId) => {
    const normalizedId = normalizeUserId(userId);
    if (!normalizedId) return;

    setOnlineUsers((previous) => {
      if (!previous.has(normalizedId)) return previous;
      const next = new Set(previous);
      next.delete(normalizedId);
      return next;
    });
  }, []);

  useEffect(() => {
    const authToken = token || getStoredToken();
    const currentUserId = normalizeUserId(user?.id);

    if (!isAuthenticated || !authToken || !currentUserId) {
      socketRef.current?.close(1000, 'not authenticated');
      socketRef.current = null;
      setOnlineUsers(new Set());
      return undefined;
    }

    let disposed = false;
    let reconnectTimer = null;
    let reconnectDelay = 1000;

    const scheduleReconnect = () => {
      if (disposed || reconnectTimer) return;
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        connect();
      }, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, 30000);
    };

    const connect = () => {
      if (disposed) return;

      const websocket = new WebSocket(
        `${WS_BASE}/api/presence/ws?token=${encodeURIComponent(authToken)}`
      );
      socketRef.current = websocket;

      websocket.onopen = () => {
        reconnectDelay = 1000;
      };

      websocket.onmessage = (event) => {
        let envelope;
        try {
          envelope = JSON.parse(event.data);
        } catch {
          return;
        }

        const payload = envelope?.data;
        if (envelope?.type === 'presence_snapshot') {
          const ids = Array.isArray(payload?.user_ids)
            ? payload.user_ids.map(normalizeUserId).filter((id) => id && id !== currentUserId)
            : [];
          setOnlineUsers(new Set(ids));
          return;
        }

        const eventUserId = normalizeUserId(payload?.user_id ?? payload);
        if (envelope?.type === 'user_online') {
          markOnline(eventUserId);
        } else if (envelope?.type === 'user_offline') {
          markOffline(eventUserId);
        }
      };

      websocket.onerror = () => {
        websocket.close();
      };

      websocket.onclose = () => {
        if (socketRef.current === websocket) socketRef.current = null;
        if (!disposed) {
          setOnlineUsers(new Set());
          scheduleReconnect();
        }
      };
    };

    connect();

    return () => {
      disposed = true;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      reconnectTimer = null;
      if (socketRef.current) {
        socketRef.current.close(1000, 'presence scope changed');
        socketRef.current = null;
      }
      setOnlineUsers(new Set());
    };
  }, [isAuthenticated, token, user?.id, markOnline, markOffline]);

  const value = useMemo(() => ({ onlineUsers, markOnline, markOffline }), [
    onlineUsers,
    markOnline,
    markOffline,
  ]);

  return <PresenceContext.Provider value={value}>{children}</PresenceContext.Provider>;
}

export function usePresence() {
  return useContext(PresenceContext);
}
