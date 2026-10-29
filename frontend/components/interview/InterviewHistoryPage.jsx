'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { AlertCircle, ChevronLeft, ChevronRight, Loader2, PlayCircle, Plus } from 'lucide-react';
import { extractErrorMessage, listInterviews } from '@/services/api';
import {
  STATUS_META,
  difficultyLabel,
  formatDateTime,
  modeLabel,
  scoreBand,
  typeLabel,
} from '@/components/interview/interviewConstants';

export const HISTORY_PAGE_SIZE = 10;

function HistoryCard({ item }) {
  const meta = STATUS_META[item.status] || STATUS_META.COMPLETED;
  const band = scoreBand(item.final_score);
  const resumable = item.status === 'IN_PROGRESS';
  const hasReport = !resumable && item.answered_count > 0;

  return (
    <li className="surface-card flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
      <div className="min-w-0 space-y-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="truncate text-base font-semibold text-slate-900">{item.target_role}</h2>
          <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${meta.className}`}>{meta.label}</span>
        </div>
        <p className="text-sm text-slate-600">
          {typeLabel(item.interview_type)} · {modeLabel(item.interaction_mode)} · {difficultyLabel(item.difficulty)} · {item.duration_minutes} min
        </p>
        <p className="text-xs text-slate-500">
          {formatDateTime(item.started_at)} · {item.answered_count} of {item.question_count} answered
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-4">
        <div className="text-right">
          <p className="text-xs text-slate-500">Score</p>
          {item.final_score !== null && item.final_score !== undefined ? (
            <p className={`text-xl font-bold ${band.className}`}>{item.final_score}</p>
          ) : (
            <p className="text-sm font-medium text-slate-400">—</p>
          )}
        </div>
        {resumable ? (
          <Link href={`/dashboard/interview/${item.id}`} className="btn-primary">
            <PlayCircle className="h-4 w-4" aria-hidden="true" />
            Resume
          </Link>
        ) : hasReport ? (
          <Link href={`/dashboard/interview/${item.id}/results`} className="btn-outline">
            View report
          </Link>
        ) : (
          <span className="text-xs text-slate-500">No answers submitted</span>
        )}
      </div>
    </li>
  );
}

export default function InterviewHistoryPage() {
  const [page, setPage] = useState(0);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async (pageIndex) => {
    setLoading(true);
    setError('');
    try {
      setData(await listInterviews({ limit: HISTORY_PAGE_SIZE, offset: pageIndex * HISTORY_PAGE_SIZE }));
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(page);
  }, [load, page]);

  const total = data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / HISTORY_PAGE_SIZE));

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">AI Interviewer</p>
          <h1 className="page-title mt-1">Interview history</h1>
          <p className="page-description">Revisit past practice interviews and their reports.</p>
        </div>
        <Link href="/dashboard/interview" className="btn-primary shrink-0">
          <Plus className="h-4 w-4" aria-hidden="true" />
          New interview
        </Link>
      </div>

      {loading && !data ? (
        <div className="flex min-h-[30vh] items-center justify-center" role="status">
          <Loader2 className="mr-2 h-5 w-5 animate-spin text-brand-500" aria-hidden="true" />
          <span className="text-sm text-slate-500">Loading interview history...</span>
        </div>
      ) : error ? (
        <div className="surface-card text-center" role="alert">
          <AlertCircle className="mx-auto h-7 w-7 text-red-600" aria-hidden="true" />
          <p className="mt-2 text-sm text-slate-600">{error}</p>
          <button type="button" onClick={() => load(page)} className="btn-outline mt-3">
            Try again
          </button>
        </div>
      ) : total === 0 ? (
        <div className="surface-card text-center">
          <h2 className="text-lg font-semibold">No interviews yet</h2>
          <p className="mt-1 text-sm text-slate-500">Your practice interviews and reports will appear here.</p>
          <Link href="/dashboard/interview" className="btn-primary mt-4">
            Start your first interview
          </Link>
        </div>
      ) : (
        <>
          <ul className={`space-y-3 ${loading ? 'opacity-60' : ''}`} aria-busy={loading}>
            {data.interviews.map((item) => (
              <HistoryCard key={item.id} item={item} />
            ))}
          </ul>
          {pageCount > 1 && (
            <nav className="flex items-center justify-between" aria-label="History pagination">
              <button type="button" onClick={() => setPage((p) => p - 1)} disabled={page === 0 || loading} className="btn-outline">
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
                Previous
              </button>
              <span className="text-sm text-slate-600">
                Page {page + 1} of {pageCount}
              </span>
              <button type="button" onClick={() => setPage((p) => p + 1)} disabled={page + 1 >= pageCount || loading} className="btn-outline">
                Next
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </button>
            </nav>
          )}
        </>
      )}
    </div>
  );
}
