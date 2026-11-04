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

export const MAX_JOB_DESCRIPTION_LENGTH = 4000;
export const MIN_QUESTIONS = 3;

export const PRACTICAL_KIND_LABELS = {
  coding: 'Coding',
  sql: 'SQL',
  calculation: 'Practical calculation',
  scenario: 'Practical scenario',
};

/** Report status of a practical slot (backend: interview_scoring._practical_section). */
export const PRACTICAL_STATUS_LABELS = {
  not_available: 'No verified assessment',
  awaiting_editor: 'Verified problem assigned · code submission not available (not scored)',
  not_reached: 'Not reached',
  not_answered: 'Not answered',
  not_assessed: 'Not assessed',
  assessed: 'Assessed',
};

/** How a practical result was produced. */
export const PRACTICAL_METHOD_LABELS = {
  deterministic: 'Auto-graded',
  ai_rubric: 'AI-reviewed, not executed',
  judge0: 'Executed on Judge0',
};

export function slotKindLabel(kind) {
  return kind === 'question' ? 'Conceptual' : PRACTICAL_KIND_LABELS[kind] || 'Practical';
}

/** Mirrors the backend rule: technical = ceil(n/3) practical; mixed reserves inside the technical half. */
export function practicalCount(interviewType, total) {
  if (interviewType === 'TECHNICAL') return Math.ceil(total / 3);
  if (interviewType === 'MIXED') return Math.ceil(Math.ceil(total / 2) / 3);
  return 0;
}

const SENIORITY_WORDS = new Set([
  'senior', 'sr', 'junior', 'jr', 'lead', 'principal', 'staff', 'associate', 'intern', 'trainee',
  'graduate', 'fresher', 'entry', 'level', 'mid', 'chief', 'head', 'experienced',
]);
const LEVEL_SUFFIX = new Set(['i', 'ii', 'iii', 'iv', '1', '2', '3', '4']);

export function titleKey(title) {
  return (title || '')
    .toLowerCase()
    .replace(/\(.*?\)/g, ' ')
    .replace(/[^a-z0-9+#/]+/g, ' ')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .join(' ');
}

/** Client-side preview of the backend's exact/alias role match (the backend stays authoritative). */
export function matchCatalogRole(title, roles = []) {
  const words = titleKey(title).split(' ').filter(Boolean);
  const stripped = words.filter((word) => !SENIORITY_WORDS.has(word));
  const candidates = [words.join(' '), stripped.join(' ')];
  if (stripped.length && LEVEL_SUFFIX.has(stripped[stripped.length - 1])) candidates.push(stripped.slice(0, -1).join(' '));
  for (const key of candidates) {
    if (!key) continue;
    const found = roles.find((role) => [role.title, ...(role.aliases || [])].some((name) => titleKey(name) === key));
    if (found) return found;
  }
  return null;
}
