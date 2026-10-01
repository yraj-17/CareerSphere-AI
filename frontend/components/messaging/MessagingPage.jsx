'use client';

/**
 * MessagingPage — top-level orchestrator for the messaging UI.
 *
 * Phase 5.8 additions:
 *   - Message management actions (star, pin, unpin, delete-for-me,
 *     delete-for-everyone, forward)
 *   - Pinned message state per conversation
 *   - Real-time message_deleted / message_pinned / message_unpinned WS events
 *   - ForwardModal for destination conversation picking
 *
 * Layout:
 *   Desktop: [ConversationList | ChatWindow]  (side by side)
 *   Mobile:  [ConversationList] → tap → [ChatWindow] (single panel)
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquare } from 'lucide-react';
import ConversationList from '@/components/messaging/ConversationList';
import ChatWindow from '@/components/messaging/ChatWindow';
import ForwardModal from '@/components/messaging/ForwardModal';
import { useMessagingWebSocket, WS_STATE } from '@/hooks/useMessagingWebSocket';
import {
  listConversations,
  listMessages,
  markMessagesRead,
  extractErrorMessage,
  starMessage,
  unstarMessage,
  pinMessage,
  unpinMessage,
  deleteMessageForMe,
  deleteMessageForEveryone,
  forwardMessage,
  getPinnedMessage,
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
  const [selectedConv, setSelectedConv] = useState(null);
  const activeConvId = selectedConv?.conversation_id ?? null;

  // ── Messages ───────────────────────────────────────────────────────────────
  const [messages, setMessages] = useState([]);
  const [msgLoading, setMsgLoading] = useState(false);
  const [msgOffset, setMsgOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  // ── Pinned message ─────────────────────────────────────────────────────────
  const [pinnedMessage, setPinnedMessage] = useState(null);

  // ── Presence ───────────────────────────────────────────────────────────────
  const [onlineUsers, setOnlineUsers] = useState(new Set());
  const [isOtherTyping, setIsOtherTyping] = useState(false);
  const typingTimerRef = useRef(null);

  // ── Unread overrides from WS ───────────────────────────────────────────────
  const [unreadMap, setUnreadMap] = useState({});

  // ── Mobile panel state ─────────────────────────────────────────────────────
  const [mobileShowChat, setMobileShowChat] = useState(false);

  // ── Forward modal ──────────────────────────────────────────────────────────
  const [forwardSource, setForwardSource] = useState(null);  // message being forwarded

  // ── Load conversations ─────────────────────────────────────────────────────
  const loadConversations = useCallback(async () => {
    setConvLoading(true);
    setConvError(null);
    try {
      const data = await listConversations({ limit: 50 });
      const list = Array.isArray(data) ? data : data.conversations ?? [];

      const normalized = list.map((c) => ({
        conversation_id: c.id,
        other_user: c.other_participant,
        latest_message_id: c.latest_message?.id ?? null,
        latest_message_content: c.latest_message?.content ?? null,
        latest_message_at: c.latest_message?.created_at ?? c.updated_at,
        latest_message_sender_id: c.latest_message?.sender_id ?? null,
        unread_count: c.unread_count ?? 0,
        updated_at: c.updated_at,
        _raw: c,
      }));

      setConversations(normalized);

      const map = {};
      normalized.forEach((c) => { map[c.conversation_id] = c.unread_count ?? 0; });
      setUnreadMap(map);

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

  // Load pinned message when conversation changes
  const loadPinnedMessage = useCallback(async (convId) => {
    try {
      const result = await getPinnedMessage(convId);
      setPinnedMessage(result?.message ?? null);
    } catch {
      setPinnedMessage(null);
    }
  }, []);

  useEffect(() => {
    if (!activeConvId) {
      setMessages([]);
      setMsgOffset(0);
      setHasMore(false);
      setIsOtherTyping(false);
      setPinnedMessage(null);
      return;
    }
    setMessages([]);
    setMsgOffset(0);
    setHasMore(false);
    setIsOtherTyping(false);
    setPinnedMessage(null);
    loadMessages(activeConvId, 0, false);
    loadPinnedMessage(activeConvId);
  }, [activeConvId, loadMessages, loadPinnedMessage]);

  // Mark messages read when conversation opens / messages change
  useEffect(() => {
    if (!activeConvId) return;
    markMessagesRead(activeConvId).catch(() => {});
    setUnreadMap((prev) => ({ ...prev, [activeConvId]: 0 }));
  }, [activeConvId, messages.length]);

  // ── WebSocket event handlers ───────────────────────────────────────────────

  const handleNewMessage = useCallback((payload, eventType) => {
    if (!payload) return;
    if (eventType === 'notification') return;

    const msg = {
      id: payload.id ?? payload.message_id,
      conversation_id: payload.conversation_id,
      sender_id: payload.sender_id,
      content: payload.content,
      created_at: payload.created_at,
      delivered_at: payload.delivered_at ?? null,
      read_at: payload.read_at ?? null,
      // Phase 5.8 fields
      reply_to_message_id: payload.reply_to_message_id ?? null,
      reply_to_message: payload.reply_to_message ?? null,
      is_deleted_for_everyone: payload.is_deleted_for_everyone ?? false,
      is_pinned: payload.is_pinned ?? false,
      is_forwarded: payload.is_forwarded ?? false,
      forwarded_from_message_id: payload.forwarded_from_message_id ?? null,
      is_starred: payload.is_starred ?? false,
      is_deleted_for_me: payload.is_deleted_for_me ?? false,
    };

    if (!msg.id || !msg.conversation_id) return;

    if (msg.conversation_id === activeConvId) {
      setMessages((prev) => {
        if (prev.some((m) => m.id === msg.id)) return prev;
        return [...prev, msg];
      });
      markMessagesRead(msg.conversation_id).catch(() => {});
    } else {
      if (msg.sender_id !== currentUser?.id) {
        setUnreadMap((prev) => ({
          ...prev,
          [msg.conversation_id]: (prev[msg.conversation_id] ?? 0) + 1,
        }));
      }
    }

    setConversations((prev) =>
      prev.map((c) => {
        if (c.conversation_id !== msg.conversation_id) return c;
        return {
          ...c,
          latest_message_id: msg.id,
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

  // ── Phase 5.8 — WS management event handlers ──────────────────────────────

  const handleMessageDeleted = useCallback((payload) => {
    if (!payload?.message_id) return;
    setMessages((prev) =>
      prev.map((m) =>
        m.id === payload.message_id
          ? {
              ...m,
              is_deleted_for_everyone: true,
              content: '🚫 This message was deleted',
              is_pinned: false,
            }
          : m
      )
    );
    // If the deleted message was pinned, clear pin state
    setPinnedMessage((prev) =>
      prev?.id === payload.message_id ? null : prev
    );
    setConversations((prev) =>
      prev.map((conversation) =>
        conversation.latest_message_id === payload.message_id
          ? {
              ...conversation,
              latest_message_content: '🚫 This message was deleted',
            }
          : conversation
      )
    );
  }, []);

  const handleMessagePinned = useCallback((payload) => {
    if (!payload?.message_id || !payload?.conversation_id) return;
    if (payload.conversation_id !== activeConvId) return;
    // Reload pinned message from backend for full data
    loadPinnedMessage(payload.conversation_id);
    // Update pin state in messages
    setMessages((prev) =>
      prev.map((m) => ({
        ...m,
        is_pinned: m.id === payload.message_id,
      }))
    );
  }, [activeConvId, loadPinnedMessage]);

  const handleMessageUnpinned = useCallback((payload) => {
    if (!payload?.message_id || !payload?.conversation_id) return;
    if (payload.conversation_id !== activeConvId) return;
    setPinnedMessage(null);
    setMessages((prev) =>
      prev.map((m) =>
        m.id === payload.message_id ? { ...m, is_pinned: false } : m
      )
    );
  }, [activeConvId]);

  const handleWsError = useCallback(() => {}, []);

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
      onMessageDeleted: handleMessageDeleted,
      onMessagePinned: handleMessagePinned,
      onMessageUnpinned: handleMessageUnpinned,
    });

  useEffect(() => {
    if (wsState === WS_STATE.CONNECTED && activeConvId) {
      sendMessageRead();
    }
  }, [wsState, activeConvId, messages.length, sendMessageRead]);

  useEffect(() => () => clearTimeout(typingTimerRef.current), []);

  // ── Navigation handlers ────────────────────────────────────────────────────
  const handleSelectConv = useCallback((conv) => {
    setSelectedConv(conv);
    setMobileShowChat(true);
  }, []);

  const handleBack = useCallback(() => {
    setMobileShowChat(false);
    setSelectedConv(null);
  }, []);

  const handleSend = useCallback((content, replyToMessageId = null) => {
    return sendMessage(content, replyToMessageId);
  }, [sendMessage]);

  const handleLoadMore = useCallback(() => {
    if (!activeConvId || msgLoading) return;
    loadMessages(activeConvId, msgOffset, true);
  }, [activeConvId, msgLoading, loadMessages, msgOffset]);

  // ── Phase 5.8 — Message action handlers ───────────────────────────────────

  const handleStar = useCallback(async (message) => {
    const wasStarred = message.is_starred;
    // Optimistic update
    setMessages((prev) =>
      prev.map((m) => m.id === message.id ? { ...m, is_starred: !wasStarred } : m)
    );
    try {
      if (wasStarred) {
        await unstarMessage(message.id);
      } else {
        await starMessage(message.id);
      }
    } catch {
      // Revert on failure
      setMessages((prev) =>
        prev.map((m) => m.id === message.id ? { ...m, is_starred: wasStarred } : m)
      );
    }
  }, []);

  const handlePin = useCallback(async (message) => {
    if (message.is_pinned) {
      // Unpin
      try {
        await unpinMessage(message.id);
        setPinnedMessage(null);
        setMessages((prev) =>
          prev.map((m) => m.id === message.id ? { ...m, is_pinned: false } : m)
        );
      } catch {
        // silent
      }
    } else {
      // Pin
      try {
        const result = await pinMessage(message.id);
        // Clear all pins, set this one
        setMessages((prev) =>
          prev.map((m) => ({ ...m, is_pinned: m.id === message.id }))
        );
        setPinnedMessage(result?.message ?? { ...message, is_pinned: true });
      } catch {
        // silent
      }
    }
  }, []);

  const handleUnpin = useCallback(async (message) => {
    if (!message) return;
    try {
      await unpinMessage(message.id);
      setPinnedMessage(null);
      setMessages((prev) =>
        prev.map((m) => m.id === message.id ? { ...m, is_pinned: false } : m)
      );
    } catch {
      // silent
    }
  }, []);

  const handleDeleteForMe = useCallback(async (message) => {
    // Optimistic: remove from local state
    setMessages((prev) => prev.filter((m) => m.id !== message.id));
    try {
      await deleteMessageForMe(message.id);
    } catch {
      // If it fails, re-fetch messages to restore state
      if (activeConvId) loadMessages(activeConvId, 0, false);
    }
  }, [activeConvId, loadMessages]);

  const handleDeleteForEveryone = useCallback(async (message) => {
    // Optimistic: mark as deleted
    const placeholder = '🚫 This message was deleted';
    setMessages((prev) =>
      prev.map((m) =>
        m.id === message.id
          ? { ...m, is_deleted_for_everyone: true, content: placeholder, is_pinned: false }
          : m
      )
    );
    setConversations((prev) =>
      prev.map((conversation) =>
        conversation.latest_message_id === message.id
          ? { ...conversation, latest_message_content: placeholder }
          : conversation
      )
    );
    // Clear pin if this was pinned
    if (pinnedMessage?.id === message.id) setPinnedMessage(null);

    try {
      await deleteMessageForEveryone(message.id);
    } catch {
      // Revert on failure
      setMessages((prev) =>
        prev.map((m) =>
          m.id === message.id
            ? { ...m, is_deleted_for_everyone: false, content: message.content, is_pinned: message.is_pinned }
            : m
        )
      );
      setConversations((prev) =>
        prev.map((conversation) =>
          conversation.latest_message_id === message.id
            ? { ...conversation, latest_message_content: message.content }
            : conversation
        )
      );
    }
  }, [pinnedMessage]);

  const handleForward = useCallback((message) => {
    setForwardSource(message);
  }, []);

  const handleForwardConfirm = useCallback(async (destinationConvId) => {
    if (!forwardSource) return;
    await forwardMessage(forwardSource.id, destinationConvId);
  }, [forwardSource]);

  // ── Derived state ──────────────────────────────────────────────────────────
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
            pinnedMessage={pinnedMessage}
            onStar={handleStar}
            onPin={handlePin}
            onUnpin={handleUnpin}
            onForward={handleForward}
            onDeleteForMe={handleDeleteForMe}
            onDeleteForEveryone={handleDeleteForEveryone}
          />
        </motion.div>
      </AnimatePresence>

      {/* ── Forward modal ─────────────────────────────────────────────── */}
      <ForwardModal
        isOpen={Boolean(forwardSource)}
        conversations={conversations}
        currentUser={currentUser}
        onClose={() => setForwardSource(null)}
        onForward={handleForwardConfirm}
        sourceMessage={forwardSource}
      />
    </div>
  );
}
