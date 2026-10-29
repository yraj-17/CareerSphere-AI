'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Flag,
  History,
  Loader2,
  Send,
  Volume2,
  VolumeX,
} from 'lucide-react';
import {
  completeInterview,
  extractErrorMessage,
  getInterview,
  requestNextInterviewQuestion,
  retryInterviewEvaluation,
  submitInterviewAnswer,
} from '@/services/api';
import AnswerFeedback from '@/components/interview/AnswerFeedback';
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
  typeLabel,
} from '@/components/interview/interviewConstants';

const DRAFT_PREFIX = 'careersphere:interview-draft:';

function readDraft(questionId) {
  try {
    return window.localStorage.getItem(DRAFT_PREFIX + questionId) || '';
  } catch {
    return '';
  }
}

function writeDraft(questionId, value) {
  try {
    if (value) window.localStorage.setItem(DRAFT_PREFIX + questionId, value);
    else window.localStorage.removeItem(DRAFT_PREFIX + questionId);
  } catch {
    // Draft persistence is a convenience only.
  }
}

function Badge({ children }) {
  return (
    <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-xs font-medium text-slate-600">
      {children}
    </span>
  );
}

function ConfirmEndDialog({ answeredCount, hasDraft, ending, error, onCancel, onConfirm }) {
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
      <div role="dialog" aria-modal="true" aria-labelledby="end-title" aria-describedby="end-description" className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <h2 id="end-title" className="text-lg font-semibold">End this interview?</h2>
        <div id="end-description" className="mt-2 space-y-2 text-sm text-slate-600">
          <p>
            {answeredCount > 0
              ? `Your ${answeredCount} submitted answer${answeredCount === 1 ? '' : 's'} will be included in the final report. Unanswered questions are not scored.`
              : 'You have not submitted any answers, so no report will be generated.'}
          </p>
          {hasDraft && <p className="font-medium text-amber-800">Your unsubmitted draft answer will not be saved.</p>}
        </div>
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
            End interview
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
        {interview.answered_count} of {interview.question_count} question{interview.question_count === 1 ? '' : 's'} answered
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

  const [draft, setDraft] = useState('');
  const [draftSource, setDraftSource] = useState('TEXT');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [reviewQuestionId, setReviewQuestionId] = useState(null);
  const [nextState, setNextState] = useState('idle');
  const [nextError, setNextError] = useState('');
  const [retryingAnswerId, setRetryingAnswerId] = useState(null);
  const [confirmEnd, setConfirmEnd] = useState(false);
  const [ending, setEnding] = useState(false);
  const [endError, setEndError] = useState('');
  const [timeUp, setTimeUp] = useState(false);
  const timeUpHandled = useRef(false);
  const draftQuestionRef = useRef(null);

  const applyInterview = useCallback((data) => {
    const clientNow = Date.now();
    setInterview(data);
    setClockOffset(new Date(data.server_time).getTime() - clientNow);
    setNowMs(clientNow);
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
        if (!cancelled) applyInterview(data);
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

  const remainingSeconds = inProgress
    ? Math.max(0, Math.floor((new Date(interview.deadline_at).getTime() - (nowMs + clockOffset)) / 1000))
    : 0;

  const currentQuestion = interview?.current_question || null;
  const answeredQuestions = useMemo(() => (interview?.questions || []).filter((q) => q.answer), [interview]);
  const lastAnswered = answeredQuestions[answeredQuestions.length - 1] || null;
  const reviewQuestion = useMemo(() => {
    if (!interview) return null;
    if (reviewQuestionId) return interview.questions.find((q) => q.id === reviewQuestionId) || null;
    if (!currentQuestion) return lastAnswered;
    return null;
  }, [currentQuestion, interview, lastAnswered, reviewQuestionId]);

  // Load the saved draft whenever a new question becomes active.
  useEffect(() => {
    if (!currentQuestion || draftQuestionRef.current === currentQuestion.id) return;
    draftQuestionRef.current = currentQuestion.id;
    setDraft(readDraft(currentQuestion.id));
    setDraftSource('TEXT');
    setSubmitError('');
    speech.stop();
  }, [currentQuestion, speech]);

  const updateDraft = (value, source = 'TEXT') => {
    setDraft(value);
    if (source === 'VOICE') setDraftSource('VOICE');
    if (currentQuestion) writeDraft(currentQuestion.id, value);
  };

  const prefetchNext = useCallback(async () => {
    setNextState('loading');
    setNextError('');
    try {
      const data = await requestNextInterviewQuestion(interviewId);
      applyInterview(data);
      setNextState('idle');
      return data;
    } catch (error) {
      setNextState('error');
      setNextError(extractErrorMessage(error));
      if (error?.response?.status === 409) {
        try {
          await refresh();
        } catch {
          // keep the existing state; the error message is shown
        }
      }
      return null;
    }
  }, [applyInterview, interviewId, refresh]);

  const maxAnswerLength = DEFAULT_MAX_ANSWER_LENGTH;
  const trimmedDraft = draft.trim();
  const overLimit = draft.length > maxAnswerLength;

  const submitAnswer = useCallback(
    async ({ silent = false } = {}) => {
      if (!currentQuestion || !trimmedDraft || overLimit || submitting) return;
      const questionId = currentQuestion.id;
      setSubmitting(true);
      setSubmitError('');
      try {
        const result = await submitInterviewAnswer(interviewId, {
          questionId,
          answerText: draft,
          answerSource: draftSource,
        });
        applyInterview(result.interview);
        writeDraft(questionId, '');
        setDraft('');
        setReviewQuestionId(questionId);
        speech.stop();
        if (result.interview.can_request_next_question && !silent) prefetchNext();
      } catch (error) {
        // The answer may have been saved even if the response was lost; recover from the server.
        try {
          const fresh = await refresh();
          const saved = fresh.questions.find((q) => q.id === questionId)?.answer;
          if (saved) {
            writeDraft(questionId, '');
            setDraft('');
            setReviewQuestionId(questionId);
            return;
          }
        } catch {
          // fall through to the original error
        }
        if (!silent) setSubmitError(extractErrorMessage(error));
      } finally {
        setSubmitting(false);
      }
    },
    [applyInterview, currentQuestion, draft, draftSource, interviewId, overLimit, prefetchNext, refresh, speech, submitting, trimmedDraft]
  );

  const goToResults = useCallback(
    (data) => {
      if (data.answered_count > 0) router.push(`/dashboard/interview/${interviewId}/results`);
    },
    [interviewId, router]
  );

  const endInterview = useCallback(async () => {
    setEnding(true);
    setEndError('');
    try {
      const data = await completeInterview(interviewId);
      applyInterview(data);
      setConfirmEnd(false);
      goToResults(data);
    } catch (error) {
      setEndError(extractErrorMessage(error));
    } finally {
      setEnding(false);
    }
  }, [applyInterview, goToResults, interviewId]);

  // Server-enforced deadline: when local time runs out, save any draft (within the
  // server's grace window), then end the interview and move to the report.
  useEffect(() => {
    if (inProgress && remainingSeconds === 0 && !timeUp) setTimeUp(true);
  }, [inProgress, remainingSeconds, timeUp]);

  useEffect(() => {
    if (!timeUp || timeUpHandled.current || submitting) return;
    timeUpHandled.current = true;
    (async () => {
      if (currentQuestion && trimmedDraft && !overLimit) await submitAnswer({ silent: true });
      await endInterview();
    })();
  }, [currentQuestion, endInterview, overLimit, submitAnswer, submitting, timeUp, trimmedDraft]);

  const handleNext = async () => {
    if (interview?.current_question) {
      setReviewQuestionId(null);
      return;
    }
    const data = await prefetchNext();
    if (data?.current_question) setReviewQuestionId(null);
  };

  const handleRetryEvaluation = async (answerId) => {
    setRetryingAnswerId(answerId);
    try {
      await retryInterviewEvaluation(interviewId, answerId);
    } catch {
      // the refreshed state below shows whether a retry is still possible
    }
    try {
      await refresh();
    } finally {
      setRetryingAnswerId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center" role="status">
        <Loader2 className="mr-2 h-5 w-5 animate-spin text-brand-500" aria-hidden="true" />
        <span className="text-sm text-slate-500">Restoring your interview...</span>
      </div>
    );
  }

  if (notFound || loadError) {
    return (
      <div className="surface-card mx-auto max-w-xl text-center" role="alert">
        <AlertCircle className="mx-auto h-8 w-8 text-red-600" aria-hidden="true" />
        <h1 className="mt-3 text-lg font-semibold">{notFound ? 'Interview not found' : 'Unable to load this interview'}</h1>
        <p className="mt-1 text-sm text-slate-500">
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
  const progressPct = Math.round((interview.answered_count / interview.max_questions) * 100);
  const timerTone = remainingSeconds <= 60 ? 'text-red-700' : remainingSeconds <= 120 ? 'text-amber-700' : 'text-slate-900';
  const displayedOrder = (reviewQuestion || currentQuestion)?.question_order ?? interview.question_count;

  return (
    <div className="space-y-5">
      <section className="surface-card flex flex-col gap-4 md:flex-row md:items-center md:justify-between" aria-label="Interview status">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">AI Interviewer</p>
          <h1 className="mt-1 truncate text-xl font-semibold">{interview.target_role}</h1>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Badge>{typeLabel(interview.interview_type)}</Badge>
            <Badge>{difficultyLabel(interview.difficulty)}</Badge>
            <Badge>{modeLabel(interview.interaction_mode)} mode</Badge>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="flex items-center justify-end gap-1 text-xs font-medium text-slate-500">
              <Clock className="h-3.5 w-3.5" aria-hidden="true" />
              Time remaining
            </p>
            <p
              className={`font-mono text-2xl font-bold tabular-nums ${timerTone}`}
              role="timer"
              aria-label={`Time remaining ${formatClock(remainingSeconds)}`}
            >
              {formatClock(remainingSeconds)}
            </p>
          </div>
          <button type="button" onClick={() => setConfirmEnd(true)} disabled={timeUp} className="btn-outline">
            <Flag className="h-4 w-4" aria-hidden="true" />
            End interview
          </button>
        </div>
      </section>

      <div>
        <div className="flex justify-between text-xs font-medium text-slate-600">
          <span>
            Question {displayedOrder} of {interview.max_questions}
          </span>
          <span>{interview.answered_count} answered</span>
        </div>
        <div
          className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-200"
          role="progressbar"
          aria-label="Interview progress"
          aria-valuemin={0}
          aria-valuemax={interview.max_questions}
          aria-valuenow={interview.answered_count}
        >
          <div className="h-full rounded-full bg-brand-500 transition-all" style={{ width: `${progressPct}%` }} />
        </div>
      </div>

      {timeUp && (
        <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm font-medium text-amber-900" role="alert">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Time&apos;s up. Saving your work and preparing your report...
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-5">
          {reviewQuestion ? (
            <section className="surface-card space-y-5" aria-labelledby="review-heading">
              <div>
                <p id="review-heading" className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Question {reviewQuestion.question_order} · Feedback
                </p>
                <p className="mt-2 text-base font-medium leading-7 text-slate-900">{reviewQuestion.question_text}</p>
              </div>
              <div className="surface-card-subtle">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Your answer</p>
                <p className="mt-1.5 whitespace-pre-wrap text-sm leading-6 text-slate-700">{reviewQuestion.answer?.answer_text}</p>
              </div>
              <AnswerFeedback
                answer={reviewQuestion.answer}
                onRetry={() => handleRetryEvaluation(reviewQuestion.answer.id)}
                retrying={retryingAnswerId === reviewQuestion.answer?.id}
              />
              <p className="text-xs text-slate-500">{SCORE_DISCLAIMER} Your full report is available when the interview ends.</p>

              {nextError && (
                <p className="text-sm text-red-700" role="alert">
                  {nextError}
                </p>
              )}
              <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 pt-4">
                {interview.current_question || interview.can_request_next_question ? (
                  <button type="button" onClick={handleNext} disabled={nextState === 'loading' || timeUp} className="btn-primary">
                    {nextState === 'loading' ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                        Preparing next question...
                      </>
                    ) : (
                      <>
                        {nextState === 'error' ? 'Try again' : 'Next question'}
                        <ArrowRight className="h-4 w-4" aria-hidden="true" />
                      </>
                    )}
                  </button>
                ) : (
                  <button type="button" onClick={endInterview} disabled={ending || timeUp} className="btn-primary">
                    {ending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <CheckCircle2 className="h-4 w-4" aria-hidden="true" />}
                    Finish and view report
                  </button>
                )}
              </div>
              {!interview.current_question && !interview.can_request_next_question && (
                <p className="text-right text-xs text-slate-500">
                  {interview.question_count >= interview.max_questions
                    ? 'You have reached the last question for this interview.'
                    : 'No more questions can be asked in the remaining time.'}
                </p>
              )}
              {endError && (
                <p className="text-right text-sm text-red-700" role="alert">
                  {endError}
                </p>
              )}
            </section>
          ) : currentQuestion ? (
            <section className="surface-card space-y-5" aria-labelledby="question-heading">
              <div>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p id="question-heading" className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Question {currentQuestion.question_order} · {categoryLabel(currentQuestion.category)} · {currentQuestion.competency}
                  </p>
                  {isVoice && speech.supported && (
                    <button
                      type="button"
                      onClick={() => (speech.speaking ? speech.stop() : speech.speak(currentQuestion.question_text))}
                      className="btn-ghost px-2 py-1 text-xs"
                    >
                      {speech.speaking ? <VolumeX className="h-4 w-4" aria-hidden="true" /> : <Volume2 className="h-4 w-4" aria-hidden="true" />}
                      {speech.speaking ? 'Stop reading' : 'Read question aloud'}
                    </button>
                  )}
                </div>
                {currentQuestion.interviewer_context && (
                  <p className="mt-2 text-sm text-slate-500">{currentQuestion.interviewer_context}</p>
                )}
                <p className="mt-2 text-lg font-medium leading-8 text-slate-900">{currentQuestion.question_text}</p>
              </div>

              {isVoice && (
                <VoiceAnswerPanel
                  key={currentQuestion.id}
                  interviewId={interviewId}
                  disabled={submitting || timeUp}
                  onTranscript={(text) => updateDraft(text, 'VOICE')}
                />
              )}

              <div>
                <label htmlFor="answer" className="text-sm font-medium text-slate-700">
                  {isVoice ? 'Transcript — review and edit before submitting' : 'Your answer'}
                </label>
                <textarea
                  id="answer"
                  rows={isVoice ? 6 : 9}
                  value={draft}
                  onChange={(event) => updateDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
                      event.preventDefault();
                      submitAnswer();
                    }
                  }}
                  disabled={submitting || timeUp}
                  placeholder={isVoice ? 'Your transcript will appear here. You can also type.' : 'Type your answer. Explain your reasoning as you would in a real interview.'}
                  className="input-base mt-1.5 resize-y leading-6"
                  aria-describedby="answer-count"
                  aria-invalid={overLimit}
                />
                <div className="mt-1 flex justify-between text-xs">
                  <span className="text-slate-400">Ctrl + Enter to submit. Submitted answers can&apos;t be edited.</span>
                  <span id="answer-count" className={overLimit ? 'font-semibold text-red-700' : 'text-slate-400'}>
                    {draft.length}/{maxAnswerLength}
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
                  onClick={() => submitAnswer()}
                  disabled={!trimmedDraft || overLimit || submitting || timeUp}
                  className="btn-primary"
                >
                  {submitting ? (
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
            </section>
          ) : (
            <section className="surface-card text-sm text-slate-600">Preparing your interview...</section>
          )}
        </div>

        <aside className="space-y-3" aria-labelledby="previous-heading">
          <h2 id="previous-heading" className="flex items-center gap-2 text-sm font-semibold text-slate-700">
            <History className="h-4 w-4" aria-hidden="true" />
            Previous questions
          </h2>
          {answeredQuestions.length === 0 ? (
            <p className="surface-card-subtle text-sm text-slate-500">Your submitted answers will appear here.</p>
          ) : (
            <ul className="space-y-2">
              {answeredQuestions.map((question) => (
                <li key={question.id}>
                  <details className="rounded-xl border border-slate-200 bg-white p-3 text-sm">
                    <summary className="flex cursor-pointer items-center justify-between gap-2 font-medium text-slate-800">
                      <span className="truncate">
                        Q{question.question_order}. {question.competency}
                      </span>
                      <span className="shrink-0 text-xs font-semibold text-slate-500">
                        {question.answer.score !== null && question.answer.score !== undefined
                          ? `${question.answer.score}/100`
                          : question.answer.evaluation_status === 'FAILED'
                            ? 'Not scored'
                            : '...'}
                      </span>
                    </summary>
                    <p className="mt-2 text-slate-700">{question.question_text}</p>
                    <p className="mt-2 whitespace-pre-wrap rounded-lg bg-slate-50 p-2 text-xs leading-5 text-slate-600">
                      {question.answer.answer_text}
                    </p>
                  </details>
                </li>
              ))}
            </ul>
          )}
        </aside>
      </div>

      {confirmEnd && (
        <ConfirmEndDialog
          answeredCount={interview.answered_count}
          hasDraft={Boolean(trimmedDraft)}
          ending={ending}
          error={endError}
          onCancel={() => {
            setConfirmEnd(false);
            setEndError('');
          }}
          onConfirm={endInterview}
        />
      )}
    </div>
  );
}
