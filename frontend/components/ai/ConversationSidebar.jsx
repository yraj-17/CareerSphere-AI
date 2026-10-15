'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import {
  Check,
  Clock3,
  Loader2,
  Menu,
  MessageSquarePlus,
  MoreHorizontal,
  Pencil,
  Pin,
  Plus,
  Star,
  Trash2,
  X,
} from 'lucide-react';

function formatStamp(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  return sameDay
    ? date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
    : date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function Section({ label, icon: Icon, items, activeConversationId, openMenuId, editingId, editingValue, onSelect, onMenuToggle, onRenameStart, onRenameChange, onRenameSubmit, onRenameCancel, onTogglePinned, onToggleFavorite, onDelete }) {
  if (!items.length) return null;

  return (
    <section className="mb-5" aria-labelledby={`conversation-section-${label.toLowerCase()}`}>
      <div className="mb-1 flex items-center gap-2 px-3">
        <Icon className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
        <h2 id={`conversation-section-${label.toLowerCase()}`} className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
          {label}
        </h2>
      </div>
      <div className="space-y-0.5">
        {items.map((conversation) => {
          const isActive = conversation.id === activeConversationId;
          const isEditing = editingId === conversation.id;
          const isMenuOpen = openMenuId === conversation.id;

          return (
            <div
              key={`${label}-${conversation.id}`}
              className={`group relative flex min-h-10 items-center gap-1 rounded-lg px-2 transition-colors ${
                isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-700 hover:bg-slate-100'
              }`}
            >
              {isEditing ? (
                <form onSubmit={(event) => onRenameSubmit(event, conversation.id)} className="flex min-w-0 flex-1 items-center gap-1">
                  <input
                    autoFocus
                    value={editingValue}
                    onChange={(event) => onRenameChange(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Escape') onRenameCancel();
                    }}
                    aria-label={`Rename ${conversation.title}`}
                    className="min-w-0 flex-1 rounded-md border border-brand-300 bg-white px-2 py-1.5 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-brand-200"
                  />
                  <button type="submit" className="rounded-md p-1.5 text-brand-600 hover:bg-brand-100" aria-label="Save conversation name">
                    <Check className="h-4 w-4" />
                  </button>
                  <button type="button" onClick={onRenameCancel} className="rounded-md p-1.5 text-slate-400 hover:bg-slate-200" aria-label="Cancel rename">
                    <X className="h-4 w-4" />
                  </button>
                </form>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => onSelect(conversation.id)}
                    title={conversation.title}
                    className="min-w-0 flex-1 truncate rounded-md px-1.5 py-2 text-left text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-200"
                  >
                    <span className="block truncate">{conversation.title || 'New conversation'}</span>
                    <span className={`mt-0.5 block text-[10px] ${isActive ? 'text-brand-500' : 'text-slate-400'}`}>
                      {formatStamp(conversation.updated_at)}
                    </span>
                  </button>
                  <div className="flex shrink-0 items-start gap-0.5 self-start pt-2" data-conversation-menu>
                    {conversation.is_favorite ? <Star className="h-3 w-3 fill-[#E89B00] text-[#E89B00]" aria-label="Favorite" /> : null}
                    {conversation.is_pinned ? <Pin className="h-3 w-3 text-brand-600" aria-label="Pinned" /> : null}
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        onMenuToggle(conversation.id);
                      }}
                      aria-label={`Actions for ${conversation.title}`}
                      aria-haspopup="menu"
                      aria-expanded={isMenuOpen}
                      className="rounded-md p-1.5 text-slate-400 opacity-100 hover:bg-slate-200 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-200 sm:opacity-0 sm:group-hover:opacity-100 sm:focus-visible:opacity-100"
                    >
                      <MoreHorizontal className="h-4 w-4" />
                    </button>
                    {isMenuOpen ? (
                      <div role="menu" className="absolute right-2 top-9 z-30 w-48 overflow-hidden rounded-lg border border-slate-200 bg-white p-1 shadow-[0_16px_36px_rgba(11,42,91,0.16)]">
                        <button type="button" role="menuitem" onClick={() => onTogglePinned(conversation)} className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-xs text-slate-700 hover:bg-slate-100">
                          <Pin className="h-3.5 w-3.5 text-slate-500" /> {conversation.is_pinned ? 'Unpin conversation' : 'Pin conversation'}
                        </button>
                        <button type="button" role="menuitem" onClick={() => onToggleFavorite(conversation)} className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-xs text-slate-700 hover:bg-slate-100">
                          <Star className="h-3.5 w-3.5 text-[#E89B00]" /> {conversation.is_favorite ? 'Remove favorite' : 'Add to favorites'}
                        </button>
                        <button type="button" role="menuitem" onClick={() => onRenameStart(conversation)} className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-xs text-slate-700 hover:bg-slate-100">
                          <Pencil className="h-3.5 w-3.5 text-slate-500" /> Rename
                        </button>
                        <div className="my-1 h-px bg-slate-100" />
                        <button type="button" role="menuitem" onClick={() => onDelete(conversation)} className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-xs text-red-600 hover:bg-red-50">
                          <Trash2 className="h-3.5 w-3.5" /> Delete
                        </button>
                      </div>
                    ) : null}
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default function ConversationSidebar({
  conversations = [],
  activeConversationId,
  isLoading,
  onNewChat,
  onSelect,
  onRename,
  onDelete,
  onUpdate,
  onClose,
  onCollapse,
}) {
  const rootRef = useRef(null);
  const [openMenuId, setOpenMenuId] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editingValue, setEditingValue] = useState('');

  useEffect(() => {
    const closeMenu = (event) => {
      if (!event.target.closest('[data-conversation-menu]')) {
        setOpenMenuId(null);
      }
    };
    document.addEventListener('mousedown', closeMenu);
    return () => document.removeEventListener('mousedown', closeMenu);
  }, []);

  const sections = useMemo(() => {
    const sorted = [...conversations].sort((a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0));
    return [
      { label: 'Pinned', icon: Pin, items: sorted.filter((item) => item.is_pinned) },
      { label: 'Favorites', icon: Star, items: sorted.filter((item) => item.is_favorite) },
      { label: 'Recent', icon: Clock3, items: sorted.filter((item) => !item.is_pinned && !item.is_favorite) },
    ];
  }, [conversations]);

  const beginRename = (conversation) => {
    setOpenMenuId(null);
    setEditingId(conversation.id);
    setEditingValue(conversation.title || '');
  };

  const submitRename = async (event, conversationId) => {
    event.preventDefault();
    const cleaned = editingValue.trim();
    if (!cleaned) return;
    try {
      await onRename(conversationId, cleaned);
      setEditingId(null);
      setEditingValue('');
    } catch {
      // Keep the inline editor open so the user can retry after the error.
    }
  };

  const toggle = async (conversation, field) => {
    setOpenMenuId(null);
    try {
      await onUpdate(conversation.id, { [field]: !conversation[field] });
    } catch {
      // The parent surfaces the request error; the menu should simply close.
    }
  };

  return (
    <div ref={rootRef} className="flex h-full min-h-0 flex-col bg-slate-50">
      <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <Link href="/dashboard" className="flex min-w-0 items-center gap-2 rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-200" aria-label="Back to CareerSphere dashboard">
          <span className="chat-inverse flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-brand-500 text-[10px] font-bold">CS</span>
          <span className="truncate text-sm font-semibold text-slate-900">CareerSphere AI</span>
        </Link>
        <div className="flex items-center gap-1">
          {onCollapse ? (
            <button type="button" onClick={onCollapse} className="hidden rounded-md p-1.5 text-slate-500 hover:bg-slate-200 hover:text-slate-900 lg:inline-flex" aria-label="Collapse conversation sidebar" title="Collapse sidebar">
              <Menu className="h-5 w-5" />
            </button>
          ) : null}
          {onClose ? (
            <button type="button" onClick={onClose} className="rounded-md p-1.5 text-slate-500 hover:bg-slate-200 hover:text-slate-900 lg:hidden" aria-label="Close conversation list">
              <X className="h-4 w-4" />
            </button>
          ) : null}
        </div>
      </div>

      <div className="px-3 py-3">
        <button type="button" onClick={onNewChat} className="chat-inverse inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-brand-500 px-3 text-sm font-semibold transition-colors hover:bg-brand-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-200">
          <Plus className="h-4 w-4" /> New chat
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">
        {isLoading ? (
          <div className="flex items-center gap-2 px-3 py-6 text-sm text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin text-brand-500" /> Loading conversations...
          </div>
        ) : conversations.length === 0 ? (
          <div className="mx-2 rounded-lg border border-dashed border-slate-300 bg-white px-4 py-8 text-center">
            <MessageSquarePlus className="mx-auto h-5 w-5 text-slate-400" />
            <p className="mt-3 text-sm font-medium text-slate-700">No conversations yet</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">Start a new chat to save your first career discussion.</p>
          </div>
        ) : (
          sections.map((section) => (
            <Section
              key={section.label}
              {...section}
              activeConversationId={activeConversationId}
              openMenuId={openMenuId}
              editingId={editingId}
              editingValue={editingValue}
              onSelect={onSelect}
              onMenuToggle={(id) => setOpenMenuId((current) => (current === id ? null : id))}
              onRenameStart={beginRename}
              onRenameChange={setEditingValue}
              onRenameSubmit={submitRename}
              onRenameCancel={() => {
                setEditingId(null);
                setEditingValue('');
              }}
              onTogglePinned={(conversation) => toggle(conversation, 'is_pinned')}
              onToggleFavorite={(conversation) => toggle(conversation, 'is_favorite')}
              onDelete={(conversation) => {
                setOpenMenuId(null);
                onDelete(conversation);
              }}
            />
          ))
        )}
      </div>
    </div>
  );
}
