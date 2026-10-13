'use client';

/**
 * ForwardModal — conversation picker for forwarding a message.
 *
 * Displays a searchable list of the user's conversations and lets them
 * choose a destination to forward a message to.
 *
 * Props:
 *   isOpen        {boolean}    — visibility flag
 *   conversations {Array}      — conversation list (MessagingPage format)
 *   currentUser   {object}     — { id, first_name, last_name }
 *   onClose       () => void
 *   onForward     (conversationId) => Promise<void>
 *   sourceMessage {object|null} — the message being forwarded (for preview)
 */

import React, { useState, useCallback, useMemo } from 'react';
import { Search, Send, X, Loader2, Share2 } from 'lucide-react';

function ConversationRow({ conv, onSelect, loading }) {
  const other = conv?.other_user;
  const initials = `${other?.first_name?.[0] ?? ''}${other?.last_name?.[0] ?? ''}`.toUpperCase() || '?';

  return (
    <button
      onClick={() => onSelect(conv.conversation_id)}
      disabled={loading}
      className="group flex w-full items-center gap-3 rounded-lg px-4 py-3 transition-colors hover:bg-slate-100 disabled:opacity-50"
    >
      {/* Avatar */}
      {other?.profile_photo_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={other.profile_photo_url}
          alt={`${other.first_name} ${other.last_name}`}
          className="h-9 w-9 rounded-full object-cover border border-white/10 flex-shrink-0"
          onError={(e) => { e.currentTarget.style.display = 'none'; }}
        />
      ) : (
        <div className="chat-inverse flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-500 text-xs font-bold">
          {initials}
        </div>
      )}

      {/* Name */}
      <div className="flex-1 min-w-0 text-left">
        <p className="truncate text-sm font-medium text-slate-900">
          {other?.first_name} {other?.last_name}
        </p>
        <p className="truncate text-xs text-slate-500">
          {conv.latest_message_content || 'No messages yet'}
        </p>
      </div>

      {/* Forward indicator */}
      <Share2 className="h-3.5 w-3.5 shrink-0 text-slate-400 transition-colors group-hover:text-brand-600" />
    </button>
  );
}

export default function ForwardModal({
  isOpen,
  conversations = [],
  currentUser,
  onClose,
  onForward,
  sourceMessage = null,
}) {
  const [query, setQuery] = useState('');
  const [forwarding, setForwarding] = useState(false);
  const [error, setError] = useState(null);

  const filtered = useMemo(() => {
    if (!query.trim()) return conversations;
    const q = query.toLowerCase();
    return conversations.filter((c) => {
      const other = c.other_user;
      return (
        other?.first_name?.toLowerCase().includes(q) ||
        other?.last_name?.toLowerCase().includes(q) ||
        other?.username?.toLowerCase().includes(q)
      );
    });
  }, [conversations, query]);

  const handleSelect = useCallback(async (conversationId) => {
    if (forwarding) return;
    setForwarding(true);
    setError(null);
    try {
      await onForward?.(conversationId);
      setQuery('');
      onClose?.();
    } catch (e) {
      setError(e?.response?.data?.detail || 'Failed to forward message.');
    } finally {
      setForwarding(false);
    }
  }, [forwarding, onForward, onClose]);

  const handleClose = useCallback(() => {
    if (forwarding) return;
    setQuery('');
    setError(null);
    onClose?.();
  }, [forwarding, onClose]);

  if (!isOpen) return null;

  const preview = sourceMessage?.is_deleted_for_everyone
    ? '🚫 This message was deleted'
    : sourceMessage?.content ?? '';
  const previewTruncated = preview.length > 80 ? preview.slice(0, 80) + '…' : preview;

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      onClick={handleClose}
    >
      {/* Blur backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Modal panel */}
      <div
        className="relative flex w-full max-w-sm flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-[0_24px_64px_rgba(11,42,91,0.2)]"
        style={{ maxHeight: '70vh' }}
        onClick={(e) => e.stopPropagation()}
        data-testid="forward-modal"
      >
        {/* Header */}
        <div className="flex items-center gap-3 border-b border-slate-200 px-5 py-4">
          <Share2 className="h-4.5 w-4.5 text-brand-600" />
          <h2 className="flex-1 text-sm font-semibold text-slate-900">Forward Message</h2>
          <button
            onClick={handleClose}
            disabled={forwarding}
            aria-label="Close"
            className="flex h-7 w-7 items-center justify-center rounded-full text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
          >
            <X className="h-4 w-4 text-slate-400" />
          </button>
        </div>

        {/* Message preview */}
        {sourceMessage && (
          <div className="mx-4 mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="mb-1 text-[11px] text-slate-500">Forwarding:</p>
            <p className="text-xs leading-relaxed text-slate-700">{previewTruncated}</p>
          </div>
        )}

        {/* Search */}
        <div className="px-4 py-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500 pointer-events-none" />
            <input
              type="text"
              placeholder="Search conversations…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
              className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-9 pr-4 text-sm text-slate-800 outline-none placeholder:text-slate-400 focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
            />
          </div>
        </div>

        {/* Error */}
        {error && (
          <p className="text-xs text-rose-400 px-4 pb-2">{error}</p>
        )}

        {/* Conversation list */}
        <div className="flex-1 overflow-y-auto px-2 pb-3">
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 gap-2">
              <p className="text-sm text-slate-500">No conversations found</p>
            </div>
          ) : (
            filtered.map((conv) => (
              <ConversationRow
                key={conv.conversation_id}
                conv={conv}
                onSelect={handleSelect}
                loading={forwarding}
              />
            ))
          )}
        </div>

        {/* Loading overlay */}
        {forwarding && (
          <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-black/40">
            <Loader2 className="h-6 w-6 text-accent animate-spin" />
          </div>
        )}
      </div>
    </div>
  );
}
