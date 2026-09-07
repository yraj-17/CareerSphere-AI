'use client';

import React from 'react';
import { Check, Circle } from 'lucide-react';

export default function PasswordRules({ password = '' }) {
  const rules = [
    {
      id: 'length',
      label: 'At least 8 characters',
      valid: password.length >= 8,
    },
    {
      id: 'uppercase',
      label: 'One uppercase letter (A-Z)',
      valid: /[A-Z]/.test(password),
    },
    {
      id: 'lowercase',
      label: 'One lowercase letter (a-z)',
      valid: /[a-z]/.test(password),
    },
    {
      id: 'number',
      label: 'One number (0-9)',
      valid: /[0-9]/.test(password),
    },
  ];

  return (
    <div className="rounded-xl bg-slate-950/60 border border-white/10 p-3.5 space-y-2 text-xs backdrop-blur-md">
      <p className="font-medium text-slate-400">Password must contain:</p>
      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-1.5" aria-label="Password requirements">
        {rules.map((rule) => (
          <li
            key={rule.id}
            className={`flex items-center gap-1.5 transition-colors duration-200 ${
              rule.valid ? 'text-emerald-400 font-medium' : 'text-slate-500'
            }`}
          >
            {rule.valid ? (
              <Check className="h-3.5 w-3.5 text-emerald-400 shrink-0" aria-hidden="true" />
            ) : (
              <Circle className="h-3 w-3 text-slate-600 shrink-0" aria-hidden="true" />
            )}
            <span>{rule.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

