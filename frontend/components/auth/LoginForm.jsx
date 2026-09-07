'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import PasswordInput from './PasswordInput';
import { User, ArrowRight, AlertCircle, Loader2, Sparkles, CheckCircle2 } from 'lucide-react';

export default function LoginForm({ searchParams = {} }) {
  const router = useRouter();
  const { login } = useAuth();

  const [formData, setFormData] = useState({
    identifier: '',
    password: '',
  });

  const [fieldErrors, setFieldErrors] = useState({});
  const [generalError, setGeneralError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [successNotice, setSuccessNotice] = useState(
    searchParams?.registered ? 'Account created successfully. Please login to continue.' : ''
  );

  const validateForm = () => {
    const errors = {};
    if (!formData.identifier.trim()) {
      errors.identifier = 'Username or email is required.';
    }
    if (!formData.password) {
      errors.password = 'Password is required.';
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
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setGeneralError('');
    setSuccessNotice('');

    if (!validateForm()) {
      return;
    }

    setIsLoading(true);

    const result = await login(formData.identifier, formData.password);

    if (result.success) {
      router.push('/dashboard');
    } else {
      setGeneralError(result.error || 'Invalid username/email or password.');
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md mx-auto relative z-10">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center h-12 w-12 rounded-2xl bg-accent/10 border border-accent/30 text-accent mb-4 shadow-[0_0_30px_rgba(255,143,50,0.25)]">
          <Sparkles className="h-6 w-6 text-accent" />
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
          Welcome Back
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Sign in to access your CareerSphere AI dashboard
        </p>
      </div>

      <div className="glass-card rounded-3xl p-6 sm:p-8 shadow-2xl border border-white/10 bg-slate-950/70 backdrop-blur-2xl">
        {/* Success Banner */}
        {successNotice && (
          <div className="mb-6 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-start gap-3 text-emerald-300 text-sm animate-fade-in">
            <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">{successNotice}</p>
            </div>
          </div>
        )}

        {/* General Error Banner */}
        {generalError && (
          <div className="mb-6 p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-start gap-3 text-rose-300 text-sm animate-fade-in" role="alert">
            <AlertCircle className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">{generalError}</p>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate className="space-y-5">
          {/* Username or Email Input */}
          <div className="space-y-1.5">
            <label htmlFor="identifier" className="block text-sm font-medium text-slate-200">
              Username or Email <span className="text-rose-400">*</span>
            </label>
            <div className="relative rounded-xl shadow-sm">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-slate-400">
                <User className="h-4 w-4" aria-hidden="true" />
              </div>
              <input
                id="identifier"
                name="identifier"
                type="text"
                value={formData.identifier}
                onChange={handleChange}
                placeholder="raj_yadav or raj@example.com"
                required
                disabled={isLoading}
                autoComplete="username"
                aria-invalid={fieldErrors.identifier ? 'true' : 'false'}
                aria-describedby={fieldErrors.identifier ? 'identifier-error' : undefined}
                className={`block w-full rounded-xl bg-slate-950/80 border pl-10 pr-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 transition-all duration-200 focus:outline-none focus:ring-2 ${
                  fieldErrors.identifier
                    ? 'border-rose-500/80 focus:border-rose-500 focus:ring-rose-500/30'
                    : 'border-white/10 hover:border-white/20 focus:border-accent/80 focus:ring-accent/30'
                } ${isLoading ? 'opacity-60 cursor-not-allowed' : ''}`}
              />
            </div>
            {fieldErrors.identifier && (
              <p id="identifier-error" className="text-xs text-rose-400 mt-1 flex items-center gap-1 font-medium">
                {fieldErrors.identifier}
              </p>
            )}
          </div>

          {/* Password Input */}
          <PasswordInput
            id="password"
            name="password"
            label="Password"
            value={formData.password}
            onChange={handleChange}
            placeholder="••••••••"
            required
            disabled={isLoading}
            error={fieldErrors.password}
            autoComplete="current-password"
          />

          {/* Forgot Password Link */}
          <div className="flex items-center justify-end text-sm">
            <button
              type="button"
              onClick={() => alert('Password reset functionality will be enabled soon.')}
              className="text-xs font-medium text-accent hover:text-accentSoft transition-colors focus:outline-none focus:underline"
            >
              Forgot Password?
            </button>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            id="login-submit-button"
            disabled={isLoading}
            className="w-full relative flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-sm font-semibold text-black bg-accent hover:bg-accentSoft shadow-[0_8px_30px_rgba(255,143,50,0.35)] hover:shadow-[0_12px_40px_rgba(255,143,50,0.45)] hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed disabled:transform-none"
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin text-black" />
                <span>Logging in...</span>
              </>
            ) : (
              <>
                <span>Login</span>
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </form>

        {/* Footer */}
        <div className="mt-6 pt-6 border-t border-white/10 text-center">
          <p className="text-sm text-slate-400">
            Don't have an account?{' '}
            <Link
              href="/signup"
              className="font-medium text-accent hover:text-accentSoft hover:underline transition-colors"
            >
              Create Account
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

