'use client';

import React, { useState } from 'react';
import { ChevronDown, Clock, Cpu, Eye, EyeOff, Lock } from 'lucide-react';
import { DifficultyNote, levelLabel } from '@/components/interview/PracticalTask';
import { DIFFICULTY_CLASSES, categoryCopy, formatMemory } from '@/components/interview/coding/codingUtils';

function Section({ id, title, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="border-b border-slate-200 last:border-b-0">
      <h3>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-controls={`problem-${id}`}
          className="flex w-full items-center justify-between gap-2 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-600 hover:text-slate-900"
        >
          {title}
          <ChevronDown className={`h-4 w-4 transition-transform ${open ? '' : '-rotate-90'}`} aria-hidden="true" />
        </button>
      </h3>
      {open && (
        <div id={`problem-${id}`} className="pb-3">
          {children}
        </div>
      )}
    </section>
  );
}

function Pre({ children, label }) {
  return (
    <pre
      aria-label={label}
      className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-slate-200 bg-slate-50 p-2.5 font-mono text-xs leading-5 text-slate-800"
    >
      {children}
    </pre>
  );
}

function Paragraphs({ text }) {
  return (
    <div className="space-y-2 text-sm leading-6 text-slate-700">
      {(text || '').split(/\n{2,}/).map((para) => (
        <p key={para.slice(0, 40)} className="whitespace-pre-wrap">
          {para}
        </p>
      ))}
    </div>
  );
}

/** Problem statement, exactly as returned by the backend (hidden tests are never part of it). */
export default function ProblemPanel({ problem, question, targetRole, practical }) {
  const copy = categoryCopy(problem.category);
  const sampleCount = problem.sample_test_count;
  return (
    <div className="flex h-full flex-col">
      <header className="space-y-2 border-b border-slate-200 pb-3">
        <h2 className="text-lg font-semibold leading-7 text-slate-900">{problem.title}</h2>
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className={`rounded-full border px-2 py-0.5 font-semibold ${DIFFICULTY_CLASSES[problem.difficulty] || DIFFICULTY_CLASSES.MEDIUM}`}>
            {levelLabel(problem.difficulty)}
          </span>
          <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-slate-600">{targetRole}</span>
          <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-slate-600">{question.competency}</span>
        </div>
        <dl className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
          <div className="flex items-center gap-1">
            <Clock className="h-3.5 w-3.5" aria-hidden="true" />
            <dt className="sr-only">Time limit</dt>
            <dd>{problem.time_limit_seconds}s per test</dd>
          </div>
          <div className="flex items-center gap-1">
            <Cpu className="h-3.5 w-3.5" aria-hidden="true" />
            <dt className="sr-only">Memory limit</dt>
            <dd>{formatMemory(problem.memory_limit_kb)}</dd>
          </div>
          <div className="flex items-center gap-1">
            <Eye className="h-3.5 w-3.5" aria-hidden="true" />
            <dt className="sr-only">Sample tests</dt>
            <dd>
              {sampleCount} sample test{sampleCount === 1 ? '' : 's'}
            </dd>
          </div>
          <div className="flex items-center gap-1">
            <EyeOff className="h-3.5 w-3.5" aria-hidden="true" />
            <dt className="sr-only">Hidden tests</dt>
            <dd>{problem.hidden_test_count} hidden</dd>
          </div>
          <div>
            <dt className="sr-only">Estimated time</dt>
            <dd>~{problem.estimated_minutes} min</dd>
          </div>
        </dl>
        <DifficultyNote practical={practical} />
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        <Section id="description" title="Description">
          <Paragraphs text={problem.statement} />
          {problem.instructions && (
            <p className="mt-2 rounded-lg border border-sky-200 bg-sky-50 px-2.5 py-2 text-xs leading-5 text-sky-900">{problem.instructions}</p>
          )}
        </Section>

        {problem.input_format && (
          <Section id="input" title={copy.inputHeading}>
            {problem.category === 'sql' ? <Pre label="Database schema">{problem.input_format}</Pre> : <Paragraphs text={problem.input_format} />}
          </Section>
        )}
        {problem.output_format && (
          <Section id="output" title="Output format">
            <Paragraphs text={problem.output_format} />
          </Section>
        )}

        <Section id="examples" title={`Examples (${problem.examples.length})`}>
          <div className="space-y-3">
            {problem.examples.map((example, index) => (
              <div key={index} className="space-y-1.5">
                <p className="text-xs font-semibold text-slate-700">Example {index + 1}</p>
                <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{copy.exampleInput}</p>
                <Pre label={`Example ${index + 1} input`}>{example.input}</Pre>
                <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{copy.exampleOutput}</p>
                <Pre label={`Example ${index + 1} expected output`}>{example.output}</Pre>
                {example.explanation && <p className="text-xs leading-5 text-slate-600">{example.explanation}</p>}
              </div>
            ))}
          </div>
        </Section>

        {problem.constraints && (
          <Section id="constraints" title="Constraints">
            <Paragraphs text={problem.constraints} />
          </Section>
        )}

        <p className="mt-3 flex items-start gap-1.5 text-xs leading-5 text-slate-500">
          <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          Submit runs every sample and hidden test on the isolated Judge0 service. Hidden test inputs and expected outputs are never shown.
        </p>
      </div>
    </div>
  );
}
