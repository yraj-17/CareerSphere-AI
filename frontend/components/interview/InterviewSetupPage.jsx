'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AlertCircle, History, Info, Loader2, Mic, PlayCircle, Plus, X } from 'lucide-react';
import {
  createInterview,
  extractErrorMessage,
  getInterviewOptions,
  getInterviewSuggestions,
  listInterviews,
} from '@/services/api';
import {
  DEFAULT_DURATION_MINUTES,
  DIFFICULTY_OPTIONS,
  FALLBACK_DURATIONS,
  INTERVIEW_TYPE_OPTIONS,
  MAX_FOCUS_AREA_LENGTH,
  MAX_INSTRUCTIONS_LENGTH,
  MAX_ROLE_LENGTH,
  MODE_OPTIONS,
  QUESTIONS_PER_DURATION,
  SCORE_DISCLAIMER,
  apiErrorDetail,
  difficultyLabel,
  modeLabel,
  typeLabel,
} from '@/components/interview/interviewConstants';

const DEFAULT_MAX_FOCUS_AREAS = 8;

export function validateSetup(form, { maxFocusAreas = DEFAULT_MAX_FOCUS_AREAS, durations = FALLBACK_DURATIONS, voiceAvailable = false } = {}) {
  const errors = {};
  const role = form.targetRole.trim();
  if (role.length < 2) errors.targetRole = 'Enter the role you are preparing for.';
  else if (role.length > MAX_ROLE_LENGTH) errors.targetRole = `Keep the role under ${MAX_ROLE_LENGTH} characters.`;
  if (!form.interviewType) errors.interviewType = 'Choose an interview type.';
  if (form.interactionMode === 'VOICE' && !voiceAvailable) errors.interactionMode = 'Voice interviews are not available.';
  if (!durations.includes(form.durationMinutes)) errors.durationMinutes = 'Choose a supported duration.';
  if (form.focusAreas.length > maxFocusAreas) errors.focusAreas = `Choose at most ${maxFocusAreas} focus areas.`;
  if (form.instructions.length > MAX_INSTRUCTIONS_LENGTH) errors.instructions = `Keep notes under ${MAX_INSTRUCTIONS_LENGTH} characters.`;
  return errors;
}

function OptionCard({ name, option, checked, onChange, disabled, note }) {
  return (
    <label
      className={`flex cursor-pointer flex-col gap-1 rounded-xl border p-4 transition-colors focus-within:ring-2 focus-within:ring-brand-300 ${
        checked ? 'border-brand-500 bg-brand-50' : 'border-slate-200 bg-white hover:border-brand-300'
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
          className="h-4 w-4 accent-[#102f6b]"
        />
        <span className="text-sm font-semibold text-slate-900">{option.label}</span>
      </span>
      <span className="pl-6 text-xs leading-5 text-slate-500">{option.description}</span>
      {note && <span className="pl-6 text-xs font-medium leading-5 text-amber-800">{note}</span>}
    </label>
  );
}

function FieldError({ id, message }) {
  if (!message) return null;
  return (
    <p id={id} className="mt-1.5 text-xs font-medium text-red-700">
      {message}
    </p>
  );
}

export default function InterviewSetupPage() {
  const router = useRouter();
  const [options, setOptions] = useState(null);
  const [suggestions, setSuggestions] = useState(null);
  const [activeInterview, setActiveInterview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const [form, setForm] = useState({
    targetRole: '',
    interviewType: 'TECHNICAL',
    interactionMode: 'TEXT',
    difficulty: 'INTERMEDIATE',
    durationMinutes: DEFAULT_DURATION_MINUTES,
    focusAreas: [],
    instructions: '',
  });
  const [focusDraft, setFocusDraft] = useState('');
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [conflictId, setConflictId] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setLoadError('');
      const [optionsResult, suggestionsResult, historyResult] = await Promise.allSettled([
        getInterviewOptions(),
        getInterviewSuggestions(),
        listInterviews({ limit: 5, offset: 0 }),
      ]);
      if (cancelled) return;
      if (optionsResult.status === 'fulfilled') {
        setOptions(optionsResult.value);
        setForm((prev) => ({ ...prev, durationMinutes: optionsResult.value.default_duration_minutes ?? DEFAULT_DURATION_MINUTES }));
      } else {
        setLoadError(extractErrorMessage(optionsResult.reason));
      }
      if (suggestionsResult.status === 'fulfilled') {
        const value = suggestionsResult.value;
        setSuggestions(value);
        if (value?.target_role) setForm((prev) => (prev.targetRole ? prev : { ...prev, targetRole: value.target_role }));
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
  const maxFocusAreas = options?.max_focus_areas ?? DEFAULT_MAX_FOCUS_AREAS;
  const voiceAvailable = Boolean(options?.transcription_available);
  const questionEstimate = QUESTIONS_PER_DURATION[form.durationMinutes];

  const suggestedSkills = useMemo(() => {
    const chosen = new Set(form.focusAreas.map((item) => item.toLowerCase()));
    return (suggestions?.skills || []).filter((skill) => !chosen.has(skill.toLowerCase()));
  }, [form.focusAreas, suggestions]);

  const update = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => ({ ...prev, [key]: undefined }));
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

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (submitting) return;
    const nextErrors = validateSetup(form, { maxFocusAreas, durations, voiceAvailable });
    setErrors(nextErrors);
    setSubmitError('');
    setConflictId(null);
    if (Object.keys(nextErrors).length > 0) return;

    setSubmitting(true);
    try {
      const interview = await createInterview({
        target_role: form.targetRole.trim(),
        interview_type: form.interviewType,
        interaction_mode: form.interactionMode,
        difficulty: form.difficulty,
        duration_minutes: form.durationMinutes,
        focus_areas: form.focusAreas,
        instructions: form.instructions.trim() || null,
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
        <Loader2 className="mr-2 h-5 w-5 animate-spin text-brand-500" aria-hidden="true" />
        <span className="text-sm text-slate-500">Loading interview setup...</span>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="surface-card mx-auto max-w-xl text-center" role="alert">
        <AlertCircle className="mx-auto h-8 w-8 text-red-600" aria-hidden="true" />
        <h1 className="mt-3 text-lg font-semibold">The AI Interviewer couldn&apos;t load</h1>
        <p className="mt-1 text-sm text-slate-500">{loadError}</p>
        <button type="button" className="btn-primary mt-4" onClick={() => window.location.reload()}>
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Practice</p>
          <h1 className="page-title mt-1">AI Interviewer</h1>
          <p className="page-description">
            Run a timed mock interview, get feedback after every answer, and review a full report at the end.
          </p>
        </div>
        <Link href="/dashboard/interview/history" className="btn-outline shrink-0">
          <History className="h-4 w-4" aria-hidden="true" />
          Interview history
        </Link>
      </div>

      {activeInterview && (
        <div className="flex flex-col gap-3 rounded-xl border border-brand-200 bg-brand-50 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold text-brand-600">You have an interview in progress</p>
            <p className="text-sm text-slate-600">
              {activeInterview.target_role} · {typeLabel(activeInterview.interview_type)} · {activeInterview.answered_count} answered
            </p>
          </div>
          <Link href={`/dashboard/interview/${activeInterview.id}`} className="btn-primary shrink-0">
            <PlayCircle className="h-4 w-4" aria-hidden="true" />
            Resume interview
          </Link>
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          <section className="surface-card space-y-5" aria-labelledby="setup-role">
            <h2 id="setup-role" className="text-base font-semibold">Role and focus</h2>

            <div>
              <label htmlFor="target-role" className="text-sm font-medium text-slate-700">
                Target job role
              </label>
              <input
                id="target-role"
                type="text"
                value={form.targetRole}
                onChange={(event) => update('targetRole', event.target.value)}
                maxLength={MAX_ROLE_LENGTH + 10}
                placeholder="e.g. Backend Engineer"
                className="input-base mt-1.5"
                aria-invalid={Boolean(errors.targetRole)}
                aria-describedby={errors.targetRole ? 'target-role-error' : 'target-role-hint'}
              />
              {suggestions?.target_role && form.targetRole === suggestions.target_role ? (
                <p id="target-role-hint" className="mt-1.5 text-xs text-slate-500">Suggested from your profile. You can change it.</p>
              ) : (
                <p id="target-role-hint" className="sr-only">The role you want to practise for.</p>
              )}
              <FieldError id="target-role-error" message={errors.targetRole} />
            </div>

            <div>
              <label htmlFor="focus-input" className="text-sm font-medium text-slate-700">
                Skills or focus areas <span className="font-normal text-slate-400">(optional, up to {maxFocusAreas})</span>
              </label>
              <div className="mt-1.5 flex gap-2">
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
                  placeholder="e.g. System design"
                  className="input-base"
                  aria-describedby={errors.focusAreas ? 'focus-error' : undefined}
                />
                <button type="button" onClick={() => addFocusArea(focusDraft)} className="btn-outline shrink-0" aria-label="Add focus area">
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  Add
                </button>
              </div>
              <FieldError id="focus-error" message={errors.focusAreas} />
              {form.focusAreas.length > 0 && (
                <ul className="mt-3 flex flex-wrap gap-2" aria-label="Selected focus areas">
                  {form.focusAreas.map((item) => (
                    <li key={item} className="inline-flex items-center gap-1 rounded-full border border-brand-200 bg-brand-50 py-1 pl-3 pr-1 text-xs font-medium text-brand-600">
                      {item}
                      <button
                        type="button"
                        onClick={() => removeFocusArea(item)}
                        className="rounded-full p-0.5 hover:bg-brand-100"
                        aria-label={`Remove ${item}`}
                      >
                        <X className="h-3.5 w-3.5" aria-hidden="true" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {suggestedSkills.length > 0 && (
                <div className="mt-3">
                  <p className="text-xs text-slate-500">From your profile skills:</p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {suggestedSkills.map((skill) => (
                      <button
                        key={skill}
                        type="button"
                        onClick={() => addFocusArea(skill)}
                        className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600 hover:border-brand-300 hover:text-brand-600"
                      >
                        <Plus className="h-3 w-3" aria-hidden="true" />
                        {skill}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div>
              <label htmlFor="instructions" className="text-sm font-medium text-slate-700">
                Topics or instructions <span className="font-normal text-slate-400">(optional)</span>
              </label>
              <textarea
                id="instructions"
                rows={3}
                value={form.instructions}
                onChange={(event) => update('instructions', event.target.value)}
                placeholder="e.g. Focus on API design and include a question about debugging production issues."
                className="input-base mt-1.5 resize-y"
                aria-describedby="instructions-count"
                aria-invalid={Boolean(errors.instructions)}
              />
              <p id="instructions-count" className={`mt-1 text-right text-xs ${form.instructions.length > MAX_INSTRUCTIONS_LENGTH ? 'text-red-700' : 'text-slate-400'}`}>
                {form.instructions.length}/{MAX_INSTRUCTIONS_LENGTH}
              </p>
              <FieldError id="instructions-error" message={errors.instructions} />
            </div>
          </section>

          <section className="surface-card space-y-3" aria-labelledby="setup-type">
            <h2 id="setup-type" className="text-base font-semibold">Interview type</h2>
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

          <section className="surface-card space-y-3" aria-labelledby="setup-mode">
            <h2 id="setup-mode" className="text-base font-semibold">Interaction mode</h2>
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
              <p className="flex gap-2 text-xs leading-5 text-slate-500">
                <Mic className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                Your browser will ask for microphone access when you first record. Recordings are only used to produce a transcript and are not stored.
              </p>
            )}
          </section>

          <section className="surface-card grid gap-5 sm:grid-cols-2" aria-label="Difficulty and duration">
            <fieldset>
              <legend className="text-sm font-medium text-slate-700">Difficulty</legend>
              <div className="mt-2 inline-flex rounded-lg border border-slate-200 bg-slate-50 p-1">
                {DIFFICULTY_OPTIONS.map((option) => (
                  <label
                    key={option.value}
                    className={`cursor-pointer rounded-md px-3 py-1.5 text-sm font-medium focus-within:ring-2 focus-within:ring-brand-300 ${
                      form.difficulty === option.value ? 'bg-white text-brand-600 shadow-sm' : 'text-slate-600'
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
              <label htmlFor="duration" className="text-sm font-medium text-slate-700">
                Duration
              </label>
              <select
                id="duration"
                value={form.durationMinutes}
                onChange={(event) => update('durationMinutes', Number(event.target.value))}
                className="input-base mt-2"
              >
                {durations.map((minutes) => (
                  <option key={minutes} value={minutes}>
                    {minutes} minutes{minutes === DEFAULT_DURATION_MINUTES ? ' (default)' : ''}
                  </option>
                ))}
              </select>
              <FieldError id="duration-error" message={errors.durationMinutes} />
            </div>
          </section>
        </div>

        <aside className="lg:sticky lg:top-24 lg:self-start">
          <div className="surface-card space-y-4" aria-labelledby="setup-summary">
            <h2 id="setup-summary" className="text-base font-semibold">Interview summary</h2>
            <dl className="space-y-2 text-sm">
              {[
                ['Role', form.targetRole.trim() || '—'],
                ['Type', typeLabel(form.interviewType)],
                ['Mode', modeLabel(form.interactionMode)],
                ['Difficulty', difficultyLabel(form.difficulty)],
                ['Duration', `${form.durationMinutes} minutes`],
                ['Questions', questionEstimate ? `Up to ${questionEstimate}` : '—'],
              ].map(([term, value]) => (
                <div key={term} className="flex justify-between gap-3">
                  <dt className="text-slate-500">{term}</dt>
                  <dd className="text-right font-medium text-slate-900">{value}</dd>
                </div>
              ))}
              <div>
                <dt className="text-slate-500">Focus areas</dt>
                <dd className="mt-1 text-slate-900">{form.focusAreas.length ? form.focusAreas.join(', ') : 'General for the role'}</dd>
              </div>
            </dl>
            <p className="flex gap-2 rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-600">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span>
                The timer starts when the first question appears and is enforced by the server. {SCORE_DISCLAIMER}
              </span>
            </p>
            {submitError && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700" role="alert">
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
                  Preparing your first question...
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
