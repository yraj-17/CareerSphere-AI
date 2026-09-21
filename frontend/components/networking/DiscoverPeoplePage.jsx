'use client';

/**
 * DiscoverPeoplePage — Phase 5.4 Networking
 *
 * LinkedIn-style people discovery page. Uses only PostgreSQL data via the
 * REST networking API — no AI recommendations, no Qdrant.
 *
 * Features:
 *   - Debounced search (name / username)
 *   - Responsive 1 / 2 / 3-column grid
 *   - Connection status per card (none / pending / accepted / rejected / cancelled)
 *   - Optimistic UI on Connect (card updates instantly, reverts on error)
 *   - Load More (append-only, hides when no more results)
 *   - Loading skeletons, empty state, error state with retry
 *   - Toast-style inline feedback
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search,
  Users,
  RefreshCw,
  AlertCircle,
  X,
  Loader2,
  ChevronDown,
  Info,
} from 'lucide-react';
import { useDebounce } from '@/hooks/useDebounce';
import { getNetworkingUsers, sendConnectionRequest, extractErrorMessage } from '@/services/api';
import PersonCard from '@/components/networking/PersonCard';
import PersonCardSkeleton from '@/components/networking/PersonCardSkeleton';

// ─── Constants ─────────────────────────────────────────────────────────────────

const PAGE_SIZE = 20;
const SKELETON_COUNT = 6;

// ─── Toast notification ────────────────────────────────────────────────────────

function Toast({ message, type = 'info', onDismiss }) {
  const styles = {
    success: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    error: 'border-rose-500/30 bg-rose-500/10 text-rose-300',
    info: 'border-accent/30 bg-accent/10 text-accent',
  };
  return (
    <motion.div
      initial={{ opacity: 0, y: -10, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -8, scale: 0.97 }}
      transition={{ duration: 0.2 }}
      role="alert"
      className={`flex items-start gap-3 px-4 py-3 rounded-2xl border text-sm ${styles[type]}`}
    >
      <Info className="h-4 w-4 flex-shrink-0 mt-0.5" aria-hidden="true" />
      <span className="flex-1 leading-relaxed">{message}</span>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss notification"
        className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
      >
        <X className="h-4 w-4" />
      </button>
    </motion.div>
  );
}

// ─── Skeleton grid ─────────────────────────────────────────────────────────────

function SkeletonGrid({ count = SKELETON_COUNT }) {
  return (
    <div
      data-testid="skeleton-grid"
      className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5"
    >
      {Array.from({ length: count }).map((_, i) => (
        <PersonCardSkeleton key={i} />
      ))}
    </div>
  );
}

// ─── Error state ───────────────────────────────────────────────────────────────

function ErrorState({ message, onRetry }) {
  return (
    <div
      data-testid="error-state"
      className="flex flex-col items-center justify-center py-24 text-center space-y-4 animate-fade-in"
    >
      <div className="h-16 w-16 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center">
        <AlertCircle className="h-8 w-8 text-rose-400" />
      </div>
      <h2 className="text-xl font-bold text-white">Failed to load people</h2>
      <p className="text-sm text-slate-400 max-w-sm leading-relaxed">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-accent text-black text-sm font-semibold shadow-[0_8px_30px_rgba(255,143,50,0.3)] hover:bg-accentSoft transition-all"
      >
        <RefreshCw className="h-4 w-4" />
        Try Again
      </button>
    </div>
  );
}

// ─── Empty state ───────────────────────────────────────────────────────────────

function EmptyState({ query }) {
  return (
    <div
      data-testid="empty-state"
      className="flex flex-col items-center justify-center py-24 text-center space-y-4 animate-fade-in"
    >
      <div className="h-16 w-16 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center">
        <Users className="h-8 w-8 text-slate-500" />
      </div>
      <div className="space-y-1">
        <h2 className="text-lg font-bold text-white">
          {query ? 'No professionals found' : 'No people to discover yet'}
        </h2>
        <p className="text-sm text-slate-400 max-w-xs leading-relaxed">
          {query
            ? `No results for "${query}". Try a different name or username.`
            : 'Check back later as more people join CareerSphere AI.'}
        </p>
      </div>
    </div>
  );
}

// ─── DiscoverPeoplePage ────────────────────────────────────────────────────────

export default function DiscoverPeoplePage() {
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebounce(query, 350);

  // user list state
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);

  // loading flags
  const [initialLoading, setInitialLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);

  // per-card connecting state: { [userId]: true }
  const [connectingIds, setConnectingIds] = useState({});

  // toast: { id, message, type }
  const [toast, setToast] = useState(null);
  const toastTimer = useRef(null);

  // ── Toast helper ─────────────────────────────────────────────────────────────

  const showToast = useCallback((message, type = 'info') => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ id: Date.now(), message, type });
    toastTimer.current = setTimeout(() => setToast(null), 4500);
  }, []);

  const dismissToast = useCallback(() => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast(null);
  }, []);

  // ── Fetch helpers ─────────────────────────────────────────────────────────────

  const fetchUsers = useCallback(async (q, off, append = false) => {
    try {
      const data = await getNetworkingUsers({ q, limit: PAGE_SIZE, offset: off });
      setTotal(data.total ?? 0);
      setUsers((prev) => (append ? [...prev, ...data.users] : data.users));
      setError(null);
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  }, []);

  // ── Initial load + search reset ───────────────────────────────────────────────

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      setInitialLoading(true);
      setOffset(0);
      setUsers([]);
      await fetchUsers(debouncedQuery, 0, false);
      if (!cancelled) setInitialLoading(false);
    };

    run();
    return () => { cancelled = true; };
  }, [debouncedQuery, fetchUsers]);

  // ── Load more ─────────────────────────────────────────────────────────────────

  const handleLoadMore = useCallback(async () => {
    if (loadingMore) return;
    const nextOffset = offset + PAGE_SIZE;
    setLoadingMore(true);
    await fetchUsers(debouncedQuery, nextOffset, true);
    setOffset(nextOffset);
    setLoadingMore(false);
  }, [loadingMore, offset, debouncedQuery, fetchUsers]);

  const hasMore = users.length < total;

  // ── Connect ───────────────────────────────────────────────────────────────────

  const handleConnect = useCallback(async (userId) => {
    // Optimistic update
    setUsers((prev) =>
      prev.map((u) => (u.id === userId ? { ...u, connection_status: 'pending' } : u))
    );
    setConnectingIds((prev) => ({ ...prev, [userId]: true }));

    try {
      await sendConnectionRequest(userId);
      showToast('Connection request sent!', 'success');
    } catch (err) {
      const status = err?.response?.status;
      let msg;
      if (status === 409) {
        msg = 'A connection with this person already exists.';
      } else if (status === 400) {
        msg = 'You cannot connect to yourself.';
      } else if (status === 404) {
        msg = 'This user no longer exists.';
      } else if (status === 401) {
        msg = 'Your session has expired. Please log in again.';
      } else {
        msg = extractErrorMessage(err) || 'Failed to send connection request.';
      }
      // Revert optimistic update
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, connection_status: 'none' } : u))
      );
      showToast(msg, 'error');
    } finally {
      setConnectingIds((prev) => {
        const next = { ...prev };
        delete next[userId];
        return next;
      });
    }
  }, [showToast]);

  // ── Search input clear ────────────────────────────────────────────────────────

  const handleClearSearch = () => {
    setQuery('');
  };

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-8 animate-fade-in">

      {/* ── Page header ── */}
      <div className="relative overflow-hidden rounded-[2.5rem] border border-white/10 bg-white/[0.04] p-7 sm:p-10 shadow-glow backdrop-blur-2xl">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_0%,rgba(255,143,50,0.14),transparent_50%),radial-gradient(circle_at_85%_30%,rgba(64,217,255,0.09),transparent_40%)] pointer-events-none" />
        <div className="relative z-10 flex flex-col sm:flex-row sm:items-center gap-4 justify-between">
          <div>
            <div className="flex items-center gap-2.5 mb-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/15 border border-accent/30">
                <Users className="h-4 w-4 text-accent" />
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                Discover People
              </h1>
            </div>
            <p className="text-sm text-slate-400 max-w-md">
              Find professionals and grow your network.
            </p>
          </div>

          {!initialLoading && !error && total > 0 && (
            <div className="flex-shrink-0 px-4 py-2 rounded-full bg-white/5 border border-white/10 text-xs text-slate-400">
              {total.toLocaleString()} {total === 1 ? 'professional' : 'professionals'}
            </div>
          )}
        </div>
      </div>

      {/* ── Toast ── */}
      <AnimatePresence mode="wait">
        {toast && (
          <Toast
            key={toast.id}
            message={toast.message}
            type={toast.type}
            onDismiss={dismissToast}
          />
        )}
      </AnimatePresence>

      {/* ── Search ── */}
      <div className="relative">
        <div className="pointer-events-none absolute inset-y-0 left-4 flex items-center">
          <Search className="h-4 w-4 text-slate-400" aria-hidden="true" />
        </div>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name or username…"
          aria-label="Search people"
          data-testid="search-input"
          className="w-full rounded-2xl border border-white/10 bg-white/[0.04] py-3 pl-11 pr-12 text-sm text-white placeholder-slate-500 backdrop-blur-xl outline-none focus:border-accent/40 focus:ring-1 focus:ring-accent/20 transition-all"
        />
        {/* Clear button */}
        {query && (
          <button
            type="button"
            onClick={handleClearSearch}
            aria-label="Clear search"
            className="absolute inset-y-0 right-3 flex items-center px-1 text-slate-400 hover:text-white transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* ── Content ── */}
      {initialLoading ? (
        <SkeletonGrid count={SKELETON_COUNT} />
      ) : error ? (
        <ErrorState
          message={error}
          onRetry={() => {
            setError(null);
            setInitialLoading(true);
            fetchUsers(debouncedQuery, 0, false).finally(() => setInitialLoading(false));
          }}
        />
      ) : users.length === 0 ? (
        <EmptyState query={debouncedQuery} />
      ) : (
        <>
          {/* People grid */}
          <div
            data-testid="people-grid"
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5"
          >
            <AnimatePresence initial={false}>
              {users.map((user) => (
                <PersonCard
                  key={user.id}
                  user={user}
                  onConnect={handleConnect}
                  isConnecting={!!connectingIds[user.id]}
                />
              ))}
            </AnimatePresence>
          </div>

          {/* Load more skeletons appended while fetching */}
          {loadingMore && (
            <div
              data-testid="load-more-skeletons"
              className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5"
            >
              {Array.from({ length: 3 }).map((_, i) => (
                <PersonCardSkeleton key={`more-${i}`} />
              ))}
            </div>
          )}

          {/* Load More button */}
          {hasMore && !loadingMore && (
            <div className="flex justify-center pt-2">
              <button
                type="button"
                onClick={handleLoadMore}
                data-testid="load-more-btn"
                className="flex items-center gap-2 px-7 py-3 rounded-full border border-white/10 bg-white/5 text-sm font-medium text-slate-200 hover:border-white/25 hover:bg-white/10 hover:text-white transition-all"
              >
                <ChevronDown className="h-4 w-4" aria-hidden="true" />
                Load More
              </button>
            </div>
          )}

          {/* End-of-list indicator */}
          {!hasMore && users.length > 0 && (
            <p className="text-center text-xs text-slate-500 py-2" data-testid="end-of-list">
              All {total.toLocaleString()} {total === 1 ? 'professional' : 'professionals'} shown
            </p>
          )}
        </>
      )}
    </div>
  );
}
