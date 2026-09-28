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
import { WS_STATE } from '@/hooks/useMessagingWebSocket';

const DM_MAX_CHARS = 4000;

// ─── Sub-components ───────────────────────────────────────────────────────────

function AvatarInitials({ user, size = 'md' }) {
  const initials = `${user?.first_name?.[0] ?? ''}${user?.last_name?.[0] ?? ''}`.toUpperCase() || '?';
  const sz = size === 'sm' ? 'h-8 w-8 text-xs' : 'h-10 w-10 text-sm';
  return (
    <div className={`${sz} rounded-full bg-gradient-to-br from-accent/30 via-accent/10 to-violet-500/20 border border-accent/20 flex items-center justify-center font-bold text-white flex-shrink-0`}>
      {initials}
    </div>
  );
}

function ConnectionStatusBanner({ wsState }) {
  if (wsState === WS_STATE.CONNECTED || wsState === WS_STATE.IDLE) return null;

  const configs = {
    [WS_STATE.CONNECTING]: {
      text: 'Connecting…',
      cls: 'bg-amber-500/10 border-amber-500/20 text-amber-300',
      Icon: Loader2,
      spin: true,
    },
    [WS_STATE.DISCONNECTED]: {
      text: 'Reconnecting…',
      cls: 'bg-amber-500/10 border-amber-500/20 text-amber-300',
      Icon: Wifi,
      spin: false,
    },
    [WS_STATE.FAILED]: {
      text: 'Unable to connect — check your network',
      cls: 'bg-rose-500/10 border-rose-500/20 text-rose-300',
      Icon: WifiOff,
      spin: false,
    },
  };

  const cfg = configs[wsState];
  if (!cfg) return null;

  return (
    <div className={`flex items-center justify-center gap-2 px-3 py-1.5 text-xs border-b ${cfg.cls}`}>
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
    <div className="flex items-center gap-2 px-4 py-2 border-b border-white/10 bg-amber-500/5 hover:bg-amber-500/10 transition-colors">
      <Pin className="h-3 w-3 text-amber-400 flex-shrink-0" />
      <button
        onClick={() => onScrollTo?.(pinnedMessage.id)}
        className="flex-1 text-left min-w-0"
      >
        <p className="text-[10px] text-amber-400/70 mb-0.5">Pinned message</p>
        <p className="text-xs text-slate-300 truncate">{preview}</p>
      </button>
      {onUnpin && (
        <button
          onClick={onUnpin}
          aria-label="Unpin message"
          className="h-5 w-5 rounded-full flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all"
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
    <div className="flex items-center gap-2 px-4 py-2 border-t border-white/10 bg-slate-950/60 backdrop-blur-sm">
      <Reply className="h-3.5 w-3.5 text-accent flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-[10px] text-accent/70 mb-0.5">Replying to</p>
        <p className="text-xs text-slate-400 truncate">{preview}</p>
      </div>
      <button
        onClick={onCancel}
        aria-label="Cancel reply"
        className="h-5 w-5 rounded-full flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/10 transition-all"
      >
        <X className="h-3 w-3" />
      </button>
    </div>
  );
}

function DeleteConfirmDialog({ message, onConfirm, onCancel }) {
  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onCancel} />
      <div
        className="relative w-full max-w-xs bg-slate-900/95 backdrop-blur-xl border border-white/10 rounded-3xl p-5 shadow-[0_24px_64px_rgba(0,0,0,0.6)]"
        data-testid="delete-confirm-dialog"
      >
        <div className="flex items-center gap-2 mb-3">
          <div className="h-8 w-8 rounded-full bg-rose-500/15 flex items-center justify-center">
            <Trash2 className="h-4 w-4 text-rose-400" />
          </div>
          <h3 className="text-sm font-semibold text-white">Delete for Everyone?</h3>
        </div>
        <p className="text-xs text-slate-400 leading-relaxed mb-4">
          This message will be permanently hidden for all participants and cannot be undone.
        </p>
        <div className="flex gap-2">
          <button
            onClick={onCancel}
            className="flex-1 py-2 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-slate-300 hover:bg-white/10 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            data-testid="confirm-delete-btn"
            className="flex-1 py-2 px-3 rounded-xl bg-rose-500/20 border border-rose-500/30 text-sm text-rose-300 hover:bg-rose-500/30 transition-colors"
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
}) {
  const [text, setText] = useState('');
  const [sendError, setSendError] = useState(null);
  const [replyingTo, setReplyingTo] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null); // message to delete-for-everyone
  const endRef = useRef(null);
  const inputRef = useRef(null);
  const prevLenRef = useRef(0);
  // Ref bag for scroll-to by message ID
  const msgScrollRefs = useRef({});

  const other = conversation?.other_user;

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (messages.length > prevLenRef.current) {
      endRef.current?.scrollIntoView?.({ behavior: 'smooth' });
    }
    prevLenRef.current = messages.length;
  }, [messages.length]);

  // Auto-scroll on first load
  useEffect(() => {
    if (!loadingHistory && messages.length > 0) {
      endRef.current?.scrollIntoView?.({ behavior: 'instant' });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadingHistory]);

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
      <div className="flex flex-col items-center justify-center h-full gap-4 text-center px-6">
        <div className="h-16 w-16 rounded-3xl bg-white/5 border border-white/10 flex items-center justify-center">
          <User className="h-8 w-8 text-slate-500" />
        </div>
        <div>
          <p className="text-sm font-medium text-slate-300">Select a conversation</p>
          <p className="text-xs text-slate-500 mt-1">Choose a conversation from the left to start messaging</p>
        </div>
      </div>
    );
  }

  const charsLeft = DM_MAX_CHARS - text.length;
  const canSend = text.trim().length > 0 && text.length <= DM_MAX_CHARS && wsState === WS_STATE.CONNECTED;

  return (
    <div className="flex flex-col h-full">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-white/10 bg-slate-950/40 backdrop-blur-sm flex-shrink-0">
        {/* Mobile back button */}
        <button
          onClick={onBack}
          className="md:hidden flex items-center gap-1.5 text-slate-400 hover:text-white transition-colors p-1 -ml-1"
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
            className="h-10 w-10 rounded-full object-cover border border-white/10 flex-shrink-0"
            onError={(e) => { e.currentTarget.style.display = 'none'; }}
          />
        ) : (
          <AvatarInitials user={other} />
        )}

        {/* Name + status */}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-white truncate">
            {other?.first_name} {other?.last_name}
          </p>
          <div className="flex items-center gap-1.5">
            <span className={`h-1.5 w-1.5 rounded-full ${isOtherOnline ? 'bg-emerald-400' : 'bg-slate-500'}`} />
            <span className="text-xs text-slate-400">
              {isOtherOnline ? 'Online' : 'Offline'}
            </span>
          </div>
        </div>

        {/* View Profile */}
        {other?.id && (
          <Link
            href={`/dashboard/networking/${other.id}`}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white border border-white/10 rounded-full px-3 py-1.5 hover:border-white/20 transition-all"
            title="View Profile"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Profile</span>
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
      <div className="flex-1 overflow-y-auto chat-scroll flex flex-col py-4 gap-2 min-h-0">
        {/* Load more */}
        {hasMore && (
          <div className="flex justify-center py-2">
            <button
              onClick={onLoadMore}
              disabled={loadingHistory}
              className="flex items-center gap-2 text-xs text-slate-400 hover:text-accent border border-white/10 rounded-full px-4 py-2 hover:border-accent/30 transition-all"
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
        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
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
        ))}

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
      <div className="flex-shrink-0 border-t border-white/10 bg-slate-950/40 backdrop-blur-sm px-4 py-3">
        {/* Send error */}
        {sendError && (
          <div className="flex items-center gap-2 mb-2 px-3 py-2 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300">
            <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
            {sendError}
          </div>
        )}

        <div className="flex items-end gap-3">
          <textarea
            ref={inputRef}
            data-testid="message-input"
            rows={1}
            value={text}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder={replyingTo ? 'Reply…' : 'Type a message… (Enter to send, Shift+Enter for newline)'}
            disabled={wsState !== WS_STATE.CONNECTED}
            className="flex-1 resize-none bg-white/[0.06] border border-white/10 rounded-2xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed max-h-32 overflow-y-auto chat-scroll leading-relaxed"
            style={{ minHeight: '42px' }}
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
            className={`flex-shrink-0 h-10 w-10 rounded-2xl flex items-center justify-center transition-all ${
              canSend
                ? 'bg-accent text-black shadow-[0_4px_20px_rgba(255,143,50,0.35)] hover:bg-accentSoft hover:scale-105'
                : 'bg-white/5 border border-white/10 text-slate-600 cursor-not-allowed'
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
