'use client';

/**
 * CareerMatchingPage — Phase 3.6 Frontend
 *
 * Presentation layer for the Career Matching pipeline.
 * Architecture rule: This component is strictly a display layer.
 * All matching, scoring, reranking (Gemini), and explanation (Qwen)
 * happen on the backend. The frontend only renders what the API returns.
 *
 * Pipeline (backend):
 *   PostgreSQL → Qdrant → Deterministic Engine → Gemini → Qwen → Redis
 *
 * Frontend responsibility: receive final_results and present them clearly.
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Briefcase,
  Sparkles,
  RefreshCw,
  AlertCircle,
  Loader2,
  ChevronDown,
  ChevronUp,
  MapPin,
  Wifi,
  Building2,
  Target,
  ArrowUpRight,
  CheckCircle2,
  XCircle,
  Star,
  Brain,
  TrendingUp,
  Award,
  Zap,
  Shield,
  BarChart2,
} from 'lucide-react';
import { getCareerMatching, extractErrorMessage } from '@/services/api';

// ─────────────────────────────────────────────────────────────────────────────
// Design-system primitives (matching SkillAnalysisPage conventions)
// ─────────────────────────────────────────────────────────────────────────────

/** Glass card wrapper */
function Card({ children, className = '' }) {
  return (
    <div
      className={`rounded-[1.75rem] border border-white/10 bg-white/[0.04] backdrop-blur-xl p-6 shadow-glow ${className}`}
    >
      {children}
    </div>
  );
}

/** Section heading with icon */
function SectionHeading({ icon: Icon, title, subtitle, accent = false, color }) {
  const iconBg = color
    ? ''
    : accent
    ? 'bg-accent/15 border-accent/30 text-accent'
    : 'bg-white/5 border-white/10 text-slate-400';

  return (
    <div className="flex items-start gap-3 mb-5">
      <div
        className={`flex-shrink-0 flex h-9 w-9 items-center justify-center rounded-xl border ${iconBg}`}
        style={color ? { backgroundColor: `${color}15`, borderColor: `${color}30`, color } : undefined}
      >
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <h2 className="text-base font-semibold text-white">{title}</h2>
        {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
      </div>
    </div>
  );
}

/** Skeleton pulse block */
function SkeletonBlock({ className = '' }) {
  return <div className={`animate-pulse bg-white/5 rounded-xl ${className}`} />;
}

/** Skill pill chip */
function SkillChip({ name, variant = 'matched' }) {
  const styles = {
    matched: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300',
    missing: 'bg-rose-500/10 border-rose-500/30 text-rose-300',
    strength: 'bg-violet/10 border-violet/30 text-violet-300',
    neutral: 'bg-white/5 border-white/10 text-slate-300',
  };
  return (
    <span
      className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border ${
        styles[variant] ?? styles.neutral
      }`}
    >
      {name}
    </span>
  );
}

/** Match score ring (SVG) */
function MatchScoreRing({ score }) {
  const r = 36;
  const circ = 2 * Math.PI * r;
  const pct = Math.min(100, Math.max(0, score));
  const offset = circ - (pct / 100) * circ;
  const color = pct >= 75 ? '#40d9ff' : pct >= 55 ? '#ff8f32' : '#9b7cff';

  return (
    <div className="relative w-24 h-24 flex-shrink-0">
      <svg viewBox="0 0 88 88" className="w-full h-full -rotate-90">
        <circle cx="44" cy="44" r={r} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="7" />
        <motion.circle
          cx="44"
          cy="44"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.2, ease: 'easeOut', delay: 0.15 }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <motion.span
          className="text-lg font-extrabold text-white leading-none"
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4, delay: 0.5 }}
        >
          {pct.toFixed(1)}%
        </motion.span>
        <span className="text-[9px] text-slate-400 font-medium mt-0.5">Match</span>
      </div>
    </div>
  );
}

/** Horizontal breakdown bar */
function BreakdownBar({ label, value, weight }) {
  const pct = Math.min(100, Math.max(0, value));
  const barColor =
    pct >= 80 ? 'from-cyan to-cyan/60' : pct >= 55 ? 'from-accent to-accentSoft' : 'from-violet to-violet/60';

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-300 font-medium">{label}</span>
        <div className="flex items-center gap-2">
          <span className="text-slate-500 text-[10px]">{weight}</span>
          <span className="text-white font-semibold tabular-nums w-10 text-right">
            {pct.toFixed(0)}%
          </span>
        </div>
      </div>
      <div className="h-1.5 w-full rounded-full bg-white/5 overflow-hidden">
        <motion.div
          className={`h-full rounded-full bg-gradient-to-r ${barColor}`}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.9, ease: 'easeOut', delay: 0.1 }}
        />
      </div>
    </div>
  );
}

/** Match summary badge */
function MatchSummaryBadge({ summary }) {
  const map = {
    'Strong Match': {
      cls: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300',
      icon: Award,
    },
    'Good Match': {
      cls: 'bg-cyan/15 border-cyan/30 text-cyan',
      icon: TrendingUp,
    },
    'Partial Match': {
      cls: 'bg-violet/15 border-violet/30 text-violet-300',
      icon: Zap,
    },
  };
  const cfg = map[summary] ?? {
    cls: 'bg-white/5 border-white/10 text-slate-300',
    icon: Star,
  };
  const Icon = cfg.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${cfg.cls}`}
    >
      <Icon className="h-3 w-3" />
      {summary}
    </span>
  );
}

/** Confidence badge for Gemini */
function ConfidenceBadge({ confidence }) {
  const map = {
    high: 'bg-emerald-500/10 border-emerald-500/25 text-emerald-300',
    medium: 'bg-amber-500/10 border-amber-500/25 text-amber-300',
    low: 'bg-slate-500/15 border-slate-500/25 text-slate-400',
  };
  return (
    <span
      className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border uppercase tracking-wide ${
        map[confidence] ?? map.low
      }`}
    >
      {confidence} confidence
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Loading skeleton
// ─────────────────────────────────────────────────────────────────────────────

function LoadingState() {
  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header skeleton */}
      <div className="space-y-3">
        <SkeletonBlock className="h-7 w-40" />
        <SkeletonBlock className="h-10 w-72 max-w-full" />
        <SkeletonBlock className="h-4 w-96 max-w-full" />
      </div>

      {/* Loading notice */}
      <div className="rounded-[1.75rem] border border-accent/20 bg-accent/5 p-6 flex items-start gap-4">
        <Loader2 className="h-5 w-5 text-accent animate-spin flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-accent">
            Analyzing your profile and finding your best opportunities…
          </p>
          <p className="text-xs text-slate-400 mt-1">
            This may take a moment while the AI reviews your career preferences and matches opportunities.
          </p>
        </div>
      </div>

      {/* Card skeletons */}
      <div className="space-y-5">
        {[...Array(3)].map((_, i) => (
          <div
            key={i}
            className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-6 space-y-4"
          >
            <div className="flex items-start gap-4">
              <SkeletonBlock className="h-24 w-24 rounded-full flex-shrink-0" />
              <div className="flex-1 space-y-2">
                <SkeletonBlock className="h-6 w-48" />
                <SkeletonBlock className="h-4 w-32" />
                <SkeletonBlock className="h-4 w-56" />
                <div className="flex gap-2 pt-1">
                  <SkeletonBlock className="h-6 w-16 rounded-full" />
                  <SkeletonBlock className="h-6 w-20 rounded-full" />
                  <SkeletonBlock className="h-6 w-14 rounded-full" />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Error state
// ─────────────────────────────────────────────────────────────────────────────

function ErrorState({ message, onRetry }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center py-24 text-center space-y-4 animate-fade-in">
      <div className="h-16 w-16 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center">
        <AlertCircle className="h-8 w-8 text-rose-400" />
      </div>
      <h2 className="text-xl font-bold text-white">Unable to load career matches</h2>
      <p className="text-sm text-slate-400 max-w-sm leading-relaxed">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-accent text-black text-sm font-semibold shadow-[0_8px_30px_rgba(255,143,50,0.3)] hover:bg-accentSoft transition-all"
      >
        <RefreshCw className="h-4 w-4" />
        Retry
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Empty / no-profile / no-target-role states
// ─────────────────────────────────────────────────────────────────────────────

function EmptyState({ icon: Icon, title, description, linkLabel, linkHref }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center py-24 text-center space-y-5 animate-fade-in">
      <div className="h-20 w-20 rounded-3xl bg-white/5 border border-white/10 flex items-center justify-center">
        <Icon className="h-10 w-10 text-slate-500" />
      </div>
      <div className="space-y-2">
        <h2 className="text-xl font-bold text-white">{title}</h2>
        <p className="text-sm text-slate-400 max-w-md mx-auto leading-relaxed">{description}</p>
      </div>
      {linkHref && (
        <Link
          href={linkHref}
          className="inline-flex items-center gap-2 px-6 py-2.5 rounded-full bg-accent text-black text-sm font-semibold shadow-[0_8px_30px_rgba(255,143,50,0.3)] hover:bg-accentSoft transition-all"
        >
          {linkLabel}
          <ArrowUpRight className="h-4 w-4" />
        </Link>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// AI status banner (qwen/gemini unavailable)
// ─────────────────────────────────────────────────────────────────────────────

function AIStatusBanner({ qwenStatus, geminiStatus, usedDeterministicFallback }) {
  const messages = [];
  if (geminiStatus !== 'success' && geminiStatus !== 'not_configured') {
    messages.push('Semantic reranking is temporarily unavailable — showing deterministic ranking.');
  }
  if (qwenStatus === 'unavailable') {
    messages.push('AI career insights are temporarily unavailable. Match scores and breakdowns are still accurate.');
  }
  if (!messages.length) return null;

  return (
    <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 px-5 py-3.5 flex items-start gap-3">
      <AlertCircle className="h-4 w-4 text-amber-400 flex-shrink-0 mt-0.5" />
      <div className="space-y-0.5">
        {messages.map((m, i) => (
          <p key={i} className="text-sm text-amber-300">
            {i === 0 && <span className="font-semibold">Note: </span>}
            {m}
          </p>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Individual opportunity card
// ─────────────────────────────────────────────────────────────────────────────

function OpportunityCard({ result, index }) {
  const [expanded, setExpanded] = useState(false);
  const [showBreakdown, setShowBreakdown] = useState(false);

  const { breakdown, explanation } = result;
  const hasExplanation = !!explanation;
  const hasMatchedSkills = breakdown?.matched_required_skills?.length > 0;
  const hasMissingSkills = breakdown?.missing_required_skills?.length > 0;
  const hasMatchedPreferred = breakdown?.matched_preferred_skills?.length > 0;
  const hasMissingPreferred = breakdown?.missing_preferred_skills?.length > 0;

  // Opportunity type & experience level display
  const typeParts = [
    result.is_remote ? 'Remote' : result.location || null,
    result.opportunity_type
      ? result.opportunity_type.charAt(0).toUpperCase() + result.opportunity_type.slice(1)
      : null,
    result.experience_level || null,
  ].filter(Boolean);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.07 }}
      className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] backdrop-blur-xl shadow-glow overflow-hidden"
    >
      {/* ── Card header ── */}
      <div className="p-5 sm:p-6">
        <div className="flex flex-col sm:flex-row sm:items-start gap-5">
          {/* Score ring */}
          <MatchScoreRing score={result.deterministic_score} />

          {/* Core info */}
          <div className="flex-1 min-w-0 space-y-2">
            {/* Rank badge */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="px-2.5 py-0.5 rounded-full bg-accent/10 border border-accent/25 text-accent text-[10px] font-bold uppercase tracking-wide">
                #{result.semantic_rank} Best Match
              </span>
              {explanation?.match_summary && (
                <MatchSummaryBadge summary={explanation.match_summary} />
              )}
            </div>

            {/* Title & company */}
            <div>
              <h3 className="text-xl font-bold text-white leading-snug truncate">
                {result.title || 'Untitled Opportunity'}
              </h3>
              <div className="flex items-center gap-1.5 mt-0.5">
                <Building2 className="h-3.5 w-3.5 text-slate-400 flex-shrink-0" />
                <span className="text-sm text-slate-300 font-medium truncate">
                  {result.company || 'Company not specified'}
                </span>
              </div>
            </div>

            {/* Meta pills */}
            <div className="flex flex-wrap gap-1.5 pt-0.5">
              {/* Location/remote */}
              {result.is_remote ? (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-cyan/10 border border-cyan/20 text-cyan">
                  <Wifi className="h-3 w-3" />
                  Remote
                </span>
              ) : result.location ? (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-white/5 border border-white/10 text-slate-300">
                  <MapPin className="h-3 w-3" />
                  {result.location}
                </span>
              ) : null}

              {/* Opportunity type */}
              {result.opportunity_type && (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-white/5 border border-white/10 text-slate-300 capitalize">
                  {result.opportunity_type}
                </span>
              )}

              {/* Experience level */}
              {result.experience_level && (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-white/5 border border-white/10 text-slate-300">
                  {result.experience_level}
                </span>
              )}

              {/* Target role */}
              {result.target_role && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-violet/10 border border-violet/20 text-violet-300">
                  <Target className="h-3 w-3" />
                  {result.target_role}
                </span>
              )}

              {/* Industry */}
              {result.industry && (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-white/5 border border-white/10 text-slate-400">
                  {result.industry}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* ── Quick skill summary ── */}
        {(hasMatchedSkills || hasMissingSkills) && (
          <div className="mt-5 pt-5 border-t border-white/8 grid grid-cols-1 sm:grid-cols-2 gap-4">
            {hasMatchedSkills && (
              <div>
                <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium mb-2 flex items-center gap-1.5">
                  <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                  Matched Skills
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {breakdown.matched_required_skills.slice(0, 6).map((s) => (
                    <SkillChip key={s} name={s} variant="matched" />
                  ))}
                  {breakdown.matched_required_skills.length > 6 && (
                    <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-white/5 border border-white/10 text-slate-400">
                      +{breakdown.matched_required_skills.length - 6} more
                    </span>
                  )}
                </div>
              </div>
            )}
            {hasMissingSkills && (
              <div>
                <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium mb-2 flex items-center gap-1.5">
                  <XCircle className="h-3 w-3 text-rose-400" />
                  Skill Gaps
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {breakdown.missing_required_skills.slice(0, 5).map((s) => (
                    <SkillChip key={s} name={s} variant="missing" />
                  ))}
                  {breakdown.missing_required_skills.length > 5 && (
                    <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-white/5 border border-white/10 text-slate-400">
                      +{breakdown.missing_required_skills.length - 5} more
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Action row ── */}
        <div className="mt-5 flex flex-wrap items-center gap-3">
          {/* Apply button */}
          {result.application_url ? (
            <a
              href={result.application_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-accent text-black text-sm font-semibold shadow-[0_8px_30px_rgba(255,143,50,0.3)] hover:bg-accentSoft hover:-translate-y-0.5 transition-all"
            >
              Apply Now
              <ArrowUpRight className="h-4 w-4" />
            </a>
          ) : (
            <span className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium border border-white/10 text-slate-500 cursor-not-allowed select-none">
              Application link unavailable
            </span>
          )}

          {/* Details toggle */}
          <button
            type="button"
            onClick={() => setExpanded((prev) => !prev)}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-full text-sm font-medium border border-white/10 text-slate-200 hover:border-white/20 hover:text-white transition-all"
            aria-expanded={expanded}
            aria-label={expanded ? 'Hide details' : 'View details'}
          >
            {expanded ? (
              <>
                Hide Details <ChevronUp className="h-4 w-4" />
              </>
            ) : (
              <>
                View Details <ChevronDown className="h-4 w-4" />
              </>
            )}
          </button>
        </div>
      </div>

      {/* ── Expanded details panel ── */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="border-t border-white/8 px-5 sm:px-6 py-6 space-y-6">

              {/* ── Match breakdown ── */}
              {breakdown && (
                <div>
                  <button
                    type="button"
                    onClick={() => setShowBreakdown((p) => !p)}
                    className="flex items-center gap-2 w-full text-left mb-4 group"
                    aria-expanded={showBreakdown}
                  >
                    <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-accent/15 border border-accent/30">
                      <BarChart2 className="h-4 w-4 text-accent" />
                    </div>
                    <span className="text-sm font-semibold text-white group-hover:text-accent transition-colors">
                      Match Breakdown
                    </span>
                    <span className="ml-auto text-slate-500 group-hover:text-slate-300 transition-colors">
                      {showBreakdown ? (
                        <ChevronUp className="h-4 w-4" />
                      ) : (
                        <ChevronDown className="h-4 w-4" />
                      )}
                    </span>
                  </button>

                  <AnimatePresence>
                    {showBreakdown && (
                      <motion.div
                        initial={{ opacity: 0, y: -6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        transition={{ duration: 0.2 }}
                        className="rounded-2xl bg-slate-950/60 border border-white/8 p-5 space-y-4"
                      >
                        <BreakdownBar
                          label="Required Skills"
                          value={breakdown.required_skill_score}
                          weight="35%"
                        />
                        <BreakdownBar
                          label="Preferred Skills"
                          value={breakdown.preferred_skill_score}
                          weight="15%"
                        />
                        <BreakdownBar
                          label="Target Role"
                          value={breakdown.target_role_score}
                          weight="15%"
                        />
                        <BreakdownBar
                          label="Experience"
                          value={breakdown.experience_score}
                          weight="12%"
                        />
                        <BreakdownBar
                          label="Location / Remote"
                          value={breakdown.location_remote_score}
                          weight="8%"
                        />
                        <BreakdownBar
                          label="Career Preferences"
                          value={breakdown.career_preference_score}
                          weight="15%"
                        />

                        {/* Preferred skill chips */}
                        {(hasMatchedPreferred || hasMissingPreferred) && (
                          <div className="pt-3 border-t border-white/8 grid grid-cols-1 sm:grid-cols-2 gap-4">
                            {hasMatchedPreferred && (
                              <div>
                                <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium mb-2">
                                  Matched Preferred
                                </p>
                                <div className="flex flex-wrap gap-1.5">
                                  {breakdown.matched_preferred_skills.map((s) => (
                                    <SkillChip key={s} name={s} variant="matched" />
                                  ))}
                                </div>
                              </div>
                            )}
                            {hasMissingPreferred && (
                              <div>
                                <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium mb-2">
                                  Missing Preferred
                                </p>
                                <div className="flex flex-wrap gap-1.5">
                                  {breakdown.missing_preferred_skills.map((s) => (
                                    <SkillChip key={s} name={s} variant="missing" />
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )}

              {/* ── Gemini AI Context ── */}
              {result.rerank_reason && (
                <div className="rounded-2xl bg-slate-950/60 border border-white/8 p-5 space-y-3">
                  <div className="flex items-center gap-3 flex-wrap">
                    <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-cyan/10 border border-cyan/20">
                      <Sparkles className="h-4 w-4 text-cyan" />
                    </div>
                    <span className="text-sm font-semibold text-white">AI Context</span>
                    <span className="text-xs font-mono text-cyan">
                      Rank #{result.semantic_rank}
                    </span>
                    {result.confidence && <ConfidenceBadge confidence={result.confidence} />}
                  </div>
                  <div className="pl-11">
                    <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium mb-1.5">
                      Why this opportunity was ranked here
                    </p>
                    <p className="text-sm text-slate-300 leading-relaxed">
                      {result.rerank_reason}
                    </p>
                  </div>
                </div>
              )}

              {/* ── Qwen AI Career Insight ── */}
              {hasExplanation ? (
                <div className="rounded-2xl border border-violet/20 bg-violet/[0.04] p-5 space-y-4">
                  {/* Header */}
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-violet/15 border border-violet/30">
                      <Brain className="h-4 w-4 text-violet-300" />
                    </div>
                    <div>
                      <span className="text-sm font-semibold text-white">AI Career Insight</span>
                      <p className="text-[10px] text-slate-400">
                        Powered by Qwen · Grounded in your profile &amp; match data
                      </p>
                    </div>
                    {explanation.match_summary && (
                      <div className="ml-auto">
                        <MatchSummaryBadge summary={explanation.match_summary} />
                      </div>
                    )}
                  </div>

                  {/* Why this matches */}
                  {explanation.why_match && (
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium mb-1.5 flex items-center gap-1.5">
                        <Target className="h-3 w-3" />
                        Why this matches you
                      </p>
                      <p className="text-sm text-slate-300 leading-relaxed">
                        {explanation.why_match}
                      </p>
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {/* Strengths */}
                    {explanation.strengths?.length > 0 && (
                      <div>
                        <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium mb-2 flex items-center gap-1.5">
                          <Award className="h-3 w-3 text-violet-400" />
                          Your strengths
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {explanation.strengths.map((s) => (
                            <SkillChip key={s} name={s} variant="strength" />
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Skill gaps */}
                    {explanation.skill_gaps?.length > 0 && (
                      <div>
                        <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium mb-2 flex items-center gap-1.5">
                          <Zap className="h-3 w-3 text-rose-400" />
                          Skill gaps
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {explanation.skill_gaps.map((s) => (
                            <SkillChip key={s} name={s} variant="missing" />
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Recommendation */}
                  {explanation.recommendation && (
                    <div className="rounded-xl bg-slate-950/50 border border-white/8 px-4 py-3">
                      <p className="text-[10px] uppercase tracking-wider text-slate-500 font-medium mb-1.5">
                        Recommendation
                      </p>
                      <p className="text-sm text-slate-300 leading-relaxed">
                        {explanation.recommendation}
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                /* AI insight section omitted when unavailable — per spec */
                null
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main page component
// ─────────────────────────────────────────────────────────────────────────────

export default function CareerMatchingPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const fetchedRef = useRef(false);

  const fetchMatches = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getCareerMatching(true);
      setData(result);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;
    fetchMatches();
  }, [fetchMatches]);

  // ── Loading ──────────────────────────────────────────────────────────────
  if (loading) return <LoadingState />;

  // ── Error ────────────────────────────────────────────────────────────────
  if (error) {
    return (
      <ErrorState
        message={error}
        onRetry={() => {
          fetchedRef.current = false;
          fetchMatches();
        }}
      />
    );
  }

  // ── No profile ───────────────────────────────────────────────────────────
  if (data?.status === 'no_profile') {
    return (
      <EmptyState
        icon={Briefcase}
        title="Profile Not Found"
        description="Set up your profile to get personalised career matches. Add your skills, experience, and career preferences to get started."
        linkLabel="Set Up Your Profile"
        linkHref="/dashboard/profile"
      />
    );
  }

  // ── No target role ───────────────────────────────────────────────────────
  if (data?.status === 'no_target_role') {
    return (
      <EmptyState
        icon={Target}
        title="No Target Role Configured"
        description="Set a Target Role in your Career Preferences so CareerSphere can match you against real opportunities."
        linkLabel="Go to Career Preferences"
        linkHref="/dashboard/profile"
      />
    );
  }

  // ── No results ───────────────────────────────────────────────────────────
  if (!data?.final_results?.length) {
    return (
      <EmptyState
        icon={Briefcase}
        title="No Matching Opportunities Found"
        description="Try updating your target role, skills, experience, or career preferences. More opportunities are regularly added to the platform."
        linkLabel="Update Your Profile"
        linkHref="/dashboard/profile"
      />
    );
  }

  const {
    target_role,
    final_results = [],
    gemini_status,
    qwen_status,
    used_deterministic_fallback,
    cache,
  } = data;

  return (
    <div className="space-y-8 animate-fade-in">

      {/* ── Page header ──────────────────────────────────────────────────── */}
      <div>
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent/10 border border-accent/30 text-accent text-xs font-semibold mb-3">
          <Briefcase className="h-3.5 w-3.5" />
          <span>Career Matching</span>
        </div>

        <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
          Career{' '}
          <span className="bg-gradient-to-r from-accent via-accentSoft to-cyan bg-clip-text text-transparent">
            Opportunities
          </span>
        </h1>
        <p className="mt-2 text-slate-400 text-sm max-w-2xl">
          Personalised opportunities based on your profile, skills, experience, and career
          preferences.
        </p>
      </div>

      {/* ── Target role card ─────────────────────────────────────────────── */}
      <Card>
        <div className="flex flex-col sm:flex-row sm:items-center gap-5">
          {/* Target role */}
          <div className="flex-1">
            <SectionHeading icon={Target} title="Target Role" accent />
            <p className="text-2xl font-bold text-white pl-12 -mt-3">
              {target_role}
            </p>
          </div>

          {/* Pipeline info */}
          <div className="flex flex-wrap gap-3 sm:justify-end">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-950/60 border border-white/8 text-xs">
              <Shield className="h-3.5 w-3.5 text-accent" />
              <span className="text-slate-400">Deterministic engine</span>
              <span className="text-emerald-400 font-semibold">Active</span>
            </div>
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-950/60 border border-white/8 text-xs">
              <Sparkles className="h-3.5 w-3.5 text-cyan" />
              <span className="text-slate-400">AI reranking</span>
              <span
                className={`font-semibold ${
                  gemini_status === 'success' ? 'text-emerald-400' : 'text-amber-400'
                }`}
              >
                {gemini_status === 'success' ? 'Active' : 'Fallback'}
              </span>
            </div>
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-950/60 border border-white/8 text-xs">
              <Brain className="h-3.5 w-3.5 text-violet-400" />
              <span className="text-slate-400">AI insights</span>
              <span
                className={`font-semibold ${
                  qwen_status === 'success' ? 'text-emerald-400' : 'text-amber-400'
                }`}
              >
                {qwen_status === 'success' ? 'Active' : qwen_status === 'skipped' ? 'Skipped' : 'Unavailable'}
              </span>
            </div>
            {cache?.hit && (
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs">
                <TrendingUp className="h-3.5 w-3.5 text-emerald-400" />
                <span className="text-emerald-300 font-medium">Cached result</span>
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* ── AI status banner ─────────────────────────────────────────────── */}
      <AIStatusBanner
        qwenStatus={qwen_status}
        geminiStatus={gemini_status}
        usedDeterministicFallback={used_deterministic_fallback}
      />

      {/* ── Results header ───────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-white">
            Your Top{' '}
            <span className="text-accent">{final_results.length}</span>{' '}
            {final_results.length === 1 ? 'Match' : 'Matches'}
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Opportunities ranked using your profile, skills, and career preferences.
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            fetchedRef.current = false;
            fetchMatches();
          }}
          className="flex items-center gap-2 px-4 py-2 rounded-full text-xs font-medium border border-white/10 text-slate-300 hover:border-white/20 hover:text-white transition-all self-start sm:self-auto"
          aria-label="Refresh career matches"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {/* ── Opportunity cards ────────────────────────────────────────────── */}
      <div className="space-y-5">
        {final_results.map((result, index) => (
          <OpportunityCard
            key={result.opportunity_id}
            result={result}
            index={index}
          />
        ))}
      </div>

      {/* ── Footer note ──────────────────────────────────────────────────── */}
      <div className="rounded-2xl border border-white/8 bg-white/[0.02] px-5 py-4 flex items-start gap-3">
        <Shield className="h-4 w-4 text-slate-500 flex-shrink-0 mt-0.5" />
        <p className="text-xs text-slate-500 leading-relaxed">
          Match scores are calculated by CareerSphere&apos;s deterministic engine using your
          profile data from PostgreSQL. AI insights from Gemini and Qwen are explanatory only
          and do not modify your scores.{' '}
          <Link href="/dashboard/profile" className="text-accent hover:text-accentSoft transition-colors">
            Update your profile
          </Link>{' '}
          to refresh your matches.
        </p>
      </div>
    </div>
  );
}
