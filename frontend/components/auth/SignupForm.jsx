'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { checkUsername, checkEmail, sendOtp, verifyOtp } from '@/services/api';
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
  ShieldCheck,
} from 'lucide-react';

const OTP_LENGTH = 6;
const RESEND_COOLDOWN_SECONDS = 60;

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

  // Email availability & validation state
  const [emailStatus, setEmailStatus] = useState({
    checking: false,
    available: null,
    message: '',
  });

  // --- Email OTP verification state ---
  // otpStep: 'idle' -> not started, 'sending' -> request in flight,
  // 'sent' -> code sent, awaiting entry, 'verifying' -> checking code,
  // 'verified' -> done
  const [otpStep, setOtpStep] = useState('idle');
  const [otpDigits, setOtpDigits] = useState(Array(OTP_LENGTH).fill(''));
  const [otpError, setOtpError] = useState('');
  const [verificationToken, setVerificationToken] = useState(null);
  const [resendCooldown, setResendCooldown] = useState(0);
  const otpInputRefs = useRef([]);

  const debouncedUsername = useDebounce(formData.username.trim(), 400);
  const debouncedEmail = useDebounce(formData.email.trim(), 400);

  // Debounced username availability check
  useEffect(() => {
    const checkAvailability = async () => {
      const username = debouncedUsername.toLowerCase();
      if (!username || username.length < 3) {
        setUsernameStatus({ checking: false, available: null, message: '' });
        return;
      }

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

  // Debounced email format and availability check
  useEffect(() => {
    const checkEmailAvailability = async () => {
      const email = debouncedEmail.toLowerCase();
      if (!email) {
        setEmailStatus({ checking: false, available: null, message: '' });
        return;
      }

      if (/\s/.test(email)) {
        setEmailStatus({
          checking: false,
          available: false,
          message: 'Email address cannot contain spaces.',
        });
        return;
      }

      const EMAIL_REGEX = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
      if (!EMAIL_REGEX.test(email)) {
        setEmailStatus({
          checking: false,
          available: false,
          message: 'Please enter a valid email format (e.g. user@example.com).',
        });
        return;
      }

      setEmailStatus({ checking: true, available: null, message: 'Checking...' });

      try {
        const res = await checkEmail(email);
        setEmailStatus({
          checking: false,
          available: res.available,
          message: res.message || (res.available ? 'Email available' : 'An account with this email already exists'),
        });
      } catch (err) {
        setEmailStatus({
          checking: false,
          available: null,
          message: '',
        });
      }
    };

    checkEmailAvailability();
  }, [debouncedEmail]);

  // Resend cooldown ticker
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = setInterval(() => {
      setResendCooldown((s) => (s > 0 ? s - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [resendCooldown]);

  const isEmailVerifiable =
    !fieldErrors.email &&
    emailStatus.available === true &&
    !emailStatus.checking &&
    formData.email.trim().length > 0;

  const resetOtpState = () => {
    setOtpStep('idle');
    setOtpDigits(Array(OTP_LENGTH).fill(''));
    setOtpError('');
    setVerificationToken(null);
    setResendCooldown(0);
  };

  const handleSendOtp = async () => {
    setOtpError('');
    setOtpStep('sending');
    try {
      await sendOtp(formData.email.trim().toLowerCase());
      setOtpStep('sent');
      setOtpDigits(Array(OTP_LENGTH).fill(''));
      setResendCooldown(RESEND_COOLDOWN_SECONDS);
      // Focus first OTP box once it renders
      setTimeout(() => otpInputRefs.current[0]?.focus(), 50);
    } catch (err) {
      setOtpStep('idle');
      setOtpError(
        err?.response?.data?.detail || 'Could not send verification code. Please try again.'
      );
    }
  };

  const handleResendOtp = async () => {
    if (resendCooldown > 0) return;
    setOtpError('');
    try {
      await sendOtp(formData.email.trim().toLowerCase());
      setOtpDigits(Array(OTP_LENGTH).fill(''));
      setResendCooldown(RESEND_COOLDOWN_SECONDS);
      setTimeout(() => otpInputRefs.current[0]?.focus(), 50);
    } catch (err) {
      setOtpError(
        err?.response?.data?.detail || 'Could not resend code. Please try again.'
      );
    }
  };

  const handleOtpDigitChange = (index, rawValue) => {
    const value = rawValue.replace(/[^0-9]/g, '');
    if (!value) {
      const next = [...otpDigits];
      next[index] = '';
      setOtpDigits(next);
      return;
    }

    // Handle paste of full code into one box
    if (value.length > 1) {
      const chars = value.slice(0, OTP_LENGTH).split('');
      const next = Array(OTP_LENGTH).fill('');
      chars.forEach((c, i) => {
        if (index + i < OTP_LENGTH) next[index + i] = c;
      });
      setOtpDigits(next);
      const lastFilled = Math.min(index + chars.length, OTP_LENGTH - 1);
      otpInputRefs.current[lastFilled]?.focus();
      return;
    }

    const next = [...otpDigits];
    next[index] = value;
    setOtpDigits(next);
    if (index < OTP_LENGTH - 1) {
      otpInputRefs.current[index + 1]?.focus();
    }
  };

  const handleOtpKeyDown = (index, e) => {
    if (e.key === 'Backspace' && !otpDigits[index] && index > 0) {
      otpInputRefs.current[index - 1]?.focus();
    }
  };

  const handleVerifyOtp = async () => {
    const code = otpDigits.join('');
    if (code.length !== OTP_LENGTH) {
      setOtpError(`Please enter the ${OTP_LENGTH}-digit code.`);
      return;
    }

    setOtpError('');
    setOtpStep('verifying');

    try {
      const res = await verifyOtp(formData.email.trim().toLowerCase(), code);
      setVerificationToken(res.verification_token);
      setOtpStep('verified');
    } catch (err) {
      setOtpStep('sent');
      setOtpError(err?.response?.data?.detail || 'Incorrect code. Please try again.');
    }
  };

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
    } else if (/\s/.test(formData.email)) {
      errors.email = 'Email address cannot contain spaces.';
    } else if (!/^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(formData.email.trim())) {
      errors.email = 'Please enter a valid email address.';
    } else if (emailStatus.available === false) {
      errors.email = emailStatus.message || 'An account with this email already exists.';
    } else if (otpStep !== 'verified' || !verificationToken) {
      errors.email = 'Please verify your email address to continue.';
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

    // Editing the email after it was sent/verified invalidates the old code/token
    if (name === 'email') {
      resetOtpState();
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
      email_verification_token: verificationToken,
    };

    const result = await signup(payload);

    if (result.success) {
      router.push('/login?registered=true');
    } else {
      const errorMsg = result.error || 'Failed to create account. Please try again.';
      if (errorMsg.toLowerCase().includes('username')) {
        setFieldErrors((prev) => ({ ...prev, username: errorMsg }));
      } else if (errorMsg.toLowerCase().includes('verif')) {
        // Verification token expired/invalid server-side — send them back through OTP
        resetOtpState();
        setFieldErrors((prev) => ({ ...prev, email: errorMsg }));
      } else if (errorMsg.toLowerCase().includes('email')) {
        setFieldErrors((prev) => ({ ...prev, email: errorMsg }));
      } else {
        setGeneralError(errorMsg);
      }
      setIsSubmitting(false);
    }
  };

  const canSubmit =
    !isSubmitting &&
    usernameStatus.available !== false &&
    emailStatus.available !== false &&
    otpStep === 'verified';

  return (
    <div className="w-full max-w-lg mx-auto relative z-10">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center h-12 w-12 rounded-2xl bg-accent/10 border border-accent/30 text-accent mb-4 shadow-[0_0_30px_rgba(255,143,50,0.25)]">
          <Sparkles className="h-6 w-6 text-accent" />
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
          Create Your CareerSphere Account
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Join the next-generation AI platform for career growth and professional networking
        </p>
      </div>

      <div className="glass-card rounded-3xl p-6 sm:p-8 shadow-2xl border border-white/10 bg-slate-950/70 backdrop-blur-2xl">
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
                className={`block w-full rounded-xl bg-slate-950/80 border px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 transition-all duration-200 focus:outline-none focus:ring-2 ${
                  fieldErrors.first_name
                    ? 'border-rose-500/80 focus:border-rose-500 focus:ring-rose-500/30'
                    : 'border-white/10 hover:border-white/20 focus:border-accent/80 focus:ring-accent/30'
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
                className={`block w-full rounded-xl bg-slate-950/80 border px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 transition-all duration-200 focus:outline-none focus:ring-2 ${
                  fieldErrors.last_name
                    ? 'border-rose-500/80 focus:border-rose-500 focus:ring-rose-500/30'
                    : 'border-white/10 hover:border-white/20 focus:border-accent/80 focus:ring-accent/30'
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
                <span className="text-xs text-accent flex items-center gap-1">
                  <Loader2 className="h-3 w-3 animate-spin text-accent" /> Checking...
                </span>
              )}
              {!usernameStatus.checking && usernameStatus.available === true && (
                <span className="text-xs text-emerald-400 flex items-center gap-1 font-medium">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Username available
                </span>
              )}
              {!usernameStatus.checking && usernameStatus.available === false && (
                <span className="text-xs text-rose-400 flex items-center gap-1 font-medium">
                  <XCircle className="h-3.5 w-3.5" /> {usernameStatus.message}
                </span>
              )}
            </div>

            <div className="relative rounded-xl shadow-sm">
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
                aria-invalid={fieldErrors.username || usernameStatus.available === false ? 'true' : 'false'}
                aria-describedby={fieldErrors.username ? 'username-error' : undefined}
                className={`block w-full rounded-xl bg-slate-950/80 border pl-10 pr-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 transition-all duration-200 focus:outline-none focus:ring-2 ${
                  fieldErrors.username || usernameStatus.available === false
                    ? 'border-rose-500/80 focus:border-rose-500 focus:ring-rose-500/30'
                    : usernameStatus.available === true
                    ? 'border-emerald-500/80 focus:border-emerald-500 focus:ring-emerald-500/30'
                    : 'border-white/10 hover:border-white/20 focus:border-accent/80 focus:ring-accent/30'
                } ${isSubmitting ? 'opacity-60 cursor-not-allowed' : ''}`}
              />
            </div>
            {fieldErrors.username && (
              <p id="username-error" className="text-xs text-rose-400 font-medium">
                {fieldErrors.username}
              </p>
            )}
          </div>

          {/* Email ID with Live Availability & Format Check */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label htmlFor="email" className="block text-sm font-medium text-slate-200">
                Email ID <span className="text-rose-400">*</span>
              </label>
              {/* Live status badge (only shown before OTP flow starts) */}
              {otpStep === 'idle' && emailStatus.checking && (
                <span className="text-xs text-accent flex items-center gap-1">
                  <Loader2 className="h-3 w-3 animate-spin text-accent" /> Checking...
                </span>
              )}
              {otpStep === 'idle' && !emailStatus.checking && emailStatus.available === true && (
                <span className="text-xs text-emerald-400 flex items-center gap-1 font-medium">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Email available
                </span>
              )}
              {otpStep === 'idle' && !emailStatus.checking && emailStatus.available === false && (
                <span className="text-xs text-rose-400 flex items-center gap-1 font-medium">
                  <XCircle className="h-3.5 w-3.5" /> {emailStatus.message}
                </span>
              )}
              {otpStep === 'verified' && (
                <span className="text-xs text-emerald-400 flex items-center gap-1 font-medium">
                  <ShieldCheck className="h-3.5 w-3.5" /> Email verified
                </span>
              )}
            </div>

            <div className="flex gap-2">
              <div className="relative rounded-xl shadow-sm flex-1">
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
                  disabled={isSubmitting || otpStep === 'sent' || otpStep === 'verifying'}
                  autoComplete="email"
                  aria-invalid={fieldErrors.email || emailStatus.available === false ? 'true' : 'false'}
                  aria-describedby={fieldErrors.email ? 'email-error' : undefined}
                  className={`block w-full rounded-xl bg-slate-950/80 border pl-10 pr-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 transition-all duration-200 focus:outline-none focus:ring-2 ${
                    fieldErrors.email || emailStatus.available === false
                      ? 'border-rose-500/80 focus:border-rose-500 focus:ring-rose-500/30'
                      : emailStatus.available === true || otpStep === 'verified'
                      ? 'border-emerald-500/80 focus:border-emerald-500 focus:ring-emerald-500/30'
                      : 'border-white/10 hover:border-white/20 focus:border-accent/80 focus:ring-accent/30'
                  } ${isSubmitting || otpStep === 'sent' || otpStep === 'verifying' ? 'opacity-60 cursor-not-allowed' : ''}`}
                />
              </div>

              {/* Verify / re-verify trigger, sits beside the input */}
              {otpStep !== 'verified' && (
                <button
                  type="button"
                  onClick={handleSendOtp}
                  disabled={!isEmailVerifiable || otpStep === 'sending' || otpStep === 'sent' || otpStep === 'verifying'}
                  className="shrink-0 rounded-xl px-4 text-sm font-medium border border-accent/30 bg-accent/10 text-accent hover:bg-accent/20 transition-colors duration-200 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {otpStep === 'sending' ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : otpStep === 'sent' || otpStep === 'verifying' ? (
                    'Sent'
                  ) : (
                    'Verify'
                  )}
                </button>
              )}
            </div>
            {fieldErrors.email && (
              <p id="email-error" className="text-xs text-rose-400 font-medium">
                {fieldErrors.email}
              </p>
            )}

            {/* --- OTP entry panel --- */}
            {(otpStep === 'sent' || otpStep === 'verifying') && (
              <div className="mt-3 p-4 rounded-xl bg-slate-900/60 border border-white/10 space-y-3 animate-fade-in">
                <p className="text-xs text-slate-400">
                  We sent a {OTP_LENGTH}-digit code to{' '}
                  <span className="text-slate-200 font-medium">{formData.email.trim()}</span>.
                  Enter it below to verify your email.
                </p>

                <div className="flex items-center gap-2">
                  {otpDigits.map((digit, i) => (
                    <input
                      key={i}
                      ref={(el) => (otpInputRefs.current[i] = el)}
                      type="text"
                      inputMode="numeric"
                      maxLength={OTP_LENGTH}
                      value={digit}
                      onChange={(e) => handleOtpDigitChange(i, e.target.value)}
                      onKeyDown={(e) => handleOtpKeyDown(i, e)}
                      disabled={otpStep === 'verifying'}
                      className={`h-11 w-10 sm:w-11 text-center rounded-lg bg-slate-950/80 border text-base font-semibold text-slate-100 transition-all duration-150 focus:outline-none focus:ring-2 ${
                        otpError
                          ? 'border-rose-500/80 focus:border-rose-500 focus:ring-rose-500/30'
                          : 'border-white/10 hover:border-white/20 focus:border-accent/80 focus:ring-accent/30'
                      } ${otpStep === 'verifying' ? 'opacity-60 cursor-not-allowed' : ''}`}
                    />
                  ))}
                </div>

                {otpError && (
                  <p className="text-xs text-rose-400 font-medium">{otpError}</p>
                )}

                <div className="flex items-center justify-between pt-1">
                  <button
                    type="button"
                    onClick={handleResendOtp}
                    disabled={resendCooldown > 0}
                    className="text-xs font-medium text-accent hover:text-accentSoft disabled:text-slate-500 disabled:cursor-not-allowed transition-colors"
                  >
                    {resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : 'Resend code'}
                  </button>

                  <button
                    type="button"
                    onClick={handleVerifyOtp}
                    disabled={otpStep === 'verifying' || otpDigits.join('').length !== OTP_LENGTH}
                    className="flex items-center gap-1.5 text-sm font-semibold text-black bg-accent hover:bg-accentSoft rounded-lg px-4 py-1.5 transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {otpStep === 'verifying' ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Verifying...
                      </>
                    ) : (
                      'Confirm code'
                    )}
                  </button>
                </div>
              </div>
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
            disabled={!canSubmit}
            className="w-full mt-2 relative flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-sm font-semibold text-black bg-accent hover:bg-accentSoft shadow-[0_8px_30px_rgba(255,143,50,0.35)] hover:shadow-[0_12px_40px_rgba(255,143,50,0.45)] hover:-translate-y-0.5 active:translate-y-0 transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed disabled:transform-none"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin text-black" />
                <span>Creating account...</span>
              </>
            ) : (
              <>
                <span>Create Account</span>
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
          {otpStep !== 'verified' && (
            <p className="text-xs text-center text-slate-500">
              Verify your email above to enable account creation.
            </p>
          )}
        </form>

        {/* Footer */}
        <div className="mt-6 pt-6 border-t border-white/10 text-center">
          <p className="text-sm text-slate-400">
            Already have an account?{' '}
            <Link
              href="/login"
              className="font-medium text-accent hover:text-accentSoft hover:underline transition-colors"
            >
              Login
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}