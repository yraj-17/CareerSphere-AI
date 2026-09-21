'use client';

/**
 * MyNetworkPage — Phase 5.5
 *
 * Manages the authenticated user's professional connections:
 *   • Connections tab  — accepted connections with Remove action
 *   • Requests tab     — incoming pending requests with Accept / Decline
 *   • Sent tab         — outgoing pending requests with Cancel
 *
 * Data strategy:
 *   - Each tab's data is fetched once on first open (lazy-per-tab).
 *   - After any mutation, local state is updated; no full re-fetch needed.
 *   - Counts in tab headers stay in sync with local arrays.
 *
 * Confirmations:
 *   - Remove and Cancel show an inline confirmation popover before acting.
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Users,
  UserCheck,
  Send,
  AlertCircle,
  RefreshCw,
  Info,
  X,
  Loader2,
} from 'lucide-react';
import {
  getMyNetworkConnections,
  getMyNetworkIncoming,
  getMyNetworkOutgoing,
  acceptConnectionRequest,
  rejectConnectionRequest,
  cancelConnectionRequest,
  removeConnection,
  extractErrorMessage,
} from '@/services/api';
import ConnectionCard from '@/components/networking/ConnectionCard';
import PersonCardSkeleton from '@/components/networking/PersonCardSkeleton';

// ─── Constants ─────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'connections', label: 'Connections', icon: UserCheck },
  { id: 'requests',   label: 'Requests',    icon: Users },
  { id: 'sent',       label: 'Sent',        icon: Send },
];

const SKELETON_COUNT = { connections: 4, requests: 3, sent: 3 };

// ─── Toast ────────────────────────────────────────────────────────────────────

function Toast({ message, type = 'info', onDismiss }) {
  const styles = {
    success: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    error:   'border-rose-500/30 bg-rose-500/10 text-rose-300',
    info:    'border-accent/30 bg-accent/10 text-accent',
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
        aria-label="Dismiss"
        className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
      >
        <X className="h-4 w-4" />
      </button>
    </motion.div>
  );
}

// ─── Inline confirmation dialog ───────────────────────────────────────────────

function ConfirmDialog({ title, description, confirmLabel, confirmCls, onConfirm, onCancel }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.96 }}
      transition={{ duration: 0.15 }}
      role="dialog"
      aria-modal="true"
      aria-label={title}
      data-testid="confirm-dialog"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
    >
      <div className="w-full max-w-sm rounded-[2rem] border border-white/10 bg-slate-900 p-6 shadow-[0_24px_60px_rgba(0,0,0,0.6)] space-y-5">
        <div className="space-y-1.5">
          <h2 className="text-base font-bold text-white">{title}</h2>
          {description && (
            <p className="text-sm text-slate-400 leading-relaxed">{description}</p>
          )}
        </div>
        <div className="flex items-center gap-3 justify-end">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 rounded-full text-sm font-medium border border-white/10 text-slate-200 hover:border-white/25 hover:text-white transition-all"
          >
            Keep
          </button>
          <button
            type="button"
            onClick={onConfirm}
            data-testid="confirm-action-btn"
            className={`px-5 py-2 rounded-full text-sm font-semibold transition-all ${confirmCls}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </motion.div>
  );
}

// ─── Section loading skeleton ─────────────────────────────────────────────────

function SectionSkeleton({ count }) {
  return (
    <div
      data-testid="section-skeleton"
      className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5"
    >
      {Array.from({ length: count }).map((_, i) => (
        <PersonCardSkeleton key={i} />
      ))}
    </div>
  );
}

// ─── Section error state ──────────────────────────────────────────────────────

function SectionError({ message, onRetry }) {
  return (
    <div
      data-testid="section-error"
      className="flex flex-col items-center justify-center py-16 text-center space-y-4"
    >
      <div className="h-14 w-14 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center">
        <AlertCircle className="h-7 w-7 text-rose-400" />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-semibold text-white">{message}</p>
      </div>
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

// ─── Section empty state ──────────────────────────────────────────────────────

function SectionEmpty({ tabId }) {
  const cfg = {
    connections: {
      icon: UserCheck,
      title: 'No connections yet',
      sub: 'Start building your professional network by discovering people.',
      cta: 'Discover People',
      href: '/dashboard/networking',
    },
    requests: {
      icon: Users,
      title: 'No pending requests',
      sub: "You don't have any incoming connection requests right now.",
      cta: null,
    },
    sent: {
      icon: Send,
      title: 'No sent requests',
      sub: "You haven't sent any connection requests yet.",
      cta: 'Discover People',
      href: '/dashboard/networking',
    },
  };
  const { icon: Icon, title, sub, cta, href } = cfg[tabId] ?? cfg.connections;

  return (
    <div
      data-testid="section-empty"
      className="flex flex-col items-center justify-center py-16 text-center space-y-4"
    >
      <div className="h-14 w-14 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center">
        <Icon className="h-7 w-7 text-slate-500" />
      </div>
      <div className="space-y-1">
        <p className="text-base font-bold text-white">{title}</p>
        <p className="text-sm text-slate-400 max-w-xs leading-relaxed">{sub}</p>
      </div>
      {cta && (
        <Link
          href={href}
          className="inline-flex items-center gap-2 px-6 py-2.5 rounded-full bg-accent text-black text-sm font-semibold shadow-[0_8px_30px_rgba(255,143,50,0.3)] hover:bg-accentSoft transition-all"
        >
          {cta}
        </Link>
      )}
    </div>
  );
}

// ─── MyNetworkPage ────────────────────────────────────────────────────────────

export default function MyNetworkPage() {
  const [activeTab, setActiveTab] = useState('connections');

  // Per-tab data state: { data, loading, error, loaded }
  const [tabState, setTabState] = useState({
    connections: { data: [], loading: false, error: null, loaded: false },
    requests:    { data: [], loading: false, error: null, loaded: false },
    sent:        { data: [], loading: false, error: null, loaded: false },
  });

  // Per-card busy state: { [connId]: true }
  const [busyIds, setBusyIds] = useState({});

  // Pending confirmation: { connId, action } | null
  const [pending, setPending] = useState(null);

  // Toast
  const [toast, setToast] = useState(null);
  const toastTimer = useRef(null);

  // ── Toast helpers ─────────────────────────────────────────────────────────

  const showToast = useCallback((message, type = 'info') => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ id: Date.now(), message, type });
    toastTimer.current = setTimeout(() => setToast(null), 4500);
  }, []);

  const dismissToast = useCallback(() => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast(null);
  }, []);

  // ── Tab data fetcher ──────────────────────────────────────────────────────

  const fetchTabData = useCallback(async (tabId, force = false) => {
    setTabState((prev) => {
      if (!force && prev[tabId].loaded) return prev;
      return {
        ...prev,
        [tabId]: { ...prev[tabId], loading: true, error: null },
      };
    });

    const fetcher = {
      connections: getMyNetworkConnections,
      requests:    getMyNetworkIncoming,
      sent:        getMyNetworkOutgoing,
    }[tabId];

    try {
      const data = await fetcher();
      setTabState((prev) => ({
        ...prev,
        [tabId]: { data: data ?? [], loading: false, error: null, loaded: true },
      }));
    } catch (err) {
      setTabState((prev) => ({
        ...prev,
        [tabId]: { ...prev[tabId], loading: false, error: extractErrorMessage(err) || 'Failed to load.', loaded: false },
      }));
    }
  }, []);

  // Fetch initial tab and each new tab on first open
  useEffect(() => {
    fetchTabData(activeTab);
  }, [activeTab, fetchTabData]);

  // ── setBusy helpers ───────────────────────────────────────────────────────

  const setBusy = (id, val) =>
    setBusyIds((prev) => {
      const next = { ...prev };
      if (val) next[id] = true;
      else delete next[id];
      return next;
    });

  // ── Counts (from local state arrays) ─────────────────────────────────────

  const counts = {
    connections: tabState.connections.data.length,
    requests:    tabState.requests.data.length,
    sent:        tabState.sent.data.length,
  };

  // ── Accept ────────────────────────────────────────────────────────────────

  const handleAccept = useCallback(async (connId) => {
    setBusy(connId, true);
    try {
      await acceptConnectionRequest(connId);
      // Remove from requests, will appear in connections on next load
      setTabState((prev) => ({
        ...prev,
        requests: {
          ...prev.requests,
          data: prev.requests.data.filter((c) => c.id !== connId),
        },
        // Invalidate connections so it reloads fresh on next visit
        connections: { ...prev.connections, loaded: false },
      }));
      showToast('Connection accepted.', 'success');
    } catch (err) {
      showToast(extractErrorMessage(err) || 'Unable to accept request.', 'error');
    } finally {
      setBusy(connId, false);
    }
  }, [showToast]);

  // ── Reject ────────────────────────────────────────────────────────────────

  const handleReject = useCallback(async (connId) => {
    setBusy(connId, true);
    try {
      await rejectConnectionRequest(connId);
      setTabState((prev) => ({
        ...prev,
        requests: {
          ...prev.requests,
          data: prev.requests.data.filter((c) => c.id !== connId),
        },
      }));
      showToast('Connection request declined.', 'info');
    } catch (err) {
      showToast(extractErrorMessage(err) || 'Unable to decline request.', 'error');
    } finally {
      setBusy(connId, false);
    }
  }, [showToast]);

  // ── Remove (needs confirmation) ───────────────────────────────────────────

  const handleRemoveClick = useCallback((connId) => {
    setPending({ connId, action: 'remove' });
  }, []);

  const handleRemoveConfirm = useCallback(async () => {
    const connId = pending?.connId;
    setPending(null);
    if (!connId) return;
    setBusy(connId, true);
    try {
      await removeConnection(connId);
      setTabState((prev) => ({
        ...prev,
        connections: {
          ...prev.connections,
          data: prev.connections.data.filter((c) => c.id !== connId),
        },
      }));
      showToast('Connection removed.', 'success');
    } catch (err) {
      showToast(extractErrorMessage(err) || 'Unable to remove connection.', 'error');
    } finally {
      setBusy(connId, false);
    }
  }, [pending, showToast]);

  // ── Cancel (needs confirmation) ───────────────────────────────────────────

  const handleCancelClick = useCallback((connId) => {
    setPending({ connId, action: 'cancel' });
  }, []);

  const handleCancelConfirm = useCallback(async () => {
    const connId = pending?.connId;
    setPending(null);
    if (!connId) return;
    setBusy(connId, true);
    try {
      await cancelConnectionRequest(connId);
      setTabState((prev) => ({
        ...prev,
        sent: {
          ...prev.sent,
          data: prev.sent.data.filter((c) => c.id !== connId),
        },
      }));
      showToast('Connection request cancelled.', 'info');
    } catch (err) {
      showToast(extractErrorMessage(err) || 'Unable to cancel request.', 'error');
    } finally {
      setBusy(connId, false);
    }
  }, [pending, showToast]);

  // ── Retry ─────────────────────────────────────────────────────────────────

  const handleRetry = useCallback((tabId) => {
    fetchTabData(tabId, true);
  }, [fetchTabData]);

  // ── Active tab state ──────────────────────────────────────────────────────

  const { data, loading, error } = tabState[activeTab];

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-8 animate-fade-in">
      {/* ── Confirm dialog (portal-style overlay) ── */}
      <AnimatePresence>
        {pending?.action === 'remove' && (
          <ConfirmDialog
            title="Remove this connection?"
            description="This will permanently remove the connection. You can always reconnect later."
            confirmLabel="Remove"
            confirmCls="bg-rose-500 text-white hover:bg-rose-600 shadow-[0_6px_20px_rgba(239,68,68,0.3)]"
            onConfirm={handleRemoveConfirm}
            onCancel={() => setPending(null)}
          />
        )}
        {pending?.action === 'cancel' && (
          <ConfirmDialog
            title="Cancel this connection request?"
            description="The request will be withdrawn. The recipient will no longer see it."
            confirmLabel="Cancel Request"
            confirmCls="bg-amber-500 text-black hover:bg-amber-600 shadow-[0_6px_20px_rgba(245,158,11,0.3)]"
            onConfirm={handleCancelConfirm}
            onCancel={() => setPending(null)}
          />
        )}
      </AnimatePresence>

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
                My Network
              </h1>
            </div>
            <p className="text-sm text-slate-400">
              Manage your connections and connection requests.
            </p>
          </div>

          <Link
            href="/dashboard/networking"
            className="flex-shrink-0 flex items-center gap-2 px-4 py-2 rounded-full border border-white/10 bg-white/5 text-sm font-medium text-slate-200 hover:border-white/25 hover:bg-white/10 hover:text-white transition-all"
          >
            Discover People
          </Link>
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

      {/* ── Tabs ── */}
      <div
        className="flex items-center gap-2 sm:gap-3 border-b border-white/10 pb-1 overflow-x-auto no-scrollbar"
        role="tablist"
        aria-label="My Network sections"
      >
        {TABS.map(({ id, label, icon: Icon }) => {
          const isActive = activeTab === id;
          const count = tabState[id].loaded ? counts[id] : null;
          return (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={isActive}
              data-testid={`tab-${id}`}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-t-xl text-sm font-medium whitespace-nowrap transition-all border-b-2 -mb-px ${
                isActive
                  ? 'border-accent text-accent bg-accent/5'
                  : 'border-transparent text-slate-400 hover:text-white hover:bg-white/5'
              }`}
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              <span>{label}</span>
              {count !== null && (
                <span
                  data-testid={`tab-count-${id}`}
                  className={`ml-0.5 px-2 py-0.5 rounded-full text-[11px] font-bold ${
                    isActive
                      ? 'bg-accent/20 text-accent'
                      : 'bg-white/8 text-slate-400'
                  }`}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* ── Tab content ── */}
      <div role="tabpanel" aria-label={activeTab}>
        {loading ? (
          <SectionSkeleton count={SKELETON_COUNT[activeTab] ?? 4} />
        ) : error ? (
          <SectionError
            message={`Unable to load ${activeTab}. ${error}`}
            onRetry={() => handleRetry(activeTab)}
          />
        ) : data.length === 0 ? (
          <SectionEmpty tabId={activeTab} />
        ) : (
          <AnimatePresence initial={false}>
            <div
              data-testid={`${activeTab}-grid`}
              className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5"
            >
              {data.map((conn) => (
                <ConnectionCard
                  key={conn.id}
                  conn={conn}
                  variant={
                    activeTab === 'connections'
                      ? 'connection'
                      : activeTab === 'requests'
                      ? 'incoming'
                      : 'sent'
                  }
                  onAccept={handleAccept}
                  onReject={handleReject}
                  onRemove={handleRemoveClick}
                  onCancel={handleCancelClick}
                  busy={!!busyIds[conn.id]}
                />
              ))}
            </div>
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
