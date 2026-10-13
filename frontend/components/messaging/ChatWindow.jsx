'use client';

/**
 * ChatWindow — the right panel: header + message history + input.
 *
 * Phase 5.8 additions:
 *   - Reply bar above the input (shows when replying to a message)
 *   - Pinned message banner below the header
 *   - Delete-for-everyone confirmation dialog
 *   - All message action handlers passed down to MessageBubble
 *   - Scroll-to anchors for reply navigation
 *
 * Props:
 *   conversation  {object|null}   — selected conversation summary
 *   currentUser   {object}        — { id, first_name, last_name }
 *   wsState       {string}        — WS_STATE value
 *   isOtherOnline {boolean}       — derived from presence events
 *   isTyping      {boolean}       — other user is typing
 *   messages      {Array}         — persisted + live messages
 *   loadingHistory {boolean}
 *   hasMore       {boolean}       — more pages available
 *   onLoadMore    () => void
 *   onSend        (content, replyToId?) => boolean
 *   onTyping      () => void
 *   onStopTyping  () => void
 *   onBack        () => void
 *   pinnedMessage {object|null}   — currently pinned message
 *   onReply       (message) => void
 *   onStar        (message) => void
 *   onPin         (message) => void
 *   onForward     (message) => void
 *   onDeleteForMe (message) => void
 *   onDeleteForEveryone (message) => void
 */

import React, { useRef, useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  Send,
  Loader2,
  AlertCircle,
  PanelLeftOpen,
  Wifi,
  WifiOff,
  ExternalLink,
  User,
  Pin,
  X,
  Reply,
  Trash2,
} from 'lucide-react';
import MessageBubble from '@/components/messaging/MessageBubble';
import TypingIndicator from '@/components/messaging/TypingIndicator';
import { formatDateSeparatorLabel, getLocalDateKey } from '@/components/messaging/messageDateUtils';
import { WS_STATE } from '@/hooks/useMessagingWebSocket';

const DM_MAX_CHARS = 4000;

// ─── Sub-components ───────────────────────────────────────────────────────────

function AvatarInitials({ user, size = 'md' }) {
  const initials = `${user?.first_name?.[0] ?? ''}${user?.last_name?.[0] ?? ''}`.toUpperCase() || '?';
  const sz = size === 'sm' ? 'h-8 w-8 text-xs' : 'h-10 w-10 text-sm';
  return (
    <div className={`chat-inverse ${sz} flex shrink-0 items-center justify-center rounded-full bg-brand-500 font-bold`}>
      {initials}
    </div>
  );
}

function ConnectionStatusBanner({ wsState }) {
  if (wsState === WS_STATE.CONNECTED || wsState === WS_STATE.IDLE) return null;

  const configs = {
    [WS_STATE.CONNECTING]: {
      text: 'Connecting…',
      cls: 'border-amber-200 bg-amber-50 text-amber-700',
      Icon: Loader2,
      spin: true,
    },
    [WS_STATE.DISCONNECTED]: {
      text: 'Reconnecting…',
      cls: 'border-amber-200 bg-amber-50 text-amber-700',
      Icon: Wifi,
      spin: false,
    },
    [WS_STATE.FAILED]: {
      text: 'Unable to connect — check your network',
      cls: 'border-red-200 bg-red-50 text-red-700',
      Icon: WifiOff,
      spin: false,
    },
  };

  const cfg = configs[wsState];
  if (!cfg) return null;

  return (
    <div className={`flex items-center justify-center gap-2 border-b px-3 py-1.5 text-xs ${cfg.cls}`}>
      <cfg.Icon className={`h-3.5 w-3.5 ${cfg.spin ? 'animate-spin' : ''}`} />
      {cfg.text}
    </div>
  );
}

function PinnedMessageBanner({ pinnedMessage, onScrollTo, onUnpin }) {
  if (!pinnedMessage) return null;
  const preview = pinnedMessage.is_deleted_for_everyone
    ? '🚫 This message was deleted'
    : (pinnedMessage.content || '').slice(0, 60) + ((pinnedMessage.content?.length ?? 0) > 60 ? '…' : '');

  return (
    <div className="flex items-center gap-2 border-b border-amber-100 bg-amber-50 px-4 py-2 transition-colors hover:bg-amber-100">
      <Pin className="h-3 w-3 shrink-0 text-amber-600" />
      <button
        onClick={() => onScrollTo?.(pinnedMessage.id)}
        className="flex-1 text-left min-w-0"
      >
        <p className="mb-0.5 text-[10px] font-semibold text-amber-700">Pinned message</p>
        <p className="truncate text-xs text-slate-600">{preview}</p>
      </button>
      {onUnpin && (
        <button
          onClick={onUnpin}
          aria-label="Unpin message"
          className="flex h-5 w-5 items-center justify-center rounded-full text-slate-400 transition-all hover:bg-amber-200 hover:text-slate-700"
        >
          <X className="h-3 w-3" />
        </button>
      )}
    </div>
  );
}

function ReplyBar({ replyingTo, isMine, onCancel }) {
  if (!replyingTo) return null;
  const preview = replyingTo.is_deleted_for_everyone
    ? '🚫 This message was deleted'
    : (replyingTo.content || '').slice(0, 80) + ((replyingTo.content?.length ?? 0) > 80 ? '…' : '');

  return (
    <div className="flex items-center gap-2 border-t border-slate-200 bg-slate-50 px-4 py-2">
      <Reply className="h-3.5 w-3.5 shrink-0 text-brand-500" />
      <div className="flex-1 min-w-0">
        <p className="mb-0.5 text-[10px] font-semibold text-brand-600">Replying to</p>
        <p className="truncate text-xs text-slate-500">{preview}</p>
      </div>
      <button
        onClick={onCancel}
        aria-label="Cancel reply"
        className="flex h-5 w-5 items-center justify-center rounded-full text-slate-400 transition-all hover:bg-slate-200 hover:text-slate-700"
      >
        <X className="h-3 w-3" />
      </button>
    </div>
  );
}

function DateSeparator({ label }) {
  return (
    <div className="flex items-center gap-3 px-4 py-2" data-testid="message-date-separator">
      <span className="h-px flex-1 bg-slate-100" />
      <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500">
        {label}
      </span>
      <span className="h-px flex-1 bg-slate-100" />
    </div>
  );
}

function DeleteConfirmDialog({ message, onConfirm, onCancel }) {
  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onCancel} />
      <div
        className="relative w-full max-w-xs rounded-xl border border-slate-200 bg-white p-5 shadow-[0_24px_64px_rgba(11,42,91,0.2)]"
        data-testid="delete-confirm-dialog"
      >
        <div className="flex items-center gap-2 mb-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-red-50">
            <Trash2 className="h-4 w-4 text-red-600" />
          </div>
          <h3 className="text-sm font-semibold text-slate-900">Delete for Everyone?</h3>
        </div>
        <p className="mb-4 text-xs leading-relaxed text-slate-500">
          This message will be permanently hidden for all participants and cannot be undone.
        </p>
        <div className="flex gap-2">
          <button
            onClick={onCancel}
            className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 transition-colors hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            data-testid="confirm-delete-btn"
            className="chat-inverse flex-1 rounded-lg bg-red-600 px-3 py-2 text-sm font-semibold transition-colors hover:bg-red-700"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function ChatWindow({
  conversation,
  currentUser,
  wsState,
  isOtherOnline = false,
  isTyping = false,
  messages = [],
  loadingHistory = false,
  hasMore = false,
  onLoadMore,
  onSend,
  onTyping,
  onStopTyping,
  onBack,
  pinnedMessage = null,
  onReply,
  onStar,
  onPin,
  onUnpin,
  onForward,
  onDeleteForMe,
  onDeleteForEveryone,
  sidebarOpen = true,
  mobileSidebarOpen = true,
  onOpenSidebar,
}) {
  const [text, setText] = useState('');
  const [sendError, setSendError] = useState(null);
  const [replyingTo, setReplyingTo] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null); // message to delete-for-everyone
  const endRef = useRef(null);
  const scrollViewportRef = useRef(null);
  const inputRef = useRef(null);
  const prevLenRef = useRef(0);
  const prevFirstIdRef = useRef(null);
  const shouldStickToBottomRef = useRef(true);
  const previousScrollHeightRef = useRef(0);
  // Ref bag for scroll-to by message ID
  const msgScrollRefs = useRef({});

  const other = conversation?.other_user;

  useEffect(() => {
    prevLenRef.current = 0;
    prevFirstIdRef.current = null;
    shouldStickToBottomRef.current = true;
    previousScrollHeightRef.current = 0;
  }, [conversation?.conversation_id]);

  // Auto-scroll only when the reader is already near the bottom. Loading older
  // messages must not yank the reader away from the part of the thread they are viewing.
  useEffect(() => {
    const firstId = messages[0]?.id ?? null;
    const prepended = Boolean(
      prevFirstIdRef.current && firstId && firstId !== prevFirstIdRef.current && messages.length > prevLenRef.current
    );
    if (prepended && scrollViewportRef.current && previousScrollHeightRef.current) {
      const heightDelta = scrollViewportRef.current.scrollHeight - previousScrollHeightRef.current;
      scrollViewportRef.current.scrollTop += heightDelta;
      previousScrollHeightRef.current = 0;
    } else if (!prepended && messages.length > prevLenRef.current && shouldStickToBottomRef.current) {
      endRef.current?.scrollIntoView?.({ behavior: 'smooth' });
    }
    prevLenRef.current = messages.length;
    prevFirstIdRef.current = firstId;
  }, [messages]);

  const handleHistoryScroll = useCallback((event) => {
    const element = event.currentTarget;
    const distanceFromBottom = element.scrollHeight - element.scrollTop - element.clientHeight;
    shouldStickToBottomRef.current = distanceFromBottom < 120;
  }, []);

  const handleLoadEarlier = useCallback(() => {
    previousScrollHeightRef.current = scrollViewportRef.current?.scrollHeight ?? 0;
    onLoadMore?.();
  }, [onLoadMore]);

  // Scroll to a specific message by ID (for reply navigation)
  const scrollToMessage = useCallback((msgId) => {
    const el = msgScrollRefs.current?.[msgId];
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      // Highlight briefly
      el.classList.add('ring-1', 'ring-accent/40');
      setTimeout(() => el.classList.remove('ring-1', 'ring-accent/40'), 1200);
    }
  }, []);

  const handleSend = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed) return;
    if (trimmed.length > DM_MAX_CHARS) return;

    setSendError(null);
    const ok = onSend?.(trimmed, replyingTo?.id ?? null);
    if (ok === false) {
      setSendError("Message couldn't be sent — connection unavailable.");
      return;
    }
    setText('');
    setReplyingTo(null);
    onStopTyping?.();
    inputRef.current?.focus();
  }, [text, onSend, replyingTo, onStopTyping]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  const handleChange = useCallback((e) => {
    const val = e.target.value;
    setText(val);
    if (val.trim() && val.length <= DM_MAX_CHARS) {
      onTyping?.();
    } else {
      onStopTyping?.();
    }
  }, [onTyping, onStopTyping]);

  // Reply handler — set reply state, focus input
  const handleReply = useCallback((message) => {
    setReplyingTo(message);
    inputRef.current?.focus();
    onReply?.(message);
  }, [onReply]);

  // Delete-for-everyone — show confirm dialog first
  const handleDeleteForEveryoneClick = useCallback((message) => {
    setDeleteConfirm(message);
  }, []);

  const handleDeleteConfirm = useCallback(() => {
    if (deleteConfirm) {
      onDeleteForEveryone?.(deleteConfirm);
      setDeleteConfirm(null);
    }
  }, [deleteConfirm, onDeleteForEveryone]);

  // Scroll to pinned message
  const handleScrollToPinned = useCallback(() => {
    if (pinnedMessage?.id) scrollToMessage(pinnedMessage.id);
  }, [pinnedMessage, scrollToMessage]);

  // Empty / no selection state
  if (!conversation) {
    return (
      <div className="flex h-full flex-col bg-white">
        <div className="flex h-14 shrink-0 items-center gap-3 border-b border-slate-200 px-4">
          {(!sidebarOpen || !mobileSidebarOpen) && onOpenSidebar ? (
            <button type="button" onClick={onOpenSidebar} aria-label="Open conversations sidebar" title="Open sidebar" className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-brand-50 hover:text-brand-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-200">
              <PanelLeftOpen className="h-4 w-4" />
            </button>
          ) : null}
          <p className="text-sm font-semibold text-slate-900">Messages</p>
        </div>
        <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-brand-50 text-brand-600">
            <User className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800">Select a conversation</p>
            <p className="mt-1 text-xs text-slate-500">Choose a conversation from the left to start messaging</p>
          </div>
        </div>
      </div>
    );
  }

  const charsLeft = DM_MAX_CHARS - text.length;
  const canSend = text.trim().length > 0 && text.length <= DM_MAX_CHARS && wsState === WS_STATE.CONNECTED;

  return (
    <div className="flex h-full min-h-0 flex-col bg-white">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex h-16 shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-4 sm:px-6">
        {!sidebarOpen && onOpenSidebar ? (
          <button type="button" onClick={onOpenSidebar} aria-label="Open conversations sidebar" title="Open sidebar" className="hidden h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-500 hover:bg-brand-50 hover:text-brand-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-200 md:flex">
            <PanelLeftOpen className="h-4 w-4" />
          </button>
        ) : null}
        {/* Mobile back button */}
        <button
          onClick={onBack}
          className="-ml-1 flex items-center gap-1.5 p-1 text-slate-500 transition-colors hover:text-brand-600 md:hidden"
          aria-label="Back to conversations"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>

        {/* Avatar */}
        {other?.profile_photo_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={other.profile_photo_url}
            alt={`${other.first_name} ${other.last_name}`}
            className="h-9 w-9 shrink-0 rounded-full border border-slate-200 object-cover"
            onError={(e) => { e.currentTarget.style.display = 'none'; }}
          />
        ) : (
          <AvatarInitials user={other} />
        )}

        {/* Name + status */}
        <div className="flex-1 min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900">
            {other?.first_name} {other?.last_name}
          </p>
          <div className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className={`h-2 w-2 rounded-full ${isOtherOnline ? 'bg-[#22c55e] shadow-[0_0_0_3px_rgba(34,197,94,0.12)]' : 'bg-slate-300'}`}
            />
            <span className={`text-xs ${isOtherOnline ? 'font-medium text-emerald-700' : 'text-slate-500'}`}>
              {isOtherOnline ? 'Online' : 'Offline'}
            </span>
          </div>
        </div>

        {/* View Profile */}
        {other?.id && (
          <Link
            href={`/dashboard/networking/${other.id}`}
            className="group flex shrink-0 items-center gap-2 rounded-xl border border-brand-100 bg-brand-50/70 px-3 py-1.5 text-xs font-semibold text-brand-700 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-brand-200 hover:bg-brand-100 hover:shadow-[0_8px_20px_rgba(11,42,91,0.12)] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-200"
            title="View Profile"
          >
            <span className="chat-inverse flex h-6 w-6 items-center justify-center rounded-lg bg-brand-500 shadow-sm transition-colors group-hover:bg-brand-600">
              <ExternalLink className="h-3.5 w-3.5" />
            </span>
            <span className="hidden sm:inline">View profile</span>
          </Link>
        )}
      </div>

      {/* ── WS status ──────────────────────────────────────────────────────── */}
      <ConnectionStatusBanner wsState={wsState} />

      {/* ── Pinned message banner ───────────────────────────────────────────── */}
      <PinnedMessageBanner
        pinnedMessage={pinnedMessage}
        onScrollTo={scrollToMessage}
        onUnpin={pinnedMessage ? () => onUnpin?.(pinnedMessage) : null}
      />

      {/* ── Message area ─────────────────────────────────────────────────── */}
      <div ref={scrollViewportRef} onScroll={handleHistoryScroll} className="chat-scroll flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto bg-white px-1 py-5 sm:px-2">
        {/* Load more */}
        {hasMore && (
          <div className="flex justify-center py-2">
            <button
              onClick={handleLoadEarlier}
              disabled={loadingHistory}
              className="flex items-center gap-2 rounded-full border border-slate-200 px-4 py-2 text-xs text-slate-500 transition-all hover:border-brand-200 hover:bg-brand-50 hover:text-brand-700"
            >
              {loadingHistory ? (
                <><Loader2 className="h-3 w-3 animate-spin" /> Loading…</>
              ) : (
                'Load earlier messages'
              )}
            </button>
          </div>
        )}

        {/* Initial loading */}
        {loadingHistory && messages.length === 0 && (
          <div className="flex flex-col items-center justify-center flex-1 gap-3">
            <Loader2 className="h-6 w-6 text-accent animate-spin" />
            <p className="text-sm text-slate-400">Loading messages…</p>
          </div>
        )}

        {/* Empty conversation */}
        {!loadingHistory && messages.length === 0 && (
          <div className="flex flex-col items-center justify-center flex-1 gap-3 px-6 text-center">
            <p className="text-sm text-slate-400">No messages yet</p>
            <p className="text-xs text-slate-500">Say hi to {other?.first_name}!</p>
          </div>
        )}

        {/* Messages */}
        {messages.reduce((rendered, msg) => {
          const dateKey = getLocalDateKey(msg.created_at);
          const showDateSeparator = Boolean(dateKey && dateKey !== rendered.dateKey);
          const nextDateKey = dateKey || rendered.dateKey;

          return {
            dateKey: nextDateKey,
            nodes: [
              ...rendered.nodes,
              <React.Fragment key={msg.id}>
                {showDateSeparator ? (
                  <DateSeparator label={formatDateSeparatorLabel(msg.created_at)} />
                ) : null}
                <MessageBubble
                  message={msg}
                  isMine={msg.sender_id === currentUser?.id}
                  scrollRef={msgScrollRefs}
                  onReply={handleReply}
                  onStar={() => onStar?.(msg)}
                  onPin={() => onPin?.(msg)}
                  onForward={() => onForward?.(msg)}
                  onDeleteForMe={() => onDeleteForMe?.(msg)}
                  onDeleteForEveryone={() => handleDeleteForEveryoneClick(msg)}
                />
              </React.Fragment>,
            ],
          };
        }, { dateKey: null, nodes: [] }).nodes}

        {/* Typing indicator */}
        {isTyping && (
          <TypingIndicator name={other?.first_name} />
        )}

        {/* Scroll anchor */}
        <div ref={endRef} />
      </div>

      {/* ── Reply bar ─────────────────────────────────────────────────────── */}
      {replyingTo && (
        <ReplyBar
          replyingTo={replyingTo}
          isMine={replyingTo.sender_id === currentUser?.id}
          onCancel={() => setReplyingTo(null)}
        />
      )}

      {/* ── Input bar ─────────────────────────────────────────────────────── */}
      <div className="shrink-0 border-t border-slate-200 bg-white px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 sm:px-5">
        {/* Send error */}
        {sendError && (
          <div className="mb-2 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
            {sendError}
          </div>
        )}

        <div className="mx-auto flex max-w-[900px] items-end gap-2 rounded-xl border border-slate-300 bg-white p-2 shadow-[0_8px_24px_rgba(16,47,107,0.08)] focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-100">
          <textarea
            ref={inputRef}
            data-testid="message-input"
            rows={1}
            value={text}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder={replyingTo ? 'Reply…' : 'Type a message… (Enter to send, Shift+Enter for newline)'}
            disabled={wsState !== WS_STATE.CONNECTED}
            className="block max-h-32 min-h-10 flex-1 resize-none overflow-y-auto border-0 bg-transparent px-2 py-1.5 text-sm leading-6 text-slate-900 outline-none placeholder:text-slate-400 focus:ring-0 disabled:cursor-not-allowed disabled:opacity-50"
            style={{ minHeight: '40px' }}
          />

          {/* Char count — only show when close to limit */}
          {text.length > DM_MAX_CHARS * 0.8 && (
            <span className={`text-[11px] flex-shrink-0 ${charsLeft < 200 ? 'text-rose-400' : 'text-slate-500'}`}>
              {charsLeft}
            </span>
          )}

          <button
            data-testid="send-button"
            onClick={handleSend}
            disabled={!canSend}
            aria-label="Send message"
            className={`chat-inverse flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-all ${
              canSend
                ? 'bg-brand-500 shadow-sm hover:bg-brand-600'
                : 'border border-slate-200 bg-slate-100 text-slate-400 cursor-not-allowed'
            }`}
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* ── Delete for Everyone confirmation ─────────────────────────────── */}
      {deleteConfirm && (
        <DeleteConfirmDialog
          message={deleteConfirm}
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleteConfirm(null)}
        />
      )}
    </div>
  );
}
