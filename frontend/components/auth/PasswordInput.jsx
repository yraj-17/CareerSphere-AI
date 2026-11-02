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

  const toggleVisibility = () => setShowPassword((prev) => !prev);

  const borderClass = error
    ? 'border-[#F4C7C3] focus:border-[#B42318] focus:ring-[#B42318]/20 bg-[#FEF3F2]'
    : 'border-[#E3E7ED] hover:border-[#C6A15B]/60 focus:border-[#17243A] focus:ring-[#17243A]/10 bg-white';

  return (
    <div className="w-full space-y-1.5">
      <div className="flex items-center justify-between">
        <label htmlFor={id} className="block text-sm font-medium text-[#172033]">
          {label} {required && <span className="text-[#B42318]">*</span>}
        </label>
      </div>

      <div className="relative">
        <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-[#667085]">
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
          className={`block w-full rounded-xl border pl-10 pr-11 py-2 text-[13px] text-[#172033] placeholder-[#667085] transition-all duration-200 focus:outline-none focus:ring-2 ${borderClass} ${
            disabled ? 'opacity-60 cursor-not-allowed bg-[#F5F6F8]' : ''
          }`}
        />

        <button
          type="button"
          id={`${id}-toggle-visibility`}
          onClick={toggleVisibility}
          disabled={disabled}
          tabIndex={0}
          aria-label={showPassword ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
          className="absolute inset-y-0 right-0 flex items-center pr-3 text-[#667085] hover:text-[#17243A] focus:outline-none transition-colors"
        >
          {showPassword ? (
            <EyeOff className="h-4 w-4" aria-hidden="true" />
          ) : (
            <Eye className="h-4 w-4" aria-hidden="true" />
          )}
        </button>
      </div>

      {error && (
        <p id={`${id}-error`} className="text-xs text-[#B42318] mt-1 flex items-center gap-1 font-medium">
          {error}
        </p>
      )}
    </div>
  );
}
