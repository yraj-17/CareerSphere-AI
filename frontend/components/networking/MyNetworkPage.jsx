'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { AnimatePresence, motion } from 'framer-motion';
import {
  AlertCircle,
  ArrowUpRight,
  CalendarDays,
  Check,
  Clock3,
  Inbox,
  Info,
  MapPin,
  RefreshCw,
  Search,
  Send,
  SlidersHorizontal,
  User,
  UserCheck,
  UserPlus,
  UserRoundX,
  Users,
  X,
} from 'lucide-react';
import {
  acceptConnectionRequest,
  cancelConnectionRequest,
  extractErrorMessage,
  getMyNetworkConnections,
  getMyNetworkIncoming,
  getMyNetworkOutgoing,
  rejectConnectionRequest,
  removeConnection,
} from '@/services/api';
import ConnectionCard from '@/components/networking/ConnectionCard';
import PersonCardSkeleton from '@/components/networking/PersonCardSkeleton';

const TABS = [
  { id: 'connections', label: 'Connections', icon: UserCheck },
  { id: 'requests', label: 'Requests', icon: Inbox },
  { id: 'sent', label: 'Sent', icon: Send },
];

const SKELETON_COUNT = { connections: 4, requests: 3, sent: 3 };

function fullName(user = {}) {
  return `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.username || 'CareerSphere member';
}

function formatDate(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function matchesSearch(connection, query) {
  const term = query.trim().toLowerCase();
  if (!term) return true;
  const user = connection?.other_user || {};
  return [fullName(user), user.username, user.headline, user.location]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(term));
}

function sortConnections(connections, sortBy) {
  return [...connections].sort((a, b) => {
    const nameA = fullName(a?.other_user).toLowerCase();
    const nameB = fullName(b?.other_user).toLowerCase();
    if (sortBy === 'name') return nameA.localeCompare(nameB);
    return new Date(b?.created_at || 0).getTime() - new Date(a?.created_at || 0).getTime();
  });
}

function Avatar({ user, size = 'md' }) {
  const initials = `${(user?.first_name?.[0] || '').toUpperCase()}${(user?.last_name?.[0] || '').toUpperCase()}` || '?';
  const sizeClass = size === 'sm' ? 'h-12 w-12 text-sm' : 'h-14 w-14 text-base';
  return user?.profile_photo_url ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={user.profile_photo_url}
      alt={fullName(user)}
      className={`${sizeClass} flex-shrink-0 rounded-2xl border border-[var(--border)] object-cover`}
      onError={(event) => { event.currentTarget.style.display = 'none'; }}
    />
  ) : (
    <div className={`${sizeClass} flex flex-shrink-0 items-center justify-center rounded-2xl border border-[rgba(198,161,91,0.3)] bg-[var(--surface-subtle)] font-semibold text-[var(--brand-navy)]`}>
      {initials}
    </div>
  );
}

function Spinner() {
  return (
    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  );
}

function Toast({ message, type = 'info', onDismiss }) {
  const styles = {
    success: 'border-[rgba(21,128,61,0.22)] bg-[rgba(21,128,61,0.06)] text-[var(--success)]',
    error: 'border-[rgba(180,35,24,0.22)] bg-[rgba(180,35,24,0.06)] text-[var(--danger)]',
    info: 'border-[rgba(49,94,155,0.22)] bg-[rgba(49,94,155,0.06)] text-[var(--info)]',
  };
  return (
    <motion.div
      initial={{ opacity: 0, y: -10, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -8, scale: 0.97 }}
      role="alert"
      className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-sm ${styles[type]}`}
    >
      <Info className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
      <span className="flex-1 leading-relaxed">{message}</span>
      <button type="button" onClick={onDismiss} aria-label="Dismiss" className="flex-shrink-0 opacity-60 transition-opacity hover:opacity-100">
        <X className="h-4 w-4" />
      </button>
    </motion.div>
  );
}

function ConfirmDialog({ title, description, confirmLabel, confirmClassName, onConfirm, onCancel }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      role="dialog"
      aria-modal="true"
      aria-label={title}
      data-testid="confirm-dialog"
      className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(16,27,45,0.42)] p-4 backdrop-blur-sm"
    >
      <motion.div
        initial={{ opacity: 0, y: 10, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        className="surface-card w-full max-w-md space-y-5 p-6 shadow-[var(--shadow-popover)]"
      >
        <div className="space-y-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--surface-subtle)] text-[var(--brand-navy)]">
            <Info className="h-5 w-5" aria-hidden="true" />
          </div>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">{title}</h2>
          <p className="text-sm leading-6 text-[var(--text-secondary)]">{description}</p>
        </div>
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button type="button" onClick={onCancel} className="btn-outline w-full sm:w-auto">Keep</button>
          <button type="button" onClick={onConfirm} data-testid="confirm-action-btn" className={`btn-primary w-full sm:w-auto ${confirmClassName}`}>
            {confirmLabel}
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

function StatCard({ id, label, value, detail, icon: Icon, accent = false }) {
  return (
    <div data-testid={`stat-${id}`} className="surface-card flex items-center gap-4 p-4 sm:p-5">
      <div className={`flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl ${accent ? 'bg-[var(--brand-navy)] text-surface' : 'bg-[var(--surface-subtle)] text-[var(--brand-navy)]'}`}>
        <Icon className="h-5 w-5" aria-hidden="true" />
      </div>
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{label}</p>
        <p className="mt-1 text-2xl font-semibold tracking-tight text-[var(--text-primary)]">{value}</p>
        <p className="mt-0.5 text-xs text-[var(--text-muted)]">{detail}</p>
      </div>
    </div>
  );
}

function SectionSkeleton({ count, list = false }) {
  return list ? (
    <div data-testid="section-skeleton" className="space-y-3">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="h-28 animate-pulse rounded-xl border border-[var(--border)] bg-[var(--surface-subtle)]" />
      ))}
    </div>
  ) : (
    <div data-testid="section-skeleton" className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: count }).map((_, index) => <PersonCardSkeleton key={index} />)}
    </div>
  );
}

function SectionError({ message, onRetry }) {
  return (
    <div data-testid="section-error" className="surface-card flex flex-col items-center justify-center space-y-4 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[rgba(180,35,24,0.07)] text-[var(--danger)]">
        <AlertCircle className="h-6 w-6" />
      </div>
      <p className="max-w-md text-sm leading-6 text-[var(--text-secondary)]">{message}</p>
      <button type="button" onClick={onRetry} className="btn-primary">
        <RefreshCw className="h-4 w-4" />
        Try Again
      </button>
    </div>
  );
}

function SectionEmpty({ tabId, requestView = false }) {
  const config = {
    connections: {
      icon: UserCheck,
      title: 'No connections yet',
      sub: 'Start building your professional network by discovering people.',
      cta: 'Discover People',
    },
    requests: {
      icon: Inbox,
      title: 'No pending requests',
      sub: "You don't have any incoming connection requests right now.",
      cta: null,
    },
    sent: {
      icon: Send,
      title: 'No sent invitations',
      sub: "You haven't sent any connection invitations yet.",
      cta: 'Discover People',
    },
  };
  const { icon: Icon, title, sub, cta } = config[tabId] || config.connections;
  return (
    <div data-testid="section-empty" className="surface-card flex flex-col items-center justify-center py-16 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--surface-subtle)] text-[var(--brand-navy)]">
        <Icon className="h-7 w-7" />
      </div>
      <h2 className="mt-5 text-base font-semibold text-[var(--text-primary)]">{title}</h2>
      <p className="mt-2 max-w-sm text-sm leading-6 text-[var(--text-muted)]">{sub}</p>
      {cta && (
        <Link href="/dashboard/networking" className="btn-primary mt-5">
          <UserPlus className="h-4 w-4" />
          {cta}
        </Link>
      )}
      {requestView && tabId === 'requests' && (
        <p className="mt-5 text-xs font-medium text-[var(--text-muted)]">New requests will appear here.</p>
      )}
    </div>
  );
}

function SearchEmpty({ requestView }) {
  return (
    <div className="surface-card flex flex-col items-center justify-center py-14 text-center">
      <Search className="h-8 w-8 text-[var(--text-muted)]" />
      <h2 className="mt-4 text-base font-semibold text-[var(--text-primary)]">No matching {requestView ? 'requests' : 'people'}</h2>
      <p className="mt-2 text-sm text-[var(--text-muted)]">Try a different name, headline, username, or location.</p>
    </div>
  );
}

function RequestRow({ conn, variant, onAccept, onReject, onCancel, busy = false }) {
  const user = conn?.other_user || {};
  const name = fullName(user);
  const date = formatDate(conn?.created_at);
  const incoming = variant === 'incoming';
  return (
    <motion.article
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.98 }}
      data-testid="connection-card"
      className="surface-card flex flex-col gap-5 p-4 transition-shadow hover:shadow-[0_8px_24px_rgba(23,36,58,0.08)] sm:p-5 lg:flex-row lg:items-center lg:justify-between"
    >
      <div className="flex min-w-0 items-start gap-3 sm:gap-4">
        <Avatar user={user} size="sm" />
        <div className="min-w-0">
          <Link href={`/dashboard/networking/${user.id}`} className="group inline-flex max-w-full items-center gap-1 text-sm font-semibold text-[var(--text-primary)] hover:text-[var(--brand-navy)]">
            <span className="truncate">{name}</span>
            <ArrowUpRight className="h-3.5 w-3.5 flex-shrink-0 text-[var(--text-muted)] transition-colors group-hover:text-[var(--brand-amber)]" aria-hidden="true" />
          </Link>
          <p className="mt-1 truncate text-xs text-[var(--text-secondary)]">{user.headline || 'CareerSphere member'}</p>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[var(--text-muted)]">
            {user.location && <span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5" />{user.location}</span>}
            {date && <span className="inline-flex items-center gap-1"><CalendarDays className="h-3.5 w-3.5" />{incoming ? 'Received' : 'Sent'} {date}</span>}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 lg:justify-end">
        <Link href={`/dashboard/networking/${user.id}`} className="btn-outline px-3 py-2 text-xs">
          <User className="h-3.5 w-3.5" />
          View Profile
        </Link>
        {incoming ? (
          <>
            <button
              type="button"
              onClick={() => !busy && onAccept(conn.id)}
              disabled={busy}
              aria-label={`Accept connection request from ${name}`}
              data-testid="accept-btn"
              className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-[rgba(21,128,61,0.28)] bg-[rgba(21,128,61,0.05)] px-3 py-2 text-xs font-semibold text-[var(--success)] transition-colors hover:bg-[rgba(21,128,61,0.1)] disabled:cursor-wait disabled:opacity-60"
            >
              {busy ? <Spinner /> : <Check className="h-3.5 w-3.5" />}
              {busy ? 'Accepting…' : 'Accept'}
            </button>
            <button
              type="button"
              onClick={() => !busy && onReject(conn.id)}
              disabled={busy}
              aria-label={`Ignore connection request from ${name}`}
              data-testid="reject-btn"
              className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-[rgba(180,35,24,0.22)] px-3 py-2 text-xs font-semibold text-[var(--danger)] transition-colors hover:bg-[rgba(180,35,24,0.06)] disabled:cursor-wait disabled:opacity-60"
            >
              <UserRoundX className="h-3.5 w-3.5" />
              Ignore
            </button>
          </>
        ) : (
          <>
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface-subtle)] px-3 py-2 text-xs font-semibold text-[var(--text-secondary)]">
              <Clock3 className="h-3.5 w-3.5 text-[var(--brand-amber)]" />
              Pending
            </span>
            <button
              type="button"
              onClick={() => !busy && onCancel(conn.id)}
              disabled={busy}
              aria-label={`Cancel connection request to ${name}`}
              data-testid="cancel-btn"
              className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-[rgba(180,35,24,0.22)] px-3 py-2 text-xs font-semibold text-[var(--danger)] transition-colors hover:bg-[rgba(180,35,24,0.06)] disabled:cursor-wait disabled:opacity-60"
            >
              {busy ? <Spinner /> : <X className="h-3.5 w-3.5" />}
              Cancel
            </button>
          </>
        )}
      </div>
    </motion.article>
  );
}

export default function MyNetworkPage({ initialTab = 'connections' }) {
  const normalizedInitialTab = TABS.some((tab) => tab.id === initialTab) ? initialTab : 'connections';
  const requestView = normalizedInitialTab === 'requests';
  const [activeTab, setActiveTab] = useState(normalizedInitialTab);
  const [requestTab, setRequestTab] = useState('received');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('recent');
  const [tabState, setTabState] = useState({
    connections: { data: [], loading: false, error: null, loaded: false },
    requests: { data: [], loading: false, error: null, loaded: false },
    sent: { data: [], loading: false, error: null, loaded: false },
  });
  const [busyIds, setBusyIds] = useState({});
  const [pending, setPending] = useState(null);
  const [toast, setToast] = useState(null);
  const toastTimer = useRef(null);

  const showToast = useCallback((message, type = 'info') => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ id: Date.now(), message, type });
    toastTimer.current = setTimeout(() => setToast(null), 4500);
  }, []);

  const dismissToast = useCallback(() => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast(null);
  }, []);

  useEffect(() => () => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
  }, []);

  useEffect(() => {
    const nextTab = TABS.some((tab) => tab.id === initialTab) ? initialTab : 'connections';
    setActiveTab(nextTab);
    setRequestTab(initialTab === 'sent' ? 'sent' : 'received');
  }, [initialTab]);

  const fetchTabData = useCallback(async (tabId, force = false) => {
    setTabState((previous) => {
      if (!force && previous[tabId].loaded) return previous;
      return { ...previous, [tabId]: { ...previous[tabId], loading: true, error: null } };
    });

    const fetcher = {
      connections: getMyNetworkConnections,
      requests: getMyNetworkIncoming,
      sent: getMyNetworkOutgoing,
    }[tabId];

    try {
      const response = await fetcher();
      setTabState((previous) => ({
        ...previous,
        [tabId]: {
          data: Array.isArray(response) ? response : [],
          loading: false,
          error: null,
          loaded: true,
        },
      }));
    } catch (error) {
      setTabState((previous) => ({
        ...previous,
        [tabId]: {
          ...previous[tabId],
          loading: false,
          error: extractErrorMessage(error) || 'Failed to load.',
          loaded: false,
        },
      }));
    }
  }, []);

  // Summary cards use the same real collections as each tab.
  useEffect(() => {
    TABS.forEach(({ id }) => fetchTabData(id));
  }, [fetchTabData]);

  const setBusy = useCallback((id, value) => {
    setBusyIds((previous) => {
      const next = { ...previous };
      if (value) next[id] = true;
      else delete next[id];
      return next;
    });
  }, []);

  const counts = {
    connections: tabState.connections.data.length,
    requests: tabState.requests.data.length,
    sent: tabState.sent.data.length,
  };
  const dataTab = requestView ? (requestTab === 'sent' ? 'sent' : 'requests') : activeTab;
  const { data, loading, error } = tabState[dataTab];
  const visibleData = useMemo(
    () => sortConnections(data.filter((connection) => matchesSearch(connection, searchQuery)), sortBy),
    [data, searchQuery, sortBy],
  );

  const handleAccept = useCallback(async (connectionId) => {
    setBusy(connectionId, true);
    try {
      await acceptConnectionRequest(connectionId);
      setTabState((previous) => ({
        ...previous,
        requests: { ...previous.requests, data: previous.requests.data.filter((connection) => connection.id !== connectionId) },
        connections: { ...previous.connections, loaded: false },
      }));
      showToast('Connection accepted.', 'success');
    } catch (error) {
      showToast(extractErrorMessage(error) || 'Unable to accept request.', 'error');
    } finally {
      setBusy(connectionId, false);
    }
  }, [setBusy, showToast]);

  const handleReject = useCallback(async (connectionId) => {
    setBusy(connectionId, true);
    try {
      await rejectConnectionRequest(connectionId);
      setTabState((previous) => ({
        ...previous,
        requests: { ...previous.requests, data: previous.requests.data.filter((connection) => connection.id !== connectionId) },
      }));
      showToast('Connection request ignored.', 'info');
    } catch (error) {
      showToast(extractErrorMessage(error) || 'Unable to ignore request.', 'error');
    } finally {
      setBusy(connectionId, false);
    }
  }, [setBusy, showToast]);

  const handleRemoveClick = useCallback((connectionId) => setPending({ connectionId, action: 'remove' }), []);
  const handleCancelClick = useCallback((connectionId) => setPending({ connectionId, action: 'cancel' }), []);

  const handleRemoveConfirm = useCallback(async () => {
    const connectionId = pending?.connectionId;
    setPending(null);
    if (!connectionId) return;
    setBusy(connectionId, true);
    try {
      await removeConnection(connectionId);
      setTabState((previous) => ({
        ...previous,
        connections: { ...previous.connections, data: previous.connections.data.filter((connection) => connection.id !== connectionId) },
      }));
      showToast('Connection removed.', 'success');
    } catch (error) {
      showToast(extractErrorMessage(error) || 'Unable to remove connection.', 'error');
    } finally {
      setBusy(connectionId, false);
    }
  }, [pending, setBusy, showToast]);

  const handleCancelConfirm = useCallback(async () => {
    const connectionId = pending?.connectionId;
    setPending(null);
    if (!connectionId) return;
    setBusy(connectionId, true);
    try {
      await cancelConnectionRequest(connectionId);
      setTabState((previous) => ({
        ...previous,
        sent: { ...previous.sent, data: previous.sent.data.filter((connection) => connection.id !== connectionId) },
      }));
      showToast('Connection request cancelled.', 'info');
    } catch (error) {
      showToast(extractErrorMessage(error) || 'Unable to cancel request.', 'error');
    } finally {
      setBusy(connectionId, false);
    }
  }, [pending, setBusy, showToast]);

  const handleRetry = useCallback((tabId) => fetchTabData(tabId, true), [fetchTabData]);
  const headerTitle = requestView ? 'Connection Requests' : 'My Network';
  const headerDescription = requestView
    ? 'Review and manage the people who want to connect with you.'
    : 'Manage your connections and grow your professional network.';

  return (
    <div className="space-y-7 animate-fade-in">
      <AnimatePresence>
        {pending?.action === 'remove' && (
          <ConfirmDialog
            title="Remove this connection?"
            description="This will permanently remove the connection. You can always reconnect later."
            confirmLabel="Remove"
            confirmClassName="bg-[var(--danger)] hover:bg-[var(--danger)]"
            onConfirm={handleRemoveConfirm}
            onCancel={() => setPending(null)}
          />
        )}
        {pending?.action === 'cancel' && (
          <ConfirmDialog
            title="Cancel this connection request?"
            description="The request will be withdrawn. The recipient will no longer see it."
            confirmLabel="Cancel Request"
            confirmClassName="bg-[var(--brand-amber)] text-[var(--brand-deep-navy)] hover:bg-[var(--brand-yellow)]"
            onConfirm={handleCancelConfirm}
            onCancel={() => setPending(null)}
          />
        )}
      </AnimatePresence>

      <section className="surface-card relative overflow-hidden p-6 sm:p-8">
        <div className="pointer-events-none absolute right-0 top-0 h-44 w-1/2 bg-[radial-gradient(circle_at_top_right,rgba(198,161,91,0.15),transparent_65%)]" />
        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface-subtle)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--brand-navy)]">
              {requestView ? <Inbox className="h-3.5 w-3.5 text-[var(--brand-amber)]" /> : <Users className="h-3.5 w-3.5 text-[var(--brand-amber)]" />}
              {requestView ? 'Network inbox' : 'Professional network'}
            </div>
            <h1 className="text-3xl font-semibold tracking-tight text-[var(--text-primary)] sm:text-4xl">{headerTitle}</h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--text-secondary)]">{headerDescription}</p>
          </div>
          <Link href="/dashboard/networking" className="btn-primary w-full sm:w-fit">
            <UserPlus className="h-4 w-4" />
            Discover People
            <ArrowUpRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      <AnimatePresence mode="wait">
        {toast && <Toast key={toast.id} message={toast.message} type={toast.type} onDismiss={dismissToast} />}
      </AnimatePresence>

      {requestView ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <StatCard id="received" label="Received" value={tabState.requests.loaded ? counts.requests : '—'} detail="Pending invitations" icon={Inbox} accent />
          <StatCard id="sent" label="Sent" value={tabState.sent.loaded ? counts.sent : '—'} detail="Awaiting response" icon={Send} />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard id="connections" label="Total connections" value={tabState.connections.loaded ? counts.connections : '—'} detail="People in your network" icon={Users} accent />
          <StatCard id="requests" label="Pending requests" value={tabState.requests.loaded ? counts.requests : '—'} detail="Need your response" icon={Inbox} />
          <StatCard id="sent" label="Sent invitations" value={tabState.sent.loaded ? counts.sent : '—'} detail="Awaiting response" icon={Send} />
        </div>
      )}

      <section className="surface-card overflow-hidden p-0">
        <div className="flex flex-col gap-4 border-b border-[var(--border)] p-4 sm:p-5 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex overflow-x-auto rounded-xl bg-[var(--surface-subtle)] p-1" role="tablist" aria-label={requestView ? 'Connection request sections' : 'My Network sections'}>
            {(requestView
              ? [
                { id: 'received', label: 'Received', icon: Inbox, tabId: 'requests' },
                { id: 'sent', label: 'Sent', icon: Send, tabId: 'sent' },
              ]
              : TABS.map((tab) => ({ ...tab, tabId: tab.id }))
            ).map(({ id, label, icon: Icon, tabId }) => {
              const isActive = requestView ? requestTab === id : activeTab === id;
              const count = tabState[tabId].loaded ? counts[tabId] : null;
              return (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  data-testid={requestView ? `request-tab-${id}` : `tab-${id}`}
                  onClick={() => (requestView ? setRequestTab(id) : setActiveTab(id))}
                  className={`relative inline-flex items-center gap-2 whitespace-nowrap rounded-lg px-3.5 py-2.5 text-sm font-semibold transition-colors sm:px-4 ${isActive ? 'bg-[var(--surface)] text-[var(--brand-navy)] shadow-sm' : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'}`}
                >
                  <Icon className={`h-4 w-4 ${isActive ? 'text-[var(--brand-amber)]' : ''}`} aria-hidden="true" />
                  {label}
                  {count !== null && <span className={`rounded-full px-1.5 py-0.5 text-[11px] ${isActive ? 'bg-[rgba(198,161,91,0.16)] text-[var(--brand-navy)]' : 'bg-[var(--surface)] text-[var(--text-muted)]'}`}>{count}</span>}
                  {isActive && <span className="absolute inset-x-4 -bottom-1 h-0.5 rounded-full bg-[var(--brand-amber)]" aria-hidden="true" />}
                </button>
              );
            })}
          </div>

          <div className="flex flex-col gap-3 sm:flex-row xl:min-w-[27rem] xl:justify-end">
            <label className="relative block flex-1">
              <span className="sr-only">Search {requestView ? 'connection requests' : 'your network'}</span>
              <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" aria-hidden="true" />
              <input type="search" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder={requestView ? 'Search requests by name…' : 'Search your network by name…'} className="input-base pl-10" />
            </label>
            <label className="relative flex items-center">
              <SlidersHorizontal className="pointer-events-none absolute left-3 h-4 w-4 text-[var(--text-muted)]" aria-hidden="true" />
              <span className="sr-only">Sort results</span>
              <select value={sortBy} onChange={(event) => setSortBy(event.target.value)} className="input-base min-w-40 appearance-none pl-9 pr-3">
                <option value="recent">Most recent</option>
                <option value="name">Name A–Z</option>
              </select>
            </label>
          </div>
        </div>

        <div className="p-4 sm:p-5">
          <div className="mb-5 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                {requestView ? (requestTab === 'sent' ? 'Sent invitations' : 'Received requests') : TABS.find((tab) => tab.id === activeTab)?.label}
              </h2>
              <p className="mt-1 text-sm text-[var(--text-muted)]">
                {requestView
                  ? requestTab === 'sent' ? 'Keep track of invitations waiting for a response.' : 'Review people who want to join your professional network.'
                  : activeTab === 'connections' ? 'People you are connected with on CareerSphere.' : activeTab === 'requests' ? 'Requests waiting for your response.' : 'Invitations you have sent.'}
              </p>
            </div>
            {tabState[dataTab].loaded && <span className="text-xs font-medium text-[var(--text-muted)]">{counts[dataTab]} {counts[dataTab] === 1 ? 'record' : 'records'}</span>}
          </div>

          {loading ? (
            <SectionSkeleton count={SKELETON_COUNT[dataTab] || 3} list={dataTab !== 'connections'} />
          ) : error ? (
            <SectionError message={`Unable to load ${dataTab}. ${error}`} onRetry={() => handleRetry(dataTab)} />
          ) : data.length === 0 ? (
            <SectionEmpty tabId={dataTab} requestView={requestView} />
          ) : visibleData.length === 0 ? (
            <SearchEmpty requestView={requestView} />
          ) : (
            <AnimatePresence initial={false}>
              {dataTab === 'connections' ? (
                <div data-testid="connections-grid" className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
                  {visibleData.map((connection) => (
                    <ConnectionCard key={connection.id} conn={connection} variant="connection" onRemove={handleRemoveClick} busy={!!busyIds[connection.id]} />
                  ))}
                </div>
              ) : (
                <div data-testid={`${dataTab}-grid`} className="space-y-3">
                  {visibleData.map((connection) => (
                    <RequestRow key={connection.id} conn={connection} variant={dataTab === 'requests' ? 'incoming' : 'sent'} onAccept={handleAccept} onReject={handleReject} onCancel={handleCancelClick} busy={!!busyIds[connection.id]} />
                  ))}
                </div>
              )}
            </AnimatePresence>
          )}
        </div>
      </section>
    </div>
  );
}
