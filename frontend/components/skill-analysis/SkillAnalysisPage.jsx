'use client';

/**
 * SkillAnalysisPage — Phase 2C
 *
 * Presentation layer for the Phase 2A deterministic skill analysis and
 * Phase 2B Qwen AI insights.
 *
 * Architecture rule: This component is strictly a display layer.
 * All skill ownership, coverage calculation, role resolution, and AI
 * prioritisation happen on the backend.  The frontend renders what the
 * API returns and nothing more.
 */

import React, { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BarChart2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Sparkles,
  Target,
  BookOpen,
  ListOrdered,
  Map,
  RefreshCw,
  ChevronRight,
  Loader2,
  Zap,
  TrendingUp,
  Star,
  ArrowRight,
  Filter,
  Brain,
  Award,
} from 'lucide-react';
import { getSkillAnalysis, extractErrorMessage } from '@/services/api';

// ---------------------------------------------------------------------------
// Small reusable sub-components (defined at bottom to keep export at top)
// ---------------------------------------------------------------------------

/**
 * Animated SVG ring for coverage percentages.
 * pct is exactly the integer from coverage.required_pct / overall_pct / recommended_pct.
 */
function CoverageRing({ pct, label, color, trackColor = 'rgba(255,255,255,0.07)' }) {
  const r = 52;
  const circ = 2 * Math.PI * r;
  const offset = circ - (Math.min(100, Math.max(0, pct)) / 100) * circ;

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative w-36 h-36">
        <svg viewBox="0 0 128 128" className="w-full h-full -rotate-90">
          {/* Track */}
          <circle cx="64" cy="64" r={r} fill="none" stroke={trackColor} strokeWidth="10" />
          {/* Progress */}
          <motion.circle
            cx="64"
            cy="64"
            r={r}
            fill="none"
            stroke={color}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={circ}
            initial={{ strokeDashoffset: circ }}
            animate={{ strokeDashoffset: offset }}
            transition={{ duration: 1.4, ease: 'easeOut', delay: 0.2 }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <motion.span
            className="text-2xl font-extrabold text-white"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, delay: 0.6 }}
          >
            {pct}%
          </motion.span>
        </div>
      </div>
      <span className="text-sm font-medium text-slate-300 text-center">{label}</span>
    </div>
  );
}

/** Pill badge for a skill chip */
function SkillChip({ name, variant = 'have' }) {
  const styles = {
    have: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300',
    missing_required: 'bg-rose-500/10 border-rose-500/30 text-rose-300',
    missing_recommended: 'bg-amber-500/10 border-amber-500/30 text-amber-300',
    strength: 'bg-violet/10 border-violet/30 text-violet-300',
    neutral: 'bg-white/5 border-white/10 text-slate-300',
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${styles[variant] ?? styles.neutral}`}
    >
      {name}
    </span>
  );
}

/** Priority badge for AI priority gaps */
function PriorityBadge({ priority }) {
  const map = {
    high: { label: 'High', cls: 'bg-rose-500/15 text-rose-300 border-rose-500/30' },
    medium: { cls: 'bg-amber-500/15 text-amber-300 border-amber-500/30', label: 'Medium' },
    low: { cls: 'bg-slate-500/20 text-slate-300 border-slate-500/30', label: 'Low' },
  };
  const { label, cls } = map[priority] ?? map.low;
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${cls}`}>
      {label}
    </span>
  );
}

/** Section card wrapper */
function Card({ children, className = '' }) {
  return (
    <div
      className={`rounded-[1.75rem] border border-white/10 bg-white/[0.04] backdrop-blur-xl p-6 shadow-glow ${className}`}
    >
      {children}
    </div>
  );
}

/** Section heading */
function SectionHeading({ icon: Icon, title, subtitle, accent = false }) {
  return (
    <div className="flex items-start gap-3 mb-5">
      <div
        className={`flex-shrink-0 flex h-9 w-9 items-center justify-center rounded-xl ${
          accent
            ? 'bg-accent/15 border border-accent/30 text-accent'
            : 'bg-white/5 border border-white/10 text-slate-400'
        }`}
      >
        <Icon className="h-4.5 w-4.5" />
      </div>
      <div>
        <h2 className="text-base font-semibold text-white">{title}</h2>
        {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
      </div>
    </div>
  );
}

/** Filter pill button for the skill table */
function FilterPill({ label, active, onClick, count }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
        active
          ? 'bg-accent text-black shadow-[0_4px_20px_rgba(255,143,50,0.3)]'
          : 'border border-white/10 text-slate-400 hover:border-white/20 hover:text-white'
      }`}
    >
      {label}
      {count !== undefined && (
        <span
          className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
            active ? 'bg-black/20' : 'bg-white/10'
          }`}
        >
          {count}
        </span>
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Skeleton loading cards
// ---------------------------------------------------------------------------

function SkeletonBlock({ className = '' }) {
  return (
    <div className={`animate-pulse bg-white/5 rounded-xl ${className}`} />
  );
}

function LoadingState() {
  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header skeleton */}
      <div className="space-y-3">
        <SkeletonBlock className="h-8 w-48" />
        <SkeletonBlock className="h-4 w-96 max-w-full" />
      </div>

      {/* Loading notice */}
      <div className="rounded-[1.75rem] border border-accent/20 bg-accent/5 p-6 flex items-start gap-4">
        <Loader2 className="h-5 w-5 text-accent animate-spin flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-accent">
            Analyzing your skills and preparing personalized AI insights…
          </p>
          <p className="text-xs text-slate-400 mt-1">
            This may take a few minutes while the AI reviews your career gaps.
          </p>
        </div>
      </div>

      {/* Cards skeleton grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {[...Array(3)].map((_, i) => (
          <Card key={i} className="space-y-4">
            <SkeletonBlock className="h-5 w-24" />
            <div className="flex justify-center py-4">
              <SkeletonBlock className="h-36 w-36 rounded-full" />
            </div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {[...Array(3)].map((_, i) => (
          <Card key={i} className="space-y-3">
            <SkeletonBlock className="h-5 w-32" />
            {[...Array(4)].map((_, j) => (
              <SkeletonBlock key={j} className="h-8 w-full" />
            ))}
          </Card>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

function ErrorState({ message, onRetry }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center py-24 text-center space-y-4 animate-fade-in">
      <div className="h-16 w-16 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center">
        <AlertCircle className="h-8 w-8 text-rose-400" />
      </div>
      <h2 className="text-xl font-bold text-white">Unable to load skill analysis</h2>
      <p className="text-sm text-slate-400 max-w-sm">{message}</p>
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

// ---------------------------------------------------------------------------
// Empty states
// ---------------------------------------------------------------------------

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
          <ArrowRight className="h-4 w-4" />
        </Link>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main SkillAnalysisPage
// ---------------------------------------------------------------------------

export default function SkillAnalysisPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [skillFilter, setSkillFilter] = useState('all');

  const fetchAnalysis = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getSkillAnalysis(true);
      setData(result);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAnalysis();
  }, [fetchAnalysis]);

  // ── Loading ──────────────────────────────────────────────────────────────
  if (loading) return <LoadingState />;

  // ── Error ────────────────────────────────────────────────────────────────
  if (error) return <ErrorState message={error} onRetry={fetchAnalysis} />;

  // ── No target role ───────────────────────────────────────────────────────
  if (data?.status === 'no_target_role') {
    return (
      <EmptyState
        icon={Target}
        title="No Target Role Configured"
        description="Set a Target Role in your Career Preferences to generate your personalised skill analysis. CareerSphere will map your skills against the career knowledge base and identify your gaps."
        linkLabel="Go to Career Preferences"
        linkHref="/dashboard/profile"
      />
    );
  }

  // ── No match ─────────────────────────────────────────────────────────────
  if (data?.status === 'no_match') {
    return (
      <EmptyState
        icon={AlertCircle}
        title="Target Role Not Recognised"
        description={`"${data.target_role}" could not be mapped to the available career knowledge base. Try updating your Target Role to a recognised career title such as "Backend Engineer" or "Data Scientist".`}
        linkLabel="Update Career Preferences"
        linkHref="/dashboard/profile"
      />
    );
  }

  // ── Full analysis (status === "ok") ──────────────────────────────────────
  const {
    target_role,
    resolved_roles = [],
    resolution_method,
    resolution_scores = {},
    required_skills = [],
    recommended_skills = [],
    skills_have = [],
    skills_missing_required = [],
    skills_missing_recommended = [],
    coverage,
    ai_insights,
    ai_status,
  } = data ?? {};

  // Build combined skill list for the filterable table
  const allSkills = [
    ...required_skills.map((s) => ({ ...s, tier: 'required' })),
    ...recommended_skills.map((s) => ({ ...s, tier: 'recommended' })),
  ];

  const filteredSkills = allSkills.filter((s) => {
    if (skillFilter === 'all') return true;
    if (skillFilter === 'have') return s.have;
    if (skillFilter === 'missing') return !s.have;
    if (skillFilter === 'required') return s.tier === 'required';
    if (skillFilter === 'recommended') return s.tier === 'recommended';
    return true;
  });

  const counts = {
    all: allSkills.length,
    have: allSkills.filter((s) => s.have).length,
    missing: allSkills.filter((s) => !s.have).length,
    required: allSkills.filter((s) => s.tier === 'required').length,
    recommended: allSkills.filter((s) => s.tier === 'recommended').length,
  };

  const aiOk = ai_status === 'ok' && ai_insights;
  const aiUnavailable = ai_status === 'unavailable';

  return (
    <div className="space-y-8 animate-fade-in">

      {/* ── Page Header ─────────────────────────────────────────────────── */}
      <div>
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent/10 border border-accent/30 text-accent text-xs font-semibold mb-3">
          <BarChart2 className="h-3.5 w-3.5" />
          <span>Skill Analysis</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
          Career{' '}
          <span className="bg-gradient-to-r from-accent via-accentSoft to-cyan bg-clip-text text-transparent">
            Skill Analysis
          </span>
        </h1>
        <p className="mt-2 text-slate-400 text-sm max-w-2xl">
          CareerSphere compares your current skills and projects against the requirements of your
          target career, then uses AI to prioritise your gaps and build a personalised learning roadmap.
        </p>
      </div>

      {/* ── AI Unavailable Banner ────────────────────────────────────────── */}
      {aiUnavailable && (
        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 px-5 py-3.5 flex items-start gap-3">
          <AlertCircle className="h-4.5 w-4.5 text-amber-400 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-amber-300">
            <span className="font-semibold">AI insights are temporarily unavailable.</span>{' '}
            Your skill analysis is still fully available below.
          </p>
        </div>
      )}

      {/* ── Target Career Card ───────────────────────────────────────────── */}
      <Card>
        <SectionHeading icon={Target} title="Target Career" accent />

        <div className="flex flex-col sm:flex-row sm:items-start gap-6">
          {/* Target role */}
          <div className="flex-1">
            <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Target Role</p>
            <p className="text-2xl font-bold text-white">{target_role}</p>
          </div>

          {/* Resolved roles */}
          {resolved_roles.length > 0 && (
            <div className="flex-1">
              <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">
                Analysed Roles
                {resolution_method === 'semantic' && (
                  <span className="ml-2 px-2 py-0.5 rounded-full bg-cyan/10 border border-cyan/20 text-cyan text-[10px] font-medium">
                    AI Matched
                  </span>
                )}
              </p>
              <div className="flex flex-wrap gap-2">
                {resolved_roles.map((role) => (
                  <div
                    key={role}
                    className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-950/60 border border-white/10"
                  >
                    <span className="text-sm font-semibold text-white">{role}</span>
                    {resolution_scores[role] !== undefined && resolution_method === 'semantic' && (
                      <span className="text-[10px] text-slate-500 font-mono">
                        {Math.round(resolution_scores[role] * 100)}%
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* ── Coverage Overview ────────────────────────────────────────────── */}
      {coverage && (
        <Card>
          <SectionHeading
            icon={TrendingUp}
            title="Skill Coverage"
            subtitle="Percentage of required and recommended skills currently in your profile"
            accent
          />
          <div className="grid grid-cols-3 gap-4 py-2">
            <CoverageRing
              pct={coverage.overall_pct}
              label="Overall"
              color="#ff8f32"
            />
            <CoverageRing
              pct={coverage.required_pct}
              label="Required"
              color="#40d9ff"
            />
            <CoverageRing
              pct={coverage.recommended_pct}
              label="Recommended"
              color="#9b7cff"
            />
          </div>
        </Card>
      )}

      {/* ── Skills Grid ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">

        {/* Your Skills */}
        <Card>
          <SectionHeading icon={CheckCircle2} title="Your Skills" />
          {skills_have.length === 0 ? (
            <p className="text-sm text-slate-500 italic">No matching skills found in your profile yet.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {skills_have.map((s) => (
                <SkillChip key={s} name={s} variant="have" />
              ))}
            </div>
          )}
        </Card>

        {/* Missing Required */}
        <Card>
          <SectionHeading icon={XCircle} title="Missing Required" />
          {skills_missing_required.length === 0 ? (
            <div className="flex items-start gap-2.5">
              <CheckCircle2 className="h-4.5 w-4.5 text-emerald-400 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-emerald-300">
                Great — you currently have all required skills for this career direction.
              </p>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {skills_missing_required.map((s) => (
                <SkillChip key={s} name={s} variant="missing_required" />
              ))}
            </div>
          )}
        </Card>

        {/* Missing Recommended */}
        <Card>
          <SectionHeading icon={Star} title="Recommended to Gain" />
          {skills_missing_recommended.length === 0 ? (
            <div className="flex items-start gap-2.5">
              <CheckCircle2 className="h-4.5 w-4.5 text-emerald-400 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-emerald-300">
                You have all recommended skills for this career direction.
              </p>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {skills_missing_recommended.map((s) => (
                <SkillChip key={s} name={s} variant="missing_recommended" />
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* ── Detailed Skill Table ──────────────────────────────────────────── */}
      {allSkills.length > 0 && (
        <Card>
          <SectionHeading
            icon={Filter}
            title="All Skills"
            subtitle="Full breakdown of required and recommended skills for your target career"
          />

          {/* Filter pills */}
          <div className="flex flex-wrap gap-2 mb-5">
            {[
              { key: 'all', label: 'All' },
              { key: 'have', label: 'Have' },
              { key: 'missing', label: 'Missing' },
              { key: 'required', label: 'Required' },
              { key: 'recommended', label: 'Recommended' },
            ].map(({ key, label }) => (
              <FilterPill
                key={key}
                label={label}
                active={skillFilter === key}
                onClick={() => setSkillFilter(key)}
                count={counts[key]}
              />
            ))}
          </div>

          {/* Skill rows */}
          <div className="space-y-2">
            <AnimatePresence mode="popLayout">
              {filteredSkills.length === 0 ? (
                <p className="text-sm text-slate-500 italic py-4 text-center">No skills match this filter.</p>
              ) : (
                filteredSkills.map((skill) => (
                  <motion.div
                    key={`${skill.tier}-${skill.name}`}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.15 }}
                    className="flex items-center justify-between px-4 py-3 rounded-xl bg-slate-950/50 border border-white/5 hover:border-white/10 transition-colors"
                  >
                    {/* Skill info */}
                    <div className="flex items-center gap-3 min-w-0">
                      <div
                        className={`flex-shrink-0 h-2 w-2 rounded-full ${
                          skill.have ? 'bg-emerald-400' : 'bg-rose-400'
                        }`}
                      />
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-white truncate">{skill.name}</p>
                        <p className="text-xs text-slate-500 capitalize">{skill.category}</p>
                      </div>
                    </div>

                    {/* Badges */}
                    <div className="flex items-center gap-2 flex-shrink-0 ml-3">
                      <span
                        className={`hidden sm:inline-block px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                          skill.tier === 'required'
                            ? 'bg-cyan/10 border-cyan/20 text-cyan'
                            : 'bg-violet/10 border-violet/30 text-violet-300'
                        }`}
                      >
                        {skill.tier === 'required' ? 'Required' : 'Recommended'}
                      </span>
                      <span
                        className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                          skill.have
                            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                            : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                        }`}
                      >
                        {skill.have ? (
                          <>
                            <CheckCircle2 className="h-3 w-3" /> Have
                          </>
                        ) : (
                          <>
                            <XCircle className="h-3 w-3" /> Missing
                          </>
                        )}
                      </span>
                    </div>
                  </motion.div>
                ))
              )}
            </AnimatePresence>
          </div>
        </Card>
      )}

      {/* ── AI Insights (only when ai_status === "ok") ───────────────────── */}
      {aiOk && (
        <div className="space-y-5">
          {/* AI Insights header */}
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-violet/10 border border-violet/30">
              <Brain className="h-4 w-4 text-violet-300" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">AI Insights</h2>
              <p className="text-xs text-slate-400">Powered by Qwen · Grounded in your skill analysis</p>
            </div>
            <div className="ml-auto">
              <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                Ready
              </span>
            </div>
          </div>

          {/* Summary */}
          <Card className="border-violet/20">
            <SectionHeading icon={Sparkles} title="AI Summary" />
            <p className="text-sm text-slate-300 leading-relaxed">{ai_insights.summary}</p>
          </Card>

          {/* Strengths */}
          {ai_insights.strengths?.length > 0 && (
            <Card>
              <SectionHeading icon={Award} title="Your Strengths" subtitle="Relevant skills you already have" />
              <div className="flex flex-wrap gap-2">
                {ai_insights.strengths.map((s) => (
                  <SkillChip key={s} name={s} variant="strength" />
                ))}
              </div>
            </Card>
          )}

          {/* Priority Gaps */}
          {ai_insights.priority_gaps?.length > 0 && (
            <Card>
              <SectionHeading
                icon={Zap}
                title="Priority Skill Gaps"
                subtitle="Skills to address first based on your target role"
                accent
              />
              <div className="space-y-3">
                {ai_insights.priority_gaps.map((gap) => (
                  <div
                    key={gap.skill}
                    className="flex flex-col sm:flex-row sm:items-start gap-3 p-4 rounded-xl bg-slate-950/50 border border-white/5"
                  >
                    <div className="flex items-center gap-2 sm:w-52 flex-shrink-0">
                      <PriorityBadge priority={gap.priority} />
                      <span className="text-sm font-semibold text-white">{gap.skill}</span>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed sm:border-l sm:border-white/10 sm:pl-3">
                      {gap.reason}
                    </p>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Learning Order */}
          {ai_insights.learning_order?.length > 0 && (
            <Card>
              <SectionHeading
                icon={ListOrdered}
                title="Recommended Learning Order"
                subtitle="AI-recommended sequence to build your skills most efficiently"
              />
              <ol className="space-y-2">
                {ai_insights.learning_order.map((skill, idx) => (
                  <li key={skill} className="flex items-center gap-3">
                    <span className="flex-shrink-0 h-6 w-6 rounded-full bg-accent/15 border border-accent/30 text-accent text-xs font-bold flex items-center justify-center">
                      {idx + 1}
                    </span>
                    <span className="text-sm text-slate-200 font-medium">{skill}</span>
                    {idx < ai_insights.learning_order.length - 1 && (
                      <ChevronRight className="h-3.5 w-3.5 text-slate-600 ml-auto flex-shrink-0" />
                    )}
                  </li>
                ))}
              </ol>
            </Card>
          )}

          {/* Roadmap */}
          {ai_insights.roadmap?.length > 0 && (
            <Card>
              <SectionHeading
                icon={Map}
                title="Learning Roadmap"
                subtitle="Step-by-step plan with practical exercises for each skill"
                accent
              />
              <div className="space-y-4">
                {ai_insights.roadmap.map((step) => (
                  <div
                    key={step.step}
                    className="relative pl-10"
                  >
                    {/* Step number vertical connector */}
                    <div className="absolute left-0 top-0 flex flex-col items-center">
                      <div className="flex h-7 w-7 items-center justify-center rounded-full bg-accent/20 border border-accent/40 text-accent text-xs font-extrabold">
                        {step.step}
                      </div>
                      {step.step < ai_insights.roadmap.length && (
                        <div className="w-px flex-1 bg-white/10 mt-1 min-h-[1.5rem]" />
                      )}
                    </div>

                    <div className="pb-4">
                      <h3 className="text-sm font-bold text-white mb-2">
                        <span className="text-accent">{step.skill}</span>
                      </h3>
                      <div className="space-y-2 pl-0">
                        <div className="rounded-xl bg-slate-950/60 border border-white/5 px-4 py-3">
                          <p className="text-[10px] text-slate-500 uppercase tracking-wider font-medium mb-1 flex items-center gap-1.5">
                            <BookOpen className="h-3 w-3" /> Focus
                          </p>
                          <p className="text-xs text-slate-300 leading-relaxed">{step.focus}</p>
                        </div>
                        <div className="rounded-xl bg-slate-950/60 border border-white/5 px-4 py-3">
                          <p className="text-[10px] text-slate-500 uppercase tracking-wider font-medium mb-1 flex items-center gap-1.5">
                            <Zap className="h-3 w-3" /> Practice
                          </p>
                          <p className="text-xs text-slate-300 leading-relaxed">{step.suggested_practice}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
