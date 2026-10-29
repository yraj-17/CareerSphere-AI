'use client';

import React from 'react';
import { AlertTriangle, CheckCircle2, Loader2, RotateCcw, TrendingUp } from 'lucide-react';
import { DIMENSION_LABELS, scoreBand } from '@/components/interview/interviewConstants';

export function ScoreBar({ label, value }) {
  return (
    <div>
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-slate-600">{label}</span>
        <span className="font-semibold text-slate-900">{value}</span>
      </div>
      <div
        className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value}
      >
        <div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      </div>
    </div>
  );
}

function FeedbackList({ title, items, icon: Icon, tone }) {
  if (!items?.length) return null;
  return (
    <div>
      <h4 className={`flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide ${tone}`}>
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        {title}
      </h4>
      <ul className="mt-1.5 space-y-1 text-sm leading-6 text-slate-700">
        {items.map((item) => (
          <li key={item} className="flex gap-2">
            <span className="mt-2.5 h-1 w-1 shrink-0 rounded-full bg-slate-400" aria-hidden="true" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Intermediate (per-answer) feedback. This is never the final report.
 */
export default function AnswerFeedback({ answer, onRetry, retrying = false, compact = false }) {
  if (!answer) return null;

  if (answer.evaluation_status === 'PENDING') {
    return (
      <div className="surface-card-subtle flex items-center gap-2 text-sm text-slate-600" role="status">
        <Loader2 className="h-4 w-4 animate-spin text-brand-500" aria-hidden="true" />
        Evaluating your answer...
      </div>
    );
  }

  if (answer.evaluation_status === 'FAILED') {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900" role="alert">
        <p className="flex items-center gap-2 font-semibold">
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          Your answer was saved, but feedback isn&apos;t available yet.
        </p>
        <p className="mt-1 text-amber-800">
          The AI evaluator didn&apos;t respond. No score has been assigned.
        </p>
        {answer.can_retry_evaluation && onRetry && (
          <button type="button" onClick={onRetry} disabled={retrying} className="btn-outline mt-3">
            {retrying ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <RotateCcw className="h-4 w-4" aria-hidden="true" />}
            {retrying ? 'Retrying...' : 'Retry evaluation'}
          </button>
        )}
      </div>
    );
  }

  const evaluation = answer.evaluation;
  if (!evaluation) return null;
  const band = scoreBand(evaluation.score);
  const dimensions = Object.entries(evaluation.dimensions || {}).filter(([, value]) => value !== null && value !== undefined);

  return (
    <div className="space-y-4" aria-label="Answer feedback">
      <div className="flex flex-wrap items-end gap-x-4 gap-y-1">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Answer score</p>
          <p className="text-3xl font-bold text-slate-900">
            {evaluation.score}
            <span className="text-base font-medium text-slate-400">/100</span>
          </p>
        </div>
        <p className={`pb-1 text-sm font-semibold ${band.className}`}>{band.label}</p>
      </div>

      {!compact && dimensions.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {dimensions.map(([key, value]) => (
            <ScoreBar key={key} label={DIMENSION_LABELS[key] || key} value={value} />
          ))}
        </div>
      )}

      <p className="text-sm leading-6 text-slate-700">{evaluation.feedback}</p>

      <div className="grid gap-4 sm:grid-cols-2">
        <FeedbackList title="Strengths" items={evaluation.strengths} icon={CheckCircle2} tone="text-emerald-700" />
        <FeedbackList title="To improve" items={evaluation.improvements} icon={TrendingUp} tone="text-amber-800" />
      </div>

      {!compact && evaluation.key_points?.length > 0 && (
        <details className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
          <summary className="cursor-pointer font-medium text-slate-700">What a strong answer often covers</summary>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-600">
            {evaluation.key_points.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-slate-500">Different wording or approaches can be equally valid.</p>
        </details>
      )}
    </div>
  );
}
