'use client';

import React, { useState } from 'react';
import { Eye, EyeOff, Lock } from 'lucide-react';

export default function PasswordInput({
  id,
  name,
  label = 'Password',
  value,
  onChange,
  placeholder = '••••••••',
  required = true,
  error = null,
  disabled = false,
  autoComplete = 'current-password',
}) {
  const [showPassword, setShowPassword] = useState(false);

  const toggleVisibility = () => {
    setShowPassword((prev) => !prev);
  };

  return (
    <div className="w-full space-y-1.5">
      <div className="flex items-center justify-between">
        <label htmlFor={id} className="block text-sm font-medium text-slate-200">
          {label} {required && <span className="text-rose-400">*</span>}
        </label>
      </div>

      <div className="relative rounded-xl shadow-sm">
        <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-slate-400">
          <Lock className="h-4 w-4" aria-hidden="true" />
        </div>

        <input
          id={id}
          name={name}
          type={showPassword ? 'text' : 'password'}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          required={required}
          disabled={disabled}
          autoComplete={autoComplete}
          aria-invalid={error ? 'true' : 'false'}
          aria-describedby={error ? `${id}-error` : undefined}
          className={`block w-full rounded-xl bg-slate-950/80 border pl-10 pr-11 py-2.5 text-sm text-slate-100 placeholder-slate-500 transition-all duration-200 focus:outline-none focus:ring-2 ${
            error
              ? 'border-rose-500/80 focus:border-rose-500 focus:ring-rose-500/30'
              : 'border-white/10 hover:border-white/20 focus:border-accent/80 focus:ring-accent/30'
          } ${disabled ? 'opacity-60 cursor-not-allowed' : ''}`}
        />

        <button
          type="button"
          id={`${id}-toggle-visibility`}
          onClick={toggleVisibility}
          disabled={disabled}
          tabIndex={0}
          aria-label={showPassword ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
          className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 hover:text-accent focus:outline-none focus:text-accent transition-colors"
        >
          {showPassword ? (
            <EyeOff className="h-4 w-4" aria-hidden="true" />
          ) : (
            <Eye className="h-4 w-4" aria-hidden="true" />
          )}
        </button>
      </div>

      {error && (
        <p id={`${id}-error`} className="text-xs text-rose-400 mt-1 flex items-center gap-1 font-medium">
          {error}
        </p>
      )}
    </div>
  );
}

