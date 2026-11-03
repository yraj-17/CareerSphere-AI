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
  CheckCircle2,
  XCircle,
  ShieldCheck,
  Check,
  UserRoundCheck,
  MessageSquareText,
  BriefcaseBusiness,
} from 'lucide-react';

const OTP_LENGTH = 6;
const RESEND_COOLDOWN_SECONDS = 60;

/* Note: globals.css remaps `text-white`, `bg-white/*` and `border-white*` for the
   legacy light theme, so the navy panel uses explicit hex/rgba values instead. */

const PRODUCT_FEATURES = [
  {
    icon: UserRoundCheck,
    title: 'Professional Profile',
    description: 'Manage your skills, experience, projects and career goals.',
  },
  {
    icon: MessageSquareText,
    title: 'AI Interview Preparation',
    description: 'Practice interviews with AI-powered feedback.',
  },
  {
    icon: BriefcaseBusiness,
    title: 'Career Opportunities',
    description: 'Discover relevant jobs, learning resources and connections.',
  },
];

const STEPS = ['Your Information', 'Verify Email', 'Set Password'];

/* ─── Header ─── */
function SignupHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-[#E2E8F0] bg-[#FFFFFF]">
      <div className="flex h-16 items-center justify-between gap-4 px-4 sm:px-6 lg:px-10">
        <Link href="/" className="flex min-w-0 items-center gap-2.5 rounded-lg" aria-label="CareerSphere AI home">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#1D263B] text-[11px] font-bold tracking-tight text-[#FFFFFF]">CS</span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold text-[#172033]">CareerSphere AI</span>
            <span className="hidden text-[10px] font-medium uppercase tracking-[0.18em] text-[#64748B] min-[400px]:block">AI Career Ecosystem</span>
          </span>
        </Link>
        <p className="shrink-0 text-xs text-[#64748B] sm:text-sm">
          <span className="hidden sm:inline">Already have an account? </span>
          <Link href="/login" className="font-semibold text-[#1D263B] underline-offset-4 hover:underline">Sign in</Link>
        </p>
      </div>
    </header>
  );
}

/* ─── Product introduction ─── */
/* Sticky (desktop, tall-enough viewports only) keeps this content-height card beside
   the taller form while the page scrolls. It is not a scroll container: no fixed
   height, no overflow. top-[88px] = 64px header + 24px gap; the card is ~542px tall (~490px
   on short viewports), so sticky only applies when the viewport is at least 600px tall. */
function ProductIntro() {
  return (
    <aside className="h-fit self-start rounded-2xl bg-[#1D263B] p-6 sm:p-8 lg:top-[88px] lg:[@media(min-height:600px)]:sticky lg:[@media(max-height:719px)]:p-6">
      <div className="max-w-[620px]">
        <div>
          <p className="text-xs font-semibold text-[#FFFFFF]">
            CareerSphere AI
            <span className="ml-2 border-l border-[rgba(255,255,255,0.2)] pl-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#D9BD75]">Your career, connected.</span>
          </p>
          <h2 className="mt-3 text-[1.75rem] font-semibold leading-[1.15] tracking-[-0.02em] text-[#FFFFFF] sm:text-[2rem] xl:text-[2.25rem]">
            Build your next career move with <span className="text-[#D9BD75]">confidence.</span>
          </h2>
          <p className="mt-3 text-sm leading-6 text-[#C3CBD9]">
            CareerSphere AI brings your professional profile, interview preparation, career opportunities, and professional networking together in one intelligent platform.
          </p>
        </div>

        <ul className="mt-6 hidden gap-5 lg:[@media(max-height:719px)]:mt-4 border-t border-[rgba(255,255,255,0.1)] pt-5 sm:grid sm:grid-cols-3 lg:grid-cols-1 lg:gap-0 lg:pt-1" aria-label="CareerSphere AI capabilities">
          {PRODUCT_FEATURES.map(({ icon: Icon, title, description }) => (
            <li key={title} className="flex flex-col gap-2.5 lg:flex-row lg:items-start lg:gap-3.5 lg:border-t lg:border-[rgba(255,255,255,0.08)] lg:py-3.5 lg:first:border-t-0 lg:[@media(max-height:719px)]:py-2.5">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[rgba(255,255,255,0.14)] text-[#D9BD75]">
                <Icon className="h-4 w-4" aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-[#FFFFFF]">{title}</p>
                <p className="mt-0.5 hidden text-[13px] leading-5 text-[#A9B4C6] lg:block">{description}</p>
              </div>
            </li>
          ))}
        </ul>

        <p className="mt-6 hidden border-t border-[rgba(255,255,255,0.1)] pt-4 text-sm text-[#8C98AE] lg:mt-1 lg:block">
          One platform. A clearer path forward.
        </p>
      </div>
    </aside>
  );
}

/* ─── Progress indicator ─── */
function StepIndicator({ currentStep }) {
  return (
    <ol className="flex items-center" aria-label="Registration progress">
      {STEPS.map((label, i) => {
        const step = i + 1;
        const isDone = currentStep > step;
        const isCurrent = currentStep === step;
        return (
          <li key={label} className={`flex items-center ${step < STEPS.length ? 'flex-1' : ''}`} aria-current={isCurrent ? 'step' : undefined}>
            <span className="flex shrink-0 items-center gap-2">
              <span className={`flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-semibold transition-colors duration-200 ${
                isDone
                  ? 'bg-[#1D263B] text-[#FFFFFF]'
                  : isCurrent
                  ? 'border-2 border-[#1D263B] bg-[#FFFFFF] text-[#1D263B]'
                  : 'border border-[#E2E8F0] bg-[#FFFFFF] text-[#94A3B8]'
              }`}>
                {isDone ? <Check className="h-3.5 w-3.5" aria-hidden="true" /> : String(step).padStart(2, '0')}
              </span>
              <span className={`text-xs font-medium ${isCurrent ? 'text-[#172033]' : isDone ? 'hidden text-[#475467] sm:inline' : 'hidden text-[#94A3B8] sm:inline'}`}>
                {label}
                {isDone && <span className="sr-only"> (completed)</span>}
              </span>
            </span>
            {step < STEPS.length && (
              <span className={`mx-3 h-px flex-1 transition-colors duration-200 ${isDone ? 'bg-[#1D263B]' : 'bg-[#E2E8F0]'}`} aria-hidden="true" />
            )}
          </li>
        );
      })}
    </ol>
  );
}

/* ─── Field error ─── */
function FieldError({ id, message }) {
  if (!message) return null;
  return (
    <p id={id} role="alert" className="mt-1.5 flex items-center gap-1 text-xs font-medium text-[#B42318]">
      <AlertCircle className="h-3.5 w-3.5 shrink-0" />
      {message}
    </p>
  );
}

/* ─── Text input wrapper ─── */
function FormInput({ id, name, type = 'text', value, onChange, placeholder, disabled, error, statusBorder, icon: Icon, autoComplete, ariaInvalid, ariaDescribedby, rightSlot }) {
  const border =
    error || statusBorder === 'error'
      ? 'border-[#F4C7C3] bg-[#FEF3F2] focus:border-[#B42318] focus:ring-[#B42318]/15'
      : statusBorder === 'success'
      ? 'border-[#ABEFC6] bg-[#FFFFFF] focus:border-[#15803D] focus:ring-[#15803D]/15'
      : 'border-[#E2E8F0] bg-[#FFFFFF] hover:border-[#CBD5E1] focus:border-[#1D263B] focus:ring-[#1D263B]/10';

  return (
    <div className="relative">
      {Icon && (
        <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-[#94A3B8]">
          <Icon className="h-4 w-4" aria-hidden="true" />
        </div>
      )}
      <input
        id={id} name={name} type={type} value={value} onChange={onChange}
        placeholder={placeholder} disabled={disabled}
        autoComplete={autoComplete} aria-invalid={ariaInvalid} aria-describedby={ariaDescribedby}
        // Password-manager/autofill extensions inject inline styles before hydration.
        suppressHydrationWarning
        className={`block w-full rounded-xl border py-2.5 text-sm text-[#172033] placeholder-[#94A3B8] transition-colors duration-150 focus:outline-none focus:ring-2 ${Icon ? 'pl-10' : 'pl-3.5'} ${rightSlot ? 'pr-28' : 'pr-3.5'} ${border} ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
      />
      {rightSlot && (
        <div className="absolute inset-y-0 right-0 flex items-center pr-1.5">{rightSlot}</div>
      )}
    </div>
  );
}

/* ─── Form section ─── */
function FormSection({ title, description, isComplete, children }) {
  return (
    <section className="border-t border-[#EEF2F6] py-5 first:border-t-0 first:pt-0">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-[#172033]">{title}</h2>
          <p className="mt-0.5 text-xs text-[#64748B]">{description}</p>
        </div>
        {isComplete && (
          <span className="flex shrink-0 items-center gap-1 rounded-full border border-[#ABEFC6] bg-[#ECFDF3] px-2.5 py-0.5 text-[11px] font-semibold text-[#15803D]">
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" /> Verified
          </span>
        )}
      </div>
      {children}
    </section>
  );
}

const labelClass = 'block text-sm font-medium text-[#172033]';
const requiredMark = <span className="text-[#B42318]">*</span>;

/* ══════════════════════════════════════════════════
   MAIN COMPONENT
══════════════════════════════════════════════════ */
export default function SignupForm() {
  const router = useRouter();
  const { signup } = useAuth();

  const [formData, setFormData] = useState({ first_name: '', last_name: '', username: '', email: '', password: '', confirm_password: '' });
  const [fieldErrors, setFieldErrors] = useState({});
  const [generalError, setGeneralError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [usernameStatus, setUsernameStatus] = useState({ checking: false, available: null, message: '' });
  const [emailStatus, setEmailStatus] = useState({ checking: false, available: null, message: '' });

  const [otpStep, setOtpStep] = useState('idle');
  const [otpDigits, setOtpDigits] = useState(Array(OTP_LENGTH).fill(''));
  const [otpError, setOtpError] = useState('');
  const [verificationToken, setVerificationToken] = useState(null);
  const [resendCooldown, setResendCooldown] = useState(0);
  const otpInputRefs = useRef([]);

  const debouncedUsername = useDebounce(formData.username.trim(), 400);
  const debouncedEmail = useDebounce(formData.email.trim(), 400);

  const visualStep = otpStep === 'verified' ? 3 : otpStep !== 'idle' ? 2 : 1;

  useEffect(() => {
    const check = async () => {
      const u = debouncedUsername.toLowerCase();
      if (!u || u.length < 3) { setUsernameStatus({ checking: false, available: null, message: '' }); return; }
      if (/\s/.test(u)) { setUsernameStatus({ checking: false, available: false, message: 'No spaces allowed.' }); return; }
      if (!/^[a-zA-Z0-9_.]+$/.test(u)) { setUsernameStatus({ checking: false, available: false, message: 'Letters, numbers, _ and . only.' }); return; }
      setUsernameStatus({ checking: true, available: null, message: '' });
      try {
        const res = await checkUsername(u);
        setUsernameStatus({ checking: false, available: res.available, message: res.message || (res.available ? 'Username available' : 'Already taken') });
      } catch { setUsernameStatus({ checking: false, available: null, message: '' }); }
    };
    check();
  }, [debouncedUsername]);

  useEffect(() => {
    const check = async () => {
      const e = debouncedEmail.toLowerCase();
      if (!e) { setEmailStatus({ checking: false, available: null, message: '' }); return; }
      if (/\s/.test(e)) { setEmailStatus({ checking: false, available: false, message: 'No spaces allowed.' }); return; }
      if (!/^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(e)) { setEmailStatus({ checking: false, available: false, message: 'Invalid email format.' }); return; }
      setEmailStatus({ checking: true, available: null, message: '' });
      try {
        const res = await checkEmail(e);
        setEmailStatus({ checking: false, available: res.available, message: res.message || (res.available ? 'Email available' : 'Account already exists') });
      } catch { setEmailStatus({ checking: false, available: null, message: '' }); }
    };
    check();
  }, [debouncedEmail]);

  useEffect(() => {
    if (resendCooldown <= 0) return;
    const t = setInterval(() => setResendCooldown(s => s > 0 ? s - 1 : 0), 1000);
    return () => clearInterval(t);
  }, [resendCooldown]);

  const isEmailVerifiable = !fieldErrors.email && emailStatus.available === true && !emailStatus.checking && formData.email.trim().length > 0;

  const resetOtp = () => { setOtpStep('idle'); setOtpDigits(Array(OTP_LENGTH).fill('')); setOtpError(''); setVerificationToken(null); setResendCooldown(0); };

  const handleSendOtp = async () => {
    setOtpError(''); setOtpStep('sending');
    try {
      await sendOtp(formData.email.trim().toLowerCase());
      setOtpStep('sent'); setOtpDigits(Array(OTP_LENGTH).fill('')); setResendCooldown(RESEND_COOLDOWN_SECONDS);
      setTimeout(() => otpInputRefs.current[0]?.focus(), 50);
    } catch (err) { setOtpStep('idle'); setOtpError(err?.response?.data?.detail || 'Could not send code. Please try again.'); }
  };

  const handleResendOtp = async () => {
    if (resendCooldown > 0) return;
    setOtpError('');
    try {
      await sendOtp(formData.email.trim().toLowerCase());
      setOtpDigits(Array(OTP_LENGTH).fill('')); setResendCooldown(RESEND_COOLDOWN_SECONDS);
      setTimeout(() => otpInputRefs.current[0]?.focus(), 50);
    } catch (err) { setOtpError(err?.response?.data?.detail || 'Could not resend code.'); }
  };

  const handleOtpChange = (i, raw) => {
    const v = raw.replace(/[^0-9]/g, '');
    if (!v) { const n = [...otpDigits]; n[i] = ''; setOtpDigits(n); return; }
    if (v.length > 1) {
      const chars = v.slice(0, OTP_LENGTH).split('');
      const n = Array(OTP_LENGTH).fill('');
      chars.forEach((c, j) => { if (i + j < OTP_LENGTH) n[i + j] = c; });
      setOtpDigits(n);
      otpInputRefs.current[Math.min(i + chars.length, OTP_LENGTH - 1)]?.focus();
      return;
    }
    const n = [...otpDigits]; n[i] = v; setOtpDigits(n);
    if (i < OTP_LENGTH - 1) otpInputRefs.current[i + 1]?.focus();
  };

  const handleOtpKey = (i, e) => { if (e.key === 'Backspace' && !otpDigits[i] && i > 0) otpInputRefs.current[i - 1]?.focus(); };

  const handleVerifyOtp = async () => {
    const code = otpDigits.join('');
    if (code.length !== OTP_LENGTH) { setOtpError(`Enter the ${OTP_LENGTH}-digit code.`); return; }
    setOtpError(''); setOtpStep('verifying');
    try {
      const res = await verifyOtp(formData.email.trim().toLowerCase(), code);
      setVerificationToken(res.verification_token); setOtpStep('verified');
    } catch (err) { setOtpStep('sent'); setOtpError(err?.response?.data?.detail || 'Incorrect code.'); }
  };

  const validate = () => {
    const e = {};
    if (!formData.first_name.trim()) e.first_name = 'First name is required.';
    if (!formData.last_name.trim()) e.last_name = 'Last name is required.';
    if (!formData.username.trim()) e.username = 'Username is required.';
    else if (formData.username.trim().length < 3) e.username = 'At least 3 characters.';
    else if (formData.username.trim().length > 30) e.username = 'Max 30 characters.';
    else if (/\s/.test(formData.username)) e.username = 'No spaces allowed.';
    else if (!/^[a-zA-Z0-9_.]+$/.test(formData.username.trim())) e.username = 'Letters, numbers, _ and . only.';
    else if (usernameStatus.available === false) e.username = usernameStatus.message || 'Username taken.';
    if (!formData.email.trim()) e.email = 'Email is required.';
    else if (!/^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(formData.email.trim())) e.email = 'Invalid email.';
    else if (emailStatus.available === false) e.email = emailStatus.message || 'Email already used.';
    else if (otpStep !== 'verified' || !verificationToken) e.email = 'Please verify your email first.';
    const p = formData.password;
    if (!p) e.password = 'Password is required.';
    else if (p.length < 8) e.password = 'At least 8 characters.';
    else if (!/[A-Z]/.test(p)) e.password = 'Add an uppercase letter.';
    else if (!/[a-z]/.test(p)) e.password = 'Add a lowercase letter.';
    else if (!/[0-9]/.test(p)) e.password = 'Add a number.';
    if (!formData.confirm_password) e.confirm_password = 'Please confirm your password.';
    else if (formData.confirm_password !== formData.password) e.confirm_password = "Passwords don't match.";
    setFieldErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleChange = (ev) => {
    const { name, value } = ev.target;
    setFormData(p => ({ ...p, [name]: value }));
    if (fieldErrors[name]) setFieldErrors(p => ({ ...p, [name]: '' }));
    if (generalError) setGeneralError('');
    if (name === 'email') resetOtp();
    if (name === 'confirm_password') {
      if (formData.password && value !== formData.password) setFieldErrors(p => ({ ...p, confirm_password: "Passwords don't match." }));
      else setFieldErrors(p => ({ ...p, confirm_password: '' }));
    }
  };

  const handleSubmit = async (ev) => {
    ev.preventDefault(); setGeneralError('');
    if (!validate()) return;
    setIsSubmitting(true);
    const payload = { first_name: formData.first_name.trim(), last_name: formData.last_name.trim(), username: formData.username.trim().toLowerCase(), email: formData.email.trim().toLowerCase(), password: formData.password, email_verification_token: verificationToken };
    const result = await signup(payload);
    if (result.success) { router.push('/login?registered=true'); }
    else {
      const msg = result.error || 'Failed to create account.';
      if (msg.toLowerCase().includes('username')) setFieldErrors(p => ({ ...p, username: msg }));
      else if (msg.toLowerCase().includes('verif')) { resetOtp(); setFieldErrors(p => ({ ...p, email: msg })); }
      else if (msg.toLowerCase().includes('email')) setFieldErrors(p => ({ ...p, email: msg }));
      else setGeneralError(msg);
      setIsSubmitting(false);
    }
  };

  const canSubmit = !isSubmitting && usernameStatus.available !== false && emailStatus.available !== false && otpStep === 'verified';

  const uBorder = fieldErrors.username || usernameStatus.available === false ? 'error' : usernameStatus.available === true ? 'success' : 'default';
  const eBorder = fieldErrors.email || emailStatus.available === false ? 'error' : emailStatus.available === true || otpStep === 'verified' ? 'success' : 'default';

  return (
    <div className="signup-page flex min-h-[100dvh] w-full flex-col bg-[#F7F8FA] text-[#172033]">
      <SignupHeader />

      {/* items-start: columns size to their own content instead of stretching to the row height. */}
      <div className="mx-auto grid w-full max-w-[1280px] content-start items-start gap-5 px-4 py-5 sm:gap-6 sm:px-6 sm:py-8 lg:grid-cols-[minmax(0,40fr)_minmax(0,60fr)] lg:gap-8 lg:px-10 lg:py-10">
        <ProductIntro />

        <section className="min-w-0">
          <div className="w-full">
            <div className="rounded-2xl border border-[#E2E8F0] bg-[#FFFFFF] p-5 shadow-[0_1px_2px_rgba(16,24,40,0.04),0_8px_24px_rgba(16,24,40,0.04)] sm:p-7">
              <div className="mb-5">
                <h1 className="text-2xl font-semibold tracking-[-0.02em] text-[#172033] sm:text-[1.65rem]">Create your CareerSphere account</h1>
                <p className="mt-1 text-sm text-[#64748B]">Start building your professional future.</p>
              </div>

              <div className="mb-5 border-b border-[#EEF2F6] pb-5">
                <StepIndicator currentStep={visualStep} />
              </div>

              {generalError && (
                <div className="mb-6 flex items-start gap-2.5 rounded-xl border border-[#F4C7C3] bg-[#FEF3F2] p-3.5" role="alert">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-[#B42318]" />
                  <p className="text-sm font-medium text-[#B42318]">{generalError}</p>
                </div>
              )}

              <form onSubmit={handleSubmit} noValidate>
                <FormSection title="Personal information" description="Tell us a little about yourself.">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <label htmlFor="first_name" className={labelClass}>First name {requiredMark}</label>
                      <FormInput id="first_name" name="first_name" value={formData.first_name} onChange={handleChange} placeholder="Your first name" disabled={isSubmitting} error={fieldErrors.first_name} autoComplete="given-name" ariaInvalid={fieldErrors.first_name ? 'true' : 'false'} ariaDescribedby="first_name-error" />
                      <FieldError id="first_name-error" message={fieldErrors.first_name} />
                    </div>
                    <div className="space-y-1.5">
                      <label htmlFor="last_name" className={labelClass}>Last name {requiredMark}</label>
                      <FormInput id="last_name" name="last_name" value={formData.last_name} onChange={handleChange} placeholder="Your last name" disabled={isSubmitting} error={fieldErrors.last_name} autoComplete="family-name" ariaInvalid={fieldErrors.last_name ? 'true' : 'false'} ariaDescribedby="last_name-error" />
                      <FieldError id="last_name-error" message={fieldErrors.last_name} />
                    </div>
                  </div>

                  <div className="mt-3 space-y-1.5">
                    <div className="flex items-center justify-between gap-3">
                      <label htmlFor="username" className={labelClass}>Username {requiredMark}</label>
                      {usernameStatus.checking && <span className="flex items-center gap-1 text-xs text-[#64748B]"><Loader2 className="h-3 w-3 animate-spin" /> Checking…</span>}
                      {!usernameStatus.checking && usernameStatus.available === true && <span className="flex items-center gap-1 text-xs font-medium text-[#15803D]"><CheckCircle2 className="h-3.5 w-3.5" /> Available</span>}
                      {!usernameStatus.checking && usernameStatus.available === false && <span className="flex items-center gap-1 text-xs font-medium text-[#B42318]"><XCircle className="h-3.5 w-3.5" /> Taken</span>}
                    </div>
                    <FormInput id="username" name="username" value={formData.username} onChange={handleChange} placeholder="Choose a username" disabled={isSubmitting} error={fieldErrors.username} statusBorder={uBorder} icon={User} autoComplete="username" ariaInvalid={fieldErrors.username || usernameStatus.available === false ? 'true' : 'false'} ariaDescribedby="username-error username-hint" />
                    <FieldError id="username-error" message={fieldErrors.username} />
                    <p id="username-hint" className="text-xs text-[#64748B]">Letters, numbers, underscores (_) and periods (.) · 3–30 characters</p>
                  </div>
                </FormSection>

                <FormSection title="Email verification" description="We’ll send a 6-digit code to confirm your address." isComplete={otpStep === 'verified'}>
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between gap-3">
                      <label htmlFor="email" className={labelClass}>Email address {requiredMark}</label>
                      {otpStep === 'idle' && emailStatus.checking && <span className="flex items-center gap-1 text-xs text-[#64748B]"><Loader2 className="h-3 w-3 animate-spin" /> Checking…</span>}
                      {otpStep === 'idle' && !emailStatus.checking && emailStatus.available === true && <span className="flex items-center gap-1 text-xs font-medium text-[#15803D]"><CheckCircle2 className="h-3.5 w-3.5" /> Available</span>}
                      {otpStep === 'idle' && !emailStatus.checking && emailStatus.available === false && <span className="flex items-center gap-1 text-xs font-medium text-[#B42318]"><XCircle className="h-3.5 w-3.5" /> Registered</span>}
                    </div>
                    <FormInput id="email" name="email" type="email" value={formData.email} onChange={handleChange} placeholder="you@example.com" disabled={isSubmitting || otpStep === 'sent' || otpStep === 'verifying' || otpStep === 'verified'} error={fieldErrors.email} statusBorder={eBorder} icon={Mail} autoComplete="email" ariaInvalid={fieldErrors.email || emailStatus.available === false ? 'true' : 'false'} ariaDescribedby="email-error" rightSlot={otpStep !== 'verified' ? (
                      <button type="button" onClick={handleSendOtp} disabled={!isEmailVerifiable || otpStep === 'sending' || otpStep === 'sent' || otpStep === 'verifying'} className="flex h-8 min-w-[96px] shrink-0 items-center justify-center rounded-lg bg-[#1D263B] px-3 text-xs font-semibold text-[#FFFFFF] transition-colors hover:bg-[#141B2B] disabled:cursor-not-allowed disabled:opacity-40">{otpStep === 'sending' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : otpStep === 'sent' || otpStep === 'verifying' ? 'Code sent' : 'Verify email'}</button>
                    ) : null} />
                    <FieldError id="email-error" message={fieldErrors.email} />
                  </div>

                  {/* Send errors surface here when the OTP panel is not open. */}
                  {otpStep === 'idle' && otpError && (
                    <p className="mt-2 flex items-center gap-1 text-xs font-medium text-[#B42318]" role="alert"><AlertCircle className="h-3.5 w-3.5" /> {otpError}</p>
                  )}

                  {(otpStep === 'sent' || otpStep === 'verifying') && (
                    <div className="mt-4 space-y-4 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] p-4">
                      <div>
                        <p className="text-sm font-semibold text-[#172033]">Check your inbox</p>
                        <p className="mt-0.5 text-xs text-[#64748B]">Enter the code sent to <span className="font-semibold text-[#172033]">{formData.email.trim()}</span></p>
                      </div>
                      <div className="flex items-center justify-center gap-2">
                        {otpDigits.map((digit, i) => (
                          <input key={i} ref={el => (otpInputRefs.current[i] = el)} type="text" inputMode="numeric" maxLength={OTP_LENGTH} value={digit} onChange={e => handleOtpChange(i, e.target.value)} onKeyDown={e => handleOtpKey(i, e)} disabled={otpStep === 'verifying'} aria-label={`Verification digit ${i + 1}`} className={`h-12 w-10 rounded-lg border bg-[#FFFFFF] text-center text-lg font-semibold text-[#172033] transition-colors duration-150 focus:outline-none focus:ring-2 sm:w-12 ${otpError ? 'border-[#F4C7C3] focus:border-[#B42318] focus:ring-[#B42318]/15' : digit ? 'border-[#1D263B] focus:border-[#1D263B] focus:ring-[#1D263B]/10' : 'border-[#CBD5E1] focus:border-[#1D263B] focus:ring-[#1D263B]/10'} ${otpStep === 'verifying' ? 'cursor-not-allowed opacity-50' : ''}`} />
                        ))}
                      </div>
                      {otpError && <p className="flex items-center justify-center gap-1 text-center text-xs font-medium text-[#B42318]" role="alert"><AlertCircle className="h-3.5 w-3.5" /> {otpError}</p>}
                      <div className="flex items-center justify-between gap-3">
                        <button type="button" onClick={handleResendOtp} disabled={resendCooldown > 0} className="text-xs font-semibold text-[#1D263B] underline-offset-4 hover:underline disabled:cursor-not-allowed disabled:text-[#94A3B8] disabled:no-underline">{resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : 'Resend code'}</button>
                        <button type="button" onClick={handleVerifyOtp} disabled={otpStep === 'verifying' || otpDigits.join('').length !== OTP_LENGTH} className="flex h-9 items-center gap-1.5 rounded-lg bg-[#1D263B] px-4 text-xs font-semibold text-[#FFFFFF] transition-colors hover:bg-[#141B2B] disabled:cursor-not-allowed disabled:opacity-40">{otpStep === 'verifying' ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Verifying…</> : 'Confirm code'}</button>
                      </div>
                    </div>
                  )}

                  {otpStep === 'verified' && (
                    <div className="mt-3 flex items-center gap-2.5 rounded-xl border border-[#ABEFC6] bg-[#ECFDF3] px-3.5 py-3">
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-[#15803D]" aria-hidden="true" />
                      <p className="min-w-0 text-sm text-[#15803D]"><span className="font-semibold">Email verified</span><span className="text-[#475467]"> · {formData.email.trim()}</span></p>
                    </div>
                  )}
                </FormSection>

                <FormSection title="Account security" description="Choose a strong password for your account.">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <PasswordInput id="password" name="password" label="Password" value={formData.password} onChange={handleChange} placeholder="Create a strong password" required disabled={isSubmitting} error={fieldErrors.password} autoComplete="new-password" />
                    <PasswordInput id="confirm_password" name="confirm_password" label="Confirm password" value={formData.confirm_password} onChange={handleChange} placeholder="Re-enter your password" required disabled={isSubmitting} error={fieldErrors.confirm_password} autoComplete="new-password" />
                  </div>
                  <div className="mt-3">
                    <PasswordRules password={formData.password} />
                  </div>
                  {formData.confirm_password && !fieldErrors.confirm_password && formData.confirm_password === formData.password && (
                    <p className="mt-2 flex items-center gap-1 text-xs font-medium text-[#15803D]"><CheckCircle2 className="h-3.5 w-3.5" /> Passwords match</p>
                  )}
                </FormSection>

                <div className="border-t border-[#EEF2F6] pt-5">
                  <button type="submit" id="signup-submit-button" disabled={!canSubmit} className="flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#1D263B] px-4 text-sm font-semibold text-[#FFFFFF] transition-colors duration-150 hover:bg-[#141B2B] focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-45">
                    {isSubmitting ? <><Loader2 className="h-4 w-4 animate-spin" /> Creating your account…</> : <>Create my account <ArrowRight className="h-4 w-4" /></>}
                  </button>
                  {!canSubmit && !isSubmitting && <p className="mt-3 text-center text-xs text-[#64748B]">{otpStep !== 'verified' ? 'Verify your email to enable account creation.' : 'Complete all required fields to continue.'}</p>}
                </div>
              </form>
            </div>

            <p className="mx-auto mt-4 max-w-lg text-center text-xs leading-relaxed text-[#64748B]">By creating an account you agree to our <span className="font-medium text-[#172033]">Terms of Service</span> and <span className="font-medium text-[#172033]">Privacy Policy</span>.</p>
          </div>
        </section>
      </div>
    </div>
  );
}
