'use client';

/**
 * SkillAnalysisPage — Phase 2C
 *
 * Presentation layer for the deterministic skill analysis and optional AI
 * insights. The backend remains the source of truth for all skills,
 * percentages, role matches, priorities, and roadmap content.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertCircle,
  ArrowRight,
  ArrowUpRight,
  Award,
  BarChart3,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  Filter,
  Gauge,
  Layers3,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
  Star,
  Target,
  TrendingUp,
  XCircle,
  Zap,
} from 'lucide-react';
import { getSkillAnalysis, extractErrorMessage } from '@/services/api';

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'have', label: 'Have' },
  { key: 'missing', label: 'Missing' },
  { key: 'required', label: 'Required' },
  { key: 'recommended', label: 'Recommended' },
];

function Surface({ children, className = '' }) {
  return <div className={`surface-card ${className}`}>{children}</div>;
}

function SectionHeader({ icon: Icon, eyebrow, title, description, action }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-brand-200 bg-brand-50 text-brand-500">
          <Icon className="h-4 w-4" aria-hidden="true" />
        </div>
        <div>
          {eyebrow && (
            <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
              {eyebrow}
            </p>
          )}
          <h2 className="text-lg font-bold tracking-tight text-slate-900">{title}</h2>
          {description && <p className="mt-1 max-w-2xl text-sm leading-5 text-slate-500">{description}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}

function StatusPill({ children, tone = 'neutral' }) {
  const tones = {
    neutral: 'border-slate-200 bg-slate-50 text-slate-600',
    navy: 'border-brand-200 bg-brand-50 text-brand-500',
    success: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    danger: 'border-red-200 bg-red-50 text-red-700',
    gold: 'border-amber-200 bg-amber-50 text-amber-800',
  };

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${tones[tone] ?? tones.neutral}`}>
      {children}
    </span>
  );
}

function SkillChip({ name, variant = 'have' }) {
  const variants = {
    have: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    missing_required: 'border-red-200 bg-red-50 text-red-700',
    missing_recommended: 'border-amber-200 bg-amber-50 text-amber-800',
    strength: 'border-brand-200 bg-brand-50 text-brand-600',
  };

  return (
    <span className={`inline-flex max-w-full items-center rounded-md border px-2.5 py-1 text-xs font-medium ${variants[variant] ?? variants.have}`}>
      <span className="truncate">{name}</span>
    </span>
  );
}

function PriorityBadge({ priority, showLabel = true }) {
  const map = {
    high: { label: 'High priority', dot: 'bg-red-500', text: 'text-red-700' },
    medium: { label: 'Medium priority', dot: 'bg-amber-500', text: 'text-amber-800' },
    low: { label: 'Low priority', dot: 'bg-slate-400', text: 'text-slate-600' },
  };
  const item = map[priority] ?? map.low;
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${item.text}`}>
      <span className={`h-2 w-2 rounded-full ${item.dot}`} aria-hidden="true" />
      {showLabel && item.label}
    </span>
  );
}

function ProgressMetric({ icon: Icon, label, description, pct, emphasis = false }) {
  const numericPct = typeof pct === 'number' && Number.isFinite(pct) ? pct : null;
  const visualPct = numericPct === null ? 0 : Math.max(0, Math.min(100, numericPct));

  return (
    <article className={`rounded-xl border p-4 ${emphasis ? 'border-brand-200 bg-brand-50/60' : 'border-slate-200 bg-slate-50/70'}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${emphasis ? 'bg-brand-500 !text-white' : 'bg-white text-brand-500'}`}>
            <Icon className="h-4 w-4" aria-hidden="true" />
          </div>
          <p className="text-sm font-semibold text-slate-800">{label}</p>
        </div>
        <span className={`text-xl font-bold tracking-tight ${emphasis ? 'text-brand-500' : 'text-slate-900'}`}>
          {numericPct === null ? '—' : `${numericPct}%`}
        </span>
      </div>
      <div
        className="mt-4 h-2 overflow-hidden rounded-full bg-slate-200"
        role="progressbar"
        aria-label={`${label} progress`}
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow={numericPct ?? 0}
      >
        <div className={`h-full rounded-full ${emphasis ? 'bg-brand-500' : 'bg-brand-300'}`} style={{ width: `${visualPct}%` }} />
      </div>
      <p className="mt-2 text-xs leading-5 text-slate-500">{description}</p>
    </article>
  );
}

function SkillSummaryCard({ icon: Icon, title, count, description, skills, variant, emptyMessage }) {
  const accents = {
    have: 'border-emerald-200 bg-emerald-50/50 text-emerald-700',
    required: 'border-red-200 bg-red-50/40 text-red-700',
    recommended: 'border-amber-200 bg-amber-50/50 text-amber-800',
  };

  return (
    <Surface className="flex min-h-[218px] flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className={`flex h-8 w-8 items-center justify-center rounded-lg border ${accents[variant]}`}>
            <Icon className="h-4 w-4" aria-hidden="true" />
          </div>
          <h3 className="text-sm font-bold text-slate-900">{title}</h3>
        </div>
        <span className="text-2xl font-bold tracking-tight text-slate-900">{count}</span>
      </div>
      <p className="mt-3 text-xs leading-5 text-slate-500">{description}</p>
      <div className="mt-4 flex flex-1 flex-wrap content-start gap-2">
        {skills.length > 0 ? skills.map((skill) => <SkillChip key={skill} name={skill} variant={variant === 'required' ? 'missing_required' : variant === 'recommended' ? 'missing_recommended' : 'have'} />) : (
          <div className="flex items-start gap-2 text-sm text-emerald-700">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{emptyMessage}</span>
          </div>
        )}
      </div>
    </Surface>
  );
}

function FilterButton({ label, count, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold transition-colors ${active ? 'border-brand-500 bg-brand-500 !text-white' : 'border-slate-200 bg-white text-slate-600 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-600'}`}
    >
      {label}
      <span className={`rounded-full px-1.5 py-0.5 text-[10px] ${active ? 'bg-white/15 !text-white' : 'bg-slate-100 text-slate-500'}`}>
        {count}
      </span>
    </button>
  );
}

function LoadingState() {
  return (
    <div className="space-y-6" aria-busy="true" aria-live="polite">
      <div className="space-y-3">
        <div className="h-3 w-28 animate-pulse rounded bg-slate-200" />
        <div className="h-9 w-72 max-w-full animate-pulse rounded bg-slate-200" />
        <div className="h-4 w-[32rem] max-w-full animate-pulse rounded bg-slate-200" />
      </div>
      <Surface>
        <div className="flex items-center gap-3 border-b border-slate-200 pb-4">
          <Loader2 className="h-5 w-5 animate-spin text-brand-500" aria-hidden="true" />
          <div>
            <p className="text-sm font-semibold text-slate-800">Preparing your skill analysis</p>
            <p className="mt-1 text-xs text-slate-500">Your profile is being compared with the requirements for your target career.</p>
          </div>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-3">
          {[0, 1, 2].map((item) => <div key={item} className="h-32 animate-pulse rounded-xl bg-slate-100" />)}
        </div>
      </Surface>
    </div>
  );
}

function ErrorState({ message, onRetry }) {
  return (
    <Surface className="flex flex-col items-center justify-center py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-red-200 bg-red-50 text-red-600">
        <AlertCircle className="h-6 w-6" aria-hidden="true" />
      </div>
      <h2 className="mt-4 text-xl font-bold text-slate-900">Unable to load skill analysis</h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">{message}</p>
      <button type="button" onClick={onRetry} className="btn-primary mt-5">
        <RefreshCw className="h-4 w-4" aria-hidden="true" />
        Retry analysis
      </button>
    </Surface>
  );
}

function EmptyState({ icon: Icon, title, description, linkLabel, linkHref }) {
  return (
    <Surface className="flex flex-col items-center justify-center py-16 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-xl border border-brand-200 bg-brand-50 text-brand-500">
        <Icon className="h-7 w-7" aria-hidden="true" />
      </div>
      <h2 className="mt-4 text-xl font-bold text-slate-900">{title}</h2>
      <p className="mt-2 max-w-lg text-sm leading-6 text-slate-500">{description}</p>
      {linkHref && (
        <Link href={linkHref} className="btn-primary mt-5">
          {linkLabel}
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Link>
      )}
    </Surface>
  );
}

function normalise(value) {
  return String(value ?? '').trim().toLowerCase();
}

export default function SkillAnalysisPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [skillFilter, setSkillFilter] = useState('all');
  const [skillSearch, setSkillSearch] = useState('');
  const [openLearningStep, setOpenLearningStep] = useState(null);

  const fetchAnalysis = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getSkillAnalysis(true);
      setData(result);
      setOpenLearningStep(null);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAnalysis();
  }, [fetchAnalysis]);

  const allSkills = useMemo(() => {
    const required = (data?.required_skills ?? []).map((skill) => ({ ...skill, tier: 'required' }));
    const recommended = (data?.recommended_skills ?? []).map((skill) => ({ ...skill, tier: 'recommended' }));
    return [...required, ...recommended];
  }, [data]);

  const counts = useMemo(() => ({
    all: allSkills.length,
    have: allSkills.filter((skill) => skill.have).length,
    missing: allSkills.filter((skill) => !skill.have).length,
    required: allSkills.filter((skill) => skill.tier === 'required').length,
    recommended: allSkills.filter((skill) => skill.tier === 'recommended').length,
  }), [allSkills]);

  const filteredSkills = useMemo(() => {
    const query = normalise(skillSearch);
    return allSkills.filter((skill) => {
      const matchesFilter = skillFilter === 'all'
        || (skillFilter === 'have' && skill.have)
        || (skillFilter === 'missing' && !skill.have)
        || (skillFilter === 'required' && skill.tier === 'required')
        || (skillFilter === 'recommended' && skill.tier === 'recommended');
      const matchesSearch = !query || normalise(skill.name).includes(query) || normalise(skill.category).includes(query);
      return matchesFilter && matchesSearch;
    });
  }, [allSkills, skillFilter, skillSearch]);

  const roleAlternatives = useMemo(() => {
    const target = normalise(data?.target_role);
    return (data?.resolved_roles ?? []).filter((role) => normalise(role) !== target);
  }, [data]);

  const learningSteps = useMemo(() => {
    const insights = data?.ai_insights;
    if (!insights) return [];

    const roadmapBySkill = new Map((insights.roadmap ?? []).map((step) => [normalise(step.skill), step]));
    const priorityBySkill = new Map((insights.priority_gaps ?? []).map((gap) => [normalise(gap.skill), gap]));
    const orderedSkills = insights.learning_order?.length
      ? insights.learning_order
      : (insights.roadmap ?? []).map((step) => step.skill);

    return orderedSkills.map((skill, index) => {
      const roadmapStep = roadmapBySkill.get(normalise(skill));
      return {
        skill,
        // Display order is authoritative. Roadmap step fields can be stale or duplicated.
        step: index + 1,
        focus: roadmapStep?.focus,
        suggestedPractice: roadmapStep?.suggested_practice,
        priority: priorityBySkill.get(normalise(skill))?.priority,
      };
    });
  }, [data]);

  const priorityGapGroups = useMemo(() => {
    const gaps = data?.ai_insights?.priority_gaps ?? [];
    return ['high', 'medium', 'low']
      .map((priority) => ({
        priority,
        items: gaps.filter((gap) => gap.priority === priority),
      }))
      .filter((group) => group.items.length > 0);
  }, [data]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={fetchAnalysis} />;

  if (data?.status === 'no_target_role') {
    return (
      <EmptyState
        icon={Target}
        title="No target role configured"
        description="Set a Target Role in your Career Preferences to generate your personalised skill analysis and identify the capabilities to build next."
        linkLabel="Go to Career Preferences"
        linkHref="/dashboard/profile"
      />
    );
  }

  if (data?.status === 'no_match') {
    return (
      <EmptyState
        icon={AlertCircle}
        title="Target role not recognised"
        description={`“${data.target_role}” could not be mapped to the available career knowledge base. Try a more specific career title such as “Backend Engineer” or “Data Scientist”.`}
        linkLabel="Update Career Preferences"
        linkHref="/dashboard/profile"
      />
    );
  }

  const {
    target_role: targetRole,
    resolution_method: resolutionMethod,
    resolution_scores: resolutionScores = {},
    skills_have: skillsHave = [],
    skills_missing_required: missingRequired = [],
    skills_missing_recommended: missingRecommended = [],
    coverage,
    ai_insights: aiInsights,
    ai_status: aiStatus,
  } = data ?? {};

  const aiReady = aiStatus === 'ok' && aiInsights;

  return (
    <div className="space-y-7 pb-10">
      <header className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
        <div>
          <div className="mb-3 inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] text-brand-500">
            <BarChart3 className="h-4 w-4" aria-hidden="true" />
            Career intelligence
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-[34px]">Career Skill Analysis</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500 sm:text-[15px]">
            Understand your current capabilities, identify skill gaps, and build a focused learning plan for your target career.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <StatusPill tone="navy">
              <Target className="h-3.5 w-3.5" aria-hidden="true" />
              Target role: {targetRole}
            </StatusPill>
            <StatusPill tone={resolutionMethod === 'semantic' ? 'gold' : 'neutral'}>
              {resolutionMethod === 'semantic' ? 'AI matched' : 'Direct role match'}
            </StatusPill>
          </div>
        </div>
        <button type="button" onClick={fetchAnalysis} disabled={loading} className="btn-outline shrink-0 self-start">
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
          Re-analyze
        </button>
      </header>

      {aiStatus === 'unavailable' && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3.5 text-sm text-amber-900" role="status">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p><span className="font-semibold">AI insights are temporarily unavailable.</span> Your deterministic skill analysis remains available below.</p>
        </div>
      )}

      <section>
        <SectionHeader
          icon={Target}
          eyebrow="01 · Career direction"
          title="Target career overview"
          description="Your analysis is anchored to this role and the closest matches returned by the career knowledge base."
        />
        <Surface className="mt-4 p-0">
          <div className="grid gap-0 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
            <div className="border-b border-slate-200 bg-brand-50/60 p-5 sm:p-6 lg:border-b-0 lg:border-r">
              <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-brand-500">Primary target</p>
              <h3 className="mt-2 text-2xl font-bold tracking-tight text-slate-900">{targetRole}</h3>
              <p className="mt-3 max-w-md text-sm leading-6 text-slate-600">
                Your skill coverage and learning recommendations are measured against this career direction.
              </p>
              <div className="mt-5">
                <StatusPill tone="success"><Check className="h-3.5 w-3.5" aria-hidden="true" /> Analysis ready</StatusPill>
              </div>
            </div>
            <div className="p-5 sm:p-6">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-slate-500">Alternative role matches</p>
                  <p className="mt-1 text-xs text-slate-500">Only roles returned by the existing resolver are shown.</p>
                </div>
                <Layers3 className="h-5 w-5 text-slate-400" aria-hidden="true" />
              </div>
              {roleAlternatives.length > 0 ? (
                <div className="mt-4 space-y-2">
                  {roleAlternatives.map((role) => {
                    const score = resolutionScores[role];
                    return (
                      <div key={role} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white px-3.5 py-3">
                        <span className="min-w-0 truncate text-sm font-semibold text-slate-800">{role}</span>
                        {typeof score === 'number' && Number.isFinite(score) && (
                          <span className="shrink-0 text-xs font-bold text-brand-500">{Math.round(score * 100)}% match</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="mt-4 rounded-lg border border-dashed border-slate-300 bg-slate-50 px-3.5 py-4 text-sm text-slate-500">
                  No alternative role matches were returned for this analysis.
                </div>
              )}
            </div>
          </div>
        </Surface>
      </section>

      <section>
        <SectionHeader
          icon={TrendingUp}
          eyebrow="02 · Coverage"
          title="Skill coverage overview"
          description="Coverage values are calculated by the backend from the skills in your profile and the requirements of the target role."
        />
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <ProgressMetric icon={Gauge} label="Overall skill coverage" description="All required and recommended skills" pct={coverage?.overall_pct} emphasis />
          <ProgressMetric icon={Target} label="Required skill coverage" description="Core skills for the role" pct={coverage?.required_pct} />
          <ProgressMetric icon={Star} label="Recommended coverage" description="Skills that strengthen your profile" pct={coverage?.recommended_pct} />
        </div>
      </section>

      <section>
        <SectionHeader
          icon={CheckCircle2}
          eyebrow="03 · Skill inventory"
          title="Skills overview"
          description="A concise view of the capabilities you already have and the gaps that matter most for this role."
        />
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <SkillSummaryCard
            icon={CheckCircle2}
            title="Your skills"
            count={skillsHave.length}
            description="Relevant skills already present in your profile or projects."
            skills={skillsHave}
            variant="have"
            emptyMessage="No matching skills found in your profile yet."
          />
          <SkillSummaryCard
            icon={XCircle}
            title="Missing required skills"
            count={missingRequired.length}
            description="Core capabilities to prioritise for your target career."
            skills={missingRequired}
            variant="required"
            emptyMessage="You currently have all required skills for this direction."
          />
          <SkillSummaryCard
            icon={Star}
            title="Recommended to gain"
            count={missingRecommended.length}
            description="Additional capabilities that can improve your readiness."
            skills={missingRecommended}
            variant="recommended"
            emptyMessage="You have all recommended skills for this direction."
          />
        </div>
      </section>

      {allSkills.length > 0 && (
        <section>
          <SectionHeader
            icon={Filter}
            eyebrow="04 · Directory"
            title="All skills"
            description={`${allSkills.length} skills mapped to this role. Search by skill name or category, then narrow the list with a status filter.`}
            action={<span className="text-sm font-semibold text-slate-500">{filteredSkills.length} shown</span>}
          />
          <Surface className="mt-4 overflow-hidden p-0">
            <div className="flex flex-col gap-4 border-b border-slate-200 p-4 sm:p-5">
              <label className="relative block">
                <span className="sr-only">Search skills</span>
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
                <input
                  type="search"
                  value={skillSearch}
                  onChange={(event) => setSkillSearch(event.target.value)}
                  placeholder="Search by skill or category"
                  className="input-base pl-9"
                />
              </label>
              <div className="flex flex-wrap gap-2" role="group" aria-label="Filter skills">
                {FILTERS.map((filter) => (
                  <FilterButton
                    key={filter.key}
                    label={filter.label}
                    count={counts[filter.key]}
                    active={skillFilter === filter.key}
                    onClick={() => setSkillFilter(filter.key)}
                  />
                ))}
              </div>
            </div>
            <div className="hidden grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_auto_auto] gap-4 border-b border-slate-200 bg-slate-50 px-5 py-3 text-[11px] font-bold uppercase tracking-[0.13em] text-slate-500 sm:grid">
              <span>Skill</span>
              <span>Category</span>
              <span>Tier</span>
              <span>Status</span>
            </div>
            <div className="divide-y divide-slate-100">
              {filteredSkills.length === 0 ? (
                <div className="px-5 py-12 text-center text-sm text-slate-500">No skills match the current search and filters.</div>
              ) : filteredSkills.map((skill) => (
                <div key={`${skill.tier}-${skill.name}`} className="grid grid-cols-1 gap-2 px-5 py-3.5 sm:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_auto_auto] sm:items-center sm:gap-4">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-800">{skill.name}</p>
                    <p className="mt-0.5 text-xs text-slate-500 sm:hidden">{skill.category}</p>
                  </div>
                  <span className="hidden truncate text-xs capitalize text-slate-500 sm:block">{skill.category}</span>
                  <span><StatusPill tone={skill.tier === 'required' ? 'navy' : 'gold'}>{skill.tier === 'required' ? 'Required' : 'Recommended'}</StatusPill></span>
                  <span>
                    <StatusPill tone={skill.have ? 'success' : 'danger'}>
                      {skill.have ? <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" /> : <XCircle className="h-3.5 w-3.5" aria-hidden="true" />}
                      {skill.have ? 'Have' : 'Missing'}
                    </StatusPill>
                  </span>
                </div>
              ))}
            </div>
          </Surface>
        </section>
      )}

      {aiReady && (
        <section>
          <SectionHeader
            icon={Sparkles}
            eyebrow="05 · AI guidance"
            title="AI Insights"
            description="A grounded interpretation of your current readiness, based on the skill analysis above."
            action={<StatusPill tone="success"><Check className="h-3.5 w-3.5" aria-hidden="true" /> Ready</StatusPill>}
          />
          <Surface className="mt-4 border-brand-200 bg-brand-50/35">
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-500 !text-white">
                <Sparkles className="h-4 w-4" aria-hidden="true" />
              </div>
              <div className="min-w-0">
                <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-brand-500">AI career assessment</p>
                <p className="mt-1 text-xs text-slate-500">Generated from your profile, projects, target role, and skill coverage.</p>
              </div>
              <StatusPill tone="success"><Check className="h-3.5 w-3.5" aria-hidden="true" /> Ready</StatusPill>
            </div>
            <p className="mt-5 max-w-4xl text-[15px] leading-7 text-slate-700">{aiInsights.summary}</p>
          </Surface>

          {aiInsights.strengths?.length > 0 && (
            <Surface className="mt-4 border-emerald-200">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-700">
                    <Award className="h-4 w-4" aria-hidden="true" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">Career strengths</h3>
                    <p className="mt-0.5 text-xs text-slate-500">Relevant capabilities already working in your favour.</p>
                  </div>
                </div>
                <StatusPill tone="success">{aiInsights.strengths.length} identified</StatusPill>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {aiInsights.strengths.map((skill) => <SkillChip key={skill} name={skill} variant="strength" />)}
              </div>
            </Surface>
          )}

          <Surface className="mt-4 overflow-hidden p-0">
            <div className="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-red-200 bg-red-50 text-red-700">
                  <Zap className="h-4 w-4" aria-hidden="true" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">Priority skill gaps</h3>
                  <p className="mt-0.5 text-xs text-slate-500">The AI-ranked gaps to address first.</p>
                </div>
              </div>
              <span className="text-xs font-semibold text-slate-500">{aiInsights.priority_gaps?.length ?? 0} gaps identified</span>
            </div>
            {priorityGapGroups.length > 0 ? (
              <div className="divide-y divide-slate-100">
                {priorityGapGroups.map((group) => (
                  <div key={group.priority}>
                    <div className="flex items-center gap-2 bg-slate-50 px-5 py-2.5 sm:px-6">
                      <PriorityBadge priority={group.priority} />
                      <span className="text-xs text-slate-500">{group.items.length} {group.items.length === 1 ? 'skill' : 'skills'}</span>
                    </div>
                    <div className="divide-y divide-slate-100">
                      {group.items.map((gap) => (
                        <div key={gap.skill} className="grid gap-2 px-5 py-4 sm:grid-cols-[minmax(0,0.75fr)_minmax(0,1.5fr)] sm:gap-6 sm:px-6">
                          <p className="text-sm font-bold text-slate-800">{gap.skill}</p>
                          <p className="text-sm leading-5 text-slate-600">{gap.reason}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="px-5 py-6 text-sm text-slate-500 sm:px-6">No priority gaps were returned for this analysis.</p>
            )}
          </Surface>
        </section>
      )}

      {aiReady && learningSteps.length > 0 && (
        <section>
          <SectionHeader
            icon={BookOpen}
            eyebrow="06 · Guided development"
            title="Learning Roadmap"
            description="Follow your personalized learning sequence to close skill gaps and strengthen your career readiness."
            action={<StatusPill tone="navy">{learningSteps.length} {learningSteps.length === 1 ? 'step' : 'steps'}</StatusPill>}
          />
          <Surface className="relative mt-4 overflow-hidden p-0">
            <div className="relative px-4 py-3 sm:px-5">
              <div className="pointer-events-none absolute bottom-8 left-[2.25rem] top-8 w-px bg-slate-200" aria-hidden="true" />
              <div>
              {learningSteps.map((step, index) => {
                const isOpen = openLearningStep === index;
                const previousPriority = learningSteps[index - 1]?.priority;
                const showPriorityLabel = index === 0 || step.priority !== previousPriority;
                return (
                  <div key={`${step.step}-${step.skill}`} className="relative border-b border-slate-100 py-1 last:border-b-0">
                    <button
                      type="button"
                      onClick={() => setOpenLearningStep(isOpen ? null : index)}
                      aria-expanded={isOpen}
                      aria-controls={`learning-step-${index}`}
                      className="group flex w-full items-center gap-3 rounded-lg px-1 py-3 text-left transition-colors hover:bg-slate-50 sm:gap-4 sm:px-2"
                    >
                      <span className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-4 border-white bg-brand-500 text-xs font-bold !text-white shadow-sm">{index + 1}</span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-bold text-slate-900">{step.skill}</span>
                        <span className="mt-0.5 block truncate text-xs text-slate-500">{step.focus || 'Expand to view the learning focus and practical exercise.'}</span>
                      </span>
                      {step.priority && <PriorityBadge priority={step.priority} showLabel={showPriorityLabel} />}
                      <ChevronDown className={`h-4 w-4 shrink-0 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} aria-hidden="true" />
                    </button>
                    {isOpen && (
                      <div id={`learning-step-${index}`} className="ml-11 grid gap-3 bg-slate-50 px-4 py-4 sm:grid-cols-2 sm:px-5">
                        {step.focus && (
                          <div className="rounded-lg border border-slate-200 bg-white p-3.5">
                            <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-500">Learning focus</p>
                            <p className="mt-2 text-sm leading-5 text-slate-600">{step.focus}</p>
                          </div>
                        )}
                        {step.suggestedPractice && (
                          <div className="rounded-lg border border-slate-200 bg-white p-3.5">
                            <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-slate-500">Practical exercise</p>
                            <p className="mt-2 text-sm leading-5 text-slate-600">{step.suggestedPractice}</p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
              </div>
            </div>
          </Surface>
        </section>
      )}

      <div className="flex items-center justify-between gap-4 border-t border-slate-200 pt-5 text-xs text-slate-500">
        <span>Analysis uses your current profile, projects, and career preferences.</span>
        <Link href="/dashboard/profile" className="inline-flex shrink-0 items-center gap-1 font-semibold text-brand-500 hover:text-brand-600">
          Update profile
          <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </div>
    </div>
  );
}
