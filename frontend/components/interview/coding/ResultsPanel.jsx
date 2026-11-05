'use client';

import React from 'react';
import { AlertTriangle, CheckCircle2, EyeOff, History, Loader2, RefreshCw, XCircle } from 'lucide-react';
import {
  TONE_CLASSES,
  formatMemory,
  formatTime,
  formatTimestamp,
  isPending,
  parseSqlRows,
  toneOf,
} from '@/components/interview/coding/codingUtils';
import CodeReviewPanel, { ReviewStatusLine } from '@/components/interview/coding/CodeReviewPanel';

export const RESULT_TABS = [
  { id: 'tests', label: 'Test Cases' },
  { id: 'custom', label: 'Custom Input' },
  { id: 'output', label: 'Output' },
  { id: 'compile', label: 'Compilation' },
  { id: 'review', label: 'AI Code Review' },
  { id: 'history', label: 'Submission History' },
];

function Block({ label, children, tone }) {
  return (
    <div className="min-w-0">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <pre
        className={`mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-md border p-2 font-mono text-xs leading-5 ${
          tone === 'error' ? 'border-red-200 bg-red-50 text-red-900' : 'border-slate-200 bg-slate-50 text-slate-800'
        }`}
      >
        {children === '' ? <span className="italic text-slate-400">(empty)</span> : children}
      </pre>
    </div>
  );
}

export function SqlTable({ stdout, label = 'Query result' }) {
  const rows = parseSqlRows(stdout);
  if (rows === null) return <Block label={label}>{stdout}</Block>;
  if (rows.length === 0) return <p className="text-xs italic text-slate-500">The query returned no rows.</p>;
  return (
    <div className="min-w-0">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
        {label} · {rows.length} row{rows.length === 1 ? '' : 's'}
      </p>
      <div className="mt-1 max-h-56 overflow-auto rounded-md border border-slate-200">
        <table className="w-full border-collapse text-left font-mono text-xs">
          <thead className="sticky top-0 bg-slate-100 text-slate-600">
            <tr>
              {rows[0].map((_, i) => (
                <th key={i} scope="col" className="border-b border-slate-200 px-2 py-1 font-semibold">
                  col {i + 1}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, r) => (
              <tr key={r} className="odd:bg-white even:bg-slate-50">
                {row.map((cell, c) => (
                  <td key={c} className={`border-b border-slate-100 px-2 py-1 ${cell === 'NULL' ? 'italic text-slate-400' : 'text-slate-800'}`}>
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Output({ text, sql, label }) {
  return sql ? <SqlTable stdout={text} label={label} /> : <Block label={label}>{text}</Block>;
}

export function VerdictBanner({ submission }) {
  if (!submission) return null;
  if (submission.status === 'FAILED') {
    return (
      <div role="status" className={`rounded-lg border px-3 py-2 text-sm ${TONE_CLASSES.neutral}`}>
        <p className="font-semibold">Not executed</p>
        <p className="text-xs">{submission.error || 'The execution service could not run this code. Please try again.'}</p>
      </div>
    );
  }
  const tone = toneOf(submission.verdict);
  const Icon = tone === 'success' ? CheckCircle2 : tone === 'danger' ? XCircle : AlertTriangle;
  const isSubmit = submission.submission_type === 'SUBMIT';
  return (
    <div role="status" className={`flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 ${TONE_CLASSES[tone]}`}>
      <p className="flex items-center gap-2 text-sm font-semibold">
        <Icon className="h-4 w-4" aria-hidden="true" />
        {submission.verdict_label || submission.verdict}
        <span className="text-xs font-medium opacity-80">· {isSubmit ? 'Submission (all tests)' : 'Run (sample tests only)'}</span>
      </p>
      <p className="text-xs">
        {submission.tests_total !== null && submission.tests_total !== undefined && (
          <span>
            {submission.tests_passed}/{submission.tests_total} tests passed ·{' '}
          </span>
        )}
        {isSubmit && submission.correctness_score !== null && submission.correctness_score !== undefined && (
          <span>score {Math.round(submission.correctness_score)}/100 · </span>
        )}
        <span>
          {formatTime(submission.max_time_seconds)} · {formatMemory(submission.max_memory_kb)}
        </span>
      </p>
    </div>
  );
}

function TestRow({ result, sql }) {
  const passed = result.passed;
  const tone = result.kind === 'custom' ? 'info' : passed ? 'success' : 'danger';
  const title =
    result.kind === 'hidden' ? `Hidden test ${result.ordinal}` : result.kind === 'custom' ? 'Custom input' : `Sample test ${result.ordinal}`;
  return (
    <li className="rounded-lg border border-slate-200 bg-white p-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-slate-800">{title}</p>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span>{formatTime(result.time)}</span>
          <span>{formatMemory(result.memory)}</span>
          <span className={`rounded-full border px-2 py-0.5 font-semibold ${TONE_CLASSES[tone]}`}>
            {result.kind === 'custom' ? result.verdict_label : passed ? 'Passed' : result.verdict_label || 'Failed'}
          </span>
        </div>
      </div>
      {result.kind === 'hidden' ? (
        <p className="mt-1 flex items-center gap-1 text-xs text-slate-500">
          <EyeOff className="h-3.5 w-3.5" aria-hidden="true" />
          Input and expected output are hidden.
        </p>
      ) : (
        <div className="mt-2 grid gap-2 md:grid-cols-2">
          <Block label="Input">{result.input}</Block>
          {result.expected_output !== null && result.expected_output !== undefined && (
            <Output sql={sql} label="Expected output" text={result.expected_output} />
          )}
          <Output sql={sql} label="Your output" text={result.stdout} />
          {result.stderr && (
            <Block label="Standard error" tone="error">
              {result.stderr}
            </Block>
          )}
          {result.reason && <p className="text-xs text-slate-600 md:col-span-2">{result.reason}</p>}
        </div>
      )}
    </li>
  );
}

function Pending({ phase, submission }) {
  let text = 'Sending your code…';
  if (submission?.status === 'QUEUED') text = 'Queued on the execution service…';
  if (submission?.status === 'RUNNING') text = 'Compiling and running on Judge0…';
  if (phase === 'reconnecting') text = 'Lost contact with the server — checking the result again…';
  return (
    <p className="flex items-center gap-2 text-sm text-slate-600" role="status">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      {text}
    </p>
  );
}

export default function ResultsPanel({
  tab,
  onTab,
  copy,
  sql,
  view, // { submission, phase, error, historical }
  customInput,
  onCustomInputChange,
  useCustomInput,
  onUseCustomInputChange,
  customHelp,
  readOnly,
  history,
  historyState, // { loading, error }
  onRefreshHistory,
  onSelectHistory,
  onCheckStatus,
  onRetryReview,
  retryingReview,
}) {
  const submission = view.submission;
  const pending = view.phase === 'sending' || view.phase === 'reconnecting' || isPending(submission);
  const results = submission?.results || [];
  const visible = results.filter((r) => r.kind !== 'hidden');
  const outputSource = results.find((r) => r.kind === 'custom') || visible[0];

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div role="tablist" aria-label="Execution results" className="flex shrink-0 gap-1 overflow-x-auto border-b border-slate-200 px-2">
        {RESULT_TABS.map((t) => (
          <button
            key={t.id}
            id={`results-tab-${t.id}`}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            aria-controls={`results-panel-${t.id}`}
            onClick={() => onTab(t.id)}
            className={`whitespace-nowrap border-b-2 px-2.5 py-2 text-xs font-semibold transition-colors ${
              tab === t.id ? 'border-[var(--brand-amber)] text-slate-900' : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            {t.id === 'custom' ? copy.customLabel : t.label}
            {t.id === 'history' && history.length > 0 ? ` (${history.length})` : ''}
          </button>
        ))}
      </div>

      <div id={`results-panel-${tab}`} role="tabpanel" aria-labelledby={`results-tab-${tab}`} className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
        {view.error && (
          <div role="alert" className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            <span>{view.error}</span>
            {view.canCheckStatus && (
              <button type="button" onClick={onCheckStatus} className="btn-outline px-2 py-1 text-xs">
                <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                Check status
              </button>
            )}
          </div>
        )}
        {view.historical && submission && (
          <p className="text-xs text-slate-500">
            Viewing an earlier {submission.submission_type === 'SUBMIT' ? 'submission' : 'run'} from {formatTimestamp(submission.created_at)} (
            {submission.language_label}).
          </p>
        )}

        {tab === 'tests' &&
          (pending ? (
            <Pending phase={view.phase} submission={submission} />
          ) : !submission ? (
            <p className="text-sm text-slate-500">
              {copy.run} executes your code on the sample tests{sql ? '' : ' (and your custom input, if enabled)'}. {copy.submit} runs every sample and hidden test.
            </p>
          ) : (
            <>
              <VerdictBanner submission={submission} />
              <ReviewStatusLine submission={submission} onOpen={() => onTab('review')} />
              <ul className="space-y-2" aria-label="Test case results">
                {results.map((result) => (
                  <TestRow key={`${result.kind}-${result.ordinal}`} result={result} sql={sql} />
                ))}
              </ul>
            </>
          ))}

        {tab === 'custom' && (
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={useCustomInput}
                onChange={(e) => onUseCustomInputChange(e.target.checked)}
                disabled={readOnly}
                className="h-4 w-4 rounded border-slate-300"
              />
              Include this {copy.customLabel.toLowerCase()} when I run my code
            </label>
            <p className="text-xs text-slate-500">{customHelp}</p>
            <textarea
              aria-label={copy.customLabel}
              value={customInput}
              onChange={(e) => onCustomInputChange(e.target.value)}
              disabled={readOnly}
              rows={6}
              spellCheck={false}
              className="input-base resize-y font-mono text-xs leading-5"
            />
          </div>
        )}

        {tab === 'output' &&
          (pending ? (
            <Pending phase={view.phase} submission={submission} />
          ) : outputSource ? (
            <div className="space-y-2">
              <p className="text-xs text-slate-500">
                {outputSource.kind === 'custom' ? 'Output for your custom input.' : `Output for sample test ${outputSource.ordinal}.`}
              </p>
              <Output sql={sql} label="Standard output" text={outputSource.stdout} />
              {outputSource.stderr ? (
                <Block label="Standard error" tone="error">
                  {outputSource.stderr}
                </Block>
              ) : (
                <p className="text-xs text-slate-500">No standard error output.</p>
              )}
            </div>
          ) : (
            <p className="text-sm text-slate-500">
              {submission?.submission_type === 'SUBMIT'
                ? 'Submissions show per-test results only; program output on hidden tests is never shown.'
                : 'Run your code to see its output.'}
            </p>
          ))}

        {tab === 'compile' &&
          (pending ? (
            <Pending phase={view.phase} submission={submission} />
          ) : !submission ? (
            <p className="text-sm text-slate-500">Compiler messages appear here after you run your code.</p>
          ) : submission.compile_output ? (
            <Block label={submission.verdict === 'COMPILATION_ERROR' ? 'Compilation failed' : 'Compiler output'} tone={submission.verdict === 'COMPILATION_ERROR' ? 'error' : undefined}>
              {submission.compile_output}
            </Block>
          ) : (
            <p className="text-sm text-slate-600">
              {submission.status === 'FAILED' ? 'The code was not executed.' : `No compiler messages (${submission.language_label}).`}
            </p>
          ))}

        {tab === 'review' && <CodeReviewPanel submission={pending ? null : submission} onRetry={onRetryReview} retrying={retryingReview} />}

        {tab === 'history' && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="flex items-center gap-1.5 text-xs text-slate-500">
                <History className="h-3.5 w-3.5" aria-hidden="true" />
                Your runs and submissions for this question. Viewing one never re-runs it.
              </p>
              <button type="button" onClick={onRefreshHistory} disabled={historyState.loading} className="btn-ghost px-2 py-1 text-xs">
                <RefreshCw className={`h-3.5 w-3.5 ${historyState.loading ? 'animate-spin' : ''}`} aria-hidden="true" />
                Refresh
              </button>
            </div>
            {historyState.error && (
              <p role="alert" className="text-sm text-red-700">
                {historyState.error}
              </p>
            )}
            {history.length === 0 && !historyState.loading ? (
              <p className="text-sm text-slate-500">No runs or submissions yet.</p>
            ) : (
              <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white" aria-label="Submission history">
                {history.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => onSelectHistory(item)}
                      className="flex w-full flex-wrap items-center justify-between gap-2 px-3 py-2 text-left text-xs hover:bg-slate-50"
                    >
                      <span className="flex items-center gap-2">
                        <span className="font-mono text-slate-500">{formatTimestamp(item.created_at)}</span>
                        <span className="font-semibold text-slate-800">{item.submission_type === 'SUBMIT' ? 'Submit' : 'Run'}</span>
                        <span className="text-slate-500">{item.language_label}</span>
                      </span>
                      <span className="flex items-center gap-2">
                        {item.tests_total !== null && item.tests_total !== undefined && (
                          <span className="text-slate-500">
                            {item.tests_passed}/{item.tests_total}
                          </span>
                        )}
                        <span
                          className={`rounded-full border px-2 py-0.5 font-semibold ${
                            TONE_CLASSES[isPending(item) ? 'info' : item.status === 'FAILED' ? 'neutral' : toneOf(item.verdict)]
                          }`}
                        >
                          {isPending(item) ? 'Running' : item.status === 'FAILED' ? 'Not executed' : item.verdict_label || item.verdict}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
