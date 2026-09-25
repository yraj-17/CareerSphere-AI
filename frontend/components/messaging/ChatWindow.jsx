'use client';

/**
 * ChatWindow — the right panel: header + message history + input.
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
 *   onSend        (content) => boolean  — returns false if WS not ready
 *   onTyping      () => void       — called on keystroke (debounced internally)
 *   onStopTyping  () => void
 *   onBack        () => void       — mobile back navigation
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
} from 'lucide-react';
import MessageBubble from '@/components/messaging/MessageBubble';
import TypingIndicator from '@/components/messaging/TypingIndicator';
import { WS_STATE } from '@/hooks/useMessagingWebSocket';

const DM_MAX_CHARS = 4000;

function AvatarInitials({ user, size = 'md' }) {
  const initials = `${user?.first_name?.[0] ?? ''}${user?.last_name?.[0] ?? ''}`.toUpperCase() || '?';
  const sz = size === 'sm' ? 'h-8 w-8 text-xs' : 'h-10 w-10 text-sm';
  return (
    <div className={`${sz} rounded-full bg-gradient-to-br from-accent/30 via-accent/10 to-violet/20 border border-accent/20 flex items-center justify-center font-bold text-white flex-shrink-0`}>
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
}) {
  const [text, setText] = useState('');
  const [sendError, setSendError] = useState(null);
  const endRef = useRef(null);
  const inputRef = useRef(null);
  const prevLenRef = useRef(0);

  const other = conversation?.other_user;

  // Auto-scroll to bottom when new messages arrive (but not when loading more above)
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

  const handleSend = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed) return;
    if (trimmed.length > DM_MAX_CHARS) return;

    setSendError(null);
    const ok = onSend?.(trimmed);
    if (ok === false) {
      setSendError('Message couldn\'t be sent — connection unavailable.');
      return;
    }
    setText('');
    onStopTyping?.();
    inputRef.current?.focus();
  }, [text, onSend, onStopTyping]);

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
      {/* ── Header ────────────────────────────────────────────────────── */}
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

      {/* ── WS connection status ───────────────────────────────────────── */}
      <ConnectionStatusBanner wsState={wsState} />

      {/* ── Message area ──────────────────────────────────────────────── */}
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
          />
        ))}

        {/* Typing indicator */}
        {isTyping && (
          <TypingIndicator name={other?.first_name} />
        )}

        {/* Scroll anchor */}
        <div ref={endRef} />
      </div>

      {/* ── Input bar ─────────────────────────────────────────────────── */}
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
            placeholder="Type a message… (Enter to send, Shift+Enter for newline)"
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
    </div>
  );
}
