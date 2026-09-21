'use client';

/**
 * UserProfileView — Phase 5.6
 *
 * Full public professional profile page for a networking user.
 *
 * Responsibilities:
 *   - Fetch public profile via GET /api/networking/users/{userId}/profile
 *   - Fetch connection status via GET /api/networking/users/{userId}/connection
 *   - Render all profile sections with empty states
 *   - Handle connection actions (Connect, Accept, Reject, Remove) without reload
 *   - Detect own profile and show Edit Profile instead of connection buttons
 *
 * Props:
 *   userId       {string}  — from URL params
 *   currentUser  {object}  — from AuthContext (id, first_name, etc.)
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft,
  MapPin,
  Briefcase,
  GraduationCap,
  FolderOpen,
  Award,
  Wrench,
  UserPlus,
  UserCheck,
  UserMinus,
  UserX,
  Clock,
  Pencil,
  AlertCircle,
  RefreshCw,
  ExternalLink,
  Github,
  Info,
  X,
} from 'lucide-react';
import {
  getPublicProfile,
  getNetworkingUserConnection,
  sendConnectionRequest,
  acceptConnectionRequest,
  rejectConnectionRequest,
  removeConnection,
  extractErrorMessage,
} from '@/services/api';

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
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.2 }}
      role="alert"
      className={`flex items-start gap-3 px-4 py-3 rounded-2xl border text-sm ${styles[type]}`}
    >
      <Info className="h-4 w-4 flex-shrink-0 mt-0.5" aria-hidden="true" />
      <span className="flex-1 leading-relaxed">{message}</span>
      <button type="button" onClick={onDismiss} aria-label="Dismiss" className="opacity-60 hover:opacity-100 transition-opacity">
        <X className="h-4 w-4" />
      </button>
    </motion.div>
  );
}

// ─── Avatar ───────────────────────────────────────────────────────────────────

function Avatar({ photoUrl, firstName, lastName, size = 'lg' }) {
  const initials = `${(firstName?.[0] ?? '').toUpperCase()}${(lastName?.[0] ?? '').toUpperCase()}` || '?';
  const sizeMap = {
    lg: 'h-24 w-24 text-3xl rounded-3xl',
    xl: 'h-28 w-28 text-4xl rounded-[2rem]',
  };
  if (photoUrl) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={photoUrl}
        alt={`${firstName} ${lastName}`}
        data-testid="profile-photo"
        className={`${sizeMap[size]} object-cover border-2 border-white/10 flex-shrink-0`}
        onError={(e) => { e.currentTarget.style.display = 'none'; }}
      />
    );
  }
  return (
    <div
      data-testid="profile-avatar"
      className={`${sizeMap[size]} bg-gradient-to-br from-accent/30 via-accent/10 to-violet/20 border-2 border-accent/20 flex items-center justify-center font-bold text-white select-none flex-shrink-0`}
    >
      {initials}
    </div>
  );
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function ProfileSkeleton() {
  return (
    <div data-testid="profile-skeleton" className="space-y-6 animate-fade-in">
      {/* Header skeleton */}
      <div className="rounded-[2.5rem] border border-white/10 bg-white/[0.04] p-8 space-y-4">
        <div className="flex items-start gap-6">
          <div className="h-24 w-24 rounded-3xl bg-white/5 animate-pulse flex-shrink-0" />
          <div className="flex-1 space-y-3 pt-1">
            <div className="h-6 w-48 rounded-lg bg-white/5 animate-pulse" />
            <div className="h-4 w-32 rounded-lg bg-white/5 animate-pulse" />
            <div className="h-4 w-56 rounded-lg bg-white/5 animate-pulse" />
            <div className="h-9 w-28 rounded-full bg-white/5 animate-pulse mt-2" />
          </div>
        </div>
      </div>
      {/* Section skeletons */}
      {[1, 2, 3].map((i) => (
        <div key={i} className="rounded-[2rem] border border-white/10 bg-white/[0.04] p-6 space-y-3">
          <div className="h-5 w-32 rounded-lg bg-white/5 animate-pulse" />
          <div className="h-4 w-full rounded-lg bg-white/5 animate-pulse" />
          <div className="h-4 w-3/4 rounded-lg bg-white/5 animate-pulse" />
        </div>
      ))}
    </div>
  );
}

// ─── Error state ──────────────────────────────────────────────────────────────

function ProfileError({ message, onRetry }) {
  return (
    <div data-testid="profile-error" className="flex flex-col items-center justify-center py-24 text-center space-y-4">
      <div className="h-16 w-16 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center">
        <AlertCircle className="h-8 w-8 text-rose-400" />
      </div>
      <h2 className="text-xl font-bold text-white">Could not load profile</h2>
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

// ─── Section wrapper ──────────────────────────────────────────────────────────

function Section({ icon: Icon, title, children, testId }) {
  return (
    <div
      data-testid={testId}
      className="rounded-[2rem] border border-white/10 bg-white/[0.04] backdrop-blur-xl shadow-glow p-6 space-y-4"
    >
      <div className="flex items-center gap-2.5">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-accent/15 border border-accent/30">
          <Icon className="h-4 w-4 text-accent" aria-hidden="true" />
        </div>
        <h2 className="text-base font-semibold text-white">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function EmptySection({ message }) {
  return (
    <p className="text-sm text-slate-500 italic py-2">{message}</p>
  );
}

// ─── Skill chips ──────────────────────────────────────────────────────────────

function SkillBadge({ name }) {
  return (
    <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium border border-white/10 bg-white/5 text-slate-200">
      {name}
    </span>
  );
}

// ─── Date helpers ─────────────────────────────────────────────────────────────

function fmtDate(iso) {
  if (!iso) return null;
  try {
    const d = new Date(iso + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  } catch {
    return iso;
  }
}

function DateRange({ start, end, current }) {
  if (!start && !end) return null;
  const s = fmtDate(start) || '';
  const e = current ? 'Present' : (fmtDate(end) || 'Present');
  return <span className="text-xs text-slate-400">{s}{s ? ' – ' : ''}{e}</span>;
}

// ─── Connection action button ─────────────────────────────────────────────────

function ConnectionButton({ connStatus, connId, userId, onAction, busy }) {
  const isOwn = connStatus === 'own';

  if (isOwn) {
    return (
      <Link
        href="/dashboard/profile"
        data-testid="edit-profile-btn"
        className="inline-flex items-center gap-2 px-5 py-2 rounded-full text-sm font-medium border border-accent/40 text-accent hover:bg-accent/10 transition-all"
      >
        <Pencil className="h-4 w-4" />
        Edit Profile
      </Link>
    );
  }

  const Spinner = () => (
    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  );

  if (connStatus === 'none' || connStatus === null) {
    return (
      <button
        type="button"
        onClick={() => onAction('connect', userId)}
        disabled={busy}
        data-testid="connect-btn"
        className="inline-flex items-center gap-2 px-5 py-2 rounded-full text-sm font-semibold bg-accent text-black shadow-[0_6px_20px_rgba(255,143,50,0.30)] hover:bg-accentSoft hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:cursor-wait"
      >
        {busy ? <Spinner /> : <UserPlus className="h-4 w-4" />}
        {busy ? 'Sending…' : 'Connect'}
      </button>
    );
  }

  if (connStatus === 'pending_sent') {
    return (
      <div className="flex items-center gap-2">
        <span
          data-testid="pending-btn"
          className="inline-flex items-center gap-2 px-5 py-2 rounded-full text-sm border border-amber-500/40 bg-amber-500/10 text-amber-300"
        >
          <Clock className="h-4 w-4" />
          Pending
        </span>
      </div>
    );
  }

  if (connStatus === 'pending_received') {
    return (
      <div className="flex items-center gap-2" data-testid="incoming-actions">
        <button
          type="button"
          onClick={() => onAction('accept', connId)}
          disabled={busy}
          data-testid="accept-btn"
          className="inline-flex items-center gap-2 px-5 py-2 rounded-full text-sm font-semibold border border-emerald-500/40 bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25 transition-all disabled:opacity-50 disabled:cursor-wait"
        >
          {busy ? <Spinner /> : <UserCheck className="h-4 w-4" />}
          {busy ? 'Accepting…' : 'Accept'}
        </button>
        <button
          type="button"
          onClick={() => onAction('reject', connId)}
          disabled={busy}
          data-testid="reject-btn"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm border border-rose-500/30 text-rose-400 hover:bg-rose-500/10 transition-all disabled:opacity-50 disabled:cursor-wait"
        >
          {busy ? <Spinner /> : <UserX className="h-4 w-4" />}
          Decline
        </button>
      </div>
    );
  }

  if (connStatus === 'accepted') {
    return (
      <div className="flex items-center gap-2">
        <span
          data-testid="connected-btn"
          className="inline-flex items-center gap-2 px-5 py-2 rounded-full text-sm border border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
        >
          <UserCheck className="h-4 w-4" />
          Connected
        </span>
        <button
          type="button"
          onClick={() => onAction('remove', connId)}
          disabled={busy}
          data-testid="remove-btn"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm border border-rose-500/30 text-rose-400 hover:bg-rose-500/10 transition-all disabled:opacity-50 disabled:cursor-wait"
        >
          {busy ? <Spinner /> : <UserMinus className="h-4 w-4" />}
          Remove
        </button>
      </div>
    );
  }

  // rejected / cancelled — show Connect again disabled (backend blocks re-request until row is removed)
  return (
    <button
      type="button"
      disabled
      data-testid="connect-btn"
      className="inline-flex items-center gap-2 px-5 py-2 rounded-full text-sm border border-white/10 text-slate-500 cursor-not-allowed"
    >
      <UserPlus className="h-4 w-4" />
      Connect
    </button>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function UserProfileView({ userId, currentUser }) {
  const [profile, setProfile] = useState(null);
  const [connStatus, setConnStatus] = useState(null); // 'none'|'pending_sent'|'pending_received'|'accepted'|'rejected'|'cancelled'|'own'
  const [connId, setConnId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);
  const toastTimer = useRef(null);

  const isOwnProfile = currentUser?.id === userId;

  const showToast = useCallback((message, type = 'info') => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ id: Date.now(), message, type });
    toastTimer.current = setTimeout(() => setToast(null), 4500);
  }, []);

  const dismissToast = useCallback(() => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast(null);
  }, []);

  // ── Derive simple connection status ──────────────────────────────────────

  const _resolveConnStatus = useCallback((connData) => {
    if (isOwnProfile) { setConnStatus('own'); return; }
    if (!connData || connData.status === 'none') { setConnStatus('none'); setConnId(null); return; }
    const { status, requester_id, receiver_id, connection_id } = connData;
    setConnId(connection_id ?? null);
    if (status === 'pending') {
      setConnStatus(requester_id === currentUser?.id ? 'pending_sent' : 'pending_received');
    } else {
      setConnStatus(status); // accepted | rejected | cancelled
    }
  }, [isOwnProfile, currentUser?.id]);

  // ── Fetch data ────────────────────────────────────────────────────────────

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [profileData, connData] = await Promise.all([
        getPublicProfile(userId),
        isOwnProfile ? Promise.resolve(null) : getNetworkingUserConnection(userId),
      ]);
      setProfile(profileData);
      _resolveConnStatus(connData);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to load profile.');
    } finally {
      setLoading(false);
    }
  }, [userId, isOwnProfile, _resolveConnStatus]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // ── Connection actions ────────────────────────────────────────────────────

  const handleAction = useCallback(async (action, idParam) => {
    setBusy(true);
    try {
      if (action === 'connect') {
        const res = await sendConnectionRequest(idParam);
        setConnId(res.id);
        setConnStatus('pending_sent');
        showToast('Connection request sent!', 'success');
      } else if (action === 'accept') {
        await acceptConnectionRequest(idParam);
        setConnStatus('accepted');
        showToast('Connection accepted.', 'success');
      } else if (action === 'reject') {
        await rejectConnectionRequest(idParam);
        setConnStatus('none');
        setConnId(null);
        showToast('Connection request declined.', 'info');
      } else if (action === 'remove') {
        await removeConnection(idParam);
        setConnStatus('none');
        setConnId(null);
        showToast('Connection removed.', 'info');
      }
    } catch (err) {
      const status = err?.response?.status;
      const msg =
        status === 409 ? 'A connection with this person already exists.' :
        status === 403 ? 'You are not authorised to perform this action.' :
        status === 404 ? 'This user no longer exists.' :
        extractErrorMessage(err) || 'Action failed. Please try again.';
      showToast(msg, 'error');
    } finally {
      setBusy(false);
    }
  }, [showToast]);

  // ── Render ────────────────────────────────────────────────────────────────

  if (loading) return <ProfileSkeleton />;
  if (error) return <ProfileError message={error} onRetry={fetchAll} />;
  if (!profile) return null;

  const u = profile.user;
  const name = `${u.first_name} ${u.last_name}`.trim();

  return (
    <div className="space-y-6 animate-fade-in" data-testid="profile-view">

      {/* ── Back navigation ── */}
      <div className="flex items-center gap-3 flex-wrap">
        <Link
          href="/dashboard/networking"
          className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Discover People
        </Link>
        <span className="text-slate-600">·</span>
        <Link
          href="/dashboard/networking/my-network"
          className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-white transition-colors"
        >
          My Network
        </Link>
      </div>

      {/* ── Toast ── */}
      <AnimatePresence mode="wait">
        {toast && (
          <Toast key={toast.id} message={toast.message} type={toast.type} onDismiss={dismissToast} />
        )}
      </AnimatePresence>

      {/* ── Profile header ── */}
      <div className="relative overflow-hidden rounded-[2.5rem] border border-white/10 bg-white/[0.04] p-7 sm:p-10 shadow-glow backdrop-blur-2xl">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_0%,rgba(255,143,50,0.12),transparent_50%)] pointer-events-none" />
        <div className="relative z-10 flex flex-col sm:flex-row items-start gap-6">
          <Avatar
            photoUrl={profile.profile_photo_url}
            firstName={u.first_name}
            lastName={u.last_name}
            size="xl"
          />
          <div className="flex-1 min-w-0 space-y-3">
            <div>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight" data-testid="profile-name">
                {name}
              </h1>
              <p className="text-sm font-mono text-accent mt-0.5" data-testid="profile-username">
                @{u.username}
              </p>
            </div>
            {profile.headline && (
              <p className="text-base text-slate-300 leading-snug" data-testid="profile-headline">
                {profile.headline}
              </p>
            )}
            {profile.location && (
              <div className="flex items-center gap-1.5 text-sm text-slate-400">
                <MapPin className="h-3.5 w-3.5 text-slate-500" aria-hidden="true" />
                <span data-testid="profile-location">{profile.location}</span>
              </div>
            )}
            <div className="pt-1">
              <ConnectionButton
                connStatus={connStatus}
                connId={connId}
                userId={userId}
                onAction={handleAction}
                busy={busy}
              />
            </div>
          </div>
        </div>
      </div>

      {/* ── About ── */}
      {profile.about && (
        <Section icon={Info} title="About" testId="section-about">
          <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">{profile.about}</p>
        </Section>
      )}

      {/* ── Skills ── */}
      <Section icon={Wrench} title="Skills" testId="section-skills">
        {profile.skills.length === 0 ? (
          <EmptySection message="No skills listed yet." />
        ) : (
          <div className="flex flex-wrap gap-2">
            {profile.skills.map((s) => (
              <SkillBadge key={s.id} name={s.name} />
            ))}
          </div>
        )}
      </Section>

      {/* ── Experience ── */}
      <Section icon={Briefcase} title="Experience" testId="section-experience">
        {profile.experience.length === 0 ? (
          <EmptySection message="No experience listed yet." />
        ) : (
          <div className="space-y-5">
            {profile.experience.map((ex) => (
              <div key={ex.id} className="flex flex-col gap-0.5">
                <p className="text-sm font-semibold text-white">{ex.job_title}</p>
                <p className="text-sm text-slate-300">{ex.company}{ex.employment_type ? ` · ${ex.employment_type}` : ''}</p>
                <DateRange start={ex.start_date} end={ex.end_date} current={ex.currently_working} />
                {ex.location && <p className="text-xs text-slate-500">{ex.location}</p>}
                {ex.description && (
                  <p className="text-xs text-slate-400 mt-1 leading-relaxed">{ex.description}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* ── Education ── */}
      <Section icon={GraduationCap} title="Education" testId="section-education">
        {profile.education.length === 0 ? (
          <EmptySection message="No education listed yet." />
        ) : (
          <div className="space-y-5">
            {profile.education.map((ed) => (
              <div key={ed.id} className="flex flex-col gap-0.5">
                <p className="text-sm font-semibold text-white">{ed.institution}</p>
                <p className="text-sm text-slate-300">
                  {ed.degree}{ed.field_of_study ? ` · ${ed.field_of_study}` : ''}
                </p>
                <DateRange start={ed.start_date} end={ed.end_date} />
                {ed.description && (
                  <p className="text-xs text-slate-400 mt-1 leading-relaxed">{ed.description}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* ── Projects ── */}
      {profile.projects.length > 0 && (
        <Section icon={FolderOpen} title="Projects" testId="section-projects">
          <div className="space-y-5">
            {profile.projects.map((proj) => (
              <div key={proj.id} className="space-y-1.5">
                <div className="flex items-start gap-2 flex-wrap">
                  <p className="text-sm font-semibold text-white">{proj.name}</p>
                  <div className="flex items-center gap-2">
                    {proj.github_url && (
                      <a
                        href={proj.github_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-slate-400 hover:text-white transition-colors"
                        aria-label="GitHub"
                      >
                        <Github className="h-3.5 w-3.5" />
                      </a>
                    )}
                    {proj.live_url && (
                      <a
                        href={proj.live_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-slate-400 hover:text-white transition-colors"
                        aria-label="Live demo"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    )}
                  </div>
                </div>
                {proj.technologies.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {proj.technologies.map((t) => (
                      <span key={t} className="px-2 py-0.5 rounded-full text-[11px] border border-violet/30 text-violet-300 bg-violet/10">
                        {t}
                      </span>
                    ))}
                  </div>
                )}
                <DateRange start={proj.start_date} end={proj.end_date} />
                {proj.description && (
                  <p className="text-xs text-slate-400 leading-relaxed">{proj.description}</p>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* ── Certifications ── */}
      {profile.certifications.length > 0 && (
        <Section icon={Award} title="Certifications" testId="section-certifications">
          <div className="space-y-4">
            {profile.certifications.map((c) => (
              <div key={c.id} className="flex flex-col gap-0.5">
                <p className="text-sm font-semibold text-white">{c.name}</p>
                <p className="text-xs text-slate-400">{c.issuing_organization}</p>
                {c.issue_date && (
                  <p className="text-xs text-slate-500">Issued {fmtDate(c.issue_date)}</p>
                )}
                {c.credential_url && (
                  <a
                    href={c.credential_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-accent hover:text-accentSoft transition-colors mt-0.5"
                  >
                    <ExternalLink className="h-3 w-3" />
                    View credential
                  </a>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}
