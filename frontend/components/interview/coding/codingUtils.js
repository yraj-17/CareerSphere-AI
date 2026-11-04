/**
 * Shared helpers for the coding assessment workspace.
 * Everything shown here comes from the FastAPI coding API — nothing is computed or
 * invented client-side except presentation (labels, colours, table layout).
 */

export const CODE_KINDS = new Set(['coding', 'sql']);

export const isCodeQuestion = (question) => Boolean(question) && CODE_KINDS.has(question.kind);

// Mirrors backend SubmissionOut.status; QUEUED/RUNNING are the only non-terminal states.
export const PENDING_STATUSES = new Set(['QUEUED', 'RUNNING']);
export const isPending = (submission) => Boolean(submission) && PENDING_STATUSES.has(submission.status);

/** Backend source-size limit (settings.CODING_MAX_SOURCE_BYTES) — the server enforces it; this only avoids a pointless request. */
export const MAX_SOURCE_BYTES = 64 * 1024;
export const MAX_CUSTOM_INPUT_BYTES = 16 * 1024;

/** UTF-8 byte length (the backend limits are in bytes, not characters). */
export function byteLength(text) {
  const value = text || '';
  if (typeof TextEncoder !== 'undefined') return new TextEncoder().encode(value).length;
  return unescape(encodeURIComponent(value)).length;
}

export const VERDICT_TONE = {
  ACCEPTED: 'success',
  WRONG_ANSWER: 'danger',
  COMPILATION_ERROR: 'warning',
  RUNTIME_ERROR: 'danger',
  TIME_LIMIT_EXCEEDED: 'warning',
  MEMORY_LIMIT_EXCEEDED: 'warning',
  JUDGE_ERROR: 'neutral', // execution-service fault, never blamed on the candidate
  EXECUTED: 'info',
};

export const TONE_CLASSES = {
  success: 'border-emerald-300 bg-emerald-50 text-emerald-800',
  danger: 'border-red-300 bg-red-50 text-red-800',
  warning: 'border-amber-300 bg-amber-50 text-amber-900',
  info: 'border-sky-300 bg-sky-50 text-sky-900',
  neutral: 'border-slate-300 bg-slate-50 text-slate-700',
};

export const toneOf = (verdict) => VERDICT_TONE[verdict] || 'neutral';

export const DIFFICULTY_CLASSES = {
  EASY: 'border-emerald-300 bg-emerald-50 text-emerald-700',
  MEDIUM: 'border-amber-300 bg-amber-50 text-amber-800',
  HARD: 'border-red-300 bg-red-50 text-red-700',
};

/** Idempotency key accepted by the backend pattern ^[A-Za-z0-9_-]{8,64}$. */
export function newIdempotencyKey() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID().replace(/-/g, '');
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`;
}

/** Same request content ⇒ same fingerprint (used to reuse an idempotency key on retry). */
export const fingerprint = (type, language, source, customInput) =>
  JSON.stringify([type, language, source, customInput ?? null]);

export function formatTime(seconds) {
  if (seconds === null || seconds === undefined) return '—';
  return `${Math.round(seconds * 1000)} ms`;
}

export function formatMemory(kb) {
  if (kb === null || kb === undefined) return '—';
  return kb >= 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb} KB`;
}

export function formatTimestamp(value) {
  if (!value) return '';
  return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

/**
 * SQLite list-mode output (the backend runs `.mode list`, no header row, NULL shown as NULL):
 * one row per line, columns separated by '|'. Returns null when the output isn't tabular.
 */
export function parseSqlRows(stdout) {
  const text = (stdout || '').replace(/\n$/, '');
  if (!text) return [];
  const rows = text.split('\n').map((line) => line.split('|'));
  const width = rows[0].length;
  return rows.every((r) => r.length === width) ? rows : null;
}

/** Problem category → wording for its editor actions and panels. */
export function categoryCopy(category) {
  if (category === 'sql') {
    return {
      run: 'Run Query',
      submit: 'Submit Query',
      inputHeading: 'Schema',
      exampleInput: 'Sample dataset (setup SQL)',
      exampleOutput: 'Expected result',
      customLabel: 'Custom dataset',
      customHelp:
        'SQL statements that create and fill tables. They run before your query in a fresh, isolated SQLite database (never the application database).',
    };
  }
  return {
    run: 'Run Code',
    submit: 'Submit Solution',
    inputHeading: 'Input format',
    exampleInput: 'Input',
    exampleOutput: 'Expected output',
    customLabel: 'Custom input',
    customHelp: 'Sent to your program on standard input. Runs against your code only — it is not graded.',
  };
}

export const WORKSPACE_CUSTOM_HELP =
  'JSON describing the working directory: {"files": {"name": "content"}, "stdin": ""}. Each run starts from a fresh sandbox.';

/** Translate an API error into a candidate-facing message (never exposes service internals). */
export function codingErrorMessage(error, fallback) {
  const status = error?.response?.status;
  const detail = error?.response?.data?.detail;
  const message = typeof detail === 'string' ? detail : detail?.message;
  const code = detail?.status || detail?.stage;
  if (!error?.response) {
    if (error?.code === 'ECONNABORTED') return 'The request took too long. Your code may still be running — check Submission History.';
    return 'Unable to reach the server. Check your connection and try again.';
  }
  if (status === 401) return 'Your session has expired. Please sign in again to continue.';
  if (status === 429) return message || 'Too many requests. Please wait a moment and try again.';
  if (status === 503) return 'The code execution service is temporarily unavailable. Please try again shortly.';
  if (status === 409 && code === 'ENDED') return 'This interview has ended, so code can no longer be run or submitted.';
  if (status === 422 && Array.isArray(detail)) return detail.map((d) => d.msg?.replace(/^Value error, /, '')).join(' ');
  return message || fallback || 'Something went wrong. Please try again.';
}
