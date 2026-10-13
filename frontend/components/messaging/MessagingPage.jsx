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
import { MessageSquare, PanelLeftDashed, Search, X } from 'lucide-react';
import ConversationList from '@/components/messaging/ConversationList';
import ChatWindow from '@/components/messaging/ChatWindow';
import ForwardModal from '@/components/messaging/ForwardModal';
import { compareMessages } from '@/components/messaging/messageDateUtils';
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
  const byId = new Map(existing.filter((message) => message?.id).map((message) => [message.id, message]));
  incoming.filter((message) => message?.id).forEach((message) => {
    // Prefer the server's newest representation when REST and WebSocket
    // deliver the same message with different delivery/read metadata.
    byId.set(message.id, { ...byId.get(message.id), ...message });
  });
  return [...byId.values()].sort(compareMessages);
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
  const [historyCursor, setHistoryCursor] = useState(null);
  const [hasMore, setHasMore] = useState(false);

  // ── Pinned message ─────────────────────────────────────────────────────────
  const [pinnedMessage, setPinnedMessage] = useState(null);

  // ── Presence ───────────────────────────────────────────────────────────────
  const [onlineUsers, setOnlineUsers] = useState(new Set());
  const [isOtherTyping, setIsOtherTyping] = useState(false);
  const typingTimerRef = useRef(null);

  // ── Unread overrides from WS ───────────────────────────────────────────────
  const [unreadMap, setUnreadMap] = useState({});

  // ── Responsive shell state ────────────────────────────────────────────────
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

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
          setMobileSidebarOpen(false);
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
  const loadMessages = useCallback(async (convId, options = {}, prepend = false) => {
    setMsgLoading(true);
    try {
      const data = await listMessages(convId, {
        limit: PAGE_SIZE,
        offset: options.offset ?? 0,
        latest: options.latest ?? false,
        beforeCreatedAt: options.beforeCreatedAt,
        beforeId: options.beforeId,
      });
      const raw = Array.isArray(data) ? data : data.messages ?? [];
      setHasMore(raw.length === PAGE_SIZE);
      if (prepend) {
        setMessages((prev) => mergeMessages(raw, prev));
      } else {
        setMessages(raw);
      }
      setHistoryCursor(raw[0] ? {
        beforeCreatedAt: raw[0].created_at,
        beforeId: raw[0].id,
      } : null);
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
      setHistoryCursor(null);
      setHasMore(false);
      setIsOtherTyping(false);
      setPinnedMessage(null);
      return;
    }
    setMessages([]);
    setHistoryCursor(null);
    setHasMore(false);
    setIsOtherTyping(false);
    setPinnedMessage(null);
    loadMessages(activeConvId, { latest: true }, false);
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
      message_type: payload.message_type ?? 'TEXT',
      resource_id: payload.resource_id ?? null,
      resource: payload.resource ?? null,
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
      setMessages((prev) => mergeMessages(prev, [msg]));
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
          latest_message_content: msg.content || (msg.message_type === 'RESOURCE_SHARE' ? 'Shared a resource' : ''),
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
    setMobileSidebarOpen(false);
  }, []);

  const handleBack = useCallback(() => {
    setMobileSidebarOpen(true);
    setSelectedConv(null);
  }, []);

  const handleOpenSidebar = useCallback(() => {
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setMobileSidebarOpen(true);
    } else {
      setSidebarOpen(true);
    }
  }, []);

  const handleSend = useCallback((content, replyToMessageId = null) => {
    return sendMessage(content, replyToMessageId);
  }, [sendMessage]);

  const handleLoadMore = useCallback(() => {
    if (!activeConvId || msgLoading || !historyCursor?.beforeCreatedAt) return;
    loadMessages(activeConvId, historyCursor, true);
  }, [activeConvId, historyCursor, msgLoading, loadMessages]);

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
      if (activeConvId) loadMessages(activeConvId, { latest: true }, false);
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

  const renderSidebar = (mobile = false) => (
    <div className="flex h-full min-h-0 flex-col bg-slate-50" style={mobile ? undefined : { minHeight: '100vh' }}>
      <header className="flex h-16 shrink-0 items-center justify-between gap-3 border-b border-slate-200 px-4">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
            <MessageSquare className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <h1 className="truncate text-[15px] font-semibold text-slate-900">Messages</h1>
            <p className="truncate text-[11px] text-slate-500">Direct conversations</p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => (mobile ? setMobileSidebarOpen(false) : setSidebarOpen(false))}
          aria-label={mobile ? 'Close conversations' : 'Collapse conversations sidebar'}
          title={mobile ? 'Close conversations' : 'Collapse sidebar'}
          className="group flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-slate-200/80 bg-white text-slate-500 shadow-sm transition-all duration-200 hover:-translate-x-0.5 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-700 hover:shadow-[0_6px_16px_rgba(11,42,91,0.12)] active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-200"
        >
          {mobile ? (
            <X className="h-[18px] w-[18px] transition-transform duration-200 group-hover:rotate-90" />
          ) : (
            <PanelLeftDashed className="h-[18px] w-[18px] transition-transform duration-200 group-hover:-translate-x-0.5" />
          )}
        </button>
      </header>
      <div className="shrink-0 border-b border-slate-200 px-3 py-3">
        <label className="relative block">
          <span className="sr-only">Search conversations</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
          <input
            type="search"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Search conversations"
            className="h-9 w-full rounded-lg border border-slate-200 bg-white pl-9 pr-3 text-sm text-slate-800 outline-none placeholder:text-slate-400 focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
          />
        </label>
      </div>
      <div className="min-h-0 flex-1">
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
          searchQuery={searchQuery}
        />
      </div>
    </div>
  );

  return (
    <div
      data-testid="messaging-page"
      className="relative flex h-full min-h-0 min-w-0 w-full flex-1 overflow-hidden bg-white"
      style={{ height: '100vh', minHeight: '100vh' }}
    >
      {/* ── Conversation list panel ──────────────────────────────────── */}
      <aside
        className={`hidden h-full shrink-0 overflow-hidden border-r border-slate-200 bg-slate-50 transition-[width] duration-200 md:flex ${sidebarOpen ? 'w-[300px]' : 'w-0 border-r-0'}`}
        style={{ minHeight: '100vh' }}
      >
        <div className="h-full w-[300px]">{renderSidebar(false)}</div>
      </aside>

      {mobileSidebarOpen ? (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="Conversation list">
          <button type="button" onClick={() => setMobileSidebarOpen(false)} className="absolute inset-0 bg-black/40" aria-label="Close conversation list" />
          <aside className="relative z-10 flex h-full w-[min(320px,88vw)] flex-col bg-slate-50 shadow-[16px_0_32px_rgba(11,42,91,0.16)]">
            {renderSidebar(true)}
          </aside>
        </div>
      ) : null}

      {/* ── Chat window panel ────────────────────────────────────────── */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeConvId ?? 'empty'}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="flex min-h-0 min-w-0 flex-1 flex-col"
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
            sidebarOpen={sidebarOpen}
            mobileSidebarOpen={mobileSidebarOpen}
            onOpenSidebar={handleOpenSidebar}
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
