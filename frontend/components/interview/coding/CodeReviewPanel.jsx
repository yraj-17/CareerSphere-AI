'use client';

import React from 'react';
import { Bot, Loader2, RotateCcw } from 'lucide-react';

/**
 * "AI Code Review" — code quality only. Execution correctness always comes from Judge0 and is
 * shown separately; nothing here can change a verdict.
 */
export const REVIEW_LABEL = 'AI Code Review';

function List({ title, items }) {
  if (!items?.length) return null;
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{title}</p>
      <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-slate-700">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

/** One-line status used under the Judge0 verdict. */
export function ReviewStatusLine({ submission, onOpen }) {
  const review = submission?.ai_review;
  if (!review) return null;
  let text;
  if (review.status === 'COMPLETED') {
    text = (
      <>
        Code quality {Math.round(review.quality_score)}/100
        {submission.coding_score !== null && submission.coding_score !== undefined && (
          <> · combined coding score {Math.round(submission.coding_score)}/100 (70% correctness + 30% quality)</>
        )}
      </>
    );
  } else if (review.status === 'FAILED') {
    text = 'unavailable — correctness from Judge0 is shown on its own';
  } else {
    text = (
      <span className="inline-flex items-center gap-1">
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
        reviewing your code… (results above are final)
      </span>
    );
  }
  return (
    <p className="flex flex-wrap items-center gap-1 text-xs text-slate-600" aria-live="polite">
      <Bot className="h-3.5 w-3.5" aria-hidden="true" />
      <span className="font-semibold">{REVIEW_LABEL}:</span> {text}
      {onOpen && review.status === 'COMPLETED' && (
        <button type="button" onClick={onOpen} className="ml-1 font-semibold text-[var(--brand-navy)] underline">
          View review
        </button>
      )}
    </p>
  );
}

export default function CodeReviewPanel({ submission, onRetry, retrying }) {
  const review = submission?.ai_review;
  if (!submission || submission.submission_type !== 'SUBMIT') {
    return <p className="text-sm text-slate-500">Submit your solution to get an {REVIEW_LABEL}. Runs are not reviewed.</p>;
  }
  if (!review) {
    return <p className="text-sm text-slate-500">No {REVIEW_LABEL} is available for this submission.</p>;
  }
  return (
    <section className="space-y-3" aria-label={REVIEW_LABEL}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-2.5 py-0.5 text-xs font-semibold text-slate-700">
          <Bot className="h-3.5 w-3.5" aria-hidden="true" />
          {REVIEW_LABEL}
        </span>
        {review.status === 'COMPLETED' && (
          <span className="text-sm font-semibold text-slate-800">Code quality {Math.round(review.quality_score)}/100</span>
        )}
      </div>
      <p className="text-xs text-slate-500">{review.note}</p>

      {(review.status === 'PENDING' || review.status === 'RUNNING') && (
        <p className="flex items-center gap-2 text-sm text-slate-600" role="status">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          The AI is reviewing your code. Your Judge0 results are already final.
        </p>
      )}

      {review.status === 'FAILED' && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-700" role="status">
          <span>The code review is unavailable right now. Your score uses Judge0 correctness only.</span>
          {review.can_retry && onRetry && (
            <button type="button" onClick={onRetry} disabled={retrying} className="btn-outline px-2 py-1 text-xs">
              {retrying ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />}
              Retry review
            </button>
          )}
        </div>
      )}

      {review.status === 'COMPLETED' && (
        <>
          <p className="text-sm leading-6 text-slate-700">{review.summary}</p>
          <ul className="grid gap-1.5 sm:grid-cols-2" aria-label="Review criteria">
            {review.criteria.map((c) => (
              <li key={c.id} className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5">
                <div className="flex justify-between text-xs">
                  <span className="font-medium text-slate-700">{c.title}</span>
                  <span className="text-slate-500">
                    {c.score}/100 · weight {c.weight}%
                  </span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-label={c.title}
                  aria-valuenow={c.score} aria-valuemin={0} aria-valuemax={100}>
                  <div className="h-full rounded-full bg-[var(--brand-navy)]" style={{ width: `${c.score}%` }} />
                </div>
              </li>
            ))}
          </ul>
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Time complexity (AI estimate)</dt>
              <dd className="font-mono text-slate-800">{review.time_complexity}</dd>
            </div>
            <div>
              <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Space complexity (AI estimate)</dt>
              <dd className="font-mono text-slate-800">{review.space_complexity}</dd>
            </div>
          </dl>
          <div className="grid gap-3 sm:grid-cols-2">
            <List title="Strengths" items={review.strengths} />
            <List title="Weaknesses" items={review.weaknesses} />
            <List title="Improvements" items={review.improvements} />
            <List title="Alternative approaches" items={review.alternative_approaches} />
            <List title="Missing edge cases" items={review.missing_edge_cases} />
            <List title="Recommendations" items={review.recommendations} />
          </div>
        </>
      )}
    </section>
  );
}
