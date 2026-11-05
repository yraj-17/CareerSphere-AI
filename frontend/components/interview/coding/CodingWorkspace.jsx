'use client';

/**
 * LeetCode-style coding/SQL assessment workspace for one interview question.
 *
 * Problem, starter code, languages, execution and verdicts all come from the FastAPI
 * coding API (which alone talks to Judge0). Run and Submit are independent actions:
 * Run executes the sample tests (and optional custom input); Submit runs every sample
 * and hidden test and its latest completed result becomes the question's answer.
 *
 * The code draft ({ language, code: { LANG: source }, custom_input, edited }) is owned by
 * InterviewRoom and autosaved through the existing interview draft API, so it survives
 * question switches, language switches and page refreshes. Per-question UI state that is
 * not worth persisting (last result, tab, a submission still being polled) lives in the
 * `cache` object the room keeps for each question.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, Loader2, Play, RotateCcw, Send, Settings2, WandSparkles } from 'lucide-react';
import {
  getCodingLanguages,
  getCodingProblem,
  getCodingSubmission,
  listCodingSubmissions,
  retryCodeReview,
  runCode,
  submitCode,
} from '@/services/api';
import CodeEditor from '@/components/interview/coding/CodeEditor';
import ProblemPanel from '@/components/interview/coding/ProblemPanel';
import ResultsPanel from '@/components/interview/coding/ResultsPanel';
import {
  MAX_CUSTOM_INPUT_BYTES,
  MAX_SOURCE_BYTES,
  TONE_CLASSES,
  WORKSPACE_CUSTOM_HELP,
  byteLength,
  categoryCopy,
  codingErrorMessage,
  fingerprint,
  isPending,
  newIdempotencyKey,
  toneOf,
} from '@/components/interview/coding/codingUtils';

export const POLL_INTERVAL_MS = 1500;
// The AI review loads independently of (and much more slowly than) the Judge0 result.
export const REVIEW_POLL_INTERVAL_MS = 4000;
export const REVIEW_POLL_TIMEOUT_MS = 6 * 60 * 1000;
const reviewPending = (submission) => ['PENDING', 'RUNNING'].includes(submission?.ai_review?.status);
export const POLL_TIMEOUT_MS = 120000;
const MAX_POLL_FAILURES = 5;
const FORMATTABLE = new Set(['javascript']);

// Execution availability is per server, not per question: fetch once per page.
let languagesPromise = null;
function loadLanguages() {
  if (!languagesPromise) {
    languagesPromise = getCodingLanguages().catch((error) => {
      languagesPromise = null;
      throw error;
    });
  }
  return languagesPromise;
}
export function resetLanguageCache() {
  languagesPromise = null;
}

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

/** Draggable, keyboard-adjustable divider between two panels (value is a percentage). */
function Splitter({ orientation, value, onChange, containerRef, label, min = 20, max = 80 }) {
  const vertical = orientation === 'vertical';
  const onPointerDown = (event) => {
    event.preventDefault();
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const move = (e) => {
      const pct = vertical ? ((e.clientX - rect.left) / rect.width) * 100 : ((e.clientY - rect.top) / rect.height) * 100;
      onChange(clamp(Math.round(pct), min, max));
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };
  const onKeyDown = (event) => {
    const step = event.shiftKey ? 10 : 2;
    const back = vertical ? 'ArrowLeft' : 'ArrowUp';
    const fwd = vertical ? 'ArrowRight' : 'ArrowDown';
    if (event.key === back) onChange(clamp(value - step, min, max));
    else if (event.key === fwd) onChange(clamp(value + step, min, max));
    else return;
    event.preventDefault();
  };
  return (
    <div
      role="separator"
      tabIndex={0}
      aria-label={label}
      aria-orientation={vertical ? 'vertical' : 'horizontal'}
      aria-valuenow={value}
      aria-valuemin={min}
      aria-valuemax={max}
      onPointerDown={onPointerDown}
      onKeyDown={onKeyDown}
      className={`group hidden shrink-0 items-center justify-center lg:flex ${
        vertical ? 'w-2 cursor-col-resize' : 'h-2 cursor-row-resize'
      } focus:outline-none`}
    >
      <span
        className={`rounded-full bg-slate-300 transition-colors group-hover:bg-[var(--brand-amber)] group-focus:bg-[var(--brand-amber)] ${
          vertical ? 'h-10 w-1' : 'h-1 w-10'
        }`}
      />
    </div>
  );
}

function AnswerSummary({ answer }) {
  const ev = answer?.evaluation;
  if (!ev || ev.method !== 'judge0') return null;
  const correctness = ev.correctness_score ?? null;
  let quality = 'AI code review pending';
  if (ev.review_status === 'COMPLETED' && ev.quality_score !== null && ev.quality_score !== undefined) {
    quality = `AI code quality ${Math.round(ev.quality_score)}/100 · combined ${Math.round(ev.coding_score)}/100`;
  } else if (ev.review_status === 'FAILED') {
    quality = 'AI code review unavailable — scored on correctness only';
  }
  return (
    <p className={`rounded-md border px-2 py-1 text-xs ${TONE_CLASSES[toneOf(ev.verdict)]}`}>
      Recorded answer: <span className="font-semibold">{ev.verdict_label}</span> · {ev.correct}/{ev.total} tests
      {correctness !== null && <> · correctness {Math.round(correctness)}/100</>} · {quality} ({ev.language_label}). Submitting again replaces it.
    </p>
  );
}

export default function CodingWorkspace({
  interviewId,
  question,
  targetRole,
  draftMeta,
  onDraftChange,
  saveState,
  readOnly = false,
  onSubmissionComplete,
  cache,
}) {
  const [problem, setProblem] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [executionAvailable, setExecutionAvailable] = useState(true);
  const [view, setView] = useState(cache.view || { submission: null, phase: 'idle', error: '' });
  const [tab, setTab] = useState(cache.tab || 'tests');
  const [useCustomInput, setUseCustomInput] = useState(Boolean(cache.useCustomInput));
  const [history, setHistory] = useState(cache.history || []);
  const [historyState, setHistoryState] = useState({ loading: false, error: '' });
  const [split, setSplit] = useState(cache.split || 40);
  const [editorSplit, setEditorSplit] = useState(cache.editorSplit || 60);
  const [fontSize, setFontSize] = useState(14);
  const [wordWrap, setWordWrap] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const [retryingReview, setRetryingReview] = useState(false);
  const reviewTimer = useRef(null);
  const reviewToken = useRef(0);

  const mounted = useRef(true);
  const busyRef = useRef(false);
  const pollToken = useRef(0);
  const pollTimer = useRef(null);
  const lastAttempt = useRef(null); // { fp, key } of a request whose response was lost — retried with the same key
  const editorRef = useRef(null);
  const layoutRef = useRef(null);
  const rightRef = useRef(null);

  // Keep per-question UI state for when the candidate navigates back.
  useEffect(() => {
    Object.assign(cache, { view, tab, useCustomInput, history, split, editorSplit });
  }, [cache, view, tab, useCustomInput, history, split, editorSplit]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      pollToken.current += 1; // stops any polling loop for this question
      reviewToken.current += 1;
      window.clearTimeout(pollTimer.current);
      window.clearTimeout(reviewTimer.current);
    };
  }, []);

  // ---------------------------------------------------------------- problem + languages
  useEffect(() => {
    let cancelled = false;
    setLoadError('');
    getCodingProblem(interviewId, question.id)
      .then((data) => {
        if (!cancelled) setProblem(data);
      })
      .catch((error) => {
        if (!cancelled) setLoadError(codingErrorMessage(error, 'This problem could not be loaded.'));
      });
    loadLanguages()
      .then((data) => {
        if (!cancelled) setExecutionAvailable(Boolean(data.execution_available));
      })
      .catch(() => {}); // the problem endpoint still works; Run/Submit report errors themselves
    return () => {
      cancelled = true;
    };
  }, [interviewId, question.id]);

  const refreshHistory = useCallback(async () => {
    setHistoryState({ loading: true, error: '' });
    try {
      const items = await listCodingSubmissions(interviewId, question.id);
      if (!mounted.current) return;
      setHistory(items);
      setHistoryState({ loading: false, error: '' });
    } catch (error) {
      if (mounted.current) setHistoryState({ loading: false, error: codingErrorMessage(error, 'History could not be loaded.') });
    }
  }, [interviewId, question.id]);

  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  // ---------------------------------------------------------------- draft (language + per-language code)
  const languages = problem?.languages || [];
  const language = languages.some((l) => l.key === draftMeta?.language) ? draftMeta.language : languages[0]?.key;
  const languageInfo = languages.find((l) => l.key === language);
  const codeByLanguage = useMemo(() => draftMeta?.code || {}, [draftMeta]);
  const starter = problem?.starter_code?.[language] ?? '';
  const source = codeByLanguage[language] ?? starter;
  const harnessWorkspace = problem?.category === 'bash' && (problem?.examples?.[0]?.input || '').trim().startsWith('{"files"');
  const customInput = draftMeta?.custom_input ?? problem?.examples?.[0]?.input ?? '';
  const copy = categoryCopy(problem?.category);
  const sql = problem?.category === 'sql';

  const saveDraft = useCallback(
    (changes) => {
      onDraftChange({
        language,
        code: codeByLanguage,
        custom_input: draftMeta?.custom_input ?? null,
        edited: Boolean(draftMeta?.edited),
        ...changes,
      });
    },
    [codeByLanguage, draftMeta, language, onDraftChange]
  );

  const onCodeChange = (value) => {
    if (value === source) return;
    saveDraft({ code: { ...codeByLanguage, [language]: value }, edited: true });
  };

  const onLanguageChange = (next) => {
    // Code written for the previous language stays in its own slot.
    saveDraft({ language: next });
  };

  const resetCode = () => {
    const nextCode = { ...codeByLanguage };
    delete nextCode[language];
    saveDraft({ code: nextCode });
    setConfirmReset(false);
  };

  // ---------------------------------------------------------------- execution + polling
  // Poll a submission's AI review on its own (slow) loop; the Judge0 result is already shown.
  const pollReview = useCallback(
    (submission) => {
      const token = ++reviewToken.current;
      const startedAt = Date.now();
      const tick = async () => {
        if (token !== reviewToken.current || !mounted.current) return;
        try {
          const latest = await getCodingSubmission(interviewId, submission.id);
          if (token !== reviewToken.current || !mounted.current) return;
          setView((prev) => (prev.submission?.id === latest.id ? { ...prev, submission: latest } : prev));
          if (!reviewPending(latest)) {
            onSubmissionComplete?.(latest); // refresh the recorded answer (combined score) in the room
            return;
          }
        } catch {
          // transient: try again on the next tick
        }
        if (Date.now() - startedAt < REVIEW_POLL_TIMEOUT_MS) reviewTimer.current = window.setTimeout(tick, REVIEW_POLL_INTERVAL_MS);
      };
      window.clearTimeout(reviewTimer.current);
      reviewTimer.current = window.setTimeout(tick, REVIEW_POLL_INTERVAL_MS);
    },
    [interviewId, onSubmissionComplete]
  );

  const finish = useCallback(
    (submission) => {
      busyRef.current = false;
      if (!mounted.current) return;
      setView({ submission, phase: 'done', error: '' });
      refreshHistory();
      if (submission.submission_type === 'SUBMIT') {
        onSubmissionComplete?.(submission);
        if (reviewPending(submission)) pollReview(submission);
      }
    },
    [onSubmissionComplete, pollReview, refreshHistory]
  );

  const retryReview = async () => {
    const submission = view.submission;
    if (!submission || retryingReview) return;
    setRetryingReview(true);
    try {
      const latest = await retryCodeReview(interviewId, submission.id);
      if (!mounted.current) return;
      setView((prev) => (prev.submission?.id === latest.id ? { ...prev, submission: latest } : prev));
      onSubmissionComplete?.(latest);
    } catch (error) {
      if (mounted.current) setView((prev) => ({ ...prev, error: codingErrorMessage(error, 'The review could not be retried.') }));
    } finally {
      if (mounted.current) setRetryingReview(false);
    }
  };

  const poll = useCallback(
    (submission) => {
      const token = ++pollToken.current;
      const startedAt = Date.now();
      let failures = 0;
      const tick = async () => {
        if (token !== pollToken.current || !mounted.current) return;
        try {
          const latest = await getCodingSubmission(interviewId, submission.id);
          if (token !== pollToken.current || !mounted.current) return;
          failures = 0;
          if (!isPending(latest)) {
            finish(latest);
            return;
          }
          if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
            busyRef.current = false;
            setView({
              submission: latest,
              phase: 'done',
              error: 'This is taking longer than expected. It keeps running on the server — check its status in a moment.',
              canCheckStatus: true,
            });
            return;
          }
          setView({ submission: latest, phase: 'polling', error: '' });
          pollTimer.current = window.setTimeout(tick, POLL_INTERVAL_MS);
        } catch (error) {
          if (token !== pollToken.current || !mounted.current) return;
          failures += 1;
          if (error?.response?.status === 401 || failures >= MAX_POLL_FAILURES) {
            busyRef.current = false;
            setView({ submission, phase: 'done', error: codingErrorMessage(error), canCheckStatus: error?.response?.status !== 401 });
            return;
          }
          setView({ submission, phase: 'reconnecting', error: '' });
          pollTimer.current = window.setTimeout(tick, POLL_INTERVAL_MS * 2);
        }
      };
      window.clearTimeout(pollTimer.current);
      pollTimer.current = window.setTimeout(tick, POLL_INTERVAL_MS);
    },
    [finish, interviewId]
  );

  // Returning to a question whose run/submission (or its AI review) was still pending: resume polling it.
  useEffect(() => {
    const pending = cache.view?.submission;
    if (pending && isPending(pending)) {
      busyRef.current = true;
      setView({ submission: pending, phase: 'polling', error: '' });
      poll(pending);
    } else if (pending && reviewPending(pending)) {
      pollReview(pending);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const busy = ['sending', 'polling', 'reconnecting'].includes(view.phase);
  const activeAction = view.action || view.submission?.submission_type;

  const execute = async (type) => {
    if (busyRef.current || readOnly || !language) return;
    const code = source;
    if (!code.trim()) {
      setView({ submission: null, phase: 'error', error: 'Write some code before running it.' });
      return;
    }
    if (byteLength(code) > MAX_SOURCE_BYTES) {
      setView({ submission: null, phase: 'error', error: `Your code is larger than ${MAX_SOURCE_BYTES / 1024} KB. Please shorten it.` });
      return;
    }
    const custom = type === 'RUN' && useCustomInput ? customInput : null;
    if (custom !== null && byteLength(custom) > MAX_CUSTOM_INPUT_BYTES) {
      setView({ submission: null, phase: 'error', error: `Custom input is larger than ${MAX_CUSTOM_INPUT_BYTES / 1024} KB.` });
      return;
    }
    const fp = fingerprint(type, language, code, custom);
    const key = lastAttempt.current?.fp === fp ? lastAttempt.current.key : newIdempotencyKey();
    lastAttempt.current = { fp, key };
    busyRef.current = true;
    setTab('tests');
    setView({ submission: null, phase: 'sending', error: '', action: type });
    try {
      const submission =
        type === 'RUN'
          ? await runCode(interviewId, question.id, { language, sourceCode: code, customInput: custom, idempotencyKey: key })
          : await submitCode(interviewId, question.id, { language, sourceCode: code, idempotencyKey: key });
      lastAttempt.current = null;
      if (!mounted.current) return;
      if (isPending(submission)) {
        setView({ submission, phase: 'polling', error: '' });
        poll(submission);
      } else {
        finish(submission);
      }
    } catch (error) {
      busyRef.current = false;
      const status = error?.response?.status;
      // Lost response or execution service down: the same key safely resumes the same request.
      if (status && status !== 503) lastAttempt.current = null;
      if (!mounted.current) return;
      setView({ submission: null, phase: 'error', error: codingErrorMessage(error) });
      if (status === 409) onSubmissionComplete?.(null); // e.g. interview ended — let the room refresh
      if (!status || status === 503) refreshHistory();
    }
  };

  const checkStatus = () => {
    const submission = view.submission;
    if (!submission || busyRef.current) return;
    busyRef.current = true;
    setView({ submission, phase: 'polling', error: '' });
    poll(submission);
  };

  const selectHistory = async (item) => {
    if (busyRef.current) return; // never interrupt an active run
    setTab('tests');
    try {
      const full = await getCodingSubmission(interviewId, item.id);
      if (mounted.current) setView({ submission: full, phase: 'done', error: '', historical: true });
    } catch (error) {
      if (mounted.current) setView({ submission: item, phase: 'done', error: codingErrorMessage(error), historical: true });
    }
  };

  // ---------------------------------------------------------------- render
  if (loadError) {
    return (
      <div role="alert" className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
        <AlertCircle className="h-4 w-4" aria-hidden="true" />
        {loadError}
      </div>
    );
  }
  if (!problem) {
    return (
      <div className="flex min-h-[16rem] items-center justify-center gap-2 text-sm text-slate-500" role="status">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        Loading the problem…
      </div>
    );
  }
  if (languages.length === 0) {
    return (
      <div role="alert" className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
        No compatible programming language is available for this problem, so it can&apos;t be attempted here. It is not scored.
      </div>
    );
  }

  const disabled = busy || readOnly || !executionAvailable;
  const editorPath = `${question.id}/${language}`;

  return (
    <div
      ref={layoutRef}
      className="flex flex-col gap-3 lg:h-[calc(100vh-9rem)] lg:min-h-[640px] lg:flex-row lg:gap-0"
      aria-label={sql ? 'SQL assessment workspace' : 'Coding assessment workspace'}
    >
      {/* Left: problem */}
      <div
        className="min-h-0 rounded-xl border border-slate-200 bg-white p-4 lg:overflow-hidden"
        style={{ flexBasis: `${split}%` }}
      >
        <ProblemPanel problem={problem} question={question} targetRole={targetRole} practical={question.practical} />
      </div>

      <Splitter orientation="vertical" value={split} onChange={setSplit} containerRef={layoutRef} label="Resize problem panel" min={25} max={60} />

      {/* Right: editor + results */}
      <div ref={rightRef} className="flex min-h-0 min-w-0 flex-1 flex-col gap-3 lg:gap-0">
        <div
          className="flex min-h-[420px] flex-col overflow-hidden rounded-xl border border-[#22324D] bg-[#101B2D] lg:min-h-0"
          style={{ flexBasis: `${editorSplit}%` }}
        >
          <div className="flex flex-wrap items-center gap-2 border-b border-[#2A3A57] px-3 py-2">
            <label htmlFor={`lang-${question.id}`} className="sr-only">
              Programming language
            </label>
            <select
              id={`lang-${question.id}`}
              value={language}
              onChange={(e) => onLanguageChange(e.target.value)}
              disabled={busy || readOnly}
              className="rounded-md border border-[#3A4B69] bg-[#17243A] px-2 py-1 text-xs font-semibold text-[#E6EAF2] focus:border-[var(--brand-amber)] focus:outline-none"
            >
              {languages.map((l) => (
                <option key={l.key} value={l.key}>
                  {l.label}
                </option>
              ))}
            </select>
            {languageInfo?.notes && <span className="hidden text-[11px] text-[#9AA7BD] xl:inline">{languageInfo.notes}</span>}
            <span className="ml-auto text-[11px] text-[#9AA7BD]" aria-live="polite">
              {saveState}
            </span>
            <div className="relative flex items-center gap-1">
              {confirmReset ? (
                <span className="flex items-center gap-1 text-[11px] text-[#E6EAF2]">
                  Reset {languageInfo?.label} to the starter code?
                  <button type="button" onClick={resetCode} className="rounded border border-[#F08A8A] px-1.5 py-0.5 font-semibold text-[#FFC9C9] hover:bg-[#5A2230]">
                    Reset
                  </button>
                  <button type="button" onClick={() => setConfirmReset(false)} className="rounded border border-[#4F5E78] px-1.5 py-0.5 hover:bg-[#22324D]">
                    Cancel
                  </button>
                </span>
              ) : (
                <button
                  type="button"
                  onClick={() => setConfirmReset(true)}
                  disabled={busy || readOnly || source === starter}
                  className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-[#C9D2E0] hover:bg-[#22324D] disabled:opacity-40"
                >
                  <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                  Reset code
                </button>
              )}
              <button
                type="button"
                onClick={() => setSettingsOpen((v) => !v)}
                aria-expanded={settingsOpen}
                aria-label="Editor settings"
                className="rounded-md p-1.5 text-[#C9D2E0] hover:bg-[#22324D]"
              >
                <Settings2 className="h-4 w-4" aria-hidden="true" />
              </button>
              {settingsOpen && (
                <div className="absolute right-0 top-9 z-20 w-56 space-y-2 rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-700 shadow-lg">
                  <label className="flex items-center justify-between gap-2">
                    Font size
                    <select value={fontSize} onChange={(e) => setFontSize(Number(e.target.value))} className="rounded border border-slate-300 px-1 py-0.5">
                      {[12, 13, 14, 15, 16, 18].map((size) => (
                        <option key={size} value={size}>
                          {size}px
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex items-center justify-between gap-2">
                    Word wrap
                    <input type="checkbox" checked={wordWrap} onChange={(e) => setWordWrap(e.target.checked)} />
                  </label>
                  {FORMATTABLE.has(languageInfo?.monaco_language) && (
                    <button
                      type="button"
                      onClick={() => editorRef.current?.getAction('editor.action.formatDocument')?.run()}
                      disabled={readOnly}
                      className="btn-outline w-full justify-center px-2 py-1 text-xs"
                    >
                      <WandSparkles className="h-3.5 w-3.5" aria-hidden="true" />
                      Format code
                    </button>
                  )}
                  <p className="text-[11px] text-slate-500">Ctrl/⌘ + Enter runs your code.</p>
                </div>
              )}
            </div>
          </div>

          <div className="min-h-0 flex-1">
            <CodeEditor
              path={editorPath}
              language={languageInfo?.monaco_language || 'plaintext'}
              value={source}
              onChange={onCodeChange}
              readOnly={readOnly}
              fontSize={fontSize}
              wordWrap={wordWrap}
              onRunShortcut={() => execute('RUN')}
              onEditorReady={(editor) => {
                editorRef.current = editor;
              }}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2 border-t border-[#2A3A57] px-3 py-2">
            {!executionAvailable && <span className="text-xs text-[#F2C27B]">Code execution is unavailable on this server right now.</span>}
            {readOnly && <span className="text-xs text-[#9AA7BD]">The interview has ended — code is read-only.</span>}
            <div className="ml-auto flex gap-2">
              <button
                type="button"
                onClick={() => execute('RUN')}
                disabled={disabled}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[#4F5E78] px-3 py-1.5 text-sm font-semibold text-[#E6EAF2] hover:bg-[#22324D] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy && activeAction === 'RUN' ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Play className="h-4 w-4" aria-hidden="true" />
                )}
                {busy && activeAction === 'RUN' ? 'Running…' : copy.run}
              </button>
              <button
                type="button"
                onClick={() => execute('SUBMIT')}
                disabled={disabled}
                className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--brand-amber)] px-3 py-1.5 text-sm font-semibold text-[var(--brand-deep-navy)] hover:bg-[var(--brand-yellow)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy && activeAction === 'SUBMIT' ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Send className="h-4 w-4" aria-hidden="true" />
                )}
                {busy && activeAction === 'SUBMIT' ? 'Judging…' : copy.submit}
              </button>
            </div>
          </div>
        </div>

        <Splitter orientation="horizontal" value={editorSplit} onChange={setEditorSplit} containerRef={rightRef} label="Resize editor and results" min={30} max={80} />

        <div className="flex min-h-[18rem] flex-1 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white lg:min-h-0">
          {question.answer && (
            <div className="border-b border-slate-100 px-3 py-2">
              <AnswerSummary answer={question.answer} />
            </div>
          )}
          <ResultsPanel
            tab={tab}
            onTab={setTab}
            copy={copy}
            sql={sql}
            view={view}
            customInput={customInput}
            onCustomInputChange={(value) => saveDraft({ custom_input: value })}
            useCustomInput={useCustomInput}
            onUseCustomInputChange={setUseCustomInput}
            customHelp={harnessWorkspace ? WORKSPACE_CUSTOM_HELP : copy.customHelp}
            readOnly={readOnly}
            history={history}
            historyState={historyState}
            onRefreshHistory={refreshHistory}
            onSelectHistory={selectHistory}
            onCheckStatus={checkStatus}
            onRetryReview={retryReview}
            retryingReview={retryingReview}
          />
        </div>
      </div>
    </div>
  );
}
