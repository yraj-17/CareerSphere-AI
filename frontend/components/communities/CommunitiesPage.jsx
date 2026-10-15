'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, ChevronDown, Plus, RefreshCw, Search, UsersRound, X } from 'lucide-react';
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

function EmptyState({ activeView, query, category, onClear }) {
  const isJoined = activeView === 'joined';
  return (
    <div data-testid="communities-empty" className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center shadow-sm">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl border border-brand-100 bg-brand-50">
        <UsersRound className="h-7 w-7 text-brand-500" aria-hidden="true" />
      </div>
      <h2 className="text-lg font-semibold text-slate-900">
        {isJoined ? "You haven't joined any communities yet." : 'No communities found.'}
      </h2>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-slate-500">
        {isJoined
          ? 'Discover communities that match your interests.'
          : query || category !== 'all'
          ? 'Try a different search or category.'
          : 'Communities will appear here once the backend is connected.'}
      </p>
      {onClear && (query || category !== 'all' || isJoined) && (
        <button type="button" onClick={onClear} className="btn-outline mt-5">
          {isJoined ? 'Discover communities' : 'Clear filters'}
        </button>
      )}
    </div>
  );
}

function ErrorState({ message, onRetry }) {
  return (
    <div data-testid="communities-error" className="flex flex-col items-center justify-center rounded-xl border border-red-200 bg-red-50 px-6 py-16 text-center">
      <AlertCircle className="mb-4 h-10 w-10 text-red-600" aria-hidden="true" />
      <h2 className="text-lg font-semibold text-slate-900">Communities failed to load</h2>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-red-700">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="btn-primary mt-5"
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
      <button className="absolute inset-0 cursor-default bg-black/30 backdrop-blur-sm" type="button" aria-label="Cancel leave" onClick={onCancel} />
      <div className="relative w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-6 shadow-[var(--shadow-popover)]">
        <h2 className="text-base font-semibold text-slate-900">Leave this community?</h2>
        <p className="mt-2 text-sm leading-relaxed text-slate-500">
          You can join {community?.name || 'this community'} again later if it remains public.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={onCancel} className="btn-outline">
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="btn-danger"
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
  const [categoryOpen, setCategoryOpen] = useState(false);
  const categoryMenuRef = useRef(null);
  const [communities, setCommunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [backendReady, setBackendReady] = useState(true);
  const [totalCount, setTotalCount] = useState(null);
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
      setTotalCount(Number.isFinite(Number(payload?.total)) ? Number(payload.total) : null);
      setBackendReady(true);
    } catch (err) {
      if (isEndpointMissing(err)) {
        setCommunities([]);
        setTotalCount(0);
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

  useEffect(() => {
    const handleOutsideClick = (event) => {
      if (categoryMenuRef.current && !categoryMenuRef.current.contains(event.target)) {
        setCategoryOpen(false);
      }
    };

    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  useEffect(() => {
    document.documentElement.classList.add('scrollbar-hidden');
    return () => document.documentElement.classList.remove('scrollbar-hidden');
  }, []);

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

  const clearFilters = () => {
    setQuery('');
    setCategory('all');
    setActiveView('discover');
  };

  const displayedCount = totalCount ?? visibleCommunities.length;
  const selectedCategory = COMMUNITY_CATEGORIES.find((item) => item.id === category) || COMMUNITY_CATEGORIES[0];

  return (
    <div className="space-y-6 animate-fade-in">
      <CreateCommunityModal open={createOpen} onClose={() => setCreateOpen(false)} onSubmit={handleCreate} />
      {leaveTarget && (
        <LeaveConfirm
          community={leaveTarget}
          busy={!!busyIds[leaveTarget.id ?? leaveTarget.community_id]}
          onCancel={() => setLeaveTarget(null)}
          onConfirm={handleLeave}
        />
      )}

      <section className="flex flex-col gap-4 border-b border-slate-200 pb-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2">
            <UsersRound className="h-5 w-5 text-brand-500" aria-hidden="true" />
            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-500">Community network</span>
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">Communities</h1>
            <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-slate-500">
              Discover communities, connect with people, and share knowledge around your interests.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          className="btn-primary shrink-0"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          Create Community
        </button>
      </section>

      {!backendReady && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800" role="status">
          Communities backend is not connected yet. The UI is ready for real community data.
        </div>
      )}

      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span className="flex-1">{error}</span>
          <button type="button" onClick={() => setError('')} aria-label="Dismiss error" className="text-red-600/75 hover:text-red-800">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="space-y-3">
        <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm md:flex-row md:items-center md:justify-between">
          <div className="flex w-full gap-1 md:w-auto" role="tablist" aria-label="Communities view">
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
                className={`min-h-10 flex-1 rounded-lg px-3 py-2 text-sm font-semibold transition-colors md:flex-none ${
                  activeView === item.id ? 'bg-brand-50 text-brand-600' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          <label className="relative block w-full md:max-w-sm md:flex-1">
            <span className="sr-only">Search communities</span>
            <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search communities..."
              className="input-base py-2.5 pl-10 pr-10"
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery('')}
                aria-label="Clear community search"
                className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg p-1 text-slate-400 hover:text-slate-700"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </label>
        </div>

        <div ref={categoryMenuRef} className="relative flex w-full items-center gap-4 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm sm:w-[22rem]">
          <span className="whitespace-nowrap text-sm font-semibold text-slate-700">Category</span>
          <button
            type="button"
            role="combobox"
            aria-label="Community category"
            aria-expanded={categoryOpen}
            aria-controls="community-category-options"
            aria-haspopup="listbox"
            onClick={() => setCategoryOpen((open) => !open)}
            onKeyDown={(event) => {
              if (event.key === 'Escape') setCategoryOpen(false);
              if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                setCategoryOpen(true);
              }
            }}
            className="flex min-w-0 flex-1 items-center justify-between gap-3 rounded-lg px-1 py-1 text-left text-sm font-medium text-slate-700 outline-none transition-colors hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-brand-200"
          >
            <span className="truncate">{selectedCategory.label}</span>
            <ChevronDown className={`h-4 w-4 shrink-0 text-slate-600 transition-transform ${categoryOpen ? 'rotate-180' : ''}`} aria-hidden="true" />
          </button>

          {categoryOpen && (
            <div id="community-category-options" role="listbox" aria-label="Community categories" className="scrollbar-hidden absolute left-0 right-0 top-full z-30 mt-2 max-h-72 overflow-y-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-[var(--shadow-popover)]">
              {COMMUNITY_CATEGORIES.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  role="option"
                  aria-selected={category === item.id}
                  onClick={() => {
                    setCategory(item.id);
                    setCategoryOpen(false);
                  }}
                  className={`w-full rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                    category === item.id
                      ? 'bg-brand-50 font-semibold text-brand-700'
                      : 'text-slate-700 hover:bg-slate-50 hover:text-slate-900'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <section className="space-y-4" aria-label="Discover Communities">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-slate-900">{activeView === 'joined' ? 'My Communities' : 'Discover Communities'}</h2>
          {!loading && visibleCommunities.length > 0 && (
            <span className="text-sm text-slate-500">
              {displayedCount.toLocaleString()} {displayedCount === 1 ? 'community' : 'communities'}
            </span>
          )}
        </div>

        {loading ? (
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: SKELETON_COUNT }).map((_, index) => (
              <CommunityCardSkeleton key={index} />
            ))}
          </div>
        ) : error && communities.length === 0 ? (
          <ErrorState message={error} onRetry={fetchCommunities} />
        ) : visibleCommunities.length === 0 ? (
          <EmptyState activeView={activeView} query={query} category={category} onClear={clearFilters} />
        ) : (
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3" data-testid="communities-grid">
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
