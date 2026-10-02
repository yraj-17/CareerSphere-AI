'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, Globe2, Plus, RefreshCw, Search, X } from 'lucide-react';
import {
  createCommunity,
  extractErrorMessage,
  joinCommunity,
  leaveCommunity,
  listCommunities,
} from '@/services/api';
import CommunityCard, { CommunityCardSkeleton } from '@/components/communities/CommunityCard';
import CreateCommunityModal from '@/components/communities/CreateCommunityModal';
import { COMMUNITY_CATEGORIES, normalizeCommunityList } from '@/components/communities/communityConstants';

const SKELETON_COUNT = 6;

function isEndpointMissing(error) {
  return [404, 405, 501].includes(error?.response?.status);
}

function EmptyState({ activeView, query, category }) {
  const isJoined = activeView === 'joined';
  return (
    <div data-testid="communities-empty" className="flex flex-col items-center justify-center rounded-3xl border border-white/10 bg-white/[0.035] px-6 py-20 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.05]">
        <Globe2 className="h-8 w-8 text-slate-500" aria-hidden="true" />
      </div>
      <h2 className="text-lg font-bold text-white">
        {isJoined ? "You haven't joined any communities yet." : 'No communities found.'}
      </h2>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-slate-400">
        {isJoined
          ? 'Discover communities that match your interests.'
          : query || category !== 'all'
          ? 'Try a different search or category.'
          : 'Communities will appear here once the backend is connected.'}
      </p>
    </div>
  );
}

function ErrorState({ message, onRetry }) {
  return (
    <div data-testid="communities-error" className="flex flex-col items-center justify-center rounded-3xl border border-rose-500/20 bg-rose-500/10 px-6 py-16 text-center">
      <AlertCircle className="mb-4 h-10 w-10 text-rose-300" aria-hidden="true" />
      <h2 className="text-lg font-bold text-white">Communities failed to load</h2>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-rose-100/85">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-5 inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-black shadow-[0_8px_30px_rgba(255,143,50,0.28)] transition-colors hover:bg-accentSoft"
      >
        <RefreshCw className="h-4 w-4" aria-hidden="true" />
        Try Again
      </button>
    </div>
  );
}

function LeaveConfirm({ community, onCancel, onConfirm, busy }) {
  return (
    <div className="fixed inset-0 z-[65] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Leave community">
      <button className="absolute inset-0 cursor-default bg-slate-950/70 backdrop-blur-sm" type="button" aria-label="Cancel leave" onClick={onCancel} />
      <div className="relative w-full max-w-sm rounded-3xl border border-white/10 bg-slate-950 p-6 shadow-[0_24px_70px_rgba(0,0,0,0.58)]">
        <h2 className="text-base font-bold text-white">Leave this community?</h2>
        <p className="mt-2 text-sm leading-relaxed text-slate-400">
          You can join {community?.name || 'this community'} again later if it remains public.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={onCancel} className="rounded-full border border-white/10 px-4 py-2 text-sm font-medium text-slate-200 hover:text-white">
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="rounded-full bg-rose-500 px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-rose-600 disabled:opacity-60"
          >
            Leave
          </button>
        </div>
      </div>
    </div>
  );
}

export default function CommunitiesPage() {
  const [activeView, setActiveView] = useState('discover');
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('all');
  const [communities, setCommunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [backendReady, setBackendReady] = useState(true);
  const [busyIds, setBusyIds] = useState({});
  const [createOpen, setCreateOpen] = useState(false);
  const [leaveTarget, setLeaveTarget] = useState(null);

  const fetchCommunities = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const payload = await listCommunities({
        q: query,
        category,
        membership: activeView === 'joined' ? 'joined' : 'discover',
      });
      setCommunities(normalizeCommunityList(payload));
      setBackendReady(true);
    } catch (err) {
      if (isEndpointMissing(err)) {
        setCommunities([]);
        setBackendReady(false);
        setError('');
      } else {
        setError(extractErrorMessage(err) || 'Unable to load communities.');
      }
    } finally {
      setLoading(false);
    }
  }, [activeView, category, query]);

  useEffect(() => {
    fetchCommunities();
  }, [fetchCommunities]);

  const visibleCommunities = useMemo(() => {
    const term = query.trim().toLowerCase();
    return communities.filter((community) => {
      const matchesCategory = category === 'all' || community.category === category;
      const matchesView = activeView === 'discover' || community.joined || community.is_joined || community.membership_status === 'joined';
      const matchesQuery =
        !term ||
        [community.name, community.description, ...(Array.isArray(community.tags) ? community.tags : [])]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(term));
      return matchesCategory && matchesView && matchesQuery;
    });
  }, [activeView, category, communities, query]);

  const setBusy = (id, value) => {
    setBusyIds((prev) => {
      const next = { ...prev };
      if (value) next[id] = true;
      else delete next[id];
      return next;
    });
  };

  const handleJoin = async (community) => {
    const id = community.id ?? community.community_id;
    setBusy(id, true);
    try {
      await joinCommunity(id);
      setCommunities((prev) => prev.map((item) => ((item.id ?? item.community_id) === id ? { ...item, joined: true } : item)));
    } catch (err) {
      setError(isEndpointMissing(err) ? 'Community join is waiting for backend integration.' : extractErrorMessage(err));
    } finally {
      setBusy(id, false);
    }
  };

  const handleLeave = async () => {
    const id = leaveTarget?.id ?? leaveTarget?.community_id;
    if (!id) return;
    setBusy(id, true);
    try {
      await leaveCommunity(id);
      setCommunities((prev) => prev.map((item) => ((item.id ?? item.community_id) === id ? { ...item, joined: false } : item)));
      setLeaveTarget(null);
    } catch (err) {
      setError(isEndpointMissing(err) ? 'Community leave is waiting for backend integration.' : extractErrorMessage(err));
    } finally {
      setBusy(id, false);
    }
  };

  const handleCreate = async (payload) => {
    try {
      await createCommunity(payload);
      await fetchCommunities();
    } catch (err) {
      throw new Error(isEndpointMissing(err) ? 'Community creation is waiting for backend integration.' : extractErrorMessage(err));
    }
  };

  return (
    <div className="space-y-8 animate-fade-in">
      <CreateCommunityModal open={createOpen} onClose={() => setCreateOpen(false)} onSubmit={handleCreate} />
      {leaveTarget && (
        <LeaveConfirm
          community={leaveTarget}
          busy={!!busyIds[leaveTarget.id ?? leaveTarget.community_id]}
          onCancel={() => setLeaveTarget(null)}
          onConfirm={handleLeave}
        />
      )}

      <section className="relative overflow-hidden rounded-[2.5rem] border border-white/10 bg-white/[0.04] p-7 shadow-glow backdrop-blur-2xl sm:p-10">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_30%_0%,rgba(255,143,50,0.14),transparent_50%),radial-gradient(circle_at_85%_30%,rgba(64,217,255,0.09),transparent_40%)]" />
        <div className="relative z-10 flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="mb-3 flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-accent/30 bg-accent/15">
                <Globe2 className="h-4 w-4 text-accent" aria-hidden="true" />
              </div>
              <h1 className="text-2xl font-extrabold tracking-tight text-white sm:text-3xl">Communities</h1>
            </div>
            <p className="max-w-2xl text-sm leading-relaxed text-slate-400">
              Discover communities, connect with people, and share knowledge around your interests.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-black shadow-[0_8px_30px_rgba(255,143,50,0.28)] transition-colors hover:bg-accentSoft focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Create Community
          </button>
        </div>
      </section>

      {!backendReady && (
        <div className="rounded-2xl border border-accent/25 bg-accent/10 px-4 py-3 text-sm text-accent" role="status">
          Communities backend is not connected yet. The UI is ready for real community data.
        </div>
      )}

      {error && (
        <div className="flex items-start gap-3 rounded-2xl border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-200" role="alert">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span className="flex-1">{error}</span>
          <button type="button" onClick={() => setError('')} aria-label="Dismiss error" className="text-rose-200/75 hover:text-white">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="space-y-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex w-full rounded-2xl border border-white/10 bg-white/[0.04] p-1 lg:w-auto" role="tablist" aria-label="Communities view">
            {[
              { id: 'discover', label: 'Discover' },
              { id: 'joined', label: 'My Communities' },
            ].map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={activeView === item.id}
                onClick={() => setActiveView(item.id)}
                className={`flex-1 rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors lg:flex-none ${
                  activeView === item.id ? 'bg-accent text-black' : 'text-slate-300 hover:bg-white/[0.06] hover:text-white'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          <label className="relative block w-full lg:max-w-md">
            <span className="sr-only">Search communities</span>
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search communities..."
              className="w-full rounded-2xl border border-white/10 bg-white/[0.04] py-3 pl-11 pr-11 text-sm text-white outline-none transition-all placeholder:text-slate-500 focus:border-accent/45 focus:ring-1 focus:ring-accent/25"
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery('')}
                aria-label="Clear community search"
                className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg p-1 text-slate-400 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </label>
        </div>

        <div className="flex gap-2 overflow-x-auto pb-1" aria-label="Community categories">
          {COMMUNITY_CATEGORIES.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setCategory(item.id)}
              className={`shrink-0 rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
                category === item.id
                  ? 'border-accent/35 bg-accent/15 text-accent'
                  : 'border-white/10 bg-white/[0.04] text-slate-300 hover:bg-white/[0.07] hover:text-white'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <section className="space-y-4" aria-label="Discover Communities">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-xl font-bold text-white">{activeView === 'joined' ? 'My Communities' : 'Discover Communities'}</h2>
          {!loading && visibleCommunities.length > 0 && (
            <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-400">
              {visibleCommunities.length.toLocaleString()} shown
            </span>
          )}
        </div>

        {loading ? (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: SKELETON_COUNT }).map((_, index) => (
              <CommunityCardSkeleton key={index} />
            ))}
          </div>
        ) : error && communities.length === 0 ? (
          <ErrorState message={error} onRetry={fetchCommunities} />
        ) : visibleCommunities.length === 0 ? (
          <EmptyState activeView={activeView} query={query} category={category} />
        ) : (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3" data-testid="communities-grid">
            {visibleCommunities.map((community) => {
              const id = community.id ?? community.community_id;
              return (
                <CommunityCard
                  key={id}
                  community={community}
                  busy={!!busyIds[id]}
                  disabled={!backendReady}
                  onJoin={handleJoin}
                  onLeave={setLeaveTarget}
                />
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
