'use client';

/**
 * CareerMatchingPage — real job listings matched to the user's profile.
 *
 * Display layer only: listings come from external providers (Greenhouse, Lever,
 * Ashby, …) synchronised by the backend; matching and scoring happen on the
 * backend. Every card links to the genuine posting on the provider/company site.
 *
 * Each empty outcome has its own state (status from the API):
 *   no_profile · incomplete_profile · no_jobs_available · provider_error ·
 *   no_relevant_matches — plus request errors and loading.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AlertCircle,
  ArrowUpRight,
  Award,
  BarChart2,
  Brain,
  Briefcase,
  Building2,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  CloudOff,
  Filter,
  Loader2,
  MapPin,
  RefreshCw,
  Shield,
  Sparkles,
  Target,
  TrendingUp,
  Wallet,
  Wifi,
  XCircle,
  Zap,
} from 'lucide-react';
import { getCareerMatching, extractErrorMessage } from '@/services/api';

// ─────────────────────────────────────────────────────────────────────────────
// Formatting helpers
// ─────────────────────────────────────────────────────────────────────────────

const WORK_MODE_LABELS = { remote: 'Remote', hybrid: 'Hybrid', onsite: 'On-site' };
const EMPLOYMENT_LABELS = {
  full_time: 'Full-time',
  part_time: 'Part-time',
  contract: 'Contract',
  internship: 'Internship',
  temporary: 'Temporary',
};
const EXPERIENCE_FILTERS = [
  { value: 'internship', label: 'Internship' },
  { value: 'entry', label: 'Entry / Junior' },
  { value: 'mid', label: 'Mid level' },
  { value: 'senior', label: 'Senior+' },
];
const PERIOD_LABELS = { year: '/yr', month: '/mo', week: '/wk', day: '/day', hour: '/hr' };
const EMPTY_FILTERS = { location: '', work_mode: '', employment_type: '', experience: '' };

/** Only allow genuine http(s) links to be rendered as anchors. */
export function safeExternalUrl(url) {
  if (typeof url !== 'string') return null;
  return /^https?:\/\//i.test(url.trim()) ? url.trim() : null;
}

export function formatSalary(job) {
  const { salary_min: min, salary_max: max, salary_currency: currency, salary_period: period, salary_text: text } = job;
  if (min == null && max == null) return text || null;
  const fmt = (value) => {
    try {
      return new Intl.NumberFormat('en-IN', {
        style: currency ? 'currency' : 'decimal',
        currency: currency || undefined,
        maximumFractionDigits: 0,
      }).format(value);
    } catch {
      return `${currency ? `${currency} ` : ''}${Number(value).toLocaleString('en-IN')}`;
    }
  };
  const range = min != null && max != null && min !== max ? `${fmt(min)} – ${fmt(max)}` : fmt(min ?? max);
  return `${range}${PERIOD_LABELS[period] || ''}`;
}

export function formatPostedDate(iso, now = new Date()) {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  const days = Math.floor((now.getTime() - date.getTime()) / 86400000);
  if (days <= 0) return 'Posted today';
  if (days === 1) return 'Posted yesterday';
  if (days < 30) return `Posted ${days} days ago`;
  return `Posted ${date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Design-system primitives (matching SkillAnalysisPage conventions)
// ─────────────────────────────────────────────────────────────────────────────

function Card({ children, className = '' }) {
  return (
    <div className={`rounded-[1.75rem] border border-white/10 bg-white/[0.04] backdrop-blur-xl p-6 shadow-glow ${className}`}>
      {children}
    </div>
  );
}

function SkeletonBlock({ className = '' }) {
  return <div className={`animate-pulse bg-white/5 rounded-xl ${className}`} />;
}

function SkillChip({ name, variant = 'matched' }) {
  const styles = {
    matched: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300',
    missing: 'bg-rose-500/10 border-rose-500/30 text-rose-300',
    strength: 'bg-violet/10 border-violet/30 text-violet-300',
    neutral: 'bg-white/5 border-white/10 text-slate-300',
  };
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border ${styles[variant] ?? styles.neutral}`}>
      {name}
    </span>
  );
}

function Pill({ icon: Icon, children, tone = 'neutral' }) {
  const tones = {
    neutral: 'bg-white/5 border-white/10 text-slate-300',
    remote: 'bg-cyan/10 border-cyan/20 text-cyan',
    accent: 'bg-violet/10 border-violet/20 text-violet-300',
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium border ${tones[tone]}`}>
      {Icon && <Icon className="h-3 w-3" />}
      {children}
    </span>
  );
}

function MatchScoreRing({ score }) {
  const r = 36;
  const circ = 2 * Math.PI * r;
  const pct = Math.min(100, Math.max(0, score));
  const offset = circ - (pct / 100) * circ;
  const color = pct >= 75 ? 'var(--brand-navy)' : pct >= 60 ? 'var(--brand-amber)' : 'var(--brand-yellow)';
  return (
    <div className="relative w-20 h-20 sm:w-24 sm:h-24 flex-shrink-0" aria-label={`${Math.round(pct)}% match`}>
      <svg viewBox="0 0 88 88" className="w-full h-full -rotate-90">
        <circle cx="44" cy="44" r={r} fill="none" stroke="rgba(227,231,237,0.95)" strokeWidth="7" />
        <motion.circle
          cx="44" cy="44" r={r} fill="none" stroke={color} strokeWidth="7" strokeLinecap="round"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.0, ease: 'easeOut' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-lg font-extrabold text-white leading-none">{Math.round(pct)}%</span>
        <span className="text-[9px] text-slate-400 font-medium mt-0.5">Match</span>
      </div>
    </div>
  );
}

function BreakdownBar({ label, value, weight }) {
  const pct = Math.min(100, Math.max(0, value));
  const barColor = pct >= 80 ? 'from-cyan to-cyan/60' : pct >= 55 ? 'from-accent to-accentSoft' : 'from-violet to-violet/60';
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-300 font-medium">{label}</span>
        <div className="flex items-center gap-2">
          <span className="text-slate-500 text-[10px]">{weight}</span>
          <span className="text-white font-semibold tabular-nums w-10 text-right">{pct.toFixed(0)}%</span>
        </div>
      </div>
      <div className="h-1.5 w-full rounded-full bg-white/5 overflow-hidden">
        <motion.div
          className={`h-full rounded-full bg-gradient-to-r ${barColor}`}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
        />
      </div>
    </div>
  );
}

function MatchLabelBadge({ label }) {
  const map = {
    'Strong match': { cls: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300', icon: Award },
    'Good match': { cls: 'bg-cyan/15 border-cyan/30 text-cyan', icon: TrendingUp },
    'Partial match': { cls: 'bg-violet/15 border-violet/30 text-violet-300', icon: Zap },
  };
  const cfg = map[label] ?? map['Partial match'];
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${cfg.cls}`}>
      <Icon className="h-3 w-3" />
      {label}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Page-level states
// ─────────────────────────────────────────────────────────────────────────────

function LoadingState() {
  return (
    <div className="space-y-6 animate-fade-in" data-testid="career-matching-loading">
      <div className="space-y-3">
        <SkeletonBlock className="h-7 w-40" />
        <SkeletonBlock className="h-10 w-72 max-w-full" />
      </div>
      <div className="rounded-[1.75rem] border border-accent/20 bg-accent/5 p-6 flex items-start gap-4">
        <Loader2 className="h-5 w-5 text-accent animate-spin flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-accent">Matching your profile against live job listings…</p>
          <p className="text-xs text-slate-400 mt-1">Comparing your target role, skills, experience and preferences.</p>
        </div>
      </div>
      {[...Array(3)].map((_, i) => (
        <div key={i} className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-6 flex gap-4">
          <SkeletonBlock className="h-20 w-20 rounded-full flex-shrink-0" />
          <div className="flex-1 space-y-2">
            <SkeletonBlock className="h-6 w-48 max-w-full" />
            <SkeletonBlock className="h-4 w-32" />
            <SkeletonBlock className="h-4 w-56 max-w-full" />
          </div>
        </div>
      ))}
    </div>
  );
}

function StateMessage({ icon: Icon, tone = 'neutral', title, description, children, testId }) {
  const tones = {
    neutral: 'bg-white/5 border-white/10 text-slate-500',
    error: 'bg-rose-500/10 border-rose-500/20 text-rose-400',
    warning: 'bg-amber-500/10 border-amber-500/20 text-amber-400',
    info: 'bg-accent/10 border-accent/20 text-accent',
  };
  return (
    <div className="flex-1 flex flex-col items-center justify-center py-16 sm:py-24 text-center space-y-5 animate-fade-in" data-testid={testId}>
      <div className={`h-16 w-16 sm:h-20 sm:w-20 rounded-3xl border flex items-center justify-center ${tones[tone]}`}>
        <Icon className="h-8 w-8 sm:h-10 sm:w-10" />
      </div>
      <div className="space-y-2 px-2">
        <h2 className="text-xl font-bold text-white">{title}</h2>
        {description && <p className="text-sm text-slate-400 max-w-md mx-auto leading-relaxed">{description}</p>}
      </div>
      {children}
    </div>
  );
}

function PrimaryLink({ href, children }) {
  return (
    <Link
      href={href}
      className="inline-flex items-center gap-2 px-6 py-2.5 rounded-full bg-accent text-black text-sm font-semibold shadow-[0_8px_30px_rgba(23,36,58,0.18)] hover:bg-accentSoft transition-all"
    >
      {children}
      <ArrowUpRight className="h-4 w-4" />
    </Link>
  );
}

function RetryButton({ onClick, label = 'Try again' }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full border border-white/15 text-slate-200 text-sm font-semibold hover:border-white/30 hover:text-white transition-all"
    >
      <RefreshCw className="h-4 w-4" />
      {label}
    </button>
  );
}

const PROFILE_FIELD_LABELS = { target_job_role: 'a target role', skills: 'your skills', profile: 'a profile' };

// ─────────────────────────────────────────────────────────────────────────────
// Filters
// ─────────────────────────────────────────────────────────────────────────────

function SelectFilter({ id, label, value, onChange, options, disabled }) {
  return (
    <label htmlFor={id} className="flex flex-col gap-1 min-w-0">
      <span className="text-[10px] uppercase tracking-wider text-slate-500 font-medium">{label}</span>
      <select
        id={id}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-slate-200 focus:border-accent/50 focus:outline-none disabled:opacity-50"
      >
        <option value="">Any</option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
    </label>
  );
}

function FiltersBar({ filters, options, onChange, onClear, disabled }) {
  const active = Object.values(filters).some(Boolean);
  const locationOptions = [...new Set([...(options?.locations || []), ...(filters.location ? [filters.location] : [])])];
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4" data-testid="career-matching-filters">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
          <Filter className="h-3.5 w-3.5 text-accent" />
          Filters
        </p>
        {active && (
          <button type="button" onClick={onClear} disabled={disabled} className="text-xs text-accent hover:text-accentSoft">
            Clear filters
          </button>
        )}
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <SelectFilter
          id="filter-location" label="Location" value={filters.location} disabled={disabled}
          onChange={(v) => onChange({ ...filters, location: v })}
          options={locationOptions.map((loc) => ({ value: loc, label: loc }))}
        />
        <SelectFilter
          id="filter-work-mode" label="Work mode" value={filters.work_mode} disabled={disabled}
          onChange={(v) => onChange({ ...filters, work_mode: v })}
          options={Object.entries(WORK_MODE_LABELS).map(([value, label]) => ({ value, label }))}
        />
        <SelectFilter
          id="filter-employment" label="Employment type" value={filters.employment_type} disabled={disabled}
          onChange={(v) => onChange({ ...filters, employment_type: v })}
          options={Object.entries(EMPLOYMENT_LABELS).map(([value, label]) => ({ value, label }))}
        />
        <SelectFilter
          id="filter-experience" label="Experience" value={filters.experience} disabled={disabled}
          onChange={(v) => onChange({ ...filters, experience: v })}
          options={EXPERIENCE_FILTERS}
        />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Job card
// ─────────────────────────────────────────────────────────────────────────────

function SourceAttribution({ job }) {
  if (job.source === 'adzuna') {
    // Adzuna's API terms require an "Adzuna" label linked to adzuna.co.uk.
    return (
      <span className="text-[11px] text-slate-500">
        Jobs by{' '}
        <a href="https://www.adzuna.co.uk" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
          Adzuna
        </a>
      </span>
    );
  }
  return (
    <span className="text-[11px] text-slate-500" title={job.attribution || undefined}>
      Source: <span className="text-slate-300 font-medium">{job.source_label}</span>
      {job.source_board && job.source !== 'remotive' ? <span className="text-slate-500"> · {job.company} careers</span> : null}
    </span>
  );
}

export function JobCard({ job, index }) {
  const [expanded, setExpanded] = useState(false);
  const applyUrl = safeExternalUrl(job.application_url);
  const viewUrl = safeExternalUrl(job.job_url);
  const salary = formatSalary(job);
  const posted = formatPostedDate(job.posted_at);
  const { breakdown, ai_explanation: ai } = job;

  return (
    <motion.article
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(index, 6) * 0.05 }}
      className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] backdrop-blur-xl shadow-glow overflow-hidden"
      data-testid="job-card"
    >
      <div className="p-5 sm:p-6">
        <div className="flex gap-4 sm:gap-5">
          <MatchScoreRing score={job.match_score} />
          <div className="flex-1 min-w-0 space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <MatchLabelBadge label={job.match_label} />
              <SourceAttribution job={job} />
            </div>
            <div>
              <h3 className="text-lg sm:text-xl font-bold text-white leading-snug break-words">{job.title}</h3>
              <div className="flex items-center gap-1.5 mt-0.5">
                <Building2 className="h-3.5 w-3.5 text-slate-400 flex-shrink-0" />
                <span className="text-sm text-slate-300 font-medium truncate">{job.company}</span>
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {job.location && <Pill icon={MapPin}>{job.location}</Pill>}
              {job.work_mode && (
                <Pill icon={job.work_mode === 'remote' ? Wifi : undefined} tone={job.work_mode === 'remote' ? 'remote' : 'neutral'}>
                  {WORK_MODE_LABELS[job.work_mode] || job.work_mode}
                </Pill>
              )}
              {job.employment_type && <Pill>{EMPLOYMENT_LABELS[job.employment_type] || job.employment_type}</Pill>}
              {job.experience_level && <Pill tone="accent">{job.experience_level}</Pill>}
              {salary && <Pill icon={Wallet}>{salary}</Pill>}
              {posted && <Pill icon={CalendarDays}>{posted}</Pill>}
            </div>
          </div>
        </div>

        <p className="mt-4 text-sm text-slate-300 leading-relaxed" data-testid="match-explanation">{job.explanation}</p>

        {(job.matched_skills?.length > 0 || job.missing_skills?.length > 0) && (
          <div className="mt-4 pt-4 border-t border-white/8 grid grid-cols-1 sm:grid-cols-2 gap-4">
            {job.matched_skills?.length > 0 && (
              <div>
                <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium mb-2 flex items-center gap-1.5">
                  <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                  Your matching skills
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {job.matched_skills.slice(0, 8).map((s) => <SkillChip key={s} name={s} variant="matched" />)}
                </div>
              </div>
            )}
            {job.missing_skills?.length > 0 && (
              <div>
                <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium mb-2 flex items-center gap-1.5">
                  <XCircle className="h-3 w-3 text-rose-400" />
                  Also mentioned in the listing
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {job.missing_skills.slice(0, 6).map((s) => <SkillChip key={s} name={s} variant="missing" />)}
                </div>
              </div>
            )}
          </div>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-3">
          {applyUrl ? (
            <a
              href={applyUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-accent text-black text-sm font-semibold shadow-[0_8px_30px_rgba(23,36,58,0.18)] hover:bg-accentSoft transition-all"
            >
              Apply on {job.source === 'remotive' ? 'Remotive' : job.source === 'adzuna' ? 'Adzuna' : job.company}
              <ArrowUpRight className="h-4 w-4" />
            </a>
          ) : (
            <span className="inline-flex items-center px-5 py-2.5 rounded-full text-sm border border-white/10 text-slate-500">
              Application link unavailable
            </span>
          )}
          {viewUrl && viewUrl !== applyUrl && (
            <a
              href={viewUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-full text-sm font-medium border border-white/10 text-slate-200 hover:border-white/20 hover:text-white transition-all"
            >
              View job
              <ArrowUpRight className="h-4 w-4" />
            </a>
          )}
          <button
            type="button"
            onClick={() => setExpanded((prev) => !prev)}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-full text-sm font-medium border border-white/10 text-slate-200 hover:border-white/20 hover:text-white transition-all"
            aria-expanded={expanded}
          >
            {expanded ? <>Hide match details <ChevronUp className="h-4 w-4" /></> : <>Why this match <ChevronDown className="h-4 w-4" /></>}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="border-t border-white/8 px-5 sm:px-6 py-6 space-y-5">
              {job.match_reasons?.length > 0 && (
                <ul className="space-y-1.5" data-testid="match-reasons">
                  {job.match_reasons.map((reason) => (
                    <li key={reason} className="text-sm text-slate-300 flex gap-2">
                      <Target className="h-3.5 w-3.5 text-accent flex-shrink-0 mt-1" />
                      {reason}
                    </li>
                  ))}
                </ul>
              )}
              {breakdown && (
                <div className="rounded-2xl bg-slate-950/60 border border-white/8 p-5 space-y-4">
                  <p className="text-sm font-semibold text-white flex items-center gap-2">
                    <BarChart2 className="h-4 w-4 text-accent" /> Score breakdown
                  </p>
                  <BreakdownBar label="Skills" value={breakdown.required_skill_score} weight="40%" />
                  <BreakdownBar label="Target role" value={breakdown.target_role_score} weight="30%" />
                  <BreakdownBar label="Experience" value={breakdown.experience_score} weight="15%" />
                  <BreakdownBar label="Location / remote" value={breakdown.location_remote_score} weight="10%" />
                  <BreakdownBar label="Preferences" value={breakdown.career_preference_score} weight="5%" />
                </div>
              )}
              {job.rerank_reason && (
                <div className="rounded-2xl bg-slate-950/60 border border-white/8 p-5">
                  <p className="text-sm font-semibold text-white flex items-center gap-2 mb-1.5">
                    <Sparkles className="h-4 w-4 text-cyan" /> AI context
                  </p>
                  <p className="text-sm text-slate-300 leading-relaxed">{job.rerank_reason}</p>
                </div>
              )}
              {ai && (
                <div className="rounded-2xl border border-violet/20 bg-violet/[0.04] p-5 space-y-3">
                  <p className="text-sm font-semibold text-white flex items-center gap-2">
                    <Brain className="h-4 w-4 text-violet-300" /> AI career insight
                  </p>
                  {ai.why_match && <p className="text-sm text-slate-300 leading-relaxed">{ai.why_match}</p>}
                  {ai.skill_gaps?.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {ai.skill_gaps.map((s) => <SkillChip key={s} name={s} variant="missing" />)}
                    </div>
                  )}
                  {ai.recommendation && <p className="text-sm text-slate-400">{ai.recommendation}</p>}
                </div>
              )}
              {job.attribution && <p className="text-[11px] text-slate-500">{job.attribution}</p>}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.article>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────────────────────────────────────

export default function CareerMatchingPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const requestId = useRef(0);

  const fetchMatches = useCallback(async ({ nextFilters = EMPTY_FILTERS, nextPage = 1, includeAI = false, initial = false } = {}) => {
    const id = ++requestId.current;
    if (initial) setLoading(true);
    else if (includeAI) setAiLoading(true);
    else setRefreshing(true);
    setError(null);
    try {
      const result = await getCareerMatching({ includeAI, page: nextPage, filters: nextFilters });
      if (id === requestId.current) setData(result);
    } catch (err) {
      if (id === requestId.current) setError(extractErrorMessage(err));
    } finally {
      if (id === requestId.current) {
        setLoading(false);
        setRefreshing(false);
        setAiLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchMatches({ initial: true });
  }, [fetchMatches]);

  const applyFilters = (next) => {
    setFilters(next);
    setPage(1);
    fetchMatches({ nextFilters: next, nextPage: 1 });
  };
  const goToPage = (next) => {
    setPage(next);
    fetchMatches({ nextFilters: filters, nextPage: next });
    if (typeof window !== 'undefined' && window.scrollTo) window.scrollTo({ top: 0, behavior: 'smooth' });
  };
  const retry = () => fetchMatches({ nextFilters: filters, nextPage: page, initial: !data });

  if (loading) return <LoadingState />;

  if (error && !data) {
    return (
      <StateMessage icon={AlertCircle} tone="error" title="Unable to load career matches" description={error} testId="career-matching-error">
        <RetryButton onClick={retry} />
      </StateMessage>
    );
  }

  const status = data?.status;

  if (status === 'no_profile') {
    return (
      <StateMessage icon={Briefcase} title="Create your profile first" description={data.message} testId="state-no-profile">
        <PrimaryLink href="/dashboard/profile">Set up your profile</PrimaryLink>
      </StateMessage>
    );
  }

  if (status === 'incomplete_profile') {
    const missing = (data.missing_profile_fields || []).map((f) => PROFILE_FIELD_LABELS[f] || f);
    return (
      <StateMessage icon={Target} title="Complete your profile to see matches" description={data.message} testId="state-incomplete-profile">
        {missing.length > 0 && <p className="text-xs text-slate-500">Missing: {missing.join(' and ')}</p>}
        <PrimaryLink href="/dashboard/profile">Update your profile</PrimaryLink>
      </StateMessage>
    );
  }

  if (status === 'provider_error') {
    return (
      <StateMessage icon={CloudOff} tone="warning" title="Job providers are temporarily unavailable" description={data.message} testId="state-provider-error">
        <RetryButton onClick={retry} label="Check again" />
      </StateMessage>
    );
  }

  if (status === 'no_jobs_available') {
    const importing = data.availability?.sync_running || !data.availability?.last_successful_sync_at;
    return (
      <StateMessage
        icon={importing ? Loader2 : Briefcase}
        tone={importing ? 'info' : 'neutral'}
        title={importing ? 'Importing job listings' : 'No job listings available right now'}
        description={data.message}
        testId="state-no-jobs"
      >
        <RetryButton onClick={retry} label="Check again" />
      </StateMessage>
    );
  }

  const results = data?.results || [];
  const summary = data?.profile_summary;
  const totalPages = data?.total_pages || 0;

  return (
    <div className="space-y-6 sm:space-y-8 animate-fade-in">
      <div>
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent/10 border border-accent/30 text-accent text-xs font-semibold mb-3">
          <Briefcase className="h-3.5 w-3.5" />
          <span>Career Matching</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
          Job{' '}
          <span className="bg-gradient-to-r from-accent via-accentSoft to-cyan bg-clip-text text-transparent">Matches</span>
        </h1>
        <p className="mt-2 text-slate-400 text-sm max-w-2xl">
          Live openings from company career boards, matched against your profile. Applications open on the employer&apos;s own site.
        </p>
      </div>

      {summary && (
        <Card className="!p-5">
          <div className="flex flex-wrap gap-x-6 gap-y-3 text-sm">
            <div>
              <p className="text-[10px] uppercase tracking-wider text-slate-500">Target role</p>
              <p className="text-white font-semibold">{summary.target_roles?.join(', ') || 'Not set'}</p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider text-slate-500">Experience</p>
              <p className="text-white font-semibold">{summary.experience_level}</p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider text-slate-500">Skills considered</p>
              <p className="text-white font-semibold">{summary.skills_count}</p>
            </div>
            {data?.availability && (
              <div>
                <p className="text-[10px] uppercase tracking-wider text-slate-500">Live listings</p>
                <p className="text-white font-semibold">{data.availability.active_listings}</p>
              </div>
            )}
          </div>
        </Card>
      )}

      <FiltersBar
        filters={filters}
        options={data?.filter_options}
        onChange={applyFilters}
        onClear={() => applyFilters(EMPTY_FILTERS)}
        disabled={refreshing || aiLoading}
      />

      {error && (
        <div className="rounded-2xl border border-rose-500/20 bg-rose-500/5 px-5 py-3.5 flex items-center justify-between gap-3" role="alert">
          <p className="text-sm text-rose-300">{error}</p>
          <RetryButton onClick={retry} />
        </div>
      )}

      {data?.availability?.providers_with_errors?.length > 0 && (
        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 px-5 py-3 text-sm text-amber-300 flex gap-2" role="status">
          <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
          Some listings may be missing: the last update from {data.availability.providers_with_errors.join(', ')} failed.
        </div>
      )}

      {data?.availability?.sync_running && (
        <div className="rounded-2xl border border-accent/20 bg-accent/5 px-5 py-3 text-sm text-accent flex gap-2" role="status" data-testid="sync-running-notice">
          <Loader2 className="h-4 w-4 flex-shrink-0 mt-0.5 animate-spin" />
          Job listings are being refreshed from the employers&apos; boards. New or withdrawn jobs will appear after you refresh.
        </div>
      )}

      {refreshing && (
        <div className="flex items-center gap-2 text-sm text-slate-400" data-testid="career-matching-refreshing">
          <Loader2 className="h-4 w-4 animate-spin text-accent" /> Updating matches…
        </div>
      )}

      {status === 'no_relevant_matches' ? (
        <StateMessage icon={Target} title="No relevant matches yet" description={data.message} testId="state-no-matches">
          {data.suggestions?.length > 0 && (
            <ul className="text-left text-sm text-slate-400 space-y-1.5 max-w-lg" data-testid="match-suggestions">
              {data.suggestions.map((tip) => (
                <li key={tip} className="flex gap-2"><Sparkles className="h-3.5 w-3.5 text-accent flex-shrink-0 mt-1" />{tip}</li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap justify-center gap-3">
            {Object.values(filters).some(Boolean) && <RetryButton onClick={() => applyFilters(EMPTY_FILTERS)} label="Clear filters" />}
            <PrimaryLink href="/dashboard/profile">Update your profile</PrimaryLink>
          </div>
        </StateMessage>
      ) : (
        <>
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
            <div>
              <h2 className="text-xl font-bold text-white">
                <span className="text-accent">{data?.total_matches ?? results.length}</span>{' '}
                {data?.total_matches === 1 ? 'matching job' : 'matching jobs'}
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">Ranked by match score. Scores are calculated from your profile, not by AI.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {page === 1 && (
                <button
                  type="button"
                  onClick={() => fetchMatches({ nextFilters: filters, nextPage: 1, includeAI: true })}
                  disabled={aiLoading || refreshing}
                  className="flex items-center gap-2 px-4 py-2 rounded-full text-xs font-medium border border-violet/30 text-violet-300 hover:border-violet/50 transition-all disabled:opacity-50"
                >
                  {aiLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Brain className="h-3.5 w-3.5" />}
                  {aiLoading ? 'Generating AI insights…' : 'Add AI insights'}
                </button>
              )}
              <button
                type="button"
                onClick={() => fetchMatches({ nextFilters: filters, nextPage: page })}
                disabled={refreshing || aiLoading}
                className="flex items-center gap-2 px-4 py-2 rounded-full text-xs font-medium border border-white/10 text-slate-300 hover:border-white/20 hover:text-white transition-all disabled:opacity-50"
                aria-label="Refresh career matches"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Refresh
              </button>
            </div>
          </div>

          {data?.qwen_status === 'unavailable' && (
            <p className="text-xs text-amber-300">AI insights are unavailable right now; match scores and reasons are unaffected.</p>
          )}

          <div className="space-y-5">
            {results.map((job, index) => <JobCard key={job.opportunity_id} job={job} index={index} />)}
          </div>

          {totalPages > 1 && (
            <nav className="flex items-center justify-center gap-3" aria-label="Pagination">
              <button
                type="button"
                onClick={() => goToPage(page - 1)}
                disabled={page <= 1 || refreshing}
                className="inline-flex items-center gap-1 px-4 py-2 rounded-full text-sm border border-white/10 text-slate-300 disabled:opacity-40"
              >
                <ChevronLeft className="h-4 w-4" /> Previous
              </button>
              <span className="text-sm text-slate-400">Page {page} of {totalPages}</span>
              <button
                type="button"
                onClick={() => goToPage(page + 1)}
                disabled={page >= totalPages || refreshing}
                className="inline-flex items-center gap-1 px-4 py-2 rounded-full text-sm border border-white/10 text-slate-300 disabled:opacity-40"
              >
                Next <ChevronRight className="h-4 w-4" />
              </button>
            </nav>
          )}
        </>
      )}

      <div className="rounded-2xl border border-white/8 bg-white/[0.02] px-5 py-4 flex items-start gap-3">
        <Shield className="h-4 w-4 text-slate-500 flex-shrink-0 mt-0.5" />
        <p className="text-xs text-slate-500 leading-relaxed">
          Listings are imported from each employer&apos;s public job board and link to the original posting. Details such as salary
          or experience are shown only when the employer publishes them.{' '}
          <Link href="/dashboard/profile" className="text-accent hover:text-accentSoft transition-colors">Update your profile</Link>{' '}
          to improve your matches.
        </p>
      </div>
    </div>
  );
}
