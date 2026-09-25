'use client';

/**
 * MessagingPage — top-level orchestrator for the messaging UI.
 *
 * Layout:
 *   Desktop: [ConversationList | ChatWindow]  (side by side)
 *   Mobile:  [ConversationList] → tap → [ChatWindow] (single panel)
 *
 * Responsibilities:
 *   - Load conversation list from REST
 *   - Load message history for the selected conversation
 *   - Manage WebSocket for active conversation
 *   - Handle all WS events: new_message, delivered, read, typing, online/offline
 *   - Track online presence per user
 *   - Deduplicate messages using message ID
 *   - Mark messages read when conversation is open
 *   - Expose loading/error/empty states
 *
 * Props:
 *   currentUser  {object}         — from AuthContext
 *   initialConvId {string|null}   — pre-selected conversation from URL
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquare } from 'lucide-react';
import ConversationList from '@/components/messaging/ConversationList';
import ChatWindow from '@/components/messaging/ChatWindow';
import { useMessagingWebSocket, WS_STATE } from '@/hooks/useMessagingWebSocket';
import {
  listConversations,
  listMessages,
  markMessagesRead,
  extractErrorMessage,
} from '@/services/api';

const PAGE_SIZE = 50;

// Merge two message arrays, deduplicating by ID, keeping chronological order
function mergeMessages(existing, incoming) {
  const seen = new Set(existing.map((m) => m.id));
  const novel = incoming.filter((m) => !seen.has(m.id));
  return [...existing, ...novel].sort(
    (a, b) => new Date(a.created_at) - new Date(b.created_at)
  );
}

export default function MessagingPage({ currentUser, initialConvId = null }) {
  // ── Conversation list ──────────────────────────────────────────────────────
  const [conversations, setConversations] = useState([]);
  const [convLoading, setConvLoading] = useState(true);
  const [convError, setConvError] = useState(null);

  // ── Selected conversation ──────────────────────────────────────────────────
  const [selectedConv, setSelectedConv] = useState(null); // full conv summary
  const activeConvId = selectedConv?.conversation_id ?? null;

  // ── Messages ───────────────────────────────────────────────────────────────
  const [messages, setMessages] = useState([]);
  const [msgLoading, setMsgLoading] = useState(false);
  const [msgOffset, setMsgOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  // ── Presence ───────────────────────────────────────────────────────────────
  const [onlineUsers, setOnlineUsers] = useState(new Set());
  const [isOtherTyping, setIsOtherTyping] = useState(false);
  const typingTimerRef = useRef(null);

  // ── Unread overrides from WS ───────────────────────────────────────────────
  const [unreadMap, setUnreadMap] = useState({});

  // ── Mobile panel state ─────────────────────────────────────────────────────
  const [mobileShowChat, setMobileShowChat] = useState(false);

  // ── Load conversations ─────────────────────────────────────────────────────
  const loadConversations = useCallback(async () => {
    setConvLoading(true);
    setConvError(null);
    try {
      const data = await listConversations({ limit: 50 });
      const list = Array.isArray(data) ? data : data.conversations ?? [];

      // Normalize: backend returns { id, other_participant, latest_message, unread_count }
      // Frontend uses: { conversation_id, other_user, latest_message_content, ... }
      const normalized = list.map((c) => ({
        conversation_id: c.id,
        other_user: c.other_participant,
        latest_message_content: c.latest_message?.content ?? null,
        latest_message_at: c.latest_message?.created_at ?? c.updated_at,
        latest_message_sender_id: c.latest_message?.sender_id ?? null,
        unread_count: c.unread_count ?? 0,
        updated_at: c.updated_at,
        // keep raw id for getOrCreateConversation reference
        _raw: c,
      }));

      setConversations(normalized);

      // Build initial unread map
      const map = {};
      normalized.forEach((c) => { map[c.conversation_id] = c.unread_count ?? 0; });
      setUnreadMap(map);

      // Pre-select from URL param
      if (initialConvId) {
        const match = normalized.find((c) => c.conversation_id === initialConvId);
        if (match) {
          setSelectedConv(match);
          setMobileShowChat(true);
        }
      }
    } catch (e) {
      setConvError(extractErrorMessage(e) || 'Failed to load conversations.');
    } finally {
      setConvLoading(false);
    }
  }, [initialConvId]);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  // ── Load messages for selected conversation ────────────────────────────────
  const loadMessages = useCallback(async (convId, offset = 0, prepend = false) => {
    setMsgLoading(true);
    try {
      const data = await listMessages(convId, { limit: PAGE_SIZE, offset });
      const raw = Array.isArray(data) ? data : data.messages ?? [];
      setHasMore(raw.length === PAGE_SIZE);
      if (prepend) {
        setMessages((prev) => mergeMessages(raw, prev));
        setMsgOffset((prev) => prev + raw.length);
      } else {
        setMessages(raw);
        setMsgOffset(raw.length);
      }
    } catch {
      // silent — WS will still deliver real-time messages
    } finally {
      setMsgLoading(false);
    }
  }, []);

  // When conversation changes, reset and load
  useEffect(() => {
    if (!activeConvId) {
      setMessages([]);
      setMsgOffset(0);
      setHasMore(false);
      setIsOtherTyping(false);
      return;
    }
    setMessages([]);
    setMsgOffset(0);
    setHasMore(false);
    setIsOtherTyping(false);
    loadMessages(activeConvId, 0, false);
  }, [activeConvId, loadMessages]);

  // Mark messages read when conversation opens / messages change
  useEffect(() => {
    if (!activeConvId) return;
    markMessagesRead(activeConvId).catch(() => {});
    // Clear local unread count for this conv
    setUnreadMap((prev) => ({ ...prev, [activeConvId]: 0 }));
  }, [activeConvId, messages.length]);

  // ── WebSocket event handlers ───────────────────────────────────────────────
  const handleNewMessage = useCallback((payload, eventType) => {
    if (!payload) return;

    // notification events are secondary — only process if we don't already have the message
    if (eventType === 'notification') return;

    const msg = {
      id: payload.id ?? payload.message_id,
      conversation_id: payload.conversation_id,
      sender_id: payload.sender_id,
      content: payload.content,
      created_at: payload.created_at,
      delivered_at: payload.delivered_at ?? null,
      read_at: payload.read_at ?? null,
    };

    if (!msg.id || !msg.conversation_id) return;

    // Only add to messages if it's for the active conversation
    if (msg.conversation_id === activeConvId) {
      setMessages((prev) => {
        if (prev.some((m) => m.id === msg.id)) return prev;
        return [...prev, msg];
      });
      // Mark as read immediately since user is viewing
      markMessagesRead(msg.conversation_id).catch(() => {});
    } else {
      // Increment unread count for other conversations
      if (msg.sender_id !== currentUser?.id) {
        setUnreadMap((prev) => ({
          ...prev,
          [msg.conversation_id]: (prev[msg.conversation_id] ?? 0) + 1,
        }));
      }
    }

    // Update conversation list preview (normalize to local format)
    setConversations((prev) =>
      prev.map((c) => {
        if (c.conversation_id !== msg.conversation_id) return c;
        return {
          ...c,
          latest_message_content: msg.content,
          latest_message_at: msg.created_at,
          latest_message_sender_id: msg.sender_id,
          updated_at: msg.created_at,
        };
      }).sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))
    );
  }, [activeConvId, currentUser?.id]);

  const handleMessageDelivered = useCallback((payload) => {
    if (!payload?.message_id) return;
    setMessages((prev) =>
      prev.map((m) =>
        m.id === payload.message_id ? { ...m, delivered_at: payload.delivered_at ?? new Date().toISOString() } : m
      )
    );
  }, []);

  const handleMessageRead = useCallback((payload) => {
    // Backend sends message_read on the conversation level — mark all as read
    setMessages((prev) =>
      prev.map((m) =>
        m.sender_id === currentUser?.id && !m.read_at
          ? { ...m, read_at: payload?.read_at ?? new Date().toISOString() }
          : m
      )
    );
  }, [currentUser?.id]);

  const handleTyping = useCallback((payload) => {
    const userId = payload?.user_id;
    if (!userId || userId === currentUser?.id) return;
    setIsOtherTyping(payload.isTyping);
    // Auto-clear after 4 s in case stop event is lost
    if (payload.isTyping) {
      clearTimeout(typingTimerRef.current);
      typingTimerRef.current = setTimeout(() => setIsOtherTyping(false), 4000);
    } else {
      clearTimeout(typingTimerRef.current);
    }
  }, [currentUser?.id]);

  const handleUserOnline = useCallback((userId) => {
    if (!userId) return;
    setOnlineUsers((prev) => new Set([...prev, userId]));
  }, []);

  const handleUserOffline = useCallback((userId) => {
    if (!userId) return;
    setOnlineUsers((prev) => {
      const next = new Set(prev);
      next.delete(userId);
      return next;
    });
  }, []);

  const handleWsError = useCallback(() => {}, []); // silent

  // ── WebSocket ──────────────────────────────────────────────────────────────
  const { wsState, sendMessage, sendTypingStart, sendTypingStop, sendMessageRead } =
    useMessagingWebSocket(activeConvId, {
      onNewMessage: handleNewMessage,
      onMessageDelivered: handleMessageDelivered,
      onMessageRead: handleMessageRead,
      onTyping: handleTyping,
      onUserOnline: handleUserOnline,
      onUserOffline: handleUserOffline,
      onError: handleWsError,
    });

  // Send read event when WS connects for active conversation
  useEffect(() => {
    if (wsState === WS_STATE.CONNECTED && activeConvId) {
      sendMessageRead();
    }
  }, [wsState, activeConvId, sendMessageRead]);

  // Cleanup typing timer on unmount
  useEffect(() => () => clearTimeout(typingTimerRef.current), []);

  // ── Handlers ───────────────────────────────────────────────────────────────
  const handleSelectConv = useCallback((conv) => {
    setSelectedConv(conv);
    setMobileShowChat(true);
  }, []);

  const handleBack = useCallback(() => {
    setMobileShowChat(false);
    setSelectedConv(null);
  }, []);

  const handleSend = useCallback((content) => {
    return sendMessage(content);
  }, [sendMessage]);

  const handleLoadMore = useCallback(() => {
    if (!activeConvId || msgLoading) return;
    loadMessages(activeConvId, msgOffset, true);
  }, [activeConvId, msgLoading, loadMessages, msgOffset]);

  const otherUser = selectedConv?.other_user;
  const isOtherOnline = otherUser?.id ? onlineUsers.has(otherUser.id) : false;

  return (
    <div
      data-testid="messaging-page"
      className="flex h-full w-full rounded-[2rem] border border-white/10 bg-white/[0.03] backdrop-blur-xl overflow-hidden shadow-glow"
      style={{ minHeight: '600px' }}
    >
      {/* ── Conversation list panel ──────────────────────────────────── */}
      <div className={`
        ${mobileShowChat ? 'hidden md:flex' : 'flex'}
        flex-col w-full md:w-80 lg:w-96
        border-r border-white/10 bg-slate-950/30 flex-shrink-0
      `}>
        {/* Panel header */}
        <div className="flex items-center gap-2 px-4 py-4 border-b border-white/10">
          <MessageSquare className="h-5 w-5 text-accent" />
          <h1 className="text-base font-bold text-white">Messages</h1>
        </div>

        <ConversationList
          conversations={conversations}
          selected={activeConvId}
          onSelect={handleSelectConv}
          loading={convLoading}
          error={convError}
          onlineUsers={onlineUsers}
          currentUserId={currentUser?.id}
          unreadMap={unreadMap}
          onRetry={loadConversations}
        />
      </div>

      {/* ── Chat window panel ────────────────────────────────────────── */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeConvId ?? 'empty'}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className={`
            ${!mobileShowChat && !activeConvId ? 'hidden md:flex' : 'flex'}
            flex-1 flex-col min-w-0
          `}
        >
          <ChatWindow
            conversation={selectedConv}
            currentUser={currentUser}
            wsState={wsState}
            isOtherOnline={isOtherOnline}
            isTyping={isOtherTyping}
            messages={messages}
            loadingHistory={msgLoading}
            hasMore={hasMore}
            onLoadMore={handleLoadMore}
            onSend={handleSend}
            onTyping={sendTypingStart}
            onStopTyping={sendTypingStop}
            onBack={handleBack}
          />
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
