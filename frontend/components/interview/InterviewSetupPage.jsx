'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AlertCircle, ArrowUpRight, Check, Clock3, History, Loader2, Mic, PlayCircle, Plus, Settings2, SlidersHorizontal, Sparkles, Target, X } from 'lucide-react';
import {
  analyzeInterviewRole,
  createInterview,
  extractErrorMessage,
  getInterviewOptions,
  getInterviewRoles,
  getInterviewSuggestions,
  listInterviews,
  previewInterviewBlueprint,
} from '@/services/api';
import {
  DEFAULT_DURATION_MINUTES,
  DIFFICULTY_OPTIONS,
  FALLBACK_DURATIONS,
  INTERVIEW_TYPE_OPTIONS,
  MAX_FOCUS_AREA_LENGTH,
  MAX_INSTRUCTIONS_LENGTH,
  MAX_JOB_DESCRIPTION_LENGTH,
  MAX_ROLE_LENGTH,
  MIN_QUESTIONS,
  MODE_OPTIONS,
  PRACTICAL_KIND_LABELS,
  QUESTIONS_PER_DURATION,
  SCORE_DISCLAIMER,
  apiErrorDetail,
  difficultyLabel,
  matchCatalogRole,
  modeLabel,
  practicalCount,
  slotKindLabel,
  titleKey,
  typeLabel,
} from '@/components/interview/interviewConstants';

const DEFAULT_MAX_FOCUS_AREAS = 8;

export function validateSetup(
  form,
  { maxFocusAreas = DEFAULT_MAX_FOCUS_AREAS, durations = FALLBACK_DURATIONS, voiceAvailable = false, questionLimits = QUESTIONS_PER_DURATION } = {}
) {
  const errors = {};
  const role = form.targetRole.trim();
  if (role.length < 2) errors.targetRole = 'Enter the role you are preparing for.';
  else if (role.length > MAX_ROLE_LENGTH) errors.targetRole = `Keep the role under ${MAX_ROLE_LENGTH} characters.`;
  if (!form.interviewType) errors.interviewType = 'Choose an interview type.';
  if (form.interactionMode === 'VOICE' && !voiceAvailable) errors.interactionMode = 'Voice interviews are not available.';
  if (!durations.includes(form.durationMinutes)) errors.durationMinutes = 'Choose a supported duration.';
  const limit = questionLimits[form.durationMinutes];
  if (limit && (form.questionCount < MIN_QUESTIONS || form.questionCount > limit)) {
    errors.questionCount = `Choose between ${MIN_QUESTIONS} and ${limit} questions for ${form.durationMinutes} minutes.`;
  }
  if (form.focusAreas.length > maxFocusAreas) errors.focusAreas = `Choose at most ${maxFocusAreas} focus areas.`;
  if (form.instructions.length > MAX_INSTRUCTIONS_LENGTH) errors.instructions = `Keep notes under ${MAX_INSTRUCTIONS_LENGTH} characters.`;
  if ((form.jobDescription || '').length > MAX_JOB_DESCRIPTION_LENGTH) {
    errors.jobDescription = `Keep the job description under ${MAX_JOB_DESCRIPTION_LENGTH} characters.`;
  }
  return errors;
}

function OptionCard({ name, option, checked, onChange, disabled, note }) {
  return (
    <label
      className={`flex cursor-pointer flex-col gap-2 rounded-xl border p-4 transition-colors focus-within:ring-2 focus-within:ring-[rgba(198,161,91,0.22)] ${
        checked
          ? 'border-[var(--brand-navy)] bg-[rgba(23,36,58,0.04)] shadow-[0_0_0_1px_rgba(23,36,58,0.08)]'
          : 'border-[var(--border)] bg-[var(--surface)] hover:border-[var(--border-strong)] hover:bg-[var(--surface-subtle)]'
      } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
    >
      <span className="flex items-center gap-2">
        <input
          type="radio"
          name={name}
          value={option.value}
          checked={checked}
          onChange={() => onChange(option.value)}
          disabled={disabled}
          className="h-4 w-4 accent-[var(--brand-navy)]"
        />
        <span className="text-sm font-semibold text-[var(--text-primary)]">{option.label}</span>
      </span>
      <span className="pl-6 text-xs leading-5 text-[var(--text-muted)]">{option.description}</span>
      {note && <span className="pl-6 text-xs font-medium leading-5 text-[var(--warning)]">{note}</span>}
    </label>
  );
}

function FieldError({ id, message }) {
  if (!message) return null;
  return (
    <p id={id} className="mt-1.5 text-xs font-medium text-[var(--danger)]">
      {message}
    </p>
  );
}

function SectionHeading({ number, icon: Icon, title, description, id }) {
  return (
    <div className="flex items-start gap-3 border-b border-[var(--border)] pb-4">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--surface-subtle)] text-[var(--brand-navy)]">
        <Icon className="h-4 w-4" aria-hidden="true" />
      </div>
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--brand-amber)]">Section {number}</p>
        <h2 id={id} className="mt-0.5 text-base font-semibold text-[var(--text-primary)]">{title}</h2>
        <p className="mt-1 text-xs leading-5 text-[var(--text-muted)]">{description}</p>
      </div>
    </div>
  );
}

export default function InterviewSetupPage() {
  const router = useRouter();
  const [options, setOptions] = useState(null);
  const [catalog, setCatalog] = useState([]);
  const [activeInterview, setActiveInterview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const [form, setForm] = useState({
    targetRole: '',
    interviewType: 'TECHNICAL',
    interactionMode: 'TEXT',
    difficulty: 'INTERMEDIATE',
    durationMinutes: DEFAULT_DURATION_MINUTES,
    questionCount: QUESTIONS_PER_DURATION[DEFAULT_DURATION_MINUTES],
    focusAreas: [],
    instructions: '',
    jobDescription: '',
  });
  const [questionCountTouched, setQuestionCountTouched] = useState(false);
  const [focusDraft, setFocusDraft] = useState('');
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [conflictId, setConflictId] = useState(null);

  const [customRole, setCustomRole] = useState(null); // analysed custom role for the current title
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState('');
  const [relevantSkills, setRelevantSkills] = useState([]);
  const [plan, setPlan] = useState(null);
  const [planLoading, setPlanLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setLoadError('');
      const [optionsResult, rolesResult, suggestionsResult, historyResult] = await Promise.allSettled([
        getInterviewOptions(),
        getInterviewRoles(),
        getInterviewSuggestions(),
        listInterviews({ limit: 5, offset: 0 }),
      ]);
      if (cancelled) return;
      if (optionsResult.status === 'fulfilled') {
        const value = optionsResult.value;
        const duration = value.default_duration_minutes ?? DEFAULT_DURATION_MINUTES;
        const limit = value.question_limits?.[duration] ?? QUESTIONS_PER_DURATION[duration];
        setOptions(value);
        setForm((prev) => ({ ...prev, durationMinutes: duration, questionCount: limit }));
      } else {
        setLoadError(extractErrorMessage(optionsResult.reason));
      }
      if (rolesResult.status === 'fulfilled') setCatalog(rolesResult.value?.roles || []);
      if (suggestionsResult.status === 'fulfilled' && suggestionsResult.value?.target_role) {
        const role = suggestionsResult.value.target_role;
        setForm((prev) => (prev.targetRole ? prev : { ...prev, targetRole: role }));
      }
      if (historyResult.status === 'fulfilled') {
        setActiveInterview(historyResult.value?.interviews?.find((item) => item.status === 'IN_PROGRESS') || null);
      }
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const durations = options?.durations?.length ? options.durations : FALLBACK_DURATIONS;
  const questionLimits = options?.question_limits || QUESTIONS_PER_DURATION;
  const maxFocusAreas = options?.max_focus_areas ?? DEFAULT_MAX_FOCUS_AREAS;
  const voiceAvailable = Boolean(options?.transcription_available);
  const questionLimit = questionLimits[form.durationMinutes] ?? QUESTIONS_PER_DURATION[form.durationMinutes];

  const trimmedRole = form.targetRole.trim();
  const catalogRole = useMemo(() => matchCatalogRole(trimmedRole, catalog), [catalog, trimmedRole]);
  const analysedCustom = customRole && customRole.key === titleKey(trimmedRole) ? customRole.role : null;
  const activeRole = catalogRole || analysedCustom;
  const isCustomTitle = trimmedRole.length >= 2 && !catalogRole;

  // Role-relevant profile skills (the backend filters them to the selected role).
  useEffect(() => {
    if (!catalogRole) {
      setRelevantSkills([]);
      return undefined;
    }
    let cancelled = false;
    getInterviewSuggestions(catalogRole.title)
      .then((value) => {
        if (!cancelled) setRelevantSkills(value?.skills || []);
      })
      .catch(() => {
        if (!cancelled) setRelevantSkills([]);
      });
    return () => {
      cancelled = true;
    };
  }, [catalogRole]);

  // Server-built plan. Catalog roles and already-analysed custom titles need no LLM call;
  // a custom role with a job description is analysed only when the interview starts.
  const canPreview = Boolean(catalogRole || (analysedCustom && !form.jobDescription.trim()));
  const previewKey = JSON.stringify([
    canPreview && trimmedRole,
    form.interviewType,
    form.difficulty,
    form.durationMinutes,
    form.questionCount,
    form.focusAreas,
  ]);
  useEffect(() => {
    if (!canPreview) {
      setPlan(null);
      return undefined;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setPlanLoading(true);
      try {
        const value = await previewInterviewBlueprint({
          target_role: trimmedRole,
          interview_type: form.interviewType,
          difficulty: form.difficulty,
          duration_minutes: form.durationMinutes,
          question_count: form.questionCount,
          focus_areas: form.focusAreas,
        });
        if (!cancelled) setPlan(value);
      } catch {
        if (!cancelled) setPlan(null);
      } finally {
        if (!cancelled) setPlanLoading(false);
      }
    }, 350);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
    // previewKey captures every input to the preview
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewKey]);

  const update = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => ({ ...prev, [key]: undefined }));
  };

  const changeRole = (value) => {
    setAnalyzeError('');
    setErrors((prev) => ({ ...prev, targetRole: undefined }));
    // Focus areas belong to a role: when the role changes, drop the previous role's focus chips.
    const roleChanged = matchCatalogRole(value.trim(), catalog)?.slug !== catalogRole?.slug;
    const previousRoleFocus = new Set((activeRole?.focus_areas || []).map((f) => f.toLowerCase()));
    setForm((prev) => ({
      ...prev,
      targetRole: value,
      focusAreas: roleChanged ? prev.focusAreas.filter((f) => !previousRoleFocus.has(f.toLowerCase())) : prev.focusAreas,
    }));
  };

  const changeDuration = (minutes) => {
    const limit = questionLimits[minutes] ?? QUESTIONS_PER_DURATION[minutes];
    setForm((prev) => ({
      ...prev,
      durationMinutes: minutes,
      questionCount: questionCountTouched ? Math.min(prev.questionCount, limit) : limit,
    }));
    setErrors((prev) => ({ ...prev, durationMinutes: undefined, questionCount: undefined }));
  };

  const analyseRole = async () => {
    setAnalyzing(true);
    setAnalyzeError('');
    try {
      const role = await analyzeInterviewRole(trimmedRole);
      setCustomRole({ key: titleKey(trimmedRole), role });
    } catch (error) {
      setAnalyzeError(extractErrorMessage(error));
    } finally {
      setAnalyzing(false);
    }
  };

  const addFocusArea = (raw) => {
    const value = raw.trim().replace(/\s+/g, ' ');
    if (!value) return;
    if (value.length > MAX_FOCUS_AREA_LENGTH) {
      setErrors((prev) => ({ ...prev, focusAreas: `Each focus area must be under ${MAX_FOCUS_AREA_LENGTH} characters.` }));
      return;
    }
    if (form.focusAreas.some((item) => item.toLowerCase() === value.toLowerCase())) {
      setFocusDraft('');
      return;
    }
    if (form.focusAreas.length >= maxFocusAreas) {
      setErrors((prev) => ({ ...prev, focusAreas: `Choose at most ${maxFocusAreas} focus areas.` }));
      return;
    }
    update('focusAreas', [...form.focusAreas, value]);
    setFocusDraft('');
  };

  const removeFocusArea = (value) => update('focusAreas', form.focusAreas.filter((item) => item !== value));
  const toggleFocusArea = (value) =>
    form.focusAreas.some((item) => item.toLowerCase() === value.toLowerCase()) ? removeFocusArea(value) : addFocusArea(value);

  const roleFocusAreas = activeRole?.focus_areas || [];
  const roleFocusSet = new Set(roleFocusAreas.map((f) => f.toLowerCase()));
  const customFocusAreas = form.focusAreas.filter((f) => !roleFocusSet.has(f.toLowerCase()));
  const chosenLower = new Set(form.focusAreas.map((f) => f.toLowerCase()));
  const skillSuggestions = relevantSkills.filter((skill) => !chosenLower.has(skill.toLowerCase()));

  const practical = practicalCount(form.interviewType, form.questionCount);
  const plannedSlots = plan?.blueprint?.question_slots || [];
  const availableKinds = new Set(plan?.assessment_kinds_available || []);
  const reservedKinds = [...new Set(plannedSlots.filter((s) => s.kind !== 'question' && !availableKinds.has(s.kind)).map((s) => s.kind))];

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (submitting) return;
    const nextErrors = validateSetup(form, { maxFocusAreas, durations, voiceAvailable, questionLimits });
    setErrors(nextErrors);
    setSubmitError('');
    setConflictId(null);
    if (Object.keys(nextErrors).length > 0) return;

    setSubmitting(true);
    try {
      const interview = await createInterview({
        target_role: trimmedRole,
        interview_type: form.interviewType,
        interaction_mode: form.interactionMode,
        difficulty: form.difficulty,
        duration_minutes: form.durationMinutes,
        question_count: form.questionCount,
        focus_areas: form.focusAreas,
        instructions: form.instructions.trim() || null,
        job_description: form.jobDescription.trim() || null,
      });
      router.push(`/dashboard/interview/${interview.id}`);
    } catch (error) {
      const detail = apiErrorDetail(error);
      if (detail.interview_id) setConflictId(detail.interview_id);
      setSubmitError(extractErrorMessage(error));
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center" role="status">
        <Loader2 className="mr-2 h-5 w-5 animate-spin text-[var(--brand-navy)]" aria-hidden="true" />
        <span className="text-sm text-[var(--text-muted)]">Loading interview setup...</span>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="surface-card mx-auto max-w-xl text-center" role="alert">
        <AlertCircle className="mx-auto h-8 w-8 text-[var(--danger)]" aria-hidden="true" />
        <h1 className="mt-3 text-lg font-semibold">The AI Interviewer couldn&apos;t load</h1>
        <p className="mt-1 text-sm text-[var(--text-muted)]">{loadError}</p>
        <button type="button" className="btn-primary mt-4" onClick={() => window.location.reload()}>
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-4 border-b border-[var(--border)] pb-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[var(--brand-navy)] text-surface shadow-[var(--shadow-card)]">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/icons8-interview-48.png" alt="" className="h-8 w-8 object-contain" />
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--brand-amber)]">AI Interviewer · Setup</p>
            <h1 className="page-title mt-1">Configure your interview</h1>
            <p className="page-description">Build a personalised interview session based on your target role and skills.</p>
          </div>
        </div>
        <Link href="/dashboard/interview/history" className="btn-outline shrink-0 self-start sm:self-center">
          <History className="h-4 w-4" aria-hidden="true" />
          Interview history
          <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </header>

      {activeInterview && (
        <div className="flex flex-col gap-3 rounded-xl border border-[rgba(198,161,91,0.4)] bg-[rgba(198,161,91,0.08)] p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold text-[var(--brand-navy)]">You have an interview in progress</p>
            <p className="text-sm text-[var(--text-secondary)]">
              {activeInterview.target_role} · {typeLabel(activeInterview.interview_type)} · {activeInterview.answered_count} answered
            </p>
          </div>
          <Link href={`/dashboard/interview/${activeInterview.id}`} className="btn-primary shrink-0">
            <PlayCircle className="h-4 w-4" aria-hidden="true" />
            Resume interview
          </Link>
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px] xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-6">
          <section className="surface-card space-y-5" aria-labelledby="setup-role">
            <SectionHeading
              number="01"
              icon={Target}
              id="setup-role"
              title="Role & context"
              description="Tell the interviewer what role you are preparing for and where to focus."
            />

            <div>
              <label htmlFor="target-role" className="text-sm font-medium text-[var(--text-primary)]">
                Target job role
              </label>
              <input
                id="target-role"
                type="text"
                list="interview-role-options"
                value={form.targetRole}
                onChange={(event) => changeRole(event.target.value)}
                maxLength={MAX_ROLE_LENGTH + 10}
                placeholder="Search roles or type your own job title"
                className="input-base mt-1.5"
                autoComplete="off"
                aria-invalid={Boolean(errors.targetRole)}
                aria-describedby={errors.targetRole ? 'target-role-error' : 'target-role-status'}
              />
              <datalist id="interview-role-options">
                {catalog.map((role) => (
                  <option key={role.slug} value={role.title}>
                    {role.family}
                  </option>
                ))}
              </datalist>
              <FieldError id="target-role-error" message={errors.targetRole} />
              <div id="target-role-status" className="mt-2 text-xs" aria-live="polite">
                {catalogRole ? (
                  <p className="flex items-center gap-1.5 text-[var(--success)]">
                    <Check className="h-3.5 w-3.5" aria-hidden="true" />
                    {catalogRole.title === trimmedRole
                      ? `${catalogRole.family} role. Questions will be built for ${catalogRole.title}.`
                      : `Matched to ${catalogRole.title} (${catalogRole.family}). Your title "${trimmedRole}" is kept.`}
                  </p>
                ) : isCustomTitle ? (
                  <div className="space-y-2">
                    <p className="text-[var(--text-secondary)]">
                      Custom role. The interviewer will analyse &ldquo;{trimmedRole}&rdquo; on its own terms — it is never treated as a different role.
                    </p>
                    {analysedCustom ? (
                      <p className="flex items-center gap-1.5 text-[var(--success)]">
                        <Check className="h-3.5 w-3.5" aria-hidden="true" />
                        Analysed: {analysedCustom.competencies.map((c) => c.name).join(', ')}
                      </p>
                    ) : (
                      <button type="button" onClick={analyseRole} disabled={analyzing} className="btn-secondary px-3 py-1.5 text-xs">
                        {analyzing ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />}
                        {analyzing ? 'Analysing role...' : 'Analyse role to preview focus areas'}
                      </button>
                    )}
                    {analyzeError && (
                      <p className="text-[var(--danger)]" role="alert">
                        {analyzeError}
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="text-[var(--text-muted)]">Choose from {catalog.length} roles or enter any job title.</p>
                )}
              </div>
            </div>

            <div>
              <p id="focus-heading" className="text-sm font-medium text-[var(--text-primary)]">
                Focus areas <span className="font-normal text-[var(--text-muted)]">(optional, up to {maxFocusAreas})</span>
              </p>
              {roleFocusAreas.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-2" role="group" aria-labelledby="focus-heading">
                  {roleFocusAreas.map((focus) => {
                    const selected = chosenLower.has(focus.toLowerCase());
                    return (
                      <button
                        key={focus}
                        type="button"
                        aria-pressed={selected}
                        onClick={() => toggleFocusArea(focus)}
                        className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                          selected ? 'border-[var(--brand-navy)] bg-[var(--brand-navy)] text-surface' : 'border-[var(--border)] bg-[var(--surface)] text-[var(--text-secondary)] hover:border-[var(--brand-amber)]'
                        }`}
                      >
                        {focus}
                      </button>
                    );
                  })}
                </div>
              ) : (
                <p className="mt-1.5 text-xs text-[var(--text-muted)]">
                  {isCustomTitle ? 'Analyse the role to see its focus areas, or add your own below.' : 'Select a role to see its focus areas.'}
                </p>
              )}
              <div className="mt-3 flex gap-2">
                <label htmlFor="focus-input" className="sr-only">
                  Add your own focus area
                </label>
                <input
                  id="focus-input"
                  type="text"
                  value={focusDraft}
                  onChange={(event) => setFocusDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                      addFocusArea(focusDraft);
                    }
                  }}
                  placeholder="Add your own focus area"
                  className="input-base"
                  aria-describedby={errors.focusAreas ? 'focus-error' : undefined}
                />
                <button type="button" onClick={() => addFocusArea(focusDraft)} className="btn-outline shrink-0" aria-label="Add focus area">
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  Add
                </button>
              </div>
              <FieldError id="focus-error" message={errors.focusAreas} />
              {customFocusAreas.length > 0 && (
                <ul className="mt-3 flex flex-wrap gap-2" aria-label="Your focus areas">
                  {customFocusAreas.map((item) => (
                    <li key={item} className="inline-flex items-center gap-1 rounded-full border border-[rgba(198,161,91,0.45)] bg-[rgba(198,161,91,0.12)] py-1 pl-3 pr-1 text-xs font-medium text-[var(--brand-navy)]">
                      {item}
                      <button type="button" onClick={() => removeFocusArea(item)} className="rounded-full p-0.5 hover:bg-[rgba(198,161,91,0.2)]" aria-label={`Remove ${item}`}>
                        <X className="h-3.5 w-3.5" aria-hidden="true" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {skillSuggestions.length > 0 && (
                <div className="mt-3">
                  <p className="text-xs text-[var(--text-muted)]">From your profile, relevant to this role:</p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {skillSuggestions.map((skill) => (
                      <button
                        key={skill}
                        type="button"
                        onClick={() => addFocusArea(skill)}
                        className="inline-flex items-center gap-1 rounded-full border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1 text-xs text-[var(--text-secondary)] hover:border-[var(--brand-amber)] hover:text-[var(--brand-navy)]"
                      >
                        <Plus className="h-3 w-3" aria-hidden="true" />
                        {skill}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
            <div>
              <label htmlFor="job-description" className="text-sm font-medium text-[var(--text-primary)]">
                Job description <span className="font-normal text-[var(--text-muted)]">(optional)</span>
              </label>
              <textarea
                id="job-description"
                rows={4}
                value={form.jobDescription}
                onChange={(event) => update('jobDescription', event.target.value)}
                placeholder="Paste the job posting to tailor questions to it."
                className="input-base mt-1.5 resize-y"
                aria-describedby="job-description-count"
                aria-invalid={Boolean(errors.jobDescription)}
              />
              <p id="job-description-count" className={`mt-1 text-right text-xs ${form.jobDescription.length > MAX_JOB_DESCRIPTION_LENGTH ? 'text-[var(--danger)]' : 'text-[var(--text-muted)]'}`}>
                {form.jobDescription.length}/{MAX_JOB_DESCRIPTION_LENGTH}
              </p>
              <FieldError id="job-description-error" message={errors.jobDescription} />
            </div>

            <div>
              <label htmlFor="instructions" className="text-sm font-medium text-[var(--text-primary)]">
                Topics or instructions <span className="font-normal text-[var(--text-muted)]">(optional)</span>
              </label>
              <textarea
                id="instructions"
                rows={4}
                value={form.instructions}
                onChange={(event) => update('instructions', event.target.value)}
                placeholder="e.g. Include a question about debugging production issues."
                className="input-base mt-1.5 resize-y"
                aria-describedby="instructions-count"
                aria-invalid={Boolean(errors.instructions)}
              />
              <p id="instructions-count" className={`mt-1 text-right text-xs ${form.instructions.length > MAX_INSTRUCTIONS_LENGTH ? 'text-[var(--danger)]' : 'text-[var(--text-muted)]'}`}>
                {form.instructions.length}/{MAX_INSTRUCTIONS_LENGTH}
              </p>
              <FieldError id="instructions-error" message={errors.instructions} />
            </div>
            </div>
          </section>

          <section className="surface-card space-y-5" aria-labelledby="setup-type">
            <SectionHeading
              number="02"
              icon={SlidersHorizontal}
              id="setup-type"
              title="Interview format"
              description="Choose the kind of assessment that best matches your preparation goal."
            />
            <div className="grid gap-3 sm:grid-cols-3" role="radiogroup" aria-labelledby="setup-type">
              {INTERVIEW_TYPE_OPTIONS.map((option) => (
                <OptionCard
                  key={option.value}
                  name="interview-type"
                  option={option}
                  checked={form.interviewType === option.value}
                  onChange={(value) => update('interviewType', value)}
                />
              ))}
            </div>
          </section>

          <section className="surface-card space-y-5" aria-labelledby="setup-session">
            <SectionHeading
              number="03"
              icon={Settings2}
              id="setup-session"
              title="Session settings"
              description="Set the interaction mode, difficulty, length, and question count."
            />
            <div>
              <p id="setup-mode" className="text-sm font-medium text-[var(--text-primary)]">Interaction mode</p>
            <div className="grid gap-3 sm:grid-cols-2" role="radiogroup" aria-labelledby="setup-mode">
              {MODE_OPTIONS.map((option) => {
                const unavailable = option.value === 'VOICE' && !voiceAvailable;
                return (
                  <OptionCard
                    key={option.value}
                    name="interaction-mode"
                    option={option}
                    checked={form.interactionMode === option.value}
                    onChange={(value) => update('interactionMode', value)}
                    disabled={unavailable}
                    note={unavailable ? 'Unavailable: speech transcription is not configured on this server.' : null}
                  />
                );
              })}
            </div>
            <FieldError id="mode-error" message={errors.interactionMode} />
            {form.interactionMode === 'VOICE' && (
              <p className="flex gap-2 text-xs leading-5 text-[var(--text-muted)]">
                <Mic className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                Your browser will ask for microphone access when you first record. Recordings are only used to produce a transcript and are not stored.
              </p>
            )}
            </div>
            <div className="grid gap-5 border-t border-[var(--border)] pt-5 sm:grid-cols-3" aria-label="Difficulty, duration and questions">
            <fieldset className="sm:col-span-3">
              <legend className="text-sm font-medium text-[var(--text-primary)]">Difficulty</legend>
              <div className="mt-2 inline-flex rounded-lg border border-[var(--border)] bg-[var(--surface-subtle)] p-1">
                {DIFFICULTY_OPTIONS.map((option) => (
                  <label
                    key={option.value}
                    className={`cursor-pointer rounded-md px-3 py-1.5 text-sm font-medium focus-within:ring-2 focus-within:ring-brand-300 ${
                      form.difficulty === option.value ? 'bg-[var(--surface)] text-[var(--brand-navy)] shadow-sm' : 'text-[var(--text-secondary)]'
                    }`}
                  >
                    <input
                      type="radio"
                      name="difficulty"
                      value={option.value}
                      checked={form.difficulty === option.value}
                      onChange={() => update('difficulty', option.value)}
                      className="sr-only"
                    />
                    {option.label}
                  </label>
                ))}
              </div>
            </fieldset>
            <div>
              <label htmlFor="duration" className="text-sm font-medium text-[var(--text-primary)]">
                Duration
              </label>
              <select
                id="duration"
                value={form.durationMinutes}
                onChange={(event) => changeDuration(Number(event.target.value))}
                className="input-base mt-2 appearance-none"
              >
                {durations.map((minutes) => (
                  <option key={minutes} value={minutes}>
                    {minutes} minutes{minutes === DEFAULT_DURATION_MINUTES ? ' (default)' : ''}
                  </option>
                ))}
              </select>
              <FieldError id="duration-error" message={errors.durationMinutes} />
            </div>
            <div>
              <label htmlFor="question-count" className="text-sm font-medium text-[var(--text-primary)]">
                Number of questions
              </label>
              <select
                id="question-count"
                value={form.questionCount}
                onChange={(event) => {
                  setQuestionCountTouched(true);
                  update('questionCount', Number(event.target.value));
                }}
                className="input-base mt-2 appearance-none"
              >
                {Array.from({ length: Math.max(0, questionLimit - MIN_QUESTIONS + 1) }, (_, i) => MIN_QUESTIONS + i).map((count) => (
                  <option key={count} value={count}>
                    {count} questions
                  </option>
                ))}
              </select>
              <FieldError id="question-count-error" message={errors.questionCount} />
            </div>
            </div>
          </section>
        </div>

        <aside className="lg:sticky lg:top-24 lg:self-start">
          <div className="surface-card space-y-4 p-5" aria-labelledby="setup-summary">
            <h2 id="setup-summary" className="text-base font-semibold text-[var(--text-primary)]">Interview summary</h2>
            <div className="flex items-center gap-3 rounded-xl bg-[var(--brand-navy)] p-4 text-surface">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[rgba(214,184,117,0.18)] text-[var(--brand-yellow)]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/icons8-interview-48.png" alt="" className="h-7 w-7 object-contain" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold">AI Interviewer</p>
                <p className="mt-0.5 truncate text-xs text-[rgba(255,255,255,0.72)]">A focused practice session for your next opportunity</p>
              </div>
            </div>
            <dl className="space-y-2 text-sm">
              {[
                ['Role', trimmedRole || '—'],
                ['Type', typeLabel(form.interviewType)],
                ['Mode', modeLabel(form.interactionMode)],
                ['Difficulty', difficultyLabel(form.difficulty)],
                ['Duration', `${form.durationMinutes} minutes`],
                ['Questions', `${form.questionCount} (${form.questionCount - practical} conceptual · ${practical} practical)`],
              ].map(([term, value]) => (
                  <div key={term} className="flex justify-between gap-3 border-b border-[var(--border)] pb-2 last:border-0 last:pb-0">
                  <dt className="text-[var(--text-muted)]">{term}</dt>
                  <dd className="text-right font-medium text-[var(--text-primary)]">{value}</dd>
                </div>
              ))}
              <div>
                <dt className="text-[var(--text-muted)]">Focus areas</dt>
                <dd className="mt-2 flex flex-wrap gap-1.5">
                  {form.focusAreas.length ? form.focusAreas.map((focus) => <span key={focus} className="rounded-full bg-[rgba(198,161,91,0.12)] px-2 py-1 text-xs font-medium text-[var(--brand-navy)]">{focus}</span>) : 'General for the role'}
                </dd>
              </div>
            </dl>

            {(plannedSlots.length > 0 || planLoading) && (
              <div className="border-t border-[var(--border)] pt-4">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Interview plan</h3>
                {planLoading && !plannedSlots.length ? (
                  <p className="mt-2 flex items-center gap-2 text-xs text-[var(--text-muted)]" role="status">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                    Building plan...
                  </p>
                ) : (
                  <ol className="mt-2 space-y-1.5 text-xs" aria-label="Interview plan">
                    {plannedSlots.map((slot) => (
                      <li key={slot.position} className="flex gap-2">
                        <span className="w-4 shrink-0 text-right font-semibold text-[var(--text-muted)]">{slot.position}</span>
                        <span className="min-w-0">
                          <span className={slot.kind === 'question' ? 'text-[var(--text-muted)]' : 'font-semibold text-[var(--warning)]'}>
                            {slot.category === 'BEHAVIORAL' ? 'Behavioral' : slotKindLabel(slot.kind)}
                          </span>
                          <span className="text-[var(--text-secondary)]"> · {slot.competency}</span>
                        </span>
                      </li>
                    ))}
                  </ol>
                )}
                {reservedKinds.length > 0 && (
                  <p className="mt-2 rounded-lg border border-[rgba(198,161,91,0.35)] bg-[rgba(198,161,91,0.1)] p-2 text-xs leading-5 text-[var(--text-secondary)]">
                    {reservedKinds.map((k) => PRACTICAL_KIND_LABELS[k] || k).join(', ')} slots are reserved in this plan. The assessment
                    environment isn&apos;t enabled yet, so those slots will be shown and skipped, and are not scored.
                  </p>
                )}
              </div>
            )}

            <p className="flex gap-2 rounded-lg bg-[var(--surface-subtle)] p-3 text-xs leading-5 text-[var(--text-secondary)]">
              <Clock3 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--brand-amber)]" aria-hidden="true" />
              <span>
                The timer starts when the first question appears and is enforced by the server. {SCORE_DISCLAIMER}
              </span>
            </p>
            {submitError && (
              <div className="rounded-lg border border-[rgba(180,35,24,0.22)] bg-[rgba(180,35,24,0.06)] p-3 text-sm text-[var(--danger)]" role="alert">
                {submitError}
                {conflictId && (
                  <Link href={`/dashboard/interview/${conflictId}`} className="mt-2 block font-semibold underline">
                    Resume that interview
                  </Link>
                )}
              </div>
            )}
            <button type="submit" disabled={submitting} className="btn-primary w-full py-2.5">
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  {isCustomTitle ? 'Analysing role and preparing...' : 'Preparing your first question...'}
                </>
              ) : (
                <>
                  <PlayCircle className="h-4 w-4" aria-hidden="true" />
                  Start interview
                </>
              )}
            </button>
          </div>
        </aside>
      </form>
    </div>
  );
}
