'use client';

/**
 * ConversationList — left panel showing all conversations.
 *
 * Props:
 *   conversations  {Array}          — list from REST API
 *   selected       {string|null}    — active conversationId
 *   onSelect       (conv) => void   — open a conversation
 *   loading        {boolean}
 *   error          {string|null}
 *   onlineUsers    {Set<string>}    — set of online user IDs
 *   currentUserId  {string}
 *   unreadMap      {Object}         — { [convId]: count } overrides from WS
 */

import React from 'react';
import { Loader2, MessageSquare, AlertCircle, RefreshCw } from 'lucide-react';

function formatRelativeTime(iso) {
  if (!iso) return '';
  try {
    const now = Date.now();
    const then = new Date(iso).getTime();
    const diff = now - then;
    if (diff < 60_000) return 'now';
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h`;
    return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

function AvatarInitials({ user, size = 'md' }) {
  const initials = `${user?.first_name?.[0] ?? ''}${user?.last_name?.[0] ?? ''}`.toUpperCase() || '?';
  const sz = size === 'sm' ? 'h-9 w-9 text-sm' : 'h-10 w-10 text-sm';
  return (
    <div className={`${sz} rounded-full bg-gradient-to-br from-accent/30 via-accent/10 to-violet/20 border border-accent/20 flex items-center justify-center font-bold text-white flex-shrink-0 select-none`}>
      {initials}
    </div>
  );
}

function OnlineDot({ online }) {
  return (
    <span
      className={`h-2.5 w-2.5 rounded-full border-2 border-slate-900 flex-shrink-0 ${online ? 'bg-emerald-400' : 'bg-slate-600'}`}
      title={online ? 'Online' : 'Offline'}
    />
  );
}

export default function ConversationList({
  conversations = [],
  selected = null,
  onSelect,
  loading = false,
  error = null,
  onlineUsers = new Set(),
  currentUserId,
  unreadMap = {},
  onRetry,
}) {
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 py-12">
        <Loader2 className="h-6 w-6 text-accent animate-spin" />
        <p className="text-sm text-slate-400">Loading conversations…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 py-12 px-4 text-center">
        <AlertCircle className="h-6 w-6 text-rose-400" />
        <p className="text-sm text-slate-300">{error}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="flex items-center gap-1.5 text-xs text-accent hover:text-accentSoft transition-colors"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Retry
          </button>
        )}
      </div>
    );
  }

  if (conversations.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 py-12 px-4 text-center">
        <div className="h-12 w-12 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center">
          <MessageSquare className="h-6 w-6 text-slate-500" />
        </div>
        <p className="text-sm font-medium text-slate-300">No conversations yet</p>
        <p className="text-xs text-slate-500 leading-relaxed">
          Connect with someone and send them a message to get started.
        </p>
      </div>
    );
  }

  return (
    <div
      data-testid="conversation-list"
      className="flex flex-col overflow-y-auto chat-scroll h-full"
    >
      {conversations.map((conv) => {
        const other = conv.other_user;
        const isOnline = other?.id ? onlineUsers.has(other.id) : false;
        const isActive = selected === conv.conversation_id;
        const unread = unreadMap[conv.conversation_id] ?? conv.unread_count ?? 0;
        const preview = conv.latest_message_content;
        const isMineLatest = conv.latest_message_sender_id === currentUserId;

        return (
          <button
            key={conv.conversation_id}
            data-testid="conversation-item"
            onClick={() => onSelect(conv)}
            className={`w-full text-left flex items-center gap-3 px-4 py-3.5 border-b border-white/5 transition-all duration-150 ${
              isActive
                ? 'bg-accent/10 border-l-2 border-l-accent'
                : 'hover:bg-white/[0.04] border-l-2 border-l-transparent'
            }`}
          >
            {/* Avatar + online dot */}
            <div className="relative flex-shrink-0">
              {other?.profile_photo_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={other.profile_photo_url}
                  alt={`${other.first_name} ${other.last_name}`}
                  className="h-10 w-10 rounded-full object-cover border border-white/10"
                  onError={(e) => { e.currentTarget.style.display = 'none'; }}
                />
              ) : (
                <AvatarInitials user={other} />
              )}
              <span className="absolute -bottom-0.5 -right-0.5">
                <OnlineDot online={isOnline} />
              </span>
            </div>

            {/* Text content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline justify-between gap-2">
                <span className={`text-sm font-semibold truncate ${isActive ? 'text-white' : 'text-slate-200'}`}>
                  {other?.first_name} {other?.last_name}
                </span>
                <span className="text-[11px] text-slate-500 flex-shrink-0">
                  {formatRelativeTime(conv.latest_message_at || conv.updated_at)}
                </span>
              </div>
              <div className="flex items-center justify-between gap-2 mt-0.5">
                <p className={`text-xs truncate ${unread > 0 ? 'text-slate-200 font-medium' : 'text-slate-500'}`}>
                  {preview
                    ? `${isMineLatest ? 'You: ' : ''}${preview}`
                    : <span className="italic text-slate-600">No messages yet</span>
                  }
                </p>
                {unread > 0 && (
                  <span className="flex-shrink-0 h-4.5 min-w-[1.25rem] px-1.5 rounded-full bg-accent text-black text-[10px] font-bold flex items-center justify-center">
                    {unread > 99 ? '99+' : unread}
                  </span>
                )}
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
