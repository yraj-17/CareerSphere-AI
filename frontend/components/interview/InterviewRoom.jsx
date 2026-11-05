'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Clock,
  Flag,
  Loader2,
  RotateCcw,
  Send,
  Volume2,
  VolumeX,
} from 'lucide-react';
import {
  completeInterview,
  extractErrorMessage,
  getInterview,
  navigateInterview,
  retryInterviewEvaluation,
  saveInterviewDraft,
  submitInterviewAnswer,
} from '@/services/api';
import AnswerFeedback from '@/components/interview/AnswerFeedback';
import { CalculationForm, PracticalUnavailable, ScenarioBrief } from '@/components/interview/PracticalTask';
import CodingWorkspace from '@/components/interview/coding/CodingWorkspace';
import { isCodeQuestion } from '@/components/interview/coding/codingUtils';
import VoiceAnswerPanel from '@/components/interview/VoiceAnswerPanel';
import useSpeechSynthesis from '@/hooks/useSpeechSynthesis';
import {
  DEFAULT_MAX_ANSWER_LENGTH,
  STATUS_META,
  SCORE_DISCLAIMER,
  categoryLabel,
  difficultyLabel,
  formatClock,
  modeLabel,
  slotKindLabel,
  typeLabel,
} from '@/components/interview/interviewConstants';

const AUTOSAVE_DELAY_MS = 800;
// Follow-ups use question_order = 100 + parent position (backend FOLLOW_UP_ORDER_OFFSET).
const FOLLOW_UP_ORDER_OFFSET = 100;
const isFollowUpQuestion = (q) => Boolean(q?.parent_question_id);
const CODE_AUTOSAVE_DELAY_MS = 1200;
const PREPARING_POLL_MS = 2500;

export const QUESTION_STATUS = {
  NOT_STARTED: { label: 'Not started', className: 'border-slate-200 bg-white text-slate-600' },
  SKIPPED: { label: 'Skipped', className: 'border-amber-300 bg-amber-50 text-amber-800' },
  IN_PROGRESS: { label: 'In progress', className: 'border-brand-300 bg-brand-50 text-brand-600' },
  SUBMITTED: { label: 'Submitted', className: 'border-emerald-300 bg-emerald-50 text-emerald-700' },
  ANSWERED: { label: 'Answered', className: 'border-emerald-600 bg-emerald-600 text-white' },
  UNAVAILABLE: { label: 'Not available', className: 'border-dashed border-slate-300 bg-slate-50 text-slate-400' },
  PREPARING: { label: 'Preparing', className: 'border-dashed border-slate-300 bg-white text-slate-400' },
};

/** Monotonic per-tab sequence: never repeats or goes backwards, even within one millisecond. */
/**
 * A draft counts as started if it has text, (calculations) at least one filled field,
 * or (code) the candidate has edited the starter code.
 */
function draftHasContent(draft) {
  if (!draft) return false;
  if ((draft.text || '').trim()) return true;
  if (draft.meta?.code) return Boolean(draft.meta.edited) && Object.values(draft.meta.code).some((src) => String(src || '').trim());
  return Object.values(draft.meta?.answers || {}).some((value) => String(value || '').trim());
}

function makeSequencer() {
  let last = 0;
  return () => {
    last = Math.max(last + 1, Date.now());
    return last;
  };
}

function Badge({ children }) {
  return (
    <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-xs font-medium text-slate-600">
      {children}
    </span>
  );
}

function FinishDialog({ summary, ending, error, onCancel, onConfirm, onGoTo }) {
  const cancelRef = useRef(null);
  useEffect(() => {
    cancelRef.current?.focus();
    const onKey = (event) => {
      if (event.key === 'Escape' && !ending) onCancel();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [ending, onCancel]);

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/50 p-4">
      <div role="dialog" aria-modal="true" aria-labelledby="finish-title" className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <h2 id="finish-title" className="text-lg font-semibold">Finish this interview?</h2>
        <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
          <div className="rounded-lg bg-emerald-50 p-2">
            <dt className="text-xs text-emerald-700">Answered</dt>
            <dd className="text-lg font-semibold text-emerald-800">{summary.answered}</dd>
          </div>
          <div className="rounded-lg bg-slate-50 p-2">
            <dt className="text-xs text-slate-600">Unanswered</dt>
            <dd className="text-lg font-semibold text-slate-800">{summary.unanswered}</dd>
          </div>
        </dl>
        {summary.drafts.length > 0 && (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <p className="font-medium">Saved drafts that were not submitted (they will not be scored):</p>
            <ul className="mt-1 space-y-1">
              {summary.drafts.map((q) => (
                <li key={q.id} className="flex items-center justify-between gap-2">
                  <span>Question {q.question_order}</span>
                  <button type="button" onClick={() => onGoTo(q.question_order)} className="text-xs font-semibold underline">
                    Go to question {q.question_order}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {summary.unansweredQuestions.length > 0 && (
          <p className="mt-3 text-sm text-slate-600">
            Unanswered:{' '}
            {summary.unansweredQuestions.map((q, i) => (
              <React.Fragment key={q.id}>
                {i > 0 && ', '}
                <button type="button" onClick={() => onGoTo(q.question_order)} className="font-medium text-brand-600 underline">
                  Q{q.question_order}
                </button>
              </React.Fragment>
            ))}
          </p>
        )}
        <p className="mt-3 text-xs text-slate-500">After you finish, answers can no longer be changed.</p>
        {error && (
          <p className="mt-3 text-sm text-red-700" role="alert">
            {error}
          </p>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <button ref={cancelRef} type="button" onClick={onCancel} disabled={ending} className="btn-outline">
            Keep going
          </button>
          <button type="button" onClick={onConfirm} disabled={ending} className="btn-danger">
            {ending && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
            Finish interview
          </button>
        </div>
      </div>
    </div>
  );
}

function EndedState({ interview }) {
  const meta = STATUS_META[interview.status] || STATUS_META.COMPLETED;
  const hasReport = interview.answered_count > 0;
  const message = {
    COMPLETED: 'This interview is complete.',
    EXPIRED: 'The time limit for this interview was reached. Answers submitted before the deadline were saved.',
    ABANDONED: 'This interview ended before any answers were submitted, so there is no report.',
  }[interview.status];

  return (
    <div className="surface-card mx-auto max-w-xl text-center">
      <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${meta.className}`}>{meta.label}</span>
      <h1 className="mt-3 text-xl font-semibold">{interview.target_role}</h1>
      <p className="mt-2 text-sm text-slate-600">{message}</p>
      <p className="mt-1 text-sm text-slate-500">
        {interview.answered_count} of {interview.max_questions} question{interview.max_questions === 1 ? '' : 's'} answered
      </p>
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        {hasReport && (
          <Link href={`/dashboard/interview/${interview.id}/results`} className="btn-primary">
            View report
          </Link>
        )}
        <Link href="/dashboard/interview/history" className="btn-outline">
          Interview history
        </Link>
        <Link href="/dashboard/interview" className="btn-outline">
          Start a new interview
        </Link>
      </div>
    </div>
  );
}

export default function InterviewRoom({ interviewId }) {
  const router = useRouter();
  const speech = useSpeechSynthesis();

  const [interview, setInterview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [notFound, setNotFound] = useState(false);
  const [clockOffset, setClockOffset] = useState(0);
  const [nowMs, setNowMs] = useState(() => Date.now());

  const [position, setPosition] = useState(null);
  // Local drafts keyed by question ID: { text, meta, source, revision, savedRevision, saving, error }
  // (meta holds structured answers, e.g. calculation fields: { answers: { key: value } })
  const [drafts, setDrafts] = useState({});
  const [submittingId, setSubmittingId] = useState(null);
  const [submitError, setSubmitError] = useState('');
  const [retryingAnswerId, setRetryingAnswerId] = useState(null);
  const [finishOpen, setFinishOpen] = useState(false);
  const [ending, setEnding] = useState(false);
  const [endError, setEndError] = useState('');
  const [timeUp, setTimeUp] = useState(false);

  const [nextSeq] = useState(makeSequencer);
  const latestNavSeq = useRef(0);
  const saveTimers = useRef({});
  // Per-question coding workspace UI state (last result, tab, polling) kept across navigation.
  const workspaceCaches = useRef({});
  const draftsRef = useRef(drafts);
  const timeUpHandled = useRef(false);

  useEffect(() => {
    draftsRef.current = drafts;
  }, [drafts]);

  const applyInterview = useCallback((data) => {
    const clientNow = Date.now();
    setInterview(data);
    setClockOffset(new Date(data.server_time).getTime() - clientNow);
    setNowMs(clientNow);
    // Seed local drafts from the server only for questions without local edits.
    setDrafts((prev) => {
      const next = { ...prev };
      for (const q of data.questions || []) {
        if (q.answer && !isCodeQuestion(q)) {
          delete next[q.id];
        } else if (!next[q.id] && (q.draft_text || q.draft_meta)) {
          next[q.id] = {
            text: q.draft_text || '',
            meta: q.draft_meta || null,
            source: 'TEXT',
            revision: q.draft_revision,
            savedRevision: q.draft_revision,
          };
        }
      }
      return next;
    });
  }, []);

  const refresh = useCallback(async () => {
    const data = await getInterview(interviewId);
    applyInterview(data);
    return data;
  }, [applyInterview, interviewId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await getInterview(interviewId);
        if (cancelled) return;
        applyInterview(data);
        const firstOpen = data.current_question?.question_order;
        setPosition(data.current_position || firstOpen || 1);
      } catch (error) {
        if (cancelled) return;
        if (error?.response?.status === 404) setNotFound(true);
        else setLoadError(extractErrorMessage(error));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [applyInterview, interviewId]);

  const inProgress = interview?.status === 'IN_PROGRESS';

  useEffect(() => {
    if (!inProgress) return undefined;
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [inProgress]);

  // While planned questions or a follow-up are still being prepared, refresh periodically.
  useEffect(() => {
    if (!inProgress || !(interview?.preparing || interview?.follow_ups_pending)) return undefined;
    const timer = window.setTimeout(() => {
      refresh().catch(() => {});
    }, PREPARING_POLL_MS);
    return () => window.clearTimeout(timer);
  }, [inProgress, interview, refresh]);

  const remainingSeconds = inProgress
    ? Math.max(0, Math.floor((new Date(interview.deadline_at).getTime() - (nowMs + clockOffset)) / 1000))
    : 0;

  const total = interview?.max_questions || 0;
  const questionsByPosition = useMemo(() => {
    const map = {};
    for (const q of interview?.questions || []) map[q.question_order] = q;
    return map;
  }, [interview]);
  const selected = position ? questionsByPosition[position] : null;
  const sequence = useMemo(() => {
    const order = [];
    for (let n = 1; n <= total; n += 1) {
      order.push(n);
      if (questionsByPosition[FOLLOW_UP_ORDER_OFFSET + n]) order.push(FOLLOW_UP_ORDER_OFFSET + n);
    }
    return order;
  }, [questionsByPosition, total]);
  const sequenceIndex = sequence.indexOf(position);

  // ---------------------------------------------------------------------------
  // Drafts: local first, autosaved to the server; the highest revision wins there.
  // ---------------------------------------------------------------------------

  const persistDraft = useCallback(
    async (questionId) => {
      window.clearTimeout(saveTimers.current[questionId]);
      delete saveTimers.current[questionId];
      const draft = draftsRef.current[questionId];
      if (!draft || draft.savedRevision === draft.revision) return;
      const { revision } = draft;
      setDrafts((prev) => (prev[questionId] ? { ...prev, [questionId]: { ...prev[questionId], saving: true } } : prev));
      try {
        const result = await saveInterviewDraft(interviewId, questionId, { text: draft.text || '', meta: draft.meta || null, revision });
        setDrafts((prev) => {
          const current = prev[questionId];
          if (!current) return prev;
          // saved === false: a newer draft (e.g. from another tab) is stored; keep ours marked unsaved.
          const savedRevision = result.saved ? Math.max(current.savedRevision || 0, revision) : current.savedRevision;
          return { ...prev, [questionId]: { ...current, saving: false, error: false, savedRevision } };
        });
      } catch {
        // Keep the text locally and retry on the next change or navigation.
        setDrafts((prev) => (prev[questionId] ? { ...prev, [questionId]: { ...prev[questionId], saving: false, error: true } } : prev));
      }
    },
    [interviewId]
  );

  const updateDraft = (questionId, text, source = 'TEXT') => {
    setDrafts((prev) => ({
      ...prev,
      [questionId]: {
        ...(prev[questionId] || {}),
        text,
        source: source === 'VOICE' || prev[questionId]?.source === 'VOICE' ? 'VOICE' : 'TEXT',
        revision: nextSeq(),
      },
    }));
    window.clearTimeout(saveTimers.current[questionId]);
    saveTimers.current[questionId] = window.setTimeout(() => persistDraft(questionId), AUTOSAVE_DELAY_MS);
  };

  const updateDraftAnswers = (questionId, answers) => {
    setDrafts((prev) => ({
      ...prev,
      [questionId]: { ...(prev[questionId] || {}), text: '', meta: { answers }, source: 'TEXT', revision: nextSeq() },
    }));
    window.clearTimeout(saveTimers.current[questionId]);
    saveTimers.current[questionId] = window.setTimeout(() => persistDraft(questionId), AUTOSAVE_DELAY_MS);
  };

  // Code drafts: { language, code: { LANG: source }, custom_input, edited } in draft meta.
  const updateCodeDraft = useCallback(
    (questionId, meta) => {
      setDrafts((prev) => ({
        ...prev,
        [questionId]: { ...(prev[questionId] || {}), text: '', meta, source: 'TEXT', revision: nextSeq() },
      }));
      window.clearTimeout(saveTimers.current[questionId]);
      saveTimers.current[questionId] = window.setTimeout(() => persistDraft(questionId), CODE_AUTOSAVE_DELAY_MS);
    },
    [nextSeq, persistDraft]
  );

  useEffect(
    () => () => {
      Object.values(saveTimers.current).forEach((timer) => window.clearTimeout(timer));
    },
    []
  );

  // ---------------------------------------------------------------------------
  // Navigation: moves between questions only — never submits, evaluates or generates.
  // ---------------------------------------------------------------------------

  const goTo = useCallback(
    (target) => {
      if (!interview || target < 1 || (target > total && !questionsByPosition[target])) return;
      if (selected?.id) persistDraft(selected.id);
      speech.stop();
      setSubmitError('');
      setPosition(target);
      if (!inProgress) return;
      const seq = nextSeq();
      latestNavSeq.current = seq;
      navigateInterview(interviewId, target, seq)
        .then((data) => {
          if (latestNavSeq.current === seq) applyInterview(data);
        })
        .catch(() => {});
    },
    [applyInterview, inProgress, interview, interviewId, nextSeq, persistDraft, questionsByPosition, selected, speech, total]
  );

  // Record the restored position as visited once the room opens.
  const initialNavDone = useRef(false);
  useEffect(() => {
    if (!inProgress || !position || initialNavDone.current) return;
    initialNavDone.current = true;
    const seq = nextSeq();
    latestNavSeq.current = seq;
    navigateInterview(interviewId, position, seq)
      .then((data) => {
        if (latestNavSeq.current === seq) applyInterview(data);
      })
      .catch(() => {});
  }, [applyInterview, inProgress, interviewId, nextSeq, position]);

  // ---------------------------------------------------------------------------
  // Submission (separate from navigation)
  // ---------------------------------------------------------------------------

  const submitQuestion = useCallback(
    async (question, { silent = false } = {}) => {
      const draft = draftsRef.current[question.id];
      const text = draft?.text || '';
      const structured = question.kind === 'calculation';
      if (structured ? !draftHasContent(draft) : !text.trim() || text.length > DEFAULT_MAX_ANSWER_LENGTH) return;
      window.clearTimeout(saveTimers.current[question.id]);
      setSubmittingId(question.id);
      if (!silent) setSubmitError('');
      try {
        const result = await submitInterviewAnswer(
          interviewId,
          structured
            ? { questionId: question.id, structuredAnswer: draft?.meta?.answers || {}, answerSource: 'TEXT' }
            : { questionId: question.id, answerText: text, answerSource: draft?.source || 'TEXT' }
        );
        applyInterview(result.interview);
        speech.stop();
      } catch (error) {
        // The answer may have been saved even if the response was lost; recover from the server.
        try {
          const fresh = await refresh();
          if (fresh.questions.find((q) => q.id === question.id)?.answer) return;
        } catch {
          // fall through
        }
        if (!silent) setSubmitError(extractErrorMessage(error));
      } finally {
        setSubmittingId(null);
      }
    },
    [applyInterview, interviewId, refresh, speech]
  );

  const finishInterview = useCallback(async () => {
    setEnding(true);
    setEndError('');
    try {
      await Promise.allSettled(Object.keys(saveTimers.current).map((id) => persistDraft(id)));
      const data = await completeInterview(interviewId);
      applyInterview(data);
      setFinishOpen(false);
      if (data.answered_count > 0) router.push(`/dashboard/interview/${interviewId}/results`);
    } catch (error) {
      setEndError(extractErrorMessage(error));
    } finally {
      setEnding(false);
    }
  }, [applyInterview, interviewId, persistDraft, router]);

  // Server-enforced deadline: when time runs out, submit every non-empty draft
  // (accepted within the server's grace window), then end the interview.
  useEffect(() => {
    if (inProgress && remainingSeconds === 0 && !timeUp) setTimeUp(true);
  }, [inProgress, remainingSeconds, timeUp]);

  useEffect(() => {
    if (!timeUp || timeUpHandled.current || submittingId) return;
    timeUpHandled.current = true;
    (async () => {
      const pending = (interview?.questions || []).filter(
        (q) => !q.answer && !isCodeQuestion(q) && q.assessment_available !== false && draftHasContent(draftsRef.current[q.id])
      );
      await Promise.allSettled(pending.map((q) => submitQuestion(q, { silent: true })));
      await finishInterview();
    })();
  }, [finishInterview, interview, submitQuestion, submittingId, timeUp]);

  const handleRetryEvaluation = async (answerId) => {
    setRetryingAnswerId(answerId);
    try {
      await retryInterviewEvaluation(interviewId, answerId);
    } catch {
      // the refreshed state shows whether a retry is still possible
    }
    try {
      await refresh();
    } finally {
      setRetryingAnswerId(null);
    }
  };

  const statusOf = useCallback(
    (q) => {
      if (!q) return 'PREPARING';
      if (q.status === 'NOT_STARTED' || q.status === 'SKIPPED') {
        if (draftHasContent(drafts[q.id])) return 'IN_PROGRESS';
      }
      if (q.status === 'IN_PROGRESS' && drafts[q.id] && !draftHasContent(drafts[q.id])) return 'NOT_STARTED';
      return q.status || 'NOT_STARTED';
    },
    [drafts]
  );

  const finishSummary = useMemo(() => {
    const questions = interview?.questions || [];
    const answerable = questions.filter((q) => q.assessment_available !== false);
    const answered = answerable.filter((q) => q.answer);
    const open = answerable.filter((q) => !q.answer);
    return {
      answered: answered.length,
      unanswered: open.length + Math.max(0, total - questions.filter((q) => !isFollowUpQuestion(q)).length),
      drafts: open.filter((q) => statusOf(q) === 'IN_PROGRESS'),
      unansweredQuestions: open.filter((q) => statusOf(q) !== 'IN_PROGRESS'),
    };
  }, [interview, statusOf, total]);

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center" role="status">
        <Loader2 className="mr-2 h-5 w-5 animate-spin text-[var(--brand-navy)]" aria-hidden="true" />
        <span className="text-sm text-[var(--text-muted)]">Restoring your interview...</span>
      </div>
    );
  }

  if (notFound || loadError) {
    return (
      <div className="surface-card mx-auto max-w-xl text-center" role="alert">
        <AlertCircle className="mx-auto h-8 w-8 text-[var(--danger)]" aria-hidden="true" />
        <h1 className="mt-3 text-lg font-semibold">{notFound ? 'Interview not found' : 'Unable to load this interview'}</h1>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          {notFound ? 'It may have been removed, or it belongs to another account.' : loadError}
        </p>
        <div className="mt-4 flex justify-center gap-2">
          {!notFound && (
            <button type="button" className="btn-primary" onClick={() => window.location.reload()}>
              Try again
            </button>
          )}
          <Link href="/dashboard/interview" className="btn-outline">
            Back to AI Interviewer
          </Link>
        </div>
      </div>
    );
  }

  if (!interview) return null;
  if (!inProgress) return <EndedState interview={interview} />;

  const isVoice = interview.interaction_mode === 'VOICE';
  const progressPct = Math.round((interview.answered_count / Math.max(1, total)) * 100);
  const timerTone = remainingSeconds <= 60 ? 'text-[var(--danger)]' : remainingSeconds <= 120 ? 'text-[var(--warning)]' : 'text-[var(--text-primary)]';
  const draft = selected ? drafts[selected.id] : null;
  const draftText = draft?.text || '';
  const overLimit = draftText.length > DEFAULT_MAX_ANSWER_LENGTH;
  const isLast = sequenceIndex === sequence.length - 1;
  const plannedSlot = interview.blueprint?.question_slots?.[(position || 1) - 1];

  const isCode = isCodeQuestion(selected) && selected?.assessment_available !== false;
  const isCalculation = selected?.kind === 'calculation' && selected?.practical?.available;
  const isScenario = selected?.kind === 'scenario' && selected?.practical?.available;
  const canSubmit = isCalculation ? draftHasContent(draft) : Boolean(draftText.trim()) && !overLimit;

  let saveState = null;
  if (draft && draftHasContent(draft)) {
    if (draft.saving) saveState = 'Saving draft...';
    else if (draft.error) saveState = 'Draft not saved — will retry';
    else if (draft.savedRevision === draft.revision) saveState = 'Draft saved';
    else saveState = 'Unsaved changes';
  }

  return (
    <div className="space-y-5">
      <section className="surface-card flex flex-col gap-4 md:flex-row md:items-center md:justify-between" aria-label="Interview status">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--brand-amber)]">AI Interviewer · Live workspace</p>
          <h1 className="mt-1 truncate text-xl font-semibold">{interview.target_role}</h1>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Badge>{typeLabel(interview.interview_type)}</Badge>
            <Badge>{difficultyLabel(interview.difficulty)}</Badge>
            <Badge>{modeLabel(interview.interaction_mode)} mode</Badge>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="flex items-center justify-end gap-1 text-xs font-medium text-[var(--text-muted)]">
              <Clock className="h-3.5 w-3.5" aria-hidden="true" />
              Time remaining
            </p>
            <p className={`font-mono text-2xl font-bold tabular-nums ${timerTone}`} role="timer" aria-label={`Time remaining ${formatClock(remainingSeconds)}`}>
              {formatClock(remainingSeconds)}
            </p>
          </div>
          <button type="button" onClick={() => setFinishOpen(true)} disabled={timeUp} className="btn-outline">
            <Flag className="h-4 w-4" aria-hidden="true" />
            End interview
          </button>
        </div>
      </section>

      <section className="surface-card space-y-3 p-4 sm:p-5" aria-label="Question navigator">
        <div className="flex justify-between text-xs font-medium text-[var(--text-secondary)]">
          <span>
            {position > FOLLOW_UP_ORDER_OFFSET ? `Follow-up to question ${position - FOLLOW_UP_ORDER_OFFSET}` : `Question ${position} of ${total}`}
          </span>
          <span>
            {interview.answered_count} of {total} answered
          </span>
        </div>
        <div
          className="h-2 overflow-hidden rounded-full bg-[var(--surface-subtle)]"
          role="progressbar"
          aria-label="Interview progress"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={interview.answered_count}
        >
          <div className="h-full rounded-full bg-[var(--brand-navy)] transition-all" style={{ width: `${progressPct}%` }} />
        </div>
        <ol className="flex flex-wrap gap-2" aria-label="Questions">
          {sequence.map((n) => {
            const status = statusOf(questionsByPosition[n]);
            const meta = QUESTION_STATUS[status] || QUESTION_STATUS.NOT_STARTED;
            const current = n === position;
            const followUp = n > FOLLOW_UP_ORDER_OFFSET;
            const label = followUp ? `${n - FOLLOW_UP_ORDER_OFFSET}a` : String(n);
            const name = followUp ? `Follow-up to question ${n - FOLLOW_UP_ORDER_OFFSET}` : `Question ${n}`;
            return (
              <li key={n}>
                <button
                  type="button"
                  onClick={() => goTo(n)}
                  aria-current={current ? 'step' : undefined}
                  aria-label={`${name}, ${meta.label}`}
                  title={`${name}: ${meta.label}`}
                  className={`flex h-10 min-w-10 items-center justify-center rounded-lg border px-2 text-sm font-semibold transition-colors ${meta.className} ${
                    current ? 'ring-2 ring-brand-500 ring-offset-2' : 'hover:border-brand-400'
                  } ${followUp ? 'border-dashed' : ''}`}
                >
                  {label}
                </button>
              </li>
            );
          })}
        </ol>
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-[var(--text-muted)]" aria-label="Status legend">
          {['NOT_STARTED', 'IN_PROGRESS', 'SKIPPED', 'SUBMITTED', 'ANSWERED'].map((key) => (
            <li key={key} className="flex items-center gap-1">
              <span className={`inline-block h-2.5 w-2.5 rounded-sm border ${QUESTION_STATUS[key].className}`} aria-hidden="true" />
              {QUESTION_STATUS[key].label}
            </li>
          ))}
        </ul>
      </section>

      {timeUp && (
        <div className="flex items-center gap-2 rounded-xl border border-[rgba(198,161,91,0.35)] bg-[rgba(198,161,91,0.1)] p-3 text-sm font-medium text-[var(--text-secondary)]" role="alert">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Time&apos;s up. Submitting your saved drafts and preparing your report...
        </div>
      )}

      <section className="surface-card space-y-5" aria-labelledby="question-heading">
        {!selected ? (
          <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]" role="status">
            {interview.preparing ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin text-[var(--brand-navy)]" aria-hidden="true" />
                <span id="question-heading">
                  Preparing question {position}
                  {plannedSlot ? ` (${plannedSlot.competency})` : ''}...
                </span>
              </>
            ) : (
              <>
                <span id="question-heading">Question {position} couldn&apos;t be prepared yet.</span>
                <button type="button" onClick={() => goTo(position)} className="btn-outline px-3 py-1 text-xs">
                  <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                  Try again
                </button>
              </>
            )}
          </div>
        ) : (
          <>
            <div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p id="question-heading" className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {isFollowUpQuestion(selected) ? `Follow-up to question ${selected.question_order - FOLLOW_UP_ORDER_OFFSET}` : `Question ${selected.question_order}`} ·{' '}
                  {selected.assessment_available === false ? slotKindLabel(selected.kind) : categoryLabel(selected.category)} · {selected.competency}
                </p>
                <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${QUESTION_STATUS[statusOf(selected)].className}`}>
                  {QUESTION_STATUS[statusOf(selected)].label}
                </span>
              </div>
              {/* Code questions: the problem panel carries the title and statement, so the editor gets the space. */}
              {selected.interviewer_context && selected.assessment_available !== false && !isCode && (
                <p className="mt-2 text-sm text-slate-500">{selected.interviewer_context}</p>
              )}
              {selected.assessment_available !== false && !isCode && (
                <p className="mt-2 text-lg font-medium leading-8 text-slate-900">{selected.question_text}</p>
              )}
              {isVoice && speech.supported && !selected.answer && selected.assessment_available !== false && !isCalculation && !isCode && (
                <button
                  type="button"
                  onClick={() => (speech.speaking ? speech.stop() : speech.speak(selected.question_text))}
                  className="btn-ghost mt-2 px-2 py-1 text-xs"
                >
                  {speech.speaking ? <VolumeX className="h-4 w-4" aria-hidden="true" /> : <Volume2 className="h-4 w-4" aria-hidden="true" />}
                  {speech.speaking ? 'Stop reading' : 'Read question aloud'}
                </button>
              )}
            </div>

            {selected.assessment_available === false ? (
              <PracticalUnavailable question={selected} />
            ) : isCode ? (
              <CodingWorkspace
                key={selected.id}
                interviewId={interviewId}
                question={selected}
                targetRole={interview.target_role}
                draftMeta={draft?.meta || selected.draft_meta || null}
                onDraftChange={(meta) => updateCodeDraft(selected.id, meta)}
                saveState={saveState}
                readOnly={timeUp}
                onSubmissionComplete={() => refresh().catch(() => {})}
                cache={(workspaceCaches.current[selected.id] ||= {})}
              />
            ) : selected.answer ? (
              <>
                <div className="surface-card-subtle">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Your submitted answer</p>
                  <p className="mt-1.5 whitespace-pre-wrap text-sm leading-6 text-slate-700">{selected.answer.answer_text}</p>
                </div>
                <AnswerFeedback
                  answer={selected.answer}
                  onRetry={() => handleRetryEvaluation(selected.answer.id)}
                  retrying={retryingAnswerId === selected.answer.id}
                />
                <p className="text-xs text-slate-500">{SCORE_DISCLAIMER} Your full report is available when the interview ends.</p>
              </>
            ) : isCalculation ? (
              <>
                <CalculationForm
                  practical={selected.practical}
                  values={draft?.meta?.answers}
                  onChange={(answers) => updateDraftAnswers(selected.id, answers)}
                  disabled={submittingId === selected.id || timeUp}
                />
                <p className="text-xs text-slate-500" aria-live="polite">
                  {saveState || 'Drafts are saved automatically. Submitted answers can’t be edited.'}
                </p>
                {submitError && (
                  <p className="text-sm text-red-700" role="alert">
                    {submitError}
                  </p>
                )}
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => submitQuestion(selected)}
                    disabled={!canSubmit || Boolean(submittingId) || timeUp}
                    className="btn-primary"
                  >
                    {submittingId === selected.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <Send className="h-4 w-4" aria-hidden="true" />
                    )}
                    {submittingId === selected.id ? 'Checking your answers...' : 'Submit answers'}
                  </button>
                </div>
              </>
            ) : (
              <>
                {isScenario && <ScenarioBrief practical={selected.practical} />}
                {isVoice && (
                  <VoiceAnswerPanel
                    key={selected.id}
                    interviewId={interviewId}
                    disabled={Boolean(submittingId) || timeUp}
                    onTranscript={(text) => updateDraft(selected.id, text, 'VOICE')}
                  />
                )}
                <div>
                  <label htmlFor="answer" className="text-sm font-medium text-slate-700">
                    {isVoice ? 'Transcript — review and edit before submitting' : 'Your answer'}
                  </label>
                  <textarea
                    id="answer"
                    rows={isVoice ? 6 : 9}
                    value={draftText}
                    onChange={(event) => updateDraft(selected.id, event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
                        event.preventDefault();
                        submitQuestion(selected);
                      }
                    }}
                    disabled={submittingId === selected.id || timeUp}
                    placeholder={isVoice ? 'Your transcript will appear here. You can also type.' : 'Type your answer. Your draft is saved automatically.'}
                    className="input-base mt-1.5 resize-y leading-6"
                    aria-describedby="answer-count answer-save-state"
                    aria-invalid={overLimit}
                  />
                  <div className="mt-1 flex flex-wrap justify-between gap-2 text-xs">
                    <span id="answer-save-state" className="text-slate-500" aria-live="polite">
                      {saveState || 'Drafts are saved automatically. Submitted answers can’t be edited.'}
                    </span>
                    <span id="answer-count" className={overLimit ? 'font-semibold text-red-700' : 'text-slate-400'}>
                      {draftText.length}/{DEFAULT_MAX_ANSWER_LENGTH}
                    </span>
                  </div>
                </div>
                {submitError && (
                  <p className="text-sm text-red-700" role="alert">
                    {submitError}
                  </p>
                )}
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => submitQuestion(selected)}
                    disabled={!canSubmit || Boolean(submittingId) || timeUp}
                    className="btn-primary"
                  >
                    {submittingId === selected.id ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                        Evaluating your answer...
                      </>
                    ) : (
                      <>
                        <Send className="h-4 w-4" aria-hidden="true" />
                        Submit answer
                      </>
                    )}
                  </button>
                </div>
              </>
            )}
          </>
        )}

        <nav className="flex items-center justify-between gap-2 border-t border-slate-100 pt-4" aria-label="Question navigation">
          <button type="button" onClick={() => goTo(sequence[sequenceIndex - 1])} disabled={sequenceIndex <= 0} className="btn-outline">
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            Previous question
          </button>
          <span className="hidden text-xs text-slate-500 sm:inline">
            {sequenceIndex + 1} / {sequence.length}
          </span>
          {isLast ? (
            <div className="flex gap-2">
              <button type="button" disabled className="btn-outline hidden sm:inline-flex">
                Next question
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </button>
              <button type="button" onClick={() => setFinishOpen(true)} disabled={timeUp} className="btn-primary">
                Finish interview
              </button>
            </div>
          ) : (
            <button type="button" onClick={() => goTo(sequence[sequenceIndex + 1])} disabled={sequenceIndex >= sequence.length - 1} className="btn-outline">
              Next question
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </nav>
      </section>

      {finishOpen && (
        <FinishDialog
          summary={finishSummary}
          ending={ending}
          error={endError}
          onCancel={() => {
            setFinishOpen(false);
            setEndError('');
          }}
          onConfirm={finishInterview}
          onGoTo={(n) => {
            setFinishOpen(false);
            goTo(n);
          }}
        />
      )}
    </div>
  );
}
