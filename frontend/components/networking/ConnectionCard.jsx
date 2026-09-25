'use client';

/**
 * ConnectionCard — Phase 5.5 My Network
 *
 * A card that displays one enriched connection row. Adapts its action buttons
 * based on the variant:
 *
 *   'connection' — accepted connection: [View Profile] [Remove]
 *   'incoming'   — pending, I am receiver: [Accept] [Reject]
 *   'sent'       — pending, I am requester: [View Profile] [Cancel Request]
 *
 * Props:
 *   conn          {EnrichedConnectionResponse}  — enriched connection row
 *   variant       {'connection'|'incoming'|'sent'}
 *   onAccept      (connId) => void   — incoming only
 *   onReject      (connId) => void   — incoming only
 *   onRemove      (connId) => void   — connection only
 *   onCancel      (connId) => void   — sent only
 *   busy          boolean            — action in-flight for this card
 */

import React from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  MapPin,
  UserCheck,
  UserX,
  UserMinus,
  XCircle,
  ArrowUpRight,
  User,
  MessageSquare,
} from 'lucide-react';

// ─── Shared Avatar fallback ───────────────────────────────────────────────────

function AvatarFallback({ firstName, lastName }) {
  const initials =
    `${(firstName?.[0] ?? '').toUpperCase()}${(lastName?.[0] ?? '').toUpperCase()}` || '?';
  return (
    <div className="h-14 w-14 rounded-2xl bg-gradient-to-br from-accent/30 via-accent/10 to-violet/20 border border-accent/20 flex items-center justify-center font-bold text-white text-lg select-none flex-shrink-0">
      {initials}
    </div>
  );
}

// ─── Spinner ──────────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  );
}

// ─── ConnectionCard ───────────────────────────────────────────────────────────

export default function ConnectionCard({
  conn,
  variant = 'connection',
  onAccept,
  onReject,
  onRemove,
  onCancel,
  busy = false,
}) {
  const { id: connId, other_user: u } = conn;

  return (
    <motion.article
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.97 }}
      transition={{ duration: 0.22 }}
      data-testid="connection-card"
      className="group relative flex flex-col rounded-[1.75rem] border border-white/10 bg-white/[0.04] backdrop-blur-xl shadow-glow hover:border-white/20 hover:bg-white/[0.06] transition-all duration-200 overflow-hidden"
    >
      {/* top-edge accent on hover */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

      <div className="p-5 flex flex-col gap-3 flex-1">
        {/* ── Avatar + info ── */}
        <div className="flex items-start gap-4">
          <div className="flex-shrink-0">
            {u.profile_photo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={u.profile_photo_url}
                alt={`${u.first_name} ${u.last_name}`}
                className="h-14 w-14 rounded-2xl object-cover border border-white/10"
                onError={(e) => { e.currentTarget.style.display = 'none'; }}
              />
            ) : (
              <AvatarFallback firstName={u.first_name} lastName={u.last_name} />
            )}
          </div>

          <div className="flex-1 min-w-0">
            <p
              className="text-sm font-bold text-white leading-tight truncate"
              data-testid="conn-card-name"
            >
              {u.first_name} {u.last_name}
            </p>
            <p className="text-xs font-mono text-accent mt-0.5 truncate">@{u.username}</p>
            {u.headline && (
              <p className="text-xs text-slate-300 mt-1.5 leading-relaxed line-clamp-2">
                {u.headline}
              </p>
            )}
          </div>
        </div>

        {/* ── Location ── */}
        {u.location && (
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <MapPin className="h-3.5 w-3.5 flex-shrink-0 text-slate-500" />
            <span className="truncate">{u.location}</span>
          </div>
        )}

        {/* ── Spacer ── */}
        <div className="flex-1" />

        {/* ── Actions ── */}
        <div className="flex items-center gap-2 pt-1 border-t border-white/8">
          {/* ── ACCEPTED CONNECTION ── */}
          {variant === 'connection' && (
            <>
              <Link
                href={`/dashboard/networking/${u.id}`}
                aria-label={`View profile of ${u.first_name} ${u.last_name}`}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-full text-xs border border-white/10 text-slate-300 hover:border-white/25 hover:text-white transition-all"
              >
                <User className="h-3.5 w-3.5" aria-hidden="true" />
                <span>View Profile</span>
                <ArrowUpRight className="h-3 w-3 opacity-60" aria-hidden="true" />
              </Link>

              <Link
                href={`/dashboard/messaging?with=${u.id}`}
                aria-label={`Message ${u.first_name} ${u.last_name}`}
                data-testid="message-btn"
                className="flex items-center gap-1.5 px-3 py-2 rounded-full text-xs border border-accent/30 text-accent hover:bg-accent/10 hover:border-accent/50 transition-all"
              >
                <MessageSquare className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Message</span>
              </Link>

              <button
                type="button"
                onClick={() => !busy && onRemove(connId)}
                disabled={busy}
                aria-label={`Remove connection with ${u.first_name} ${u.last_name}`}
                data-testid="remove-btn"
                className={`flex items-center gap-1.5 px-3 py-2 rounded-full text-xs border transition-all ${
                  busy
                    ? 'border-white/10 text-slate-600 cursor-wait'
                    : 'border-rose-500/30 text-rose-400 hover:bg-rose-500/10 hover:border-rose-500/50'
                }`}
              >
                {busy ? <Spinner /> : <UserMinus className="h-3.5 w-3.5" aria-hidden="true" />}
                <span>Remove</span>
              </button>
            </>
          )}

          {/* ── INCOMING REQUEST ── */}
          {variant === 'incoming' && (
            <>
              <button
                type="button"
                onClick={() => !busy && onAccept(connId)}
                disabled={busy}
                aria-label={`Accept connection request from ${u.first_name} ${u.last_name}`}
                data-testid="accept-btn"
                className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-full text-xs font-semibold transition-all ${
                  busy
                    ? 'bg-emerald-500/10 text-emerald-600 cursor-wait'
                    : 'bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/25 hover:border-emerald-500/60'
                }`}
              >
                {busy ? <Spinner /> : <UserCheck className="h-3.5 w-3.5" aria-hidden="true" />}
                <span>{busy ? 'Accepting…' : 'Accept'}</span>
              </button>

              <button
                type="button"
                onClick={() => !busy && onReject(connId)}
                disabled={busy}
                aria-label={`Reject connection request from ${u.first_name} ${u.last_name}`}
                data-testid="reject-btn"
                className={`flex items-center gap-1.5 px-3 py-2 rounded-full text-xs border transition-all ${
                  busy
                    ? 'border-white/10 text-slate-600 cursor-wait'
                    : 'border-rose-500/30 text-rose-400 hover:bg-rose-500/10 hover:border-rose-500/50'
                }`}
              >
                {busy ? <Spinner /> : <UserX className="h-3.5 w-3.5" aria-hidden="true" />}
                <span>Decline</span>
              </button>
            </>
          )}

          {/* ── SENT REQUEST ── */}
          {variant === 'sent' && (
            <>
              <Link
                href={`/dashboard/networking/${u.id}`}
                aria-label={`View profile of ${u.first_name} ${u.last_name}`}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-full text-xs border border-white/10 text-slate-300 hover:border-white/25 hover:text-white transition-all"
              >
                <User className="h-3.5 w-3.5" aria-hidden="true" />
                <span>View Profile</span>
                <ArrowUpRight className="h-3 w-3 opacity-60" aria-hidden="true" />
              </Link>

              <button
                type="button"
                onClick={() => !busy && onCancel(connId)}
                disabled={busy}
                aria-label={`Cancel connection request to ${u.first_name} ${u.last_name}`}
                data-testid="cancel-btn"
                className={`flex items-center gap-1.5 px-3 py-2 rounded-full text-xs border transition-all ${
                  busy
                    ? 'border-white/10 text-slate-600 cursor-wait'
                    : 'border-amber-500/30 text-amber-400 hover:bg-amber-500/10 hover:border-amber-500/50'
                }`}
              >
                {busy ? <Spinner /> : <XCircle className="h-3.5 w-3.5" aria-hidden="true" />}
                <span>Cancel</span>
              </button>
            </>
          )}
        </div>
      </div>
    </motion.article>
  );
}
