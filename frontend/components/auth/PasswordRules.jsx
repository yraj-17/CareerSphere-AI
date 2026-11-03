'use client';

import React from 'react';
import { Check, Circle } from 'lucide-react';

export default function PasswordRules({ password = '' }) {
  const rules = [
    { id: 'length',    label: 'At least 8 characters',     valid: password.length >= 8 },
    { id: 'uppercase', label: 'One uppercase letter (A–Z)', valid: /[A-Z]/.test(password) },
    { id: 'lowercase', label: 'One lowercase letter (a–z)', valid: /[a-z]/.test(password) },
    { id: 'number',    label: 'One number (0–9)',           valid: /[0-9]/.test(password) },
  ];

  const allValid = rules.every((r) => r.valid);

  return (
    <div className={`rounded-xl border p-2.5 space-y-1.5 text-[11px] transition-colors duration-300 ${
      allValid
        ? 'bg-[#ECFDF3] border-[#BBF7D0]'
        : 'bg-[#EEF1F5] border-[#E3E7ED]'
    }`}>
      <p className={`font-semibold ${allValid ? 'text-[#15803D]' : 'text-[#667085]'}`}>
        {allValid ? '✓ Password requirements met' : 'Password must contain:'}
      </p>
      <ul className="grid grid-cols-1 gap-x-3 gap-y-1 sm:grid-cols-2" aria-label="Password requirements">
        {rules.map((rule) => (
          <li
            key={rule.id}
            className={`flex items-center gap-1.5 transition-colors duration-200 ${
              rule.valid ? 'text-[#15803D] font-medium' : 'text-[#667085]'
            }`}
          >
            {rule.valid ? (
              <Check className="h-3.5 w-3.5 text-[#15803D] shrink-0" aria-hidden="true" />
            ) : (
              <Circle className="h-3 w-3 text-[#D0D5DD] shrink-0" aria-hidden="true" />
            )}
            <span>{rule.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
