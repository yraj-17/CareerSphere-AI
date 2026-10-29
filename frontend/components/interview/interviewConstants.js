export const INTERVIEW_TYPE_OPTIONS = [
  {
    value: 'TECHNICAL',
    label: 'Technical',
    description: 'Role-relevant knowledge, practical scenarios, problem solving, and reasoning.',
  },
  {
    value: 'BEHAVIORAL',
    label: 'Behavioral / HR',
    description: 'Teamwork, communication, conflict resolution, ownership, and decisions.',
  },
  {
    value: 'MIXED',
    label: 'Mixed',
    description: 'Alternates technical and behavioral questions.',
  },
];

export const MODE_OPTIONS = [
  { value: 'TEXT', label: 'Text interview', description: 'Read each question and type your answer.' },
  {
    value: 'VOICE',
    label: 'Voice interview',
    description: 'Record a spoken answer, review the transcript, then submit.',
  },
];

export const DIFFICULTY_OPTIONS = [
  { value: 'BEGINNER', label: 'Beginner' },
  { value: 'INTERMEDIATE', label: 'Intermediate' },
  { value: 'ADVANCED', label: 'Advanced' },
];

export const DEFAULT_DURATION_MINUTES = 15;
export const FALLBACK_DURATIONS = [10, 15, 20, 30];
/** Mirrors the backend question budget per duration (about 2.5 minutes per question). */
export const QUESTIONS_PER_DURATION = { 10: 4, 15: 6, 20: 8, 30: 12 };
export const MAX_ROLE_LENGTH = 120;
export const MAX_FOCUS_AREA_LENGTH = 60;
export const MAX_INSTRUCTIONS_LENGTH = 500;
export const DEFAULT_MAX_ANSWER_LENGTH = 5000;

export const STATUS_META = {
  IN_PROGRESS: { label: 'In progress', className: 'border-brand-200 bg-brand-50 text-brand-600' },
  COMPLETED: { label: 'Completed', className: 'border-emerald-200 bg-emerald-50 text-emerald-700' },
  EXPIRED: { label: 'Time limit reached', className: 'border-amber-200 bg-amber-50 text-amber-800' },
  ABANDONED: { label: 'Ended early', className: 'border-slate-200 bg-slate-100 text-slate-600' },
};

export const DIMENSION_LABELS = {
  accuracy: 'Technical accuracy',
  reasoning: 'Reasoning & problem solving',
  relevance: 'Relevance',
  clarity: 'Clarity & communication',
  structure: 'Structure & specificity',
  reflection: 'Reflection & ownership',
};

export const SCORE_DISCLAIMER =
  'AI-generated practice feedback. Scores are not a hiring decision and do not predict real interview outcomes.';

export function labelFor(options, value) {
  return options.find((option) => option.value === value)?.label || value;
}

export function typeLabel(value) {
  return labelFor(INTERVIEW_TYPE_OPTIONS, value);
}

export function difficultyLabel(value) {
  return labelFor(DIFFICULTY_OPTIONS, value);
}

export function modeLabel(value) {
  return value === 'VOICE' ? 'Voice' : 'Text';
}

export function categoryLabel(value) {
  return value === 'BEHAVIORAL' ? 'Behavioral' : 'Technical';
}

export function formatClock(totalSeconds) {
  const safe = Math.max(0, Math.floor(totalSeconds || 0));
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

export function scoreBand(score) {
  if (score === null || score === undefined) return { label: 'Not scored', className: 'text-slate-500' };
  if (score >= 85) return { label: 'Strong', className: 'text-emerald-700' };
  if (score >= 70) return { label: 'Solid', className: 'text-brand-600' };
  if (score >= 50) return { label: 'Developing', className: 'text-amber-700' };
  return { label: 'Needs work', className: 'text-red-700' };
}

export function formatDateTime(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

/** Pull the user-facing message (and structured fields) out of an API error. */
export function apiErrorDetail(error) {
  const detail = error?.response?.data?.detail;
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) return detail;
  return {};
}
