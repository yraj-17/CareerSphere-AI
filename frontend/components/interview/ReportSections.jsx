'use client';

import React from 'react';
import { Bot, Code2 } from 'lucide-react';
import { levelLabel } from '@/components/interview/PracticalTask';
import CodeReviewPanel from '@/components/interview/coding/CodeReviewPanel';
import { TONE_CLASSES, formatMemory, formatTime, toneOf } from '@/components/interview/coding/codingUtils';
import { difficultyLabel, typeLabel } from '@/components/interview/interviewConstants';

const FOLLOW_UP_ORDER_OFFSET = 100;

export const questionLabel = (question) =>
  question.parent_question_id
    ? `Follow-up to question ${question.question_order - FOLLOW_UP_ORDER_OFFSET}`
    : `Question ${question.question_order}`;

function Stat({ label, value }) {
  return (
    <div className="surface-card-subtle">
      <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-sm font-semibold text-slate-900">{value}</dd>
    </div>
  );
}

export function ExecutiveSummary({ interview, report, aggregates, statusLabel }) {
  const practical = aggregates?.sections?.practical;
  const practicalDone = (practical?.items || []).filter((i) => i.status === 'assessed').length;
  const followUps = aggregates?.follow_ups;
  return (
    <section className="surface-card" aria-labelledby="executive-heading">
      <h2 id="executive-heading" className="text-base font-semibold">Executive summary</h2>
      <dl className="mt-3 grid gap-2 sm:grid-cols-3 lg:grid-cols-4">
        <Stat label="Target role" value={interview.target_role} />
        <Stat label="Interview type" value={typeLabel(interview.interview_type)} />
        <Stat label="Difficulty" value={difficultyLabel(interview.difficulty)} />
        <Stat label="Questions" value={`${interview.answered_count} of ${interview.max_questions} answered`} />
        <Stat label="Practical assessments" value={practical?.reserved ? `${practicalDone} of ${practical.reserved} completed` : 'None planned'} />
        {followUps?.asked > 0 && <Stat label="Follow-ups" value={`${followUps.answered} of ${followUps.asked} answered`} />}
        <Stat label="Overall score" value={report?.overall_score !== null && report?.overall_score !== undefined ? `${report.overall_score}/100` : 'Not available'} />
        <Stat label="Status" value={statusLabel} />
      </dl>
    </section>
  );
}

const DIMENSIONS = [
  ['technical_knowledge', 'Technical knowledge'],
  ['practical_assessment', 'Practical assessment'],
  ['coding_correctness', 'Coding correctness (Judge0)'],
  ['code_quality', 'Code quality (AI review)'],
  ['problem_solving', 'Problem solving'],
  ['communication', 'Communication'],
  ['behavioral', 'Behavioral'],
];

export function DimensionGrid({ dimensions }) {
  return (
    <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="Evaluation dimensions">
      {DIMENSIONS.map(([key, label]) => {
        const value = dimensions?.[key];
        const assessed = value !== null && value !== undefined;
        return (
          <div key={key} className="surface-card-subtle">
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
            <dd className="mt-1">
              {assessed ? (
                <span className="text-2xl font-bold text-slate-900">
                  {value}
                  <span className="text-sm font-medium text-slate-400">/100</span>
                </span>
              ) : (
                <span className="text-sm font-medium text-slate-400">Not assessed</span>
              )}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

export function CompetencyAnalysis({ competencies }) {
  const assessed = competencies.filter((c) => c.score !== null && c.score !== undefined);
  const notAssessed = competencies.filter((c) => c.score === null || c.score === undefined);
  return (
    <div>
      <h3 className="text-sm font-semibold text-slate-900">Role competencies</h3>
      <ul className="mt-3 grid gap-3 sm:grid-cols-2" aria-label="Competency analysis">
        {assessed.map((c) => (
          <li key={`${c.category}-${c.competency}`} className="rounded-lg border border-slate-200 p-3">
            <div className="flex items-baseline justify-between gap-2 text-sm">
              <span className="font-medium text-slate-800">{c.competency}</span>
              <span className="shrink-0 text-xs text-slate-500">
                {c.score}/100{c.level ? ` · ${c.level}` : ''}
              </span>
            </div>
            <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-label={c.competency}
              aria-valuenow={c.score} aria-valuemin={0} aria-valuemax={100}>
              <div className="h-full rounded-full bg-[var(--brand-navy)]" style={{ width: `${c.score}%` }} />
            </div>
            {c.strengths?.length > 0 && <p className="mt-2 text-xs text-emerald-800">Strengths: {c.strengths.join('; ')}</p>}
            {c.improvements?.length > 0 && <p className="mt-1 text-xs text-amber-900">To improve: {c.improvements.join('; ')}</p>}
          </li>
        ))}
      </ul>
      {notAssessed.length > 0 && (
        <p className="mt-2 text-xs text-slate-500">Not assessed in this interview: {notAssessed.map((c) => c.competency).join(', ')}.</p>
      )}
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div>
      <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="text-sm font-semibold text-slate-900">{value}</dd>
    </div>
  );
}

export function CodingResults({ coding, questions }) {
  const items = coding?.items || [];
  if (!items.length) return null;
  const byOrder = Object.fromEntries(questions.map((q) => [q.question_order, q]));
  return (
    <section className="surface-card space-y-4" aria-labelledby="coding-heading">
      <h2 id="coding-heading" className="flex items-center gap-2 text-base font-semibold">
        <Code2 className="h-4 w-4" aria-hidden="true" />
        Coding & SQL assessment results
      </h2>
      <p className="text-xs text-slate-500">
        Correctness comes only from Judge0 execution. Code quality is an AI review. The combined coding score (70% correctness + 30%
        quality) is shown only when the review completed.
      </p>
      {items.map((item) => {
        const answer = byOrder[item.question_order]?.answer;
        const sql = item.kind === 'sql';
        const reviewSubmission = { submission_type: 'SUBMIT', ai_review: item.review };
        return (
          <article key={item.question_order} className="rounded-xl border border-slate-200 p-4" aria-label={item.title}>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Q{item.question_order} · {sql ? 'SQL' : 'Coding'} · {item.competency}
                </p>
                <h3 className="text-sm font-semibold text-slate-900">
                  {item.title}
                  {item.difficulty && <span className="font-normal text-slate-500"> · {levelLabel(item.difficulty)}</span>}
                </h3>
                <p className="text-xs text-slate-500">{sql ? `Dialect: ${item.language_label}` : item.language_label}</p>
              </div>
              <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${TONE_CLASSES[toneOf(item.verdict)]}`}>
                Judge0: {item.verdict_label || item.verdict}
              </span>
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
              <Metric label="Tests passed" value={`${item.tests_passed}/${item.tests_total}`} />
              <Metric label="Correctness" value={item.correctness_score !== null ? `${Math.round(item.correctness_score)}/100` : '—'} />
              <Metric
                label="AI code quality"
                value={item.quality_score !== null && item.quality_score !== undefined ? `${Math.round(item.quality_score)}/100`
                  : item.review_status === 'FAILED' ? 'Unavailable' : 'Pending'}
              />
              <Metric label="Combined" value={item.coding_score !== null && item.coding_score !== undefined ? `${Math.round(item.coding_score)}/100` : '—'} />
              <Metric label="Max time" value={formatTime(item.max_time_seconds)} />
              <Metric label="Max memory" value={formatMemory(item.max_memory_kb)} />
              <Metric label="Attempts" value={item.submission_attempts} />
            </dl>
            <details className="mt-3 rounded-lg border border-slate-200 px-3 py-2">
              <summary className="flex cursor-pointer items-center gap-1.5 text-sm font-medium text-slate-700">
                <Bot className="h-4 w-4" aria-hidden="true" />
                {sql ? 'Query feedback and optimisation (AI Code Review)' : 'AI Code Review'}
              </summary>
              <div className="mt-3">
                <CodeReviewPanel submission={reviewSubmission} />
              </div>
            </details>
            {answer?.answer_text && (
              <details className="mt-2 rounded-lg border border-slate-200 px-3 py-2">
                <summary className="cursor-pointer text-sm font-medium text-slate-700">
                  {sql ? 'Submitted query' : 'Submitted code'} · {item.language_label}
                </summary>
                <pre className="mt-2 max-h-96 overflow-auto rounded-lg bg-[#101B2D] p-3 font-mono text-xs leading-5 text-[#E6EAF2]">
                  {answer.answer_text}
                </pre>
              </details>
            )}
          </article>
        );
      })}
    </section>
  );
}
