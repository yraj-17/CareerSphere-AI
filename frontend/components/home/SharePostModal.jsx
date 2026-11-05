'use client';

import { useEffect, useMemo, useState } from 'react';
import { Check, Link2, Loader2, Search, Send, Share2, X } from 'lucide-react';
import ProfileAvatar from '@/components/common/ProfileAvatar';
import {
  extractErrorMessage,
  getMyNetworkConnections,
  getOrCreateConversation,
  sendMessage,
} from '@/services/api';

function displayName(user = {}) {
  return [user.first_name, user.last_name].filter(Boolean).join(' ') || user.username || 'CareerSphere member';
}

function postLink(postId) {
  if (typeof window === 'undefined') return `/dashboard/home#post-${postId}`;
  return `${window.location.origin}/dashboard/home#post-${postId}`;
}

async function copyText(value) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const copyTarget = document.createElement('textarea');
  copyTarget.value = value;
  copyTarget.setAttribute('readonly', '');
  copyTarget.style.position = 'fixed';
  copyTarget.style.opacity = '0';
  document.body.appendChild(copyTarget);
  copyTarget.select();
  document.execCommand('copy');
  copyTarget.remove();
}

function ConnectionRow({ connection, selected, busy, onToggle }) {
  const user = connection?.other_user || {};
  const name = displayName(user);

  return (
    <button
      type="button"
      onClick={() => onToggle(connection)}
      disabled={busy}
      aria-pressed={selected}
      className={`flex w-full items-center gap-3 border-b border-slate-100 px-3 py-3 text-left transition last:border-b-0 hover:bg-slate-50 disabled:cursor-wait disabled:opacity-60 ${selected ? 'bg-brand-50/60' : ''}`}
    >
      <ProfileAvatar
        src={user.profile_photo_url}
        name={name}
        username={user.username}
        className="h-10 w-10 shrink-0"
      />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold text-slate-900">{name}</span>
        <span className="block truncate text-xs text-slate-500">{user.headline || `@${user.username}`}</span>
      </span>
      <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border ${selected ? 'border-brand-600 bg-brand-600 !text-white' : 'border-slate-400 bg-white text-transparent'}`} aria-hidden="true">
        <Check className="h-3.5 w-3.5" />
      </span>
    </button>
  );
}

export default function SharePostModal({ isOpen, post, onClose, onShared }) {
  const [connections, setConnections] = useState([]);
  const [query, setQuery] = useState('');
  const [selectedConnections, setSelectedConnections] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [error, setError] = useState('');
  const [copyStatus, setCopyStatus] = useState('');

  useEffect(() => {
    if (!isOpen) return undefined;
    let active = true;
    setLoading(true);
    setError('');
    setCopyStatus('');
    setSelectedConnections([]);
    getMyNetworkConnections()
      .then((result) => {
        if (active) setConnections(Array.isArray(result) ? result : []);
      })
      .catch((loadError) => {
        if (active) setError(extractErrorMessage(loadError) || 'Connections could not be loaded.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [isOpen]);

  const filteredConnections = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return connections;
    return connections.filter((connection) => {
      const user = connection?.other_user || {};
      return [displayName(user), user.username, user.headline, user.location]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(term));
    });
  }, [connections, query]);

  const handleClose = () => {
    setQuery('');
    setSelectedConnections([]);
    setError('');
    setCopyStatus('');
    onClose?.();
  };

  const toggleConnection = (connection) => {
    if (sharing || !connection?.other_user?.id) return;
    setSelectedConnections((current) => current.some((item) => item.other_user?.id === connection.other_user.id)
      ? current.filter((item) => item.other_user?.id !== connection.other_user.id)
      : [...current, connection]);
  };

  const shareSelected = async () => {
    if (!selectedConnections.length || sharing) return;
    setSharing(true);
    setError('');
    try {
      const url = postLink(post.id);
      const message = `Shared a post with you on CareerSphere AI:\n${url}`;
      await Promise.all(selectedConnections.map(async (connection) => {
        const conversation = await getOrCreateConversation(connection.other_user.id);
        const conversationId = conversation?.id || conversation?.conversation_id;
        if (!conversationId) throw new Error('Conversation could not be created.');
        await sendMessage(conversationId, message);
      }));
      onShared?.(selectedConnections.map((connection) => connection.other_user));
      handleClose();
    } catch (shareError) {
      setError(extractErrorMessage(shareError) || 'This post could not be shared.');
    } finally {
      setSharing(false);
    }
  };

  const copyPostLink = async () => {
    try {
      await copyText(postLink(post.id));
      setCopyStatus('Link copied');
      window.setTimeout(() => setCopyStatus(''), 1800);
    } catch {
      setError('The post link could not be copied.');
    }
  };

  if (!isOpen || !post) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="share-post-title">
      <button type="button" onClick={handleClose} className="absolute inset-0 bg-[rgba(16,27,45,0.46)] backdrop-blur-[1px]" aria-label="Close share post dialog" />
      <div className="relative flex max-h-[min(720px,calc(100vh-2rem))] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_24px_64px_rgba(16,27,45,0.2)]">
        <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-50 text-brand-700"><Share2 className="h-4 w-4" /></div>
          <div className="min-w-0 flex-1">
            <h2 id="share-post-title" className="text-base font-bold text-slate-900">Send {displayName(post.author)}&apos;s Post</h2>
            <p className="text-xs text-slate-500">Choose one or more people from your network.</p>
          </div>
          <button type="button" onClick={handleClose} disabled={sharing} className="rounded-lg p-2 text-slate-400 hover:bg-slate-50 hover:text-slate-700 disabled:opacity-50" aria-label="Close share post dialog"><X className="h-4 w-4" /></button>
        </div>

        <div className="px-5 py-4">
          <div className="relative">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-700" />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search" className="w-full rounded-lg border-0 bg-slate-100 py-3 pl-11 pr-3 text-sm text-slate-800 outline-none placeholder:text-slate-500 focus:ring-2 focus:ring-brand-200" disabled={sharing} />
          </div>
        </div>

        {error && <p className="px-5 pb-2 text-xs font-medium text-rose-600" role="alert">{error}</p>}

        <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-8 text-xs text-slate-500"><Loader2 className="h-4 w-4 animate-spin" /> Loading connections…</div>
          ) : filteredConnections.length ? (
            filteredConnections.map((connection) => <ConnectionRow key={connection.id || connection.other_user?.id} connection={connection} selected={selectedConnections.some((item) => item.other_user?.id === connection.other_user?.id)} busy={sharing} onToggle={toggleConnection} />)
          ) : (
            <p className="px-3 py-8 text-center text-xs text-slate-500">{connections.length ? 'No matching connections.' : 'Connect with someone first to share this post directly.'}</p>
          )}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-slate-100 px-5 py-3">
          <button type="button" onClick={copyPostLink} disabled={sharing} className="inline-flex items-center gap-2 text-sm font-semibold text-brand-700 hover:text-brand-900 disabled:opacity-50"><Link2 className="h-4 w-4" />{copyStatus || 'Copy link to post'}</button>
          <div className="flex items-center gap-2">
            <button type="button" onClick={handleClose} disabled={sharing} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50">Cancel</button>
            <button type="button" onClick={shareSelected} disabled={!selectedConnections.length || sharing} className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-xs font-semibold !text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50">{sharing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Send</button>
          </div>
        </div>
      </div>
    </div>
  );
}
