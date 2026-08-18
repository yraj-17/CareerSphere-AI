'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { checkUsername } from '@/services/api';
import { useDebounce } from '@/hooks/useDebounce';
import PasswordInput from './PasswordInput';
import PasswordRules from './PasswordRules';
import {
  User,
  Mail,
  ArrowRight,
  AlertCircle,
  Loader2,
  Sparkles,
  CheckCircle2,
  XCircle,
} from 'lucide-react';

export default function SignupForm() {
  const router = useRouter();
  const { signup } = useAuth();

  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    username: '',
    email: '',
    password: '',
    confirm_password: '',
  });

  const [fieldErrors, setFieldErrors] = useState({});
  const [generalError, setGeneralError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Username availability state
  const [usernameStatus, setUsernameStatus] = useState({
    checking: false,
    available: null,
    message: '',
  });

  const debouncedUsername = useDebounce(formData.username.trim(), 400);

  // Debounced username availability check
  useEffect(() => {
    const checkAvailability = async () => {
      const username = debouncedUsername.toLowerCase();
      if (!username || username.length < 3) {
        setUsernameStatus({ checking: false, available: null, message: '' });
        return;
      }

      // Check format before querying API
      if (/\s/.test(username)) {
        setUsernameStatus({
          checking: false,
          available: false,
          message: 'Username cannot contain spaces.',
        });
        return;
      }

      if (!/^[a-zA-Z0-9_.]+$/.test(username)) {
        setUsernameStatus({
          checking: false,
          available: false,
          message: 'Only letters, numbers, underscores, and dots are allowed.',
        });
        return;
      }

      setUsernameStatus({ checking: true, available: null, message: 'Checking...' });

      try {
        const res = await checkUsername(username);
        setUsernameStatus({
          checking: false,
          available: res.available,
          message: res.message || (res.available ? 'Username available' : 'Username already taken'),
        });
      } catch (err) {
        setUsernameStatus({
          checking: false,
          available: null,
          message: '',
        });
      }
    };

    checkAvailability();
  }, [debouncedUsername]);

  const validateForm = () => {
    const errors = {};

    if (!formData.first_name.trim()) {
      errors.first_name = 'First name is required.';
    }

    if (!formData.last_name.trim()) {
      errors.last_name = 'Last name is required.';
    }

    if (!formData.username.trim()) {
      errors.username = 'Username is required.';
    } else if (formData.username.trim().length < 3) {
      errors.username = 'Username must be at least 3 characters.';
    } else if (formData.username.trim().length > 30) {
      errors.username = 'Username cannot exceed 30 characters.';
    } else if (/\s/.test(formData.username)) {
      errors.username = 'Username cannot contain spaces.';
    } else if (!/^[a-zA-Z0-9_.]+$/.test(formData.username.trim())) {
      errors.username = 'Username can only contain letters, numbers, underscores, and dots.';
    } else if (usernameStatus.available === false) {
      errors.username = usernameStatus.message || 'This username is already taken.';
    }

    if (!formData.email.trim()) {
      errors.email = 'Email address is required.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email.trim())) {
      errors.email = 'Please enter a valid email address.';
    }

    // Password validation
    const pwd = formData.password;
    if (!pwd) {
      errors.password = 'Password is required.';
    } else if (pwd.length < 8) {
      errors.password = 'Password must be at least 8 characters.';
    } else if (!/[A-Z]/.test(pwd)) {
      errors.password = 'Password must contain at least one uppercase letter.';
    } else if (!/[a-z]/.test(pwd)) {
      errors.password = 'Password must contain at least one lowercase letter.';
    } else if (!/[0-9]/.test(pwd)) {
      errors.password = 'Password must contain at least one number.';
    }

    // Confirm password validation
    if (!formData.confirm_password) {
      errors.confirm_password = 'Please confirm your password.';
    } else if (formData.confirm_password !== formData.password) {
      errors.confirm_password = 'Passwords do not match.';
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));

    if (fieldErrors[name]) {
      setFieldErrors((prev) => ({ ...prev, [name]: '' }));
    }
    if (generalError) {
      setGeneralError('');
    }

    // Real-time confirm password check
    if (name === 'confirm_password' && formData.password && value !== formData.password) {
      setFieldErrors((prev) => ({ ...prev, confirm_password: 'Passwords do not match.' }));
    } else if (name === 'confirm_password' && value === formData.password) {
      setFieldErrors((prev) => ({ ...prev, confirm_password: '' }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setGeneralError('');

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);

    // Payload excludes confirm_password
    const payload = {
      first_name: formData.first_name.trim(),
      last_name: formData.last_name.trim(),
      username: formData.username.trim().toLowerCase(),
      email: formData.email.trim().toLowerCase(),
      password: formData.password,
    };

    const result = await signup(payload);

    if (result.success) {
      router.push('/login?registered=true');
    } else {
      const errorMsg = result.error || 'Failed to create account. Please try again.';
      if (errorMsg.toLowerCase().includes('username')) {
        setFieldErrors((prev) => ({ ...prev, username: errorMsg }));
      } else if (errorMsg.toLowerCase().includes('email')) {
        setFieldErrors((prev) => ({ ...prev, email: errorMsg }));
      } else {
        setGeneralError(errorMsg);
      }
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-lg mx-auto">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center h-12 w-12 rounded-2xl bg-indigo-600/10 border border-indigo-500/20 mb-4 shadow-inner">
          <Sparkles className="h-6 w-6 text-indigo-400" />
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
          Create Your CareerSphere Account
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Join the next-generation AI platform for career growth and professional networking
        </p>
      </div>

      <div className="glass-card rounded-2xl p-6 sm:p-8 shadow-xl border border-slate-800">
        {/* General Error Alert */}
        {generalError && (
          <div
            className="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-start gap-3 text-rose-300 text-sm animate-fade-in"
            role="alert"
          >
            <AlertCircle className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">{generalError}</p>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          {/* First & Last Name Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="first_name" className="block text-sm font-medium text-slate-200">
                First Name <span className="text-rose-400">*</span>
              </label>
              <input
                id="first_name"
                name="first_name"
                type="text"
                value={formData.first_name}
                onChange={handleChange}
                placeholder="Raj"
                required
                disabled={isSubmitting}
                autoComplete="given-name"
                aria-invalid={fieldErrors.first_name ? 'true' : 'false'}
                aria-describedby={fieldErrors.first_name ? 'first_name-error' : undefined}
                className={`block w-full rounded-lg bg-slate-900/80 border px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 transition-all duration-200 input-focus-ring ${
                  fieldErrors.first_name
                    ? 'border-rose-500/80 focus:border-rose-500 focus:ring-rose-500/30'
                    : 'border-slate-700/80 hover:border-slate-600'
                } ${isSubmitting ? 'opacity-60 cursor-not-allowed' : ''}`}
              />
              {fieldErrors.first_name && (
                <p id="first_name-error" className="text-xs text-rose-400 font-medium">
                  {fieldErrors.first_name}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <label htmlFor="last_name" className="block text-sm font-medium text-slate-200">
                Last Name <span className="text-rose-400">*</span>
              </label>
              <input
                id="last_name"
                name="last_name"
                type="text"
                value={formData.last_name}
                onChange={handleChange}
                placeholder="Yadav"
                required
                disabled={isSubmitting}
                autoComplete="family-name"
                aria-invalid={fieldErrors.last_name ? 'true' : 'false'}
                aria-describedby={fieldErrors.last_name ? 'last_name-error' : undefined}
                className={`block w-full rounded-lg bg-slate-900/80 border px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 transition-all duration-200 input-focus-ring ${
                  fieldErrors.last_name
                    ? 'border-rose-500/80 focus:border-rose-500 focus:ring-rose-500/30'
                    : 'border-slate-700/80 hover:border-slate-600'
                } ${isSubmitting ? 'opacity-60 cursor-not-allowed' : ''}`}
              />
              {fieldErrors.last_name && (
                <p id="last_name-error" className="text-xs text-rose-400 font-medium">
                  {fieldErrors.last_name}
                </p>
              )}
            </div>
          </div>

          {/* Username with Live Availability Check */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label htmlFor="username" className="block text-sm font-medium text-slate-200">
                Username <span className="text-rose-400">*</span>
              </label>
              {/* Live status badge */}
              {usernameStatus.checking && (
                <span className="text-xs text-indigo-400 flex items-center gap-1">
                  <Loader2 className="h-3 w-3 animate-spin" /> Checking...
                </span>
              )}
              {!usernameStatus.checking && usernameStatus.available === true && (
                <span className="text-xs text-emerald-400 flex items-center gap-1 font-medium">
                  <CheckCircle2 className="h-3.5 w-3.5" /> ✓ Username available
                </span>
              )}
              {!usernameStatus.checking && usernameStatus.available === false && (
                <span className="text-xs text-rose-400 flex items-center gap-1 font-medium">
                  <XCircle className="h-3.5 w-3.5" /> ✕ {usernameStatus.message}
                </span>
              )}
            </div>

            <div className="relative rounded-lg shadow-sm">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-slate-400">
                <User className="h-4 w-4" aria-hidden="true" />
              </div>
              <input
                id="username"
                name="username"
                type="text"
                value={formData.username}
                onChange={handleChange}
                placeholder="raj_yadav"
                required
                disabled={isSubmitting}
                autoComplete="username"
                aria-invalid={fieldErrors.username ? 'true' : 'false'}
                aria-describedby={fieldErrors.username ? 'username-error' : undefined}
                className={`block w-full rounded-lg bg-slate-900/80 border pl-10 pr-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 transition-all duration-200 input-focus-ring ${
                  fieldErrors.username || usernameStatus.available === false
                    ? 'border-rose-500/80 focus:border-rose-500 focus:ring-rose-500/30'
                    : usernameStatus.available === true
                    ? 'border-emerald-500/80 focus:border-emerald-500 focus:ring-emerald-500/30'
                    : 'border-slate-700/80 hover:border-slate-600'
                } ${isSubmitting ? 'opacity-60 cursor-not-allowed' : ''}`}
              />
            </div>
            {fieldErrors.username && (
              <p id="username-error" className="text-xs text-rose-400 font-medium">
                {fieldErrors.username}
              </p>
            )}
          </div>

          {/* Email ID */}
          <div className="space-y-1.5">
            <label htmlFor="email" className="block text-sm font-medium text-slate-200">
              Email ID <span className="text-rose-400">*</span>
            </label>
            <div className="relative rounded-lg shadow-sm">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-slate-400">
                <Mail className="h-4 w-4" aria-hidden="true" />
              </div>
              <input
                id="email"
                name="email"
                type="email"
                value={formData.email}
                onChange={handleChange}
                placeholder="raj@example.com"
                required
                disabled={isSubmitting}
                autoComplete="email"
                aria-invalid={fieldErrors.email ? 'true' : 'false'}
                aria-describedby={fieldErrors.email ? 'email-error' : undefined}
                className={`block w-full rounded-lg bg-slate-900/80 border pl-10 pr-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 transition-all duration-200 input-focus-ring ${
                  fieldErrors.email
                    ? 'border-rose-500/80 focus:border-rose-500 focus:ring-rose-500/30'
                    : 'border-slate-700/80 hover:border-slate-600'
                } ${isSubmitting ? 'opacity-60 cursor-not-allowed' : ''}`}
              />
            </div>
            {fieldErrors.email && (
              <p id="email-error" className="text-xs text-rose-400 font-medium">
                {fieldErrors.email}
              </p>
            )}
          </div>

          {/* Password with Eye Toggle */}
          <PasswordInput
            id="password"
            name="password"
            label="Password"
            value={formData.password}
            onChange={handleChange}
            placeholder="Create a strong password"
            required
            disabled={isSubmitting}
            error={fieldErrors.password}
            autoComplete="new-password"
          />

          {/* Live Password Rules Indicator */}
          <PasswordRules password={formData.password} />

          {/* Confirm Password with Eye Toggle */}
          <PasswordInput
            id="confirm_password"
            name="confirm_password"
            label="Confirm Password"
            value={formData.confirm_password}
            onChange={handleChange}
            placeholder="Re-enter your password"
            required
            disabled={isSubmitting}
            error={fieldErrors.confirm_password}
            autoComplete="new-password"
          />

          {/* Submit Button */}
          <button
            type="submit"
            id="signup-submit-button"
            disabled={isSubmitting || usernameStatus.available === false}
            className="w-full mt-2 relative flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-indigo-600 via-indigo-500 to-indigo-600 hover:from-indigo-500 hover:to-indigo-500 shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/35 active:scale-[0.99] transition-all duration-200 disabled:opacity-70 disabled:cursor-not-allowed disabled:transform-none"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Creating account...</span>
              </>
            ) : (
              <>
                <span>Create Account</span>
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </form>

        {/* Footer */}
        <div className="mt-6 pt-6 border-t border-slate-800/80 text-center">
          <p className="text-sm text-slate-400">
            Already have an account?{' '}
            <Link
              href="/login"
              className="font-medium text-indigo-400 hover:text-indigo-300 hover:underline transition-colors"
            >
              Login
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
