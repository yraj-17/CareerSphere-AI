'use client';

import React from 'react';
import { Bot, Calculator, Code2, Info } from 'lucide-react';
import { slotKindLabel } from '@/components/interview/interviewConstants';

/** How a practical result is produced — always shown so AI review is never mistaken for execution. */
export function AssessmentLabel({ label, kind }) {
  if (!label) return null;
  const Icon = kind === 'calculation' ? Calculator : kind === 'scenario' ? Bot : Code2;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-2.5 py-0.5 text-xs font-semibold text-slate-700">
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {label}
    </span>
  );
}

const LEVEL_LABELS = { EASY: 'Easy', MEDIUM: 'Medium', HARD: 'Hard' };

export function levelLabel(level) {
  return LEVEL_LABELS[level] || level || '';
}

/** Disclosed whenever no verified assessment exists at the planned level and the closest one was used. */
export function DifficultyNote({ practical }) {
  if (!practical?.difficulty_fallback) return null;
  return (
    <p role="note" className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-900">
      Difficulty: {levelLabel(practical.difficulty)}. Your interview level calls for {levelLabel(practical.planned_difficulty)}, but no
      verified {levelLabel(practical.planned_difficulty).toLowerCase()} assessment exists for this competency yet, so the closest verified
      level is used. This is recorded in your report.
    </p>
  );
}

export function ScenarioBrief({ practical }) {
  return (
    <div className="space-y-3" aria-label="Practical scenario">
      <AssessmentLabel label={practical.label} kind="scenario" />
      <DifficultyNote practical={practical} />
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Situation</p>
        <pre className="mt-1.5 max-h-96 overflow-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-slate-50 p-3 font-mono text-xs leading-5 text-slate-800">
          {practical.context}
        </pre>
      </div>
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Your tasks</p>
        <ol className="mt-1.5 list-decimal space-y-1 pl-5 text-sm leading-6 text-slate-700">
          {practical.tasks.map((task) => (
            <li key={task}>{task}</li>
          ))}
        </ol>
      </div>
      {practical.criteria?.length > 0 && (
        <p className="text-xs text-slate-500">
          Assessed on: {practical.criteria.join(' · ')}. Your written answer is reviewed by AI against a fixed rubric; nothing is executed.
        </p>
      )}
    </div>
  );
}

export function CalculationForm({ practical, values, onChange, disabled }) {
  return (
    <div className="space-y-3" aria-label="Practical calculation">
      <AssessmentLabel label={practical.label} kind="calculation" />
      <DifficultyNote practical={practical} />
      <p className="text-xs text-slate-500">{practical.conventions}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        {practical.fields.map((field) => {
          const id = `calc-${field.key}`;
          const value = values?.[field.key] || '';
          return (
            <div key={field.key}>
              <label htmlFor={id} className="text-sm font-medium text-slate-700">
                {field.label}
              </label>
              {field.options ? (
                <select
                  id={id}
                  value={value}
                  disabled={disabled}
                  onChange={(event) => onChange({ ...(values || {}), [field.key]: event.target.value })}
                  className="input-base mt-1"
                >
                  <option value="">Choose…</option>
                  {field.options.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  id={id}
                  type="text"
                  value={value}
                  maxLength={100}
                  disabled={disabled}
                  autoComplete="off"
                  spellCheck={false}
                  placeholder={field.hint}
                  onChange={(event) => onChange({ ...(values || {}), [field.key]: event.target.value })}
                  className="input-base mt-1 font-mono"
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function PracticalUnavailable({ question }) {
  const practical = question.practical;
  const assigned = practical?.available && (question.kind === 'coding' || question.kind === 'sql');
  return (
    <div className="rounded-xl border border-dashed border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
      <p className="flex items-center gap-2 font-semibold">
        <Info className="h-4 w-4" aria-hidden="true" />
        {slotKindLabel(question.kind)} assessment · {question.competency}
      </p>
      {assigned ? (
        <>
          <p className="mt-1">
            Assigned problem: <span className="font-semibold">{practical.title}</span> ({levelLabel(practical.difficulty).toLowerCase()}). Code
            submission isn&apos;t available for this slot, so it can&apos;t be answered here and is not scored.
          </p>
          <div className="mt-2">
            <DifficultyNote practical={practical} />
          </div>
        </>
      ) : (
        <p className="mt-1">
          {practical?.reason ||
            'This practical slot is reserved in your interview plan, but its assessment isn’t available yet, so it can’t be answered and is not scored.'}{' '}
          It is never replaced with a theoretical question.
        </p>
      )}
    </div>
  );
}

/** Graded details for practical answers (deterministic fields or rubric criteria). */
export function PracticalResult({ evaluation }) {
  if (!evaluation?.method) return null;
  if (evaluation.method === 'judge0') {
    return (
      <div className="flex flex-wrap items-center gap-2 text-sm text-slate-700">
        <AssessmentLabel label={evaluation.label} kind="coding" />
        <span>
          <span className="font-semibold">{evaluation.verdict_label}</span> · {evaluation.correct} of {evaluation.total} tests passed (
          {evaluation.language_label})
        </span>
      </div>
    );
  }
  if (evaluation.method === 'deterministic') {
    return (
      <div className="space-y-2">
        <AssessmentLabel label={evaluation.label} kind="calculation" />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[28rem] text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="py-1 pr-3 font-semibold">Field</th>
                <th className="py-1 pr-3 font-semibold">Your answer</th>
                <th className="py-1 pr-3 font-semibold">Correct value</th>
                <th className="py-1 font-semibold">Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {evaluation.fields.map((field) => (
                <tr key={field.key}>
                  <td className="py-1.5 pr-3 text-slate-700">{field.label}</td>
                  <td className="py-1.5 pr-3 font-mono text-slate-800">{field.given || '—'}</td>
                  <td className="py-1.5 pr-3 font-mono text-slate-800">{field.expected}</td>
                  <td className={`py-1.5 font-semibold ${field.correct ? 'text-emerald-700' : 'text-red-700'}`}>
                    {field.correct ? 'Correct' : 'Incorrect'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }
  if (evaluation.method === 'ai_rubric') {
    return (
      <div className="space-y-2">
        <AssessmentLabel label={evaluation.label} kind="scenario" />
        <ul className="space-y-2 text-sm">
          {evaluation.criteria.map((criterion) => (
            <li key={criterion.id} className="rounded-lg border border-slate-200 p-2.5">
              <div className="flex justify-between gap-3">
                <span className="font-medium text-slate-800">{criterion.title}</span>
                <span className="shrink-0 text-xs font-semibold text-slate-600">
                  {criterion.score}/100 · weight {criterion.points}%
                </span>
              </div>
              {criterion.comment && <p className="mt-1 text-slate-600">{criterion.comment}</p>}
            </li>
          ))}
        </ul>
      </div>
    );
  }
  return null;
}
