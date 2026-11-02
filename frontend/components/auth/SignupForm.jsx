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
  Sparkles,
  BriefcaseBusiness,
  TrendingUp,
  Users,
  Award,
} from 'lucide-react';

const OTP_LENGTH = 6;
const RESEND_COOLDOWN_SECONDS = 60;

/* ─── Career copilot signal card ─── */
function SignalRow({ label, value, color, icon: Icon }) {
  return (
    <div className="flex items-center gap-3">
      <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${color}`}>
        <Icon className="h-4 w-4 text-white" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-3 text-[11px]">
          <span className="text-white/60">{label}</span>
          <span className="font-semibold text-white/90">{value}%</span>
        </div>
        <div className="signup-signal-track mt-1.5 h-1.5 overflow-hidden rounded-full">
          <div className="h-full rounded-full bg-gradient-to-r from-[#C6A15B] to-[#F3D38A]" style={{ width: `${value}%` }} />
        </div>
      </div>
    </div>
  );
}

function CareerSignalCard() {
  return (
    <div className="signup-signal-card hidden max-w-md rounded-[26px] p-5 sm:block">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#C6A15B]/15 text-[#E8C97A]">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-white/50">Career copilot</p>
            <p className="mt-0.5 text-xs font-semibold text-white">Your signal is getting stronger</p>
          </div>
        </div>
        <span className="signup-live-pill rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-[#DFF8EC]">Live</span>
      </div>

      <div className="mt-6 flex items-center justify-between gap-6">
        <div>
          <p className="text-xs font-medium text-white/50">Career readiness</p>
          <p className="mt-1 text-4xl font-bold tracking-tight text-white">82<span className="ml-1 text-base font-medium text-white/35">/100</span></p>
          <p className="mt-2 flex items-center gap-1.5 text-[11px] font-medium text-[#B5E9CC]"><TrendingUp className="h-3.5 w-3.5" /> Up 18% this month</p>
        </div>
        <div className="relative flex h-24 w-24 items-center justify-center rounded-full border border-[#C6A15B]/30 bg-[#C6A15B]/10">
          <div className="absolute inset-2 rounded-full border border-[#C6A15B]/25" />
          <div className="absolute inset-5 rounded-full bg-[#C6A15B]/20 shadow-[0_0_28px_rgba(198,161,91,0.32)]" />
          <Sparkles className="relative h-6 w-6 text-[#E8C97A]" />
        </div>
      </div>

      <div className="mt-6 space-y-4">
        <SignalRow label="Role fit" value={91} color="bg-[#315E9B]" icon={BriefcaseBusiness} />
        <SignalRow label="Skill momentum" value={78} color="bg-[#15803D]" icon={TrendingUp} />
        <SignalRow label="Network reach" value={64} color="bg-[#7C3AED]" icon={Users} />
      </div>
    </div>
  );
}

function StepIndicator({ currentStep }) {
  return (
    <div className="mb-5 space-y-2.5">
      <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-[0.16em] text-[#98A2B3]">
        <span>Account setup</span>
        <span>Step {currentStep} of 3</span>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {[1, 2, 3].map((step) => (
          <div key={step} className={`h-1.5 rounded-full transition-colors duration-300 ${currentStep >= step ? 'bg-[#17243A]' : 'bg-[#E5EAF1]'}`} />
        ))}
      </div>
      <div className="grid grid-cols-3 text-[11px] font-semibold">
        <span className="text-[#17243A]">Your info</span>
        <span className={`text-center ${currentStep >= 2 ? 'text-[#17243A]' : 'text-[#B2BAC7]'}`}>Verify email</span>
        <span className={`text-right ${currentStep >= 3 ? 'text-[#17243A]' : 'text-[#B2BAC7]'}`}>Set password</span>
      </div>
    </div>
  );
}

/* ─── Field error ─── */
function FieldError({ id, message }) {
  if (!message) return null;
  return (
    <p id={id} role="alert" className="mt-1 text-[11px] text-[#B42318] font-medium flex items-center gap-1">
      <AlertCircle className="h-3 w-3 shrink-0" />
      {message}
    </p>
  );
}

/* ─── Text input wrapper ─── */
function FormInput({ id, name, type = 'text', value, onChange, placeholder, disabled, error, statusBorder, icon: Icon, autoComplete, ariaInvalid, ariaDescribedby, rightSlot }) {
  const border =
    error || statusBorder === 'error'
      ? 'border-[#FECDD3] focus:border-[#B42318] focus:ring-[#B42318]/15 bg-[#FFF1F2]'
      : statusBorder === 'success'
      ? 'border-[#A7F3D0] focus:border-[#059669] focus:ring-[#059669]/15'
      : 'border-[#E5E7EB] hover:border-[#C6A15B]/50 focus:border-[#17243A] focus:ring-[#17243A]/8 bg-white';

  return (
    <div className="relative">
      {Icon && (
        <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-[#9CA3AF]">
          <Icon className="h-4 w-4" />
        </div>
      )}
      <input
        id={id} name={name} type={type} value={value} onChange={onChange}
        placeholder={placeholder} disabled={disabled}
        autoComplete={autoComplete} aria-invalid={ariaInvalid} aria-describedby={ariaDescribedby}
        className={`block w-full rounded-xl border py-2.5 text-[13px] text-[#111827] placeholder-[#9CA3AF] transition-all duration-200 focus:outline-none focus:ring-2 ${Icon ? 'pl-10' : 'pl-3.5'} ${rightSlot ? 'pr-24' : 'pr-3.5'} ${border} ${disabled ? 'opacity-55 cursor-not-allowed bg-[#F9FAFB]' : ''}`}
      />
      {rightSlot && (
        <div className="absolute inset-y-0 right-0 flex items-center pr-1.5">{rightSlot}</div>
      )}
    </div>
  );
}

/* ─── Section card ─── */
function SectionCard({ step, title, description, isComplete, children }) {
  return (
    <section className="border-t border-[#EEF1F6] py-4 first:border-t-0 first:pt-0 last:pb-1">
      <div className="mb-3.5 flex items-start gap-3">
        <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-xs font-bold transition-colors duration-300 ${
          isComplete ? 'bg-[#E8F8EF] text-[#15803D]' : 'bg-[#EEF2FF] text-[#315E9B]'
        }`}>
          {isComplete ? <CheckCircle2 className="h-3 w-3" /> : step}
        </div>
        <div className="min-w-0">
          <h2 className="text-[13px] font-bold tracking-wide text-[#172033]">{title}</h2>
          <p className="mt-0.5 text-[10px] leading-relaxed text-[#98A2B3]">{description}</p>
        </div>
        {isComplete && <span className="ml-auto shrink-0 rounded-full bg-[#E8F8EF] px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-[#15803D]">Verified</span>}
      </div>
      {children}
    </section>
  );
}

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
    <div className="signup-page flex w-full min-w-0 flex-1 flex-col lg:h-full lg:flex-row">
      <aside className="signup-brand relative flex min-h-[330px] overflow-hidden bg-[#101B2D] lg:h-full lg:min-h-0 lg:w-[42%] xl:w-[40%]">
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="signup-brand-orb signup-brand-orb--gold absolute -left-40 -top-40 h-[30rem] w-[30rem] rounded-full blur-3xl" />
          <div className="signup-brand-orb signup-brand-orb--blue absolute -bottom-40 -right-32 h-[28rem] w-[28rem] rounded-full blur-3xl" />
          <div className="signup-brand-orb signup-brand-orb--soft absolute left-1/2 top-1/2 h-96 w-96 -translate-x-1/2 -translate-y-1/2 rounded-full blur-3xl" />
          <svg className="signup-brand-grid absolute inset-0 h-full w-full" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <defs>
              <pattern id="sg" width="44" height="44" patternUnits="userSpaceOnUse">
                <path d="M 44 0 L 0 0 0 44" fill="none" stroke="white" strokeWidth="0.6" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#sg)" />
          </svg>
        </div>

        <div className="relative z-10 flex h-full w-full flex-col justify-start px-6 py-6 sm:px-10 sm:py-8 lg:px-10 lg:py-8 xl:px-14">
          <div>
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-[14px] bg-gradient-to-br from-[#D9B86B] to-[#99742E] shadow-[0_10px_30px_rgba(198,161,91,0.2)]">
                  <Sparkles className="h-5 w-5 text-white" />
                </div>
                <div>
                  <p className="text-[14px] font-bold tracking-tight text-white">CareerSphere AI</p>
                  <p className="mt-0.5 text-[9px] font-semibold uppercase tracking-[0.2em] text-[#DABF7F]/70">AI career operating system</p>
                </div>
              </div>
              <span className="signup-brand-chip rounded-full px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.16em] text-[#F1D99A]">Private beta</span>
            </div>

            <div className="mt-9 max-w-xl sm:mt-12 lg:mt-14">
              <div className="mb-5 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.2em] text-[#DABF7F]">
                <span className="h-1.5 w-1.5 rounded-full bg-[#DABF7F] shadow-[0_0_14px_rgba(218,191,127,0.9)]" />
                Your unfair career advantage
              </div>
              <h2 className="max-w-[560px] text-[2.35rem] font-bold leading-[1.05] tracking-[-0.045em] text-white sm:text-4xl xl:text-[3.6rem]">
                Turn your next move into a <span className="text-[#E8C97A]">system.</span>
              </h2>
              <p className="mt-4 max-w-lg text-sm leading-6 text-white/55 sm:text-[14px]">
                CareerSphere connects your skills, opportunities, and people into one intelligent loop that keeps your career moving forward.
              </p>
            </div>

            <div className="mt-7 sm:mt-9">
              <CareerSignalCard />
            </div>
          </div>

          <div className="signup-brand-footer mt-7 border-t border-white/10 pt-4 lg:mt-8">
            <div className="flex items-center gap-2 text-[11px] font-semibold text-white/60">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#15803D]/20 text-[#A9E8C0]"><CheckCircle2 className="h-3.5 w-3.5" /></span>
              Built for ambitious students, graduates, and professionals
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="signup-proof-pill rounded-full px-3 py-1.5 text-[10px] font-semibold text-white/65">50K+ match signals</span>
              <span className="signup-proof-pill rounded-full px-3 py-1.5 text-[10px] font-semibold text-white/65">94% skill growth</span>
              <span className="signup-proof-pill rounded-full px-3 py-1.5 text-[10px] font-semibold text-white/65">12K+ professionals</span>
            </div>
          </div>
        </div>

        <div className="signup-brand-rule absolute bottom-0 left-0 right-0 h-1" />
      </aside>

      <main className="signup-form-panel min-w-0 flex-1 overflow-y-auto bg-[#F7F8FB] lg:h-full lg:overflow-hidden">
        <div className="mx-auto flex w-full max-w-[820px] flex-col px-5 py-6 sm:px-8 sm:py-8 lg:h-full lg:justify-center lg:px-10 lg:py-5 xl:px-14">
          <div className="flex justify-end">
            <p className="text-xs text-[#98A2B3]">
              Already a member?{' '}
              <Link href="/login" className="font-bold text-[#17243A] transition-colors hover:text-[#C6A15B]">Sign in <ArrowRight className="ml-0.5 inline h-3.5 w-3.5" /></Link>
            </p>
          </div>

          <div className="mt-7 sm:mt-9 lg:mt-5">
            <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#315E9B]">Build your career OS</p>
            <h1 className="mt-3 max-w-2xl text-[2rem] font-bold leading-[1.04] tracking-[-0.04em] text-[#111827] sm:text-4xl">
              Make space for your <span className="text-[#315E9B]">next big move.</span>
            </h1>
            <p className="mt-3 max-w-xl text-[13px] leading-5 text-[#667085] sm:text-[14px]">
              Create your account in a few quick steps. Your personalized career intelligence starts here.
            </p>
          </div>

          <div className="signup-form-card mt-6 rounded-[24px] border border-[#E5EAF1] bg-white p-4 shadow-[0_18px_55px_rgba(16,27,45,0.08)] sm:mt-7 sm:p-5">
            <StepIndicator currentStep={visualStep} />

            {generalError && (
              <div className="mb-5 flex items-start gap-2.5 rounded-2xl border border-[#FECACA] bg-[#FEF2F2] p-3.5" role="alert">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-[#DC2626]" />
                <p className="text-[13px] font-medium text-[#DC2626]">{generalError}</p>
              </div>
            )}

            <form onSubmit={handleSubmit} noValidate className="space-y-0">
              <SectionCard step={1} title="Personal information" description="Tell us a little about yourself.">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <label htmlFor="first_name" className="block text-[12px] font-semibold text-[#344054]">First name <span className="text-[#DC2626]">*</span></label>
                    <FormInput id="first_name" name="first_name" value={formData.first_name} onChange={handleChange} placeholder="Raj" disabled={isSubmitting} error={fieldErrors.first_name} autoComplete="given-name" ariaInvalid={fieldErrors.first_name ? 'true' : 'false'} ariaDescribedby="first_name-error" />
                    <FieldError id="first_name-error" message={fieldErrors.first_name} />
                  </div>
                  <div className="space-y-1.5">
                    <label htmlFor="last_name" className="block text-[12px] font-semibold text-[#344054]">Last name <span className="text-[#DC2626]">*</span></label>
                    <FormInput id="last_name" name="last_name" value={formData.last_name} onChange={handleChange} placeholder="Yadav" disabled={isSubmitting} error={fieldErrors.last_name} autoComplete="family-name" ariaInvalid={fieldErrors.last_name ? 'true' : 'false'} ariaDescribedby="last_name-error" />
                    <FieldError id="last_name-error" message={fieldErrors.last_name} />
                  </div>
                </div>

                <div className="mt-4 space-y-1.5">
                  <div className="flex items-center justify-between gap-3">
                    <label htmlFor="username" className="block text-[12px] font-semibold text-[#344054]">Username <span className="text-[#DC2626]">*</span></label>
                    {usernameStatus.checking && <span className="flex items-center gap-1 text-[11px] text-[#C6A15B]"><Loader2 className="h-3 w-3 animate-spin" /> Checking…</span>}
                    {!usernameStatus.checking && usernameStatus.available === true && <span className="flex items-center gap-1 text-[11px] font-semibold text-[#059669]"><CheckCircle2 className="h-3.5 w-3.5" /> Available</span>}
                    {!usernameStatus.checking && usernameStatus.available === false && <span className="flex items-center gap-1 text-[11px] font-semibold text-[#DC2626]"><XCircle className="h-3.5 w-3.5" /> Taken</span>}
                  </div>
                  <FormInput id="username" name="username" value={formData.username} onChange={handleChange} placeholder="raj_yadav" disabled={isSubmitting} error={fieldErrors.username} statusBorder={uBorder} icon={User} autoComplete="username" ariaInvalid={fieldErrors.username || usernameStatus.available === false ? 'true' : 'false'} ariaDescribedby="username-error" />
                  <FieldError id="username-error" message={fieldErrors.username} />
                  {!fieldErrors.username && <p className="text-[11px] text-[#98A2B3]">Letters, numbers, _ and . (3–30 chars)</p>}
                </div>
              </SectionCard>

              <SectionCard step={2} title="Verify your email" description="We’ll use this to secure your account." isComplete={otpStep === 'verified'}>
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between gap-3">
                    <label htmlFor="email" className="block text-[12px] font-semibold text-[#344054]">Email address <span className="text-[#DC2626]">*</span></label>
                    {otpStep === 'verified' && <span className="flex items-center gap-1 text-[11px] font-semibold text-[#059669]"><ShieldCheck className="h-3.5 w-3.5" /> Verified</span>}
                    {otpStep === 'idle' && emailStatus.checking && <span className="flex items-center gap-1 text-[11px] text-[#C6A15B]"><Loader2 className="h-3 w-3 animate-spin" /> Checking…</span>}
                    {otpStep === 'idle' && !emailStatus.checking && emailStatus.available === true && <span className="flex items-center gap-1 text-[11px] font-semibold text-[#059669]"><CheckCircle2 className="h-3.5 w-3.5" /> Available</span>}
                    {otpStep === 'idle' && !emailStatus.checking && emailStatus.available === false && <span className="flex items-center gap-1 text-[11px] font-semibold text-[#DC2626]"><XCircle className="h-3.5 w-3.5" /> Registered</span>}
                  </div>
                  <FormInput id="email" name="email" type="email" value={formData.email} onChange={handleChange} placeholder="raj@example.com" disabled={isSubmitting || otpStep === 'sent' || otpStep === 'verifying' || otpStep === 'verified'} error={fieldErrors.email} statusBorder={eBorder} icon={Mail} autoComplete="email" ariaInvalid={fieldErrors.email || emailStatus.available === false ? 'true' : 'false'} ariaDescribedby="email-error" rightSlot={otpStep !== 'verified' ? (
                    <button type="button" onClick={handleSendOtp} disabled={!isEmailVerifiable || otpStep === 'sending' || otpStep === 'sent' || otpStep === 'verifying'} className="shrink-0 rounded-lg bg-[#17243A] px-3 py-1.5 text-[11px] font-bold text-white transition-colors hover:bg-[#0F1A2E] disabled:cursor-not-allowed disabled:opacity-35">{otpStep === 'sending' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : otpStep === 'sent' || otpStep === 'verifying' ? 'Sent ✓' : 'Verify'}</button>
                  ) : null} />
                  <FieldError id="email-error" message={fieldErrors.email} />
                </div>

                {(otpStep === 'sent' || otpStep === 'verifying') && (
                  <div className="signup-otp-panel mt-4 space-y-4 rounded-2xl border p-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#315E9B]/10"><Mail className="h-4 w-4 text-[#315E9B]" /></div>
                      <div><p className="text-[13px] font-semibold text-[#1E3A5F]">Check your inbox</p><p className="mt-0.5 text-[11px] text-[#667085]">Code sent to <span className="font-bold text-[#1E3A5F]">{formData.email.trim()}</span></p></div>
                    </div>
                    <div className="flex items-center justify-center gap-2 py-1">
                      {otpDigits.map((digit, i) => (
                        <input key={i} ref={el => (otpInputRefs.current[i] = el)} type="text" inputMode="numeric" maxLength={OTP_LENGTH} value={digit} onChange={e => handleOtpChange(i, e.target.value)} onKeyDown={e => handleOtpKey(i, e)} disabled={otpStep === 'verifying'} className={`h-12 w-[38px] rounded-xl border-2 bg-white text-center text-lg font-extrabold text-[#111827] transition-all duration-150 focus:outline-none focus:ring-2 sm:w-11 ${otpError ? 'border-[#FECACA] focus:border-[#DC2626] focus:ring-[#DC2626]/15' : digit ? 'border-[#17243A] shadow-[0_2px_8px_rgba(23,36,58,0.12)] focus:border-[#17243A] focus:ring-[#17243A]/10' : 'border-[#BFDBFE] hover:border-[#93C5FD] focus:border-[#17243A] focus:ring-[#17243A]/10'} ${otpStep === 'verifying' ? 'cursor-not-allowed opacity-50' : ''}`} />
                      ))}
                    </div>
                    {otpError && <p className="flex items-center justify-center gap-1 text-center text-[11px] font-medium text-[#DC2626]"><AlertCircle className="h-3.5 w-3.5" /> {otpError}</p>}
                    <div className="flex items-center justify-between gap-3">
                      <button type="button" onClick={handleResendOtp} disabled={resendCooldown > 0} className="text-[11px] font-semibold text-[#C6A15B] transition-colors hover:text-[#17243A] disabled:cursor-not-allowed disabled:text-[#98A2B3]">{resendCooldown > 0 ? `Resend in ${resendCooldown}s` : '↺ Resend code'}</button>
                      <button type="button" onClick={handleVerifyOtp} disabled={otpStep === 'verifying' || otpDigits.join('').length !== OTP_LENGTH} className="flex items-center gap-1.5 rounded-lg bg-[#17243A] px-4 py-2 text-[12px] font-bold text-white transition-colors hover:bg-[#0F1A2E] disabled:cursor-not-allowed disabled:opacity-45">{otpStep === 'verifying' ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Verifying…</> : <><CheckCircle2 className="h-3.5 w-3.5" /> Confirm code</>}</button>
                    </div>
                  </div>
                )}

                {otpStep === 'verified' && (
                  <div className="flex items-center gap-3 rounded-2xl border border-[#A7F3D0] bg-[#ECFDF5] p-3.5">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#059669]/15"><CheckCircle2 className="h-5 w-5 text-[#059669]" /></div>
                    <div><p className="text-[13px] font-bold text-[#065F46]">Email verified</p><p className="text-[11px] text-[#059669]/70">{formData.email.trim()}</p></div>
                    <Award className="ml-auto h-5 w-5 text-[#059669]/30" />
                  </div>
                )}
              </SectionCard>

              <SectionCard step={3} title="Secure your account" description="Choose a password you’ll remember.">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <PasswordInput id="password" name="password" label="Password" value={formData.password} onChange={handleChange} placeholder="Create a strong password" required disabled={isSubmitting} error={fieldErrors.password} autoComplete="new-password" />
                  <PasswordInput id="confirm_password" name="confirm_password" label="Confirm password" value={formData.confirm_password} onChange={handleChange} placeholder="Re-enter your password" required disabled={isSubmitting} error={fieldErrors.confirm_password} autoComplete="new-password" />
                </div>
                <PasswordRules password={formData.password} />
              </SectionCard>

              <div className="border-t border-[#EEF1F6] pt-4">
                <button type="submit" id="signup-submit-button" disabled={!canSubmit} className="flex h-11 w-full items-center justify-center gap-2.5 rounded-xl bg-[#17243A] px-4 text-[13px] font-bold text-white shadow-[0_10px_24px_rgba(23,36,58,0.16)] transition-all duration-200 hover:-translate-y-0.5 hover:bg-[#0F1A2E] hover:shadow-[0_14px_30px_rgba(23,36,58,0.22)] active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-45 disabled:shadow-none disabled:hover:translate-y-0">
                  {isSubmitting ? <><Loader2 className="h-4 w-4 animate-spin" /> Creating your account…</> : <><Sparkles className="h-4 w-4" /> Create my account <ArrowRight className="h-4 w-4" /></>}
                </button>
                {!canSubmit && !isSubmitting && <p className="mt-3 text-center text-[11px] text-[#98A2B3]">{otpStep !== 'verified' ? 'Verify your email above to unlock account creation.' : 'Complete all required fields to continue.'}</p>}
              </div>
            </form>
          </div>

          <p className="mx-auto mt-4 max-w-lg text-center text-[10px] leading-relaxed text-[#98A2B3]">By creating an account you agree to our <span className="cursor-pointer font-semibold text-[#C6A15B] hover:underline">Terms of Service</span> and <span className="cursor-pointer font-semibold text-[#C6A15B] hover:underline">Privacy Policy</span>.</p>
        </div>
      </main>
    </div>
  );
}
