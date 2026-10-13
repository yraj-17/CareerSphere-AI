'use client';

import React, { useMemo } from 'react';
import { AlertCircle, Loader2, MessageSquare, RefreshCw, SearchX } from 'lucide-react';

function formatRelativeTime(iso) {
  if (!iso) return '';
  try {
    const diff = Date.now() - new Date(iso).getTime();
    if (diff < 60_000) return 'now';
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h`;
    return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

function displayName(user) {
  return [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.username || 'Unknown contact';
}

function AvatarInitials({ user }) {
  const initials = `${user?.first_name?.[0] ?? ''}${user?.last_name?.[0] ?? ''}`.toUpperCase() || '?';
  return (
    <div className="chat-inverse flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-500 text-sm font-semibold">
      {initials}
    </div>
  );
}

function OnlineDot({ online }) {
  return (
    <span
      aria-label={online ? 'Online' : 'Offline'}
      title={online ? 'Online' : 'Offline'}
      className={`block h-2.5 w-2.5 rounded-full border-2 border-white ${online ? 'bg-[#22c55e] shadow-[0_0_0_2px_rgba(34,197,94,0.12)]' : 'bg-slate-300'}`}
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
  searchQuery = '',
}) {
  const filteredConversations = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return conversations;
    return conversations.filter((conversation) => {
      const other = conversation.other_user;
      const name = displayName(other).toLowerCase();
      const username = other?.username?.toLowerCase() || '';
      const preview = conversation.latest_message_content?.toLowerCase() || '';
      return name.includes(query) || username.includes(query) || preview.includes(query);
    });
  }, [conversations, searchQuery]);

  if (loading) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 px-4 text-center">
        <Loader2 className="h-5 w-5 animate-spin text-brand-500" />
        <p className="text-sm text-slate-500">Loading conversations…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 px-5 text-center">
        <AlertCircle className="h-5 w-5 text-red-500" />
        <p className="text-sm text-slate-600">{error}</p>
        {onRetry ? (
          <button type="button" onClick={onRetry} className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-semibold text-brand-600 hover:bg-brand-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-200">
            <RefreshCw className="h-3.5 w-3.5" /> Retry
          </button>
        ) : null}
      </div>
    );
  }

  if (conversations.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
        <div className="flex h-11 w-11 items-center justify-center rounded-full bg-brand-50 text-brand-600">
          <MessageSquare className="h-5 w-5" />
        </div>
        <p className="text-sm font-semibold text-slate-800">No conversations yet</p>
        <p className="max-w-[220px] text-xs leading-5 text-slate-500">Connect with someone and send them a message to get started.</p>
      </div>
    );
  }

  if (filteredConversations.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
        <SearchX className="h-5 w-5 text-slate-400" />
        <p className="text-sm font-semibold text-slate-700">No matches found</p>
        <p className="text-xs text-slate-500">Try a different name or message preview.</p>
      </div>
    );
  }

  return (
    <div data-testid="conversation-list" className="chat-scroll flex h-full min-h-0 flex-col overflow-y-auto px-2 pb-3">
      {filteredConversations.map((conversation) => {
        const other = conversation.other_user;
        const name = displayName(other);
        const isOnline = other?.id ? onlineUsers.has(other.id) : false;
        const isActive = selected === conversation.conversation_id;
        const unread = unreadMap[conversation.conversation_id] ?? conversation.unread_count ?? 0;
        const preview = conversation.latest_message_content;
        const isMineLatest = conversation.latest_message_sender_id === currentUserId;

        return (
          <button
            key={conversation.conversation_id}
            type="button"
            data-testid="conversation-item"
            aria-current={isActive ? 'true' : undefined}
            onClick={() => onSelect(conversation)}
            className={`group flex min-h-[72px] w-full items-center gap-3 rounded-lg px-3 py-3 text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-200 ${
              isActive ? 'bg-brand-50' : 'hover:bg-slate-100'
            }`}
          >
            <div className="relative shrink-0">
              {other?.profile_photo_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={other.profile_photo_url}
                  alt={name}
                  className="h-10 w-10 rounded-full border border-slate-200 object-cover"
                  onError={(event) => { event.currentTarget.style.display = 'none'; }}
                />
              ) : <AvatarInitials user={other} />}
              <span className="absolute -bottom-0.5 -right-0.5 flex h-3 w-3 items-center justify-center">
                <OnlineDot online={isOnline} />
              </span>
            </div>

            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <span className={`truncate text-sm font-semibold ${isActive ? 'text-brand-700' : 'text-slate-800'}`}>{name}</span>
                <span className="shrink-0 text-[11px] text-slate-400">{formatRelativeTime(conversation.latest_message_at || conversation.updated_at)}</span>
              </div>
              <div className="mt-1 flex items-center justify-between gap-2">
                <p className={`truncate text-xs ${unread > 0 ? 'font-semibold text-slate-700' : 'text-slate-500'}`}>
                  {preview ? `${isMineLatest ? 'You: ' : ''}${preview}` : <span className="italic text-slate-400">No messages yet</span>}
                </p>
                {unread > 0 ? (
                  <span className="chat-inverse flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-brand-500 px-1.5 text-[10px] font-bold">
                    {unread > 99 ? '99+' : unread}
                  </span>
                ) : null}
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
