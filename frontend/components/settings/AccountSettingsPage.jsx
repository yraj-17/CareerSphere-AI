'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  AlertCircle,
  Award,
  BriefcaseBusiness,
  Camera,
  CheckCircle2,
  ChevronRight,
  GraduationCap,
  KeyRound,
  Loader2,
  LockKeyhole,
  Mail,
  Save,
  ShieldCheck,
  Trash2,
  UserRound,
  X,
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import ProfileAvatar from '@/components/common/ProfileAvatar';
import {
  changePassword,
  checkUsername,
  deleteMedia,
  extractErrorMessage,
  getMyProfile,
  updateMyAccount,
  updateMyProfile,
  uploadMedia,
} from '@/services/api';

const emptyPassword = { current_password: '', new_password: '', confirm_password: '' };

function getPersonalForm(profile) {
  return {
    first_name: profile?.user?.first_name || '',
    last_name: profile?.user?.last_name || '',
    username: profile?.user?.username || '',
    headline: profile?.headline || '',
    location: profile?.location || '',
    about: profile?.about || '',
  };
}

function Field({ label, value, onChange, type = 'text', help, error, required = false, onBlur }) {
  return (
    <label className="block text-sm font-medium text-slate-700">
      <span>{label}{required ? ' *' : ''}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onBlur={onBlur}
        required={required}
        className={`input-base mt-2 ${error ? 'border-red-400 focus:border-red-500' : ''}`}
      />
      {error ? <span className="mt-1 block text-xs font-normal text-red-700">{error}</span> : null}
      {!error && help ? <span className="mt-1 block text-xs font-normal text-slate-500">{help}</span> : null}
    </label>
  );
}

function SettingsSection({ title, description, icon: Icon, children, action }) {
  return (
    <section className="surface-card">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-500">
            <Icon className="h-5 w-5" aria-hidden="true" />
          </span>
          <div>
            <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
            {description ? <p className="mt-1 text-sm leading-6 text-slate-500">{description}</p> : null}
          </div>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function StatusMessage({ type = 'error', children }) {
  const success = type === 'success';
  return (
    <div
      role={success ? 'status' : 'alert'}
      className={`flex items-start gap-2 rounded-lg border px-3 py-2.5 text-sm ${
        success ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-red-200 bg-red-50 text-red-700'
      }`}
    >
      {success ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> : <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />}
      <span>{children}</span>
    </div>
  );
}

function getInitials(profile) {
  return `${profile?.user?.first_name?.[0] || ''}${profile?.user?.last_name?.[0] || ''}`.toUpperCase() || 'U';
}

export default function AccountSettingsPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading, checkAuth } = useAuth();
  const [profile, setProfile] = useState(null);
  const [personal, setPersonal] = useState(null);
  const [password, setPassword] = useState(emptyPassword);
  const [loading, setLoading] = useState(true);
  const [savingPersonal, setSavingPersonal] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);
  const [photoBusy, setPhotoBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [personalError, setPersonalError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [usernameStatus, setUsernameStatus] = useState(null);

  const loadProfile = async () => {
    try {
      setError('');
      const data = await getMyProfile();
      setProfile(data);
      setPersonal(getPersonalForm(data));
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated) {
      router.push('/login');
      return;
    }
    loadProfile();
  }, [authLoading, isAuthenticated, router]);

  const savedPersonal = useMemo(() => getPersonalForm(profile), [profile]);
  const isDirty = Boolean(personal && JSON.stringify(personal) !== JSON.stringify(savedPersonal));

  useEffect(() => {
    if (!isDirty) return undefined;
    const handleBeforeUnload = (event) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isDirty]);

  const setPersonalField = (field, value) => {
    setPersonal((previous) => ({ ...previous, [field]: value }));
    setPersonalError('');
    setError('');
    setNotice('');
    if (field === 'username') setUsernameStatus(null);
  };

  const validatePersonal = () => {
    if (!personal.first_name.trim() || !personal.last_name.trim()) return 'First and last name are required.';
    if (!/^[a-zA-Z0-9_.]{3,30}$/.test(personal.username.trim())) {
      return 'Username must be 3–30 characters and use only letters, numbers, underscores, or periods.';
    }
    if (personal.headline.length > 160 || personal.location.length > 160 || personal.about.length > 2000) {
      return 'Please shorten one of the profile fields before saving.';
    }
    return '';
  };

  const validateUsername = async () => {
    const username = personal?.username?.trim().toLowerCase();
    if (!username || username === profile?.user?.username) {
      setUsernameStatus(null);
      return { available: true };
    }
    if (!/^[a-zA-Z0-9_.]{3,30}$/.test(username)) {
      const result = { available: false, message: 'Use 3–30 letters, numbers, underscores, or periods.' };
      setUsernameStatus(result);
      return result;
    }
    try {
      const result = await checkUsername(username);
      setUsernameStatus(result);
      return result;
    } catch (err) {
      const result = { available: false, message: extractErrorMessage(err) };
      setUsernameStatus(result);
      return result;
    }
  };

  const refreshAfterChange = async () => {
    await loadProfile();
    await checkAuth();
  };

  const savePersonal = async (event) => {
    event.preventDefault();
    setNotice('');
    const validation = validatePersonal();
    if (validation) {
      setPersonalError(validation);
      return;
    }
    setSavingPersonal(true);
    setPersonalError('');
    try {
      const usernameResult = await validateUsername();
      if (!usernameResult?.available) {
        setPersonalError(usernameResult?.message || 'That username is not available.');
        return;
      }
      await updateMyAccount({
        first_name: personal.first_name.trim(),
        last_name: personal.last_name.trim(),
        username: personal.username.trim().toLowerCase(),
      });
      await updateMyProfile({
        headline: personal.headline.trim() || null,
        location: personal.location.trim() || null,
        about: personal.about.trim() || null,
      });
      await refreshAfterChange();
      setNotice('Personal information updated successfully.');
    } catch (err) {
      setPersonalError(extractErrorMessage(err));
    } finally {
      setSavingPersonal(false);
    }
  };

  const resetPersonal = () => {
    setPersonal(savedPersonal);
    setPersonalError('');
    setUsernameStatus(null);
  };

  const handlePhotoUpload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setError('Please choose an image file.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError('Profile photos must be smaller than 10 MB.');
      return;
    }
    setPhotoBusy(true);
    setError('');
    setNotice('');
    try {
      const uploaded = await uploadMedia(file, 'profile_image');
      await updateMyProfile({ profile_photo_media_id: uploaded.id });
      await refreshAfterChange();
      setNotice('Profile photo updated successfully.');
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setPhotoBusy(false);
    }
  };

  const handlePhotoRemove = async () => {
    const mediaId = profile?.profile_photo_media_id || profile?.profile_photo?.id;
    if (!mediaId || !window.confirm('Remove your profile photo?')) return;
    setPhotoBusy(true);
    setError('');
    setNotice('');
    try {
      await updateMyProfile({ profile_photo_media_id: null });
      await deleteMedia(mediaId);
      await refreshAfterChange();
      setNotice('Profile photo removed.');
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setPhotoBusy(false);
    }
  };

  const savePassword = async (event) => {
    event.preventDefault();
    setPasswordError('');
    setNotice('');
    if (password.new_password !== password.confirm_password) {
      setPasswordError('New password and confirmation do not match.');
      return;
    }
    if (!/[A-Z]/.test(password.new_password) || !/[a-z]/.test(password.new_password) || !/[0-9]/.test(password.new_password) || password.new_password.length < 8) {
      setPasswordError('Use at least 8 characters with uppercase, lowercase, and a number.');
      return;
    }
    setSavingPassword(true);
    try {
      await changePassword({ current_password: password.current_password, new_password: password.new_password });
      setPassword(emptyPassword);
      setNotice('Password changed successfully.');
    } catch (err) {
      setPasswordError(extractErrorMessage(err));
    } finally {
      setSavingPassword(false);
    }
  };

  if (authLoading || loading) {
    return (
      <div className="flex min-h-[60vh] flex-1 flex-col items-center justify-center">
        <Loader2 className="mb-3 h-8 w-8 animate-spin text-brand-500" />
        <p className="text-sm text-slate-500">Loading account settings...</p>
      </div>
    );
  }

  if (!profile || !personal) return null;

  const fullName = `${profile.user.first_name} ${profile.user.last_name}`.trim();
  const professionalSections = [
    { label: 'Skills', value: profile.skills?.length || 0, icon: ShieldCheck },
    { label: 'Education', value: profile.education?.length || 0, icon: GraduationCap },
    { label: 'Experience', value: profile.experience?.length || 0, icon: BriefcaseBusiness },
    { label: 'Projects', value: profile.projects?.length || 0, icon: KeyRound },
    { label: 'Certifications', value: profile.certifications?.length || 0, icon: Award },
  ];

  return (
    <div className="mx-auto flex min-h-full w-full max-w-5xl flex-1 flex-col gap-5 px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
      <div>
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-brand-500">Account</p>
        <h1 className="page-title mt-1">Settings</h1>
        <p className="page-description">Keep your account identity, professional profile, and security details up to date.</p>
      </div>

      {error ? <StatusMessage>{error}</StatusMessage> : null}
      {notice ? <StatusMessage type="success">{notice}</StatusMessage> : null}

      <SettingsSection
        title="Personal Information"
        description="Update the information shown across your profile, network, and conversations."
        icon={UserRound}
      >
        <div className="mb-6 flex flex-col gap-4 rounded-xl border border-slate-200 bg-slate-50 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <ProfileAvatar
              src={profile.profile_photo?.url}
              name={fullName}
              username={profile.user.username}
              alt={fullName}
              fallback={getInitials(profile)}
              className="h-16 w-16"
              fallbackClassName="border border-brand-200 bg-brand-50 text-lg font-bold text-brand-500"
            />
            <div>
              <p className="font-semibold text-slate-900">Profile photo</p>
              <p className="mt-1 text-xs text-slate-500">JPG, PNG, or another image under 10 MB.</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <label className="btn-outline cursor-pointer">
              {photoBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Camera className="h-4 w-4" />}
              {profile.profile_photo?.url ? 'Change photo' : 'Upload photo'}
              <input type="file" accept="image/*" className="hidden" onChange={handlePhotoUpload} disabled={photoBusy} />
            </label>
            {profile.profile_photo?.url ? (
              <button type="button" onClick={handlePhotoRemove} disabled={photoBusy} className="btn-danger">
                <Trash2 className="h-4 w-4" />
                Remove
              </button>
            ) : null}
          </div>
        </div>

        <form onSubmit={savePersonal} className="space-y-5">
          {personalError ? <StatusMessage>{personalError}</StatusMessage> : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="First name" value={personal.first_name} onChange={(value) => setPersonalField('first_name', value)} required />
            <Field label="Last name" value={personal.last_name} onChange={(value) => setPersonalField('last_name', value)} required />
          </div>
          <Field
            label="Username"
            value={personal.username}
            onChange={(value) => setPersonalField('username', value)}
            onBlur={validateUsername}
            help="Your username is unique, normalized to lowercase, and may appear in profile links."
            error={usernameStatus && !usernameStatus.available ? usernameStatus.message : undefined}
            required
          />
          {usernameStatus?.available ? <p className="-mt-3 text-xs text-emerald-700">{usernameStatus.message}</p> : null}
          {personal.username.trim().toLowerCase() !== profile.user.username ? (
            <p className="-mt-3 text-xs text-amber-700">Changing your username may update links that use your profile identity.</p>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Professional headline" value={personal.headline} onChange={(value) => setPersonalField('headline', value)} help="Up to 160 characters." />
            <Field label="Location" value={personal.location} onChange={(value) => setPersonalField('location', value)} />
          </div>
          <label className="block text-sm font-medium text-slate-700">
            <span>Bio</span>
            <textarea value={personal.about} onChange={(event) => setPersonalField('about', event.target.value)} rows={5} maxLength={2000} className="input-base mt-2 resize-y" />
            <span className="mt-1 block text-right text-xs font-normal text-slate-500">{personal.about.length}/2000</span>
          </label>
          <div className="flex flex-wrap gap-3">
            <button type="submit" disabled={savingPersonal || !isDirty} className="btn-primary">
              {savingPersonal ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Save changes
            </button>
            <button type="button" onClick={resetPersonal} disabled={!isDirty || savingPersonal} className="btn-outline">
              <X className="h-4 w-4" />
              Cancel
            </button>
          </div>
        </form>
      </SettingsSection>

      <SettingsSection
        title="Professional Profile"
        description="Your existing professional records remain in the full profile editor, including career preferences."
        icon={BriefcaseBusiness}
        action={<Link href="/dashboard/profile" className="btn-outline">Open profile <ChevronRight className="h-4 w-4" /></Link>}
      >
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {professionalSections.map(({ label, value, icon: Icon }) => (
            <Link key={label} href="/dashboard/profile" className="group rounded-xl border border-slate-200 bg-slate-50 p-4 transition hover:border-brand-200 hover:bg-brand-50">
              <Icon className="h-5 w-5 text-brand-500" aria-hidden="true" />
              <p className="mt-3 text-sm font-semibold text-slate-900">{label}</p>
              <p className="mt-1 text-xs text-slate-500">{value} {value === 1 ? 'entry' : 'entries'}</p>
            </Link>
          ))}
        </div>
      </SettingsSection>

      <SettingsSection
        title="Login & Security"
        description="Manage your password and review the email address used for sign-in."
        icon={LockKeyhole}
      >
        <div className="mb-6 flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <Mail className="mt-0.5 h-5 w-5 shrink-0 text-slate-500" aria-hidden="true" />
          <div>
            <p className="text-sm font-semibold text-slate-900">Account email</p>
            <p className="mt-1 break-all text-sm text-slate-600">{profile.user.email}</p>
            <p className="mt-2 text-xs leading-5 text-slate-500">Email changes are not enabled because this installation does not yet have a verification-and-recovery flow for changing a login identity.</p>
          </div>
        </div>

        <form onSubmit={savePassword} className="space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <KeyRound className="h-4 w-4 text-brand-500" aria-hidden="true" />
            Change password
          </div>
          {passwordError ? <StatusMessage>{passwordError}</StatusMessage> : null}
          <div className="grid gap-4">
            <Field label="Current password" type="password" value={password.current_password} onChange={(value) => setPassword({ ...password, current_password: value })} required />
            <Field label="New password" type="password" value={password.new_password} onChange={(value) => setPassword({ ...password, new_password: value })} help="8+ characters, upper/lowercase, and a number." required />
            <Field label="Confirm new password" type="password" value={password.confirm_password} onChange={(value) => setPassword({ ...password, confirm_password: value })} required />
          </div>
          <button type="submit" disabled={savingPassword} className="btn-primary">
            {savingPassword ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
            Update password
          </button>
        </form>
      </SettingsSection>

    </div>
  );
}
