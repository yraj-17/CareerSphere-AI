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
      <button type="button" aria-label="Close share resource" onClick={onClose} className="absolute inset-0 cursor-default bg-black/30 backdrop-blur-sm" />
      <div className="relative flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_24px_60px_rgba(16,47,107,0.18)]">
        <div className="border-b border-slate-200 p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="flex items-center gap-2 text-xl font-semibold text-slate-900">
                <Share2 className="h-5 w-5 text-brand-500" />
                Share Resource
              </h2>
              <p className="mt-1 text-sm text-slate-500">Send this resource to accepted connections through Messages.</p>
            </div>
            <button type="button" onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="Close">
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-500">{resourceTypeLabel(resource.resource_type)}</p>
            <h3 className="mt-2 line-clamp-2 text-base font-semibold text-slate-900">{resource.title}</h3>
            <p className="mt-1 line-clamp-2 text-sm text-slate-600">{resource.description || 'No description provided.'}</p>
            <p className="mt-2 text-xs text-slate-500">{categoryLabel(resource.category)} · {resource.source_domain}</p>
          </div>
        </div>

        <div className="scrollbar-hidden min-h-0 flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-4 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <span>{error}</span>
            </div>
          )}
          {sent && (
            <div className="mb-4 flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700" role="status">
              <Check className="h-4 w-4" aria-hidden="true" />
              Resource shared successfully.
            </div>
          )}

          <label className="relative block">
            <span className="sr-only">Search connections</span>
            <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search connections..."
              className="input-base py-2.5 pl-10"
            />
          </label>

          <div className="mt-4 max-h-72 space-y-2 overflow-y-auto pr-1">
            {loading ? (
              <div className="flex items-center justify-center rounded-xl border border-slate-200 bg-slate-50 py-10">
                <Loader2 className="h-5 w-5 animate-spin text-brand-500" />
              </div>
            ) : filteredConnections.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
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
                        ? 'border-brand-200 bg-brand-50'
                        : 'border-slate-200 bg-white hover:bg-slate-50'
                    }`}
                  >
                    <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md border ${
                      selected ? 'border-brand-500 bg-brand-500 text-white' : 'border-slate-300'
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
                      <span className="block truncate text-sm font-semibold text-slate-900">{connectionName(connection)}</span>
                      <span className="block truncate text-xs text-slate-500">{user.headline || `@${user.username}`}</span>
                    </span>
                  </button>
                );
              })
            )}
          </div>

          <label className="mt-5 grid gap-2 text-sm font-semibold text-slate-700">
            Optional message
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              rows={3}
              maxLength={4000}
              placeholder="Check this resource out..."
              className="input-base resize-none"
            />
          </label>
        </div>

        <div className="flex flex-col-reverse gap-3 border-t border-slate-200 p-6 sm:flex-row sm:justify-end">
          <button type="button" onClick={onClose} className="btn-outline">
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSend}
            disabled={selectedIds.length === 0 || sending}
            className="btn-primary"
          >
            {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
