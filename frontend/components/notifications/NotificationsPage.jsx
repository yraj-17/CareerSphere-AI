'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Bell, CheckCheck, Loader2, RefreshCw } from 'lucide-react';
import ProfileAvatar from '@/components/common/ProfileAvatar';
import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '@/services/api';

function formatRelativeTime(value) {
  if (!value) return 'Recently';
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return 'Recently';
  const seconds = Math.max(1, Math.floor((Date.now() - then) / 1000));
  if (seconds < 60) return 'Just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} minutes ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hours ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} days ago`;
  return new Date(value).toLocaleDateString();
}

function destinationFor(notification) {
  if (notification?.action_url) return notification.action_url;
  if (notification?.type === 'CONNECTION_REQUEST') return '/dashboard/networking/my-network?tab=requests';
  if (notification?.type === 'CONNECTION_ACCEPTED') return '/dashboard/networking/my-network';
  if (notification?.type === 'CONNECTION_REJECTED') return '/dashboard/networking/my-network?tab=sent';
  return '/dashboard/notifications';
}

export default function NotificationsPage() {
  const router = useRouter();
  const [filter, setFilter] = useState('all');
  const [notifications, setNotifications] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const payload = await listNotifications({
        limit: 30,
        offset: 0,
        unreadOnly: filter === 'unread',
      });
      setNotifications(payload?.notifications ?? []);
      setTotal(payload?.total ?? 0);
    } catch {
      setError('Unable to load notifications.');
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  const handleMarkAllRead = async () => {
    try {
      await markAllNotificationsRead();
      setNotifications((prev) => prev.map((notification) => ({ ...notification, is_read: true })));
      if (filter === 'unread') setNotifications([]);
    } catch {
      setError('Unable to mark notifications read.');
    }
  };

  const handleOpen = async (notification) => {
    const destination = destinationFor(notification);
    if (!notification.is_read) {
      setNotifications((prev) =>
        prev.map((item) => (item.id === notification.id ? { ...item, is_read: true } : item))
      );
      try {
        await markNotificationRead(notification.id);
      } catch {
        // Navigation still works; next load will reconcile read state.
      }
    }
    router.push(destination);
  };

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-4 py-8 sm:px-6 lg:px-8">
      <section className="rounded-[2rem] border border-white/10 bg-white/[0.04] p-6 shadow-glow backdrop-blur-xl">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-accent">Notifications</p>
            <h1 className="mt-2 text-3xl font-extrabold text-white">Your updates</h1>
            <p className="mt-2 text-sm text-slate-400">Connection requests and platform activity for your account.</p>
          </div>
          <button
            type="button"
            onClick={handleMarkAllRead}
            className="inline-flex items-center justify-center gap-2 rounded-full border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200 hover:border-accent/30 hover:text-accent"
          >
            <CheckCheck className="h-4 w-4" />
            Mark all read
          </button>
        </div>

        <div className="mt-6 flex gap-2 border-b border-white/10">
          {[
            ['all', 'All'],
            ['unread', 'Unread'],
          ].map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setFilter(id)}
              aria-pressed={filter === id}
              className={`rounded-t-xl border-b-2 px-4 py-2.5 text-sm font-semibold transition-colors ${
                filter === id
                  ? 'border-accent bg-accent/5 text-accent'
                  : 'border-transparent text-slate-400 hover:bg-white/[0.05] hover:text-white'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="mt-5">
          {loading ? (
            <div className="flex items-center justify-center rounded-3xl border border-white/10 bg-slate-950/30 py-16">
              <Loader2 className="h-6 w-6 animate-spin text-accent" />
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center rounded-3xl border border-rose-500/20 bg-rose-500/10 py-14 text-center">
              <p className="text-sm text-rose-200">{error}</p>
              <button type="button" onClick={load} className="mt-4 inline-flex items-center gap-2 rounded-full border border-white/10 px-4 py-2 text-sm text-slate-200 hover:text-white">
                <RefreshCw className="h-4 w-4" />
                Try again
              </button>
            </div>
          ) : notifications.length === 0 ? (
            <div className="rounded-3xl border border-white/10 bg-slate-950/30 px-6 py-16 text-center">
              <Bell className="mx-auto mb-3 h-8 w-8 text-slate-600" />
              <p className="font-semibold text-white">No notifications</p>
              <p className="mt-1 text-sm text-slate-500">
                {filter === 'unread' ? 'You have no unread notifications.' : 'You have no notifications yet.'}
              </p>
            </div>
          ) : (
            <div className="overflow-hidden rounded-3xl border border-white/10">
              {notifications.map((notification) => (
                <button
                  key={notification.id}
                  type="button"
                  onClick={() => handleOpen(notification)}
                  className={`flex w-full gap-4 border-b border-white/10 px-4 py-4 text-left transition-colors last:border-b-0 hover:bg-white/[0.06] ${
                    notification.is_read ? 'bg-white/[0.025]' : 'bg-accent/[0.06]'
                  }`}
                >
                  <ProfileAvatar
                    src={notification.actor?.profile_photo_url}
                    name={notification.actor?.name}
                    username={notification.actor?.username}
                    alt={notification.actor?.name || 'Notification actor'}
                    fallback={(notification.actor?.first_name?.[0] || 'N').toUpperCase()}
                    className="h-12 w-12"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold text-white">{notification.actor?.name || 'CareerSphere AI'}</span>
                    <span className="mt-1 block text-sm leading-relaxed text-slate-300">{notification.message}</span>
                    <span className="mt-2 block text-xs text-slate-500">{formatRelativeTime(notification.created_at)}</span>
                  </span>
                  {!notification.is_read && <span className="mt-2 h-2.5 w-2.5 shrink-0 rounded-full bg-accent" aria-label="Unread" />}
                </button>
              ))}
            </div>
          )}
          {!loading && !error && total > notifications.length && (
            <p className="mt-3 text-center text-xs text-slate-500">Showing latest {notifications.length} of {total} notifications.</p>
          )}
        </div>
      </section>
    </div>
  );
}
