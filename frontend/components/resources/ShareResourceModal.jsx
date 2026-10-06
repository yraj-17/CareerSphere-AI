'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, Check, Loader2, Search, Send, Share2, X } from 'lucide-react';
import ProfileAvatar from '@/components/common/ProfileAvatar';
import {
  extractErrorMessage,
  getMyNetworkConnections,
  getOrCreateConversation,
  shareResourceInConversation,
} from '@/services/api';
import { categoryLabel, resourceTypeLabel } from '@/components/resources/resourceConstants';

function connectionName(connection) {
  const user = connection?.other_user;
  if (!user) return 'CareerSphere member';
  return `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.username || 'CareerSphere member';
}

export default function ShareResourceModal({ open, resource, onClose, onShared }) {
  const [connections, setConnections] = useState([]);
  const [query, setQuery] = useState('');
  const [selectedIds, setSelectedIds] = useState([]);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [sent, setSent] = useState(false);

  const loadConnections = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const payload = await getMyNetworkConnections();
      setConnections(Array.isArray(payload) ? payload : []);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to load your connections.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    setQuery('');
    setSelectedIds([]);
    setMessage('');
    setSent(false);
    loadConnections();
  }, [loadConnections, open]);

  const filteredConnections = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return connections;
    return connections.filter((connection) => {
      const user = connection.other_user || {};
      return [connectionName(connection), user.username, user.headline, user.location]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(term));
    });
  }, [connections, query]);

  if (!open || !resource) return null;

  const toggleRecipient = (userId) => {
    setSelectedIds((prev) =>
      prev.includes(userId) ? prev.filter((id) => id !== userId) : [...prev, userId]
    );
  };

  const handleSend = async () => {
    if (selectedIds.length === 0) {
      setError('Select at least one connection.');
      return;
    }
    setSending(true);
    setError('');
    try {
      for (const userId of selectedIds) {
        const conversation = await getOrCreateConversation(userId);
        await shareResourceInConversation(conversation.id, {
          resource_id: resource.id,
          message: message.trim(),
        });
      }
      setSent(true);
      onShared?.(selectedIds.length);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to share this resource.');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[75] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Share Resource">
      <button type="button" aria-label="Close share resource" onClick={onClose} className="absolute inset-0 cursor-default bg-slate-950/75 backdrop-blur-sm" />
      <div className="relative flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-[2rem] border border-white/10 bg-slate-950 shadow-[0_30px_80px_rgba(0,0,0,0.58)]">
        <div className="border-b border-white/10 p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="flex items-center gap-2 text-xl font-bold text-white">
                <Share2 className="h-5 w-5 text-accent" />
                Share Resource
              </h2>
              <p className="mt-1 text-sm text-slate-400">Send this resource to accepted connections through Messages.</p>
            </div>
            <button type="button" onClick={onClose} className="rounded-full p-2 text-slate-400 hover:bg-white/10 hover:text-white" aria-label="Close">
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="mt-5 rounded-2xl border border-white/10 bg-white/[0.04] p-4">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-accent">{resourceTypeLabel(resource.resource_type)}</p>
            <h3 className="mt-2 line-clamp-2 text-base font-bold text-white">{resource.title}</h3>
            <p className="mt-1 line-clamp-2 text-sm text-slate-400">{resource.description || 'No description provided.'}</p>
            <p className="mt-2 text-xs text-slate-500">{categoryLabel(resource.category)} · {resource.source_domain}</p>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-4 flex items-start gap-2 rounded-2xl border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-100" role="alert">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          {sent && (
            <div className="mb-4 flex items-center gap-2 rounded-2xl border border-emerald-500/25 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100" role="status">
              <Check className="h-4 w-4" />
              Resource shared successfully.
            </div>
          )}

          <label className="relative block">
            <span className="sr-only">Search connections</span>
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search connections..."
              className="w-full rounded-2xl border border-white/10 bg-white/[0.04] py-3 pl-11 pr-4 text-sm text-white outline-none placeholder:text-slate-500 focus:border-accent/45"
            />
          </label>

          <div className="mt-4 max-h-72 space-y-2 overflow-y-auto pr-1">
            {loading ? (
              <div className="flex items-center justify-center rounded-2xl border border-white/10 bg-white/[0.035] py-10">
                <Loader2 className="h-5 w-5 animate-spin text-accent" />
              </div>
            ) : filteredConnections.length === 0 ? (
              <div className="rounded-2xl border border-white/10 bg-white/[0.035] px-4 py-10 text-center text-sm text-slate-400">
                {query ? 'No matching accepted connections.' : 'No accepted connections available to share with yet.'}
              </div>
            ) : (
              filteredConnections.map((connection) => {
                const user = connection.other_user;
                const selected = selectedIds.includes(user.id);
                return (
                  <button
                    key={user.id}
                    type="button"
                    onClick={() => toggleRecipient(user.id)}
                    className={`flex w-full items-center gap-3 rounded-2xl border px-4 py-3 text-left transition-colors ${
                      selected
                        ? 'border-accent/40 bg-accent/10'
                        : 'border-white/10 bg-white/[0.035] hover:bg-white/[0.06]'
                    }`}
                  >
                    <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md border ${
                      selected ? 'border-accent bg-accent text-black' : 'border-white/20'
                    }`}>
                      {selected && <Check className="h-3.5 w-3.5" />}
                    </span>
                    <ProfileAvatar
                      src={user.profile_photo_url}
                      name={connectionName(connection)}
                      username={user.username}
                      alt={connectionName(connection)}
                      fallback={(connectionName(connection)?.[0] || 'U').toUpperCase()}
                      className="h-10 w-10"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold text-white">{connectionName(connection)}</span>
                      <span className="block truncate text-xs text-slate-500">{user.headline || `@${user.username}`}</span>
                    </span>
                  </button>
                );
              })
            )}
          </div>

          <label className="mt-5 grid gap-2 text-sm font-semibold text-slate-200">
            Optional message
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              rows={3}
              maxLength={4000}
              placeholder="Check this resource out..."
              className="resize-none rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-accent/45"
            />
          </label>
        </div>

        <div className="flex flex-col-reverse gap-3 border-t border-white/10 p-6 sm:flex-row sm:justify-end">
          <button type="button" onClick={onClose} className="rounded-full border border-white/10 px-5 py-2.5 text-sm font-semibold text-slate-200 hover:text-white">
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSend}
            disabled={selectedIds.length === 0 || sending}
            className="inline-flex items-center justify-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-black hover:bg-accentSoft disabled:opacity-60"
          >
            {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
