'use client';

import React from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowUpRight, MapPin, MessageSquare, User, UserMinus } from 'lucide-react';

function AvatarFallback({ firstName, lastName }) {
  const initials = `${(firstName?.[0] || '').toUpperCase()}${(lastName?.[0] || '').toUpperCase()}` || '?';
  return (
    <div className="flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-2xl border border-[rgba(198,161,91,0.3)] bg-[var(--surface-subtle)] text-base font-semibold text-[var(--brand-navy)]">
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

export default function ConnectionCard({ conn, onRemove, busy = false }) {
  const user = conn?.other_user || {};
  const name = `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.username || 'CareerSphere member';

  return (
    <motion.article
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.2 }}
      data-testid="connection-card"
      className="group relative flex min-h-[236px] flex-col overflow-hidden rounded-[var(--radius-card)] border border-[var(--border)] bg-[var(--surface)] shadow-[var(--shadow-card)] transition-shadow duration-200 hover:shadow-[0_10px_28px_rgba(23,36,58,0.1)]"
    >
      <div className="absolute inset-x-0 top-0 h-1 bg-[var(--brand-amber)] opacity-0 transition-opacity group-hover:opacity-100" aria-hidden="true" />
      <div className="flex flex-1 flex-col gap-4 p-5">
        <div className="flex items-start gap-4">
          {user.profile_photo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={user.profile_photo_url} alt={name} className="h-14 w-14 flex-shrink-0 rounded-2xl border border-[var(--border)] object-cover" onError={(event) => { event.currentTarget.style.display = 'none'; }} />
          ) : (
            <AvatarFallback firstName={user.first_name} lastName={user.last_name} />
          )}
          <div className="min-w-0 flex-1">
            <Link href={`/dashboard/networking/${user.id}`} className="group/name inline-flex max-w-full items-center gap-1 text-base font-semibold leading-tight text-[var(--text-primary)] hover:text-[var(--brand-navy)]">
              <span className="truncate">{name}</span>
              <ArrowUpRight className="h-3.5 w-3.5 flex-shrink-0 text-[var(--text-muted)] transition-colors group-hover/name:text-[var(--brand-amber)]" aria-hidden="true" />
            </Link>
            {user.username && <p className="mt-1 truncate text-xs text-[var(--brand-amber)]">@{user.username}</p>}
            <p className="mt-2 line-clamp-2 text-sm leading-5 text-[var(--text-secondary)]">{user.headline || 'CareerSphere member'}</p>
          </div>
        </div>

        {user.location && (
          <div className="flex items-center gap-1.5 text-xs text-[var(--text-muted)]">
            <MapPin className="h-3.5 w-3.5 flex-shrink-0 text-[var(--brand-amber)]" />
            <span className="truncate">{user.location}</span>
          </div>
        )}

        <div className="mt-auto grid grid-cols-1 gap-2 border-t border-[var(--border)] pt-4 sm:grid-cols-3">
          <Link href={`/dashboard/networking/${user.id}`} aria-label={`View profile of ${name}`} className="btn-primary px-2.5 py-2 text-xs">
            <User className="h-3.5 w-3.5" />
            View Profile
          </Link>
          <Link href={`/dashboard/messaging?with=${user.id}`} aria-label={`Message ${name}`} data-testid="message-btn" className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-[var(--brand-yellow)] bg-[var(--brand-yellow)] px-2.5 py-2 text-xs font-semibold text-[var(--brand-deep-navy)] transition-colors hover:border-[var(--brand-amber)] hover:bg-[var(--brand-amber)]">
            <MessageSquare className="h-3.5 w-3.5 text-[var(--brand-deep-navy)]" />
            Message
          </Link>
          <button type="button" onClick={() => !busy && onRemove?.(conn.id)} disabled={busy} aria-label={`Remove connection with ${name}`} data-testid="remove-btn" className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-[rgba(180,35,24,0.2)] bg-[rgba(180,35,24,0.025)] px-2.5 py-2 text-xs font-semibold text-[var(--danger)] transition-colors hover:border-[var(--danger)] hover:bg-[rgba(180,35,24,0.07)] disabled:cursor-wait disabled:opacity-60">
            {busy ? <Spinner /> : <UserMinus className="h-3.5 w-3.5" />}
            Remove
          </button>
        </div>
      </div>
    </motion.article>
  );
}
