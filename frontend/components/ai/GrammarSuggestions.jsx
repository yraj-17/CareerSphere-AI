'use client';

import React from 'react';
import { Check, SpellCheck, X } from 'lucide-react';

export default function GrammarSuggestions({ result, isChecking, error, onApply, onDismiss }) {
  if (!result && !isChecking && !error) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-cyan/30 bg-cyan/10 backdrop-blur-xl p-4 shadow-[0_0_30px_rgba(64,217,255,0.12)] space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-white">
          <SpellCheck className="h-4 w-4 text-cyan" />
          <span className="text-cyan-200">Grammar Suggestions</span>
        </div>
        {onDismiss ? (
          <button
            type="button"
            onClick={onDismiss}
            className="rounded-full p-1 text-slate-400 hover:bg-white/10 hover:text-white transition-all"
            aria-label="Dismiss grammar suggestions"
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </div>

      {isChecking ? (
        <p className="text-xs text-cyan-200/80">Checking your writing with AI...</p>
      ) : null}

      {error ? <p className="text-sm text-rose-300">{error}</p> : null}

      {result && !isChecking ? (
        result.matches?.length ? (
          <>
            <ul className="space-y-2">
              {result.matches.map((match, index) => (
                <li
                  key={`${match.offset}-${index}`}
                  className="rounded-xl border border-white/10 bg-slate-950/70 p-3 text-sm"
                >
                  <p className="text-slate-200">
                    <span className="font-medium text-rose-300">“{match.original}”</span>
                    {match.replacements?.[0] ? (
                      <>
                        <span className="text-slate-500"> → </span>
                        <span className="font-medium text-emerald-300">“{match.replacements[0]}”</span>
                      </>
                    ) : null}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">{match.message}</p>
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={onApply}
              className="inline-flex items-center gap-2 rounded-full border border-emerald-500/40 bg-emerald-500/15 px-4 py-1.5 text-xs font-semibold text-emerald-300 hover:bg-emerald-500/25 transition-all"
            >
              <Check className="h-4 w-4" />
              Apply corrections
            </button>
          </>
        ) : (
          <p className="text-xs text-cyan-200/80">No grammar or spelling issues were found. Excellent work!</p>
        )
      ) : null}
    </div>
  );
}
