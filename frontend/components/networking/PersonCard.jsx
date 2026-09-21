'use client';

/**
 * PersonCard — Phase 5.4 Networking
 *
 * Displays public information for a discovered user:
 *   profile photo · name · username · headline · location
 *   connection status badge · Connect / Pending / Connected button
 *   View Profile link
 *
 * Props:
 *   user            {Object}   — NetworkingUserResponse from the API
 *   onConnect       {Function} — async (userId) => void
 *   isConnecting    {boolean}  — true while the POST is in-flight for this card
 */

import React from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { MapPin, UserPlus, UserCheck, Clock, UserX, ArrowUpRight, User } from 'lucide-react';

// ─── Status config ────────────────────────────────────────────────────────────

const STATUS_CFG = {
  none: {
    label: 'Connect',
    icon: UserPlus,
    cls: 'bg-accent text-black font-semibold shadow-[0_6px_20px_rgba(255,143,50,0.30)] hover:bg-accentSoft hover:-translate-y-0.5 active:translate-y-0',
    disabled: false,
  },
  pending: {
    label: 'Pending',
    icon: Clock,
    cls: 'border border-amber-500/40 bg-amber-500/10 text-amber-300 cursor-default',
    disabled: true,
  },
  accepted: {
    label: 'Connected',
    icon: UserCheck,
    cls: 'border border-emerald-500/40 bg-emerald-500/10 text-emerald-300 cursor-default',
    disabled: true,
  },
  rejected: {
    label: 'Connect',
    icon: UserPlus,
    // Backend blocks a re-request while the rejected row exists;
    // show as disabled so the user knows the state without a misleading CTA.
    cls: 'border border-white/10 bg-white/5 text-slate-500 cursor-default',
    disabled: true,
  },
  cancelled: {
    label: 'Connect',
    icon: UserPlus,
    cls: 'border border-white/10 bg-white/5 text-slate-500 cursor-default',
    disabled: true,
  },
};

// ─── Avatar initials fallback ─────────────────────────────────────────────────

function AvatarFallback({ firstName, lastName, size = 'md' }) {
  const initials = `${(firstName?.[0] ?? '').toUpperCase()}${(lastName?.[0] ?? '').toUpperCase()}` || '?';
  const sizeMap = {
    md: 'h-16 w-16 text-xl',
    lg: 'h-20 w-20 text-2xl',
  };
  return (
    <div
      className={`${sizeMap[size]} rounded-2xl bg-gradient-to-br from-accent/30 via-accent/10 to-violet/20 border border-accent/20 flex items-center justify-center font-bold text-white select-none`}
    >
      {initials}
    </div>
  );
}

// ─── PersonCard ───────────────────────────────────────────────────────────────

export default function PersonCard({ user, onConnect, isConnecting = false }) {
  const status = user.connection_status ?? 'none';
  const cfg = STATUS_CFG[status] ?? STATUS_CFG.none;
  const Icon = cfg.icon;

  const handleConnect = () => {
    if (!cfg.disabled && !isConnecting) {
      onConnect(user.id);
    }
  };

  return (
    <motion.article
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28 }}
      data-testid="person-card"
      className="group relative flex flex-col rounded-[1.75rem] border border-white/10 bg-white/[0.04] backdrop-blur-xl shadow-glow hover:border-white/20 hover:bg-white/[0.06] transition-all duration-200 overflow-hidden"
    >
      {/* subtle top-edge accent on hover */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

      <div className="p-5 flex flex-col gap-4 flex-1">
        {/* ── Avatar + Name row ── */}
        <div className="flex items-start gap-4">
          {/* Photo or initials */}
          <div className="flex-shrink-0">
            {user.profile_photo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={user.profile_photo_url}
                alt={`${user.first_name} ${user.last_name}`}
                className="h-16 w-16 rounded-2xl object-cover border border-white/10"
                onError={(e) => { e.currentTarget.style.display = 'none'; }}
              />
            ) : (
              <AvatarFallback firstName={user.first_name} lastName={user.last_name} />
            )}
          </div>

          {/* Name / username / headline */}
          <div className="flex-1 min-w-0">
            <p className="text-base font-bold text-white leading-tight truncate">
              {user.first_name} {user.last_name}
            </p>
            <p className="text-xs font-mono text-accent mt-0.5 truncate">
              @{user.username}
            </p>
            {user.headline && (
              <p className="text-xs text-slate-300 mt-1.5 leading-relaxed line-clamp-2">
                {user.headline}
              </p>
            )}
          </div>
        </div>

        {/* ── Location ── */}
        {user.location && (
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <MapPin className="h-3.5 w-3.5 flex-shrink-0 text-slate-500" />
            <span className="truncate">{user.location}</span>
          </div>
        )}

        {/* ── Spacer pushes buttons to bottom ── */}
        <div className="flex-1" />

        {/* ── Action buttons ── */}
        <div className="flex items-center gap-2 pt-1 border-t border-white/8">
          {/* Connect / status button */}
          <button
            type="button"
            onClick={handleConnect}
            disabled={cfg.disabled || isConnecting}
            aria-label={`${cfg.label} with ${user.first_name} ${user.last_name}`}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-full text-xs transition-all duration-150 ${cfg.cls} ${
              isConnecting && !cfg.disabled ? 'opacity-60 cursor-wait' : ''
            }`}
          >
            {isConnecting && !cfg.disabled ? (
              /* spinner while in-flight */
              <svg
                className="h-3.5 w-3.5 animate-spin"
                viewBox="0 0 24 24"
                fill="none"
                aria-hidden="true"
              >
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
              </svg>
            ) : (
              <Icon className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
            )}
            <span>{isConnecting && !cfg.disabled ? 'Sending…' : cfg.label}</span>
          </button>

          {/* View Profile link */}
          <Link
            href={`/dashboard/networking/${user.id}`}
            aria-label={`View profile of ${user.first_name} ${user.last_name}`}
            className="flex items-center gap-1 px-3 py-2 rounded-full text-xs border border-white/10 text-slate-300 hover:border-white/25 hover:text-white transition-all"
          >
            <User className="h-3.5 w-3.5" aria-hidden="true" />
            <span>Profile</span>
            <ArrowUpRight className="h-3 w-3 opacity-60" aria-hidden="true" />
          </Link>
        </div>
      </div>
    </motion.article>
  );
}
