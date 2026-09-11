'use client';

import React from 'react';
import { Loader2, MessageSquarePlus, Trash2, X } from 'lucide-react';

function startOfDay(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function groupConversations(conversations) {
  const today = startOfDay(new Date());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const groups = [
    { label: 'Today', items: [] },
    { label: 'Yesterday', items: [] },
    { label: 'Older', items: [] },
  ];

  conversations.forEach((conversation) => {
    const stamp = conversation.updated_at ? new Date(conversation.updated_at) : new Date(0);
    if (stamp >= today) groups[0].items.push(conversation);
    else if (stamp >= yesterday) groups[1].items.push(conversation);
    else groups[2].items.push(conversation);
  });

  return groups.filter((group) => group.items.length > 0);
}

function formatStamp(value) {
  if (!value) return '';
  const date = new Date(value);
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

export default function ConversationSidebar({
  conversations,
  activeConversationId,
  isLoading,
  onNewChat,
  onSelect,
  onDelete,
  onClose,
}) {
  const groups = groupConversations(conversations || []);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-start justify-between gap-3 px-4 pt-4 pb-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.22em] text-slate-500">History</p>
          <h2 className="mt-1 text-base font-semibold text-white">Conversations</h2>
        </div>
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-white/5 hover:text-white lg:hidden"
            aria-label="Close conversation list"
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </div>

      <div className="px-4 pb-3">
        <button
          type="button"
          onClick={onNewChat}
          className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-accent px-3 py-2.5 text-xs font-semibold text-black shadow-[0_8px_24px_rgba(255,143,50,0.28)] hover:bg-accentSoft transition-all"
        >
          <MessageSquarePlus className="h-4 w-4" />
          New Chat
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">
        {isLoading ? (
          <div className="flex items-center gap-2 px-3 py-6 text-sm text-slate-400">
            <Loader2 className="h-4 w-4 animate-spin text-accent" />
            Loading conversations...
          </div>
        ) : groups.length === 0 ? (
          <div className="mx-2 rounded-2xl border border-dashed border-white/10 px-4 py-8 text-center bg-white/[0.02]">
            <p className="text-sm font-medium text-slate-300">No conversations yet</p>
            <p className="mt-1 text-xs text-slate-500">Start a new chat to save your first career discussion.</p>
          </div>
        ) : (
          groups.map((group) => (
            <div key={group.label} className="mb-4">
              <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                {group.label}
              </p>
              <div className="space-y-1">
                {group.items.map((conversation) => {
                  const isActive = conversation.id === activeConversationId;
                  return (
                    <div
                      key={conversation.id}
                      className={`group flex items-start gap-1 rounded-xl border px-2 py-2 transition-colors ${
                        isActive
                          ? 'border-accent/40 bg-accent/15 text-white shadow-[0_0_20px_rgba(255,143,50,0.15)]'
                          : 'border-transparent hover:border-white/10 hover:bg-white/5 text-slate-300'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => onSelect(conversation.id)}
                        className="min-w-0 flex-1 rounded-lg px-1 py-0.5 text-left"
                      >
                        <p className="truncate text-sm font-medium text-white">{conversation.title}</p>
                        <p className="mt-0.5 text-[11px] text-slate-500">{formatStamp(conversation.updated_at)}</p>
                      </button>
                      <button
                        type="button"
                        onClick={() => onDelete(conversation.id)}
                        className="rounded-lg p-1.5 text-slate-500 opacity-80 hover:bg-rose-500/15 hover:text-rose-300 sm:opacity-0 sm:group-hover:opacity-100"
                        aria-label={`Delete ${conversation.title}`}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
