'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Award,
  Briefcase,
  Camera,
  CheckCircle2,
  Copy,
  Edit3,
  GraduationCap,
  Link as LinkIcon,
  Loader2,
  MapPin,
  Plus,
  Save,
  Sparkles,
  Target,
  Trash2,
  User,
  X,
  Zap,
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import {
  addCertification,
  addEducation,
  addExperience,
  addProject,
  addSkill,
  deleteCertification,
  deleteEducation,
  deleteExperience,
  deleteProject,
  deleteSkill,
  extractErrorMessage,
  getMyProfile,
  optimizeMyProfile,
  updateCareerPreferences,
  updateCertification,
  updateEducation,
  updateExperience,
  updateMyProfile,
  updateProject,
  uploadMedia,
} from '@/services/api';

const emptyEducation = { institution: '', degree: '', field_of_study: '', start_date: '', end_date: '', description: '' };
const emptyExperience = { company: '', job_title: '', employment_type: '', location: '', start_date: '', end_date: '', currently_working: false, description: '' };
const emptyProject = { name: '', description: '', technologies: '', github_url: '', live_url: '', start_date: '', end_date: '' };
const emptyCertification = { name: '', issuing_organization: '', issue_date: '', expiration_date: '', credential_id: '', credential_url: '' };
const emptyPreferences = { target_job_role: '', preferred_industry: '', preferred_work_type: '', preferred_locations: '', career_interests: '' };

function compactPayload(values) {
  return Object.fromEntries(Object.entries(values).map(([key, value]) => [key, value === '' ? null : value]));
}

function commaList(value) {
  if (Array.isArray(value)) return value.join(', ');
  return value || '';
}

function toList(value) {
  return (value || '').split(',').map((item) => item.trim()).filter(Boolean);
}

function validateDates(values, startKey = 'start_date', endKey = 'end_date') {
  if (values[startKey] && values[endKey] && values[startKey] > values[endKey]) {
    return 'Start date must be before end date.';
  }
  return '';
}

function validateUrl(value, label) {
  if (!value) return '';
  try {
    new URL(value);
    return '';
  } catch {
    return `${label} must be a valid URL.`;
  }
}

function formatDate(value) {
  if (!value) return 'Present';
  return new Date(`${value}T00:00:00`).toLocaleDateString('en-US', { year: 'numeric', month: 'short' });
}

function Field({ label, value, onChange, type = 'text', required = false, as = 'input', options }) {
  const base = 'w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition focus:border-accent/60 focus:ring-2 focus:ring-accent/20';
  return (
    <label className="space-y-2 text-xs font-medium uppercase tracking-wide text-slate-400">
      <span>{label}{required ? ' *' : ''}</span>
      {as === 'textarea' ? (
        <textarea required={required} value={value || ''} onChange={(event) => onChange(event.target.value)} rows={4} className={base} />
      ) : as === 'select' ? (
        <select required={required} value={value || ''} onChange={(event) => onChange(event.target.value)} className={base}>
          <option value="">Select</option>
          {options.map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
      ) : (
        <input required={required} type={type} value={value || ''} onChange={(event) => onChange(event.target.value)} className={base} />
      )}
    </label>
  );
}

function Section({ title, icon: Icon, action, children }) {
  return (
    <section className="rounded-[2rem] border border-white/10 bg-white/[0.04] p-5 sm:p-6 shadow-glow backdrop-blur-xl">
      <div className="mb-5 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-lg font-bold text-white">
          <Icon className="h-5 w-5 text-accent" />
          <h2>{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function ActionButton({ children, onClick, icon: Icon = Plus, variant = 'primary', type = 'button', disabled = false }) {
  const styles = variant === 'danger'
    ? 'border-rose-500/30 bg-rose-500/10 text-rose-200 hover:border-rose-500/50'
    : variant === 'ghost'
      ? 'border-white/10 bg-white/5 text-slate-200 hover:border-white/20'
      : 'border-accent/30 bg-accent text-black hover:bg-accentSoft';
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${styles}`}
    >
      <Icon className="h-4 w-4" />
      {children}
    </button>
  );
}

function EmptyState({ text }) {
  return <div className="rounded-2xl border border-dashed border-white/10 bg-slate-950/40 p-5 text-sm text-slate-400">{text}</div>;
}

export default function ProfilePage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading, checkAuth } = useAuth();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [optimization, setOptimization] = useState(null);
  const [optimizationError, setOptimizationError] = useState('');
  const [error, setError] = useState('');
  const [editingBasic, setEditingBasic] = useState(false);
  const [skillName, setSkillName] = useState('');
  const [forms, setForms] = useState({});

  const initials = useMemo(() => {
    const user = profile?.user;
    return `${user?.first_name?.[0] || ''}${user?.last_name?.[0] || ''}` || 'U';
  }, [profile]);

  const loadProfile = async () => {
    try {
      setError('');
      const data = await getMyProfile();
      setProfile(data);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.push('/login');
    if (!authLoading && isAuthenticated) loadProfile();
  }, [authLoading, isAuthenticated, router]);

  const save = async (work) => {
    setSaving(true);
    setError('');
    try {
      await work();
      await loadProfile();
      await checkAuth();
      return true;
    } catch (err) {
      setError(extractErrorMessage(err));
      return false;
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async (label, work) => {
    if (!window.confirm(`Delete ${label}?`)) return;
    await save(work);
  };

  const runProfileOptimization = async () => {
    setOptimizing(true);
    setOptimizationError('');
    try {
      const data = await optimizeMyProfile();
      setOptimization(data);
    } catch (err) {
      setOptimizationError(extractErrorMessage(err));
    } finally {
      setOptimizing(false);
    }
  };

  if (authLoading || loading) {
    return (
      <div className="flex min-h-[60vh] flex-1 flex-col items-center justify-center">
        <Loader2 className="mb-3 h-8 w-8 animate-spin text-accent" />
        <p className="text-sm text-slate-400">Loading profile...</p>
      </div>
    );
  }

  if (!profile) return null;

  const basicForm = forms.basic || {
    first_name: profile.user.first_name,
    last_name: profile.user.last_name,
    headline: profile.headline || '',
    location: profile.location || '',
    about: profile.about || '',
  };

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 py-8 sm:px-6 lg:px-8">
      {error ? <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">{error}</div> : null}

      <section className="rounded-[2rem] border border-white/10 bg-white/[0.04] p-6 shadow-glow backdrop-blur-xl">
        <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
          <div className="flex flex-col gap-5 sm:flex-row">
            <div className="relative h-28 w-28 shrink-0 overflow-hidden rounded-[1.5rem] border border-white/10 bg-slate-950">
              {profile.profile_photo?.url ? (
                <img src={profile.profile_photo.url} alt="" className="h-full w-full object-cover" />
              ) : (
                <div className="flex h-full w-full items-center justify-center bg-accent/15 text-3xl font-extrabold text-accent">{initials}</div>
              )}
            </div>
            <div className="space-y-3">
              <div>
                <h1 className="text-3xl font-extrabold text-white">{profile.user.first_name} {profile.user.last_name}</h1>
                <p className="mt-1 text-base text-accent">{profile.headline || 'Add a professional headline'}</p>
              </div>
              <p className="flex items-center gap-2 text-sm text-slate-300">
                <MapPin className="h-4 w-4 text-slate-500" />
                {profile.location || 'Add your location'}
              </p>
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-white/20">
                <Camera className="h-4 w-4" />
                Upload Photo
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={async (event) => {
                    const file = event.target.files?.[0];
                    if (!file) return;
                    if (!file.type.startsWith('image/')) {
                      setError('Please choose an image file.');
                      return;
                    }
                    await save(async () => {
                      const uploaded = await uploadMedia(file, 'profile_image');
                      await updateMyProfile({ profile_photo_media_id: uploaded.id });
                    });
                  }}
                />
              </label>
            </div>
          </div>
          <div className="w-full max-w-sm rounded-2xl border border-white/10 bg-slate-950/60 p-5">
            <div className="mb-3 flex items-center justify-between text-sm">
              <span className="font-semibold text-white">Profile Completion</span>
              <span className="font-bold text-accent">{profile.completeness.percentage}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/10">
              <div className="h-full rounded-full bg-accent" style={{ width: `${profile.completeness.percentage}%` }} />
            </div>
            <div className="mt-4 grid gap-2 text-xs text-slate-300">
              {profile.completeness.completed.map((item) => (
                <span key={item} className="flex items-center gap-2"><CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />{item}</span>
              ))}
              {profile.completeness.missing.map((item) => (
                <span key={item} className="flex items-center gap-2 text-slate-500"><X className="h-3.5 w-3.5" />{item}</span>
              ))}
            </div>
            <div className="mt-5 border-t border-white/10 pt-4">
              <ActionButton icon={optimizing ? Loader2 : Sparkles} onClick={runProfileOptimization} disabled={optimizing}>
                {optimizing ? 'Optimizing...' : 'Optimize My Profile'}
              </ActionButton>
              {optimizationError ? <p className="mt-3 text-sm text-rose-200">{optimizationError}</p> : null}
            </div>
          </div>
        </div>
      </section>

      {optimization || optimizing ? (
        <ProfileOptimizationPanel
          optimization={optimization}
          loading={optimizing}
          onRefresh={runProfileOptimization}
        />
      ) : null}

      <Section title="About" icon={User} action={<ActionButton icon={editingBasic ? X : Edit3} variant="ghost" onClick={() => setEditingBasic(!editingBasic)}>{editingBasic ? 'Cancel' : 'Edit'}</ActionButton>}>
        {editingBasic ? (
          <form
            className="grid gap-4"
            onSubmit={async (event) => {
              event.preventDefault();
              const ok = await save(async () => updateMyProfile(compactPayload(basicForm)));
              if (ok) setEditingBasic(false);
            }}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="First Name" required value={basicForm.first_name} onChange={(value) => setForms({ ...forms, basic: { ...basicForm, first_name: value } })} />
              <Field label="Last Name" required value={basicForm.last_name} onChange={(value) => setForms({ ...forms, basic: { ...basicForm, last_name: value } })} />
            </div>
            <Field label="Professional Headline" value={basicForm.headline} onChange={(value) => setForms({ ...forms, basic: { ...basicForm, headline: value } })} />
            <Field label="Location" value={basicForm.location} onChange={(value) => setForms({ ...forms, basic: { ...basicForm, location: value } })} />
            <Field label="About" as="textarea" value={basicForm.about} onChange={(value) => setForms({ ...forms, basic: { ...basicForm, about: value } })} />
            <ActionButton type="submit" icon={Save} disabled={saving}>Save Profile</ActionButton>
          </form>
        ) : (
          <p className="whitespace-pre-wrap text-sm leading-7 text-slate-300">{profile.about || 'Add a short bio that explains what you do, what you are learning, and where you want to grow.'}</p>
        )}
      </Section>

      <Section title="Skills" icon={Target}>
        <div className="mb-4 flex flex-wrap gap-2">
          {profile.skills.length ? profile.skills.map((skill) => (
            <span key={skill.id} className="inline-flex items-center gap-2 rounded-full border border-accent/20 bg-accent/10 px-3 py-1 text-sm text-accent">
              {skill.name}
              <button type="button" title="Delete skill" onClick={() => confirmDelete(skill.name, () => deleteSkill(skill.id))}>
                <X className="h-3.5 w-3.5" />
              </button>
            </span>
          )) : <EmptyState text="No skills added yet. Add your strongest technical and professional skills." />}
        </div>
        <form
          className="flex flex-col gap-3 sm:flex-row"
          onSubmit={async (event) => {
            event.preventDefault();
            if (!skillName.trim()) return setError('Skill name is required.');
            const ok = await save(async () => addSkill({ name: skillName }));
            if (ok) setSkillName('');
          }}
        >
          <input value={skillName} onChange={(event) => setSkillName(event.target.value)} placeholder="Python, React, PostgreSQL" className="min-w-0 flex-1 rounded-full border border-white/10 bg-slate-950/70 px-4 py-2 text-sm text-white outline-none focus:border-accent/60" />
          <ActionButton type="submit" disabled={saving}>Add Skill</ActionButton>
        </form>
      </Section>

      <EditableListSection title="Experience" icon={Briefcase} items={profile.experience} empty="No experience added yet." formKey="experience" emptyForm={emptyExperience} forms={forms} setForms={setForms} saving={saving} save={save} addFn={addExperience} updateFn={updateExperience} deleteFn={deleteExperience} renderItem={(item) => (
        <Entry item={item} title={item.job_title} subtitle={item.company} meta={`${formatDate(item.start_date)} - ${item.currently_working ? 'Present' : formatDate(item.end_date)}${item.employment_type ? ` | ${item.employment_type}` : ''}`} />
      )} validate={(values) => validateDates(values)} fields={(values, setValue) => (
        <>
          <Field label="Job Title" required value={values.job_title} onChange={(v) => setValue('job_title', v)} />
          <Field label="Company" required value={values.company} onChange={(v) => setValue('company', v)} />
          <Field label="Employment Type" as="select" options={['Full-time', 'Part-time', 'Internship', 'Freelance', 'Contract']} value={values.employment_type} onChange={(v) => setValue('employment_type', v)} />
          <Field label="Location" value={values.location} onChange={(v) => setValue('location', v)} />
          <Field label="Start Date" type="date" value={values.start_date} onChange={(v) => setValue('start_date', v)} />
          <Field label="End Date" type="date" value={values.end_date} onChange={(v) => setValue('end_date', v)} />
          <label className="flex items-center gap-2 text-sm text-slate-300"><input type="checkbox" checked={values.currently_working} onChange={(e) => setValue('currently_working', e.target.checked)} /> Currently working here</label>
          <Field label="Description" as="textarea" value={values.description} onChange={(v) => setValue('description', v)} />
        </>
      )} />

      <EditableListSection title="Education" icon={GraduationCap} items={profile.education} empty="No education added yet." formKey="education" emptyForm={emptyEducation} forms={forms} setForms={setForms} saving={saving} save={save} addFn={addEducation} updateFn={updateEducation} deleteFn={deleteEducation} renderItem={(item) => (
        <Entry item={item} title={item.degree} subtitle={item.institution} meta={`${item.field_of_study || ''} ${formatDate(item.start_date)} - ${formatDate(item.end_date)}`} />
      )} validate={(values) => validateDates(values)} fields={(values, setValue) => (
        <>
          <Field label="Institution" required value={values.institution} onChange={(v) => setValue('institution', v)} />
          <Field label="Degree" required value={values.degree} onChange={(v) => setValue('degree', v)} />
          <Field label="Field Of Study" value={values.field_of_study} onChange={(v) => setValue('field_of_study', v)} />
          <Field label="Start Date" type="date" value={values.start_date} onChange={(v) => setValue('start_date', v)} />
          <Field label="End Date" type="date" value={values.end_date} onChange={(v) => setValue('end_date', v)} />
          <Field label="Description" as="textarea" value={values.description} onChange={(v) => setValue('description', v)} />
        </>
      )} />

      <EditableListSection title="Projects" icon={LinkIcon} items={profile.projects} empty="No projects added yet." formKey="projects" emptyForm={emptyProject} forms={forms} setForms={setForms} saving={saving} save={save} addFn={addProject} updateFn={updateProject} deleteFn={deleteProject} renderItem={(item) => (
        <Entry item={item} title={item.name} subtitle={(item.technologies || []).join(' | ')} meta={`${formatDate(item.start_date)} - ${formatDate(item.end_date)}`} />
      )} validate={(values) => validateDates(values) || validateUrl(values.github_url, 'GitHub URL') || validateUrl(values.live_url, 'Live URL')} prepare={(values) => ({ ...compactPayload(values), technologies: toList(values.technologies) })} hydrate={(item) => ({ ...item, technologies: commaList(item.technologies) })} fields={(values, setValue) => (
        <>
          <Field label="Project Name" required value={values.name} onChange={(v) => setValue('name', v)} />
          <Field label="Technologies" value={values.technologies} onChange={(v) => setValue('technologies', v)} />
          <Field label="GitHub URL" value={values.github_url} onChange={(v) => setValue('github_url', v)} />
          <Field label="Live URL" value={values.live_url} onChange={(v) => setValue('live_url', v)} />
          <Field label="Start Date" type="date" value={values.start_date} onChange={(v) => setValue('start_date', v)} />
          <Field label="End Date" type="date" value={values.end_date} onChange={(v) => setValue('end_date', v)} />
          <Field label="Description" as="textarea" value={values.description} onChange={(v) => setValue('description', v)} />
        </>
      )} />

      <EditableListSection title="Certifications" icon={Award} items={profile.certifications} empty="No certifications added yet." formKey="certifications" emptyForm={emptyCertification} forms={forms} setForms={setForms} saving={saving} save={save} addFn={addCertification} updateFn={updateCertification} deleteFn={deleteCertification} renderItem={(item) => (
        <Entry item={item} title={item.name} subtitle={item.issuing_organization} meta={`${formatDate(item.issue_date)}${item.expiration_date ? ` - ${formatDate(item.expiration_date)}` : ''}`} />
      )} validate={(values) => validateDates(values, 'issue_date', 'expiration_date') || validateUrl(values.credential_url, 'Credential URL')} fields={(values, setValue) => (
        <>
          <Field label="Certification Name" required value={values.name} onChange={(v) => setValue('name', v)} />
          <Field label="Issuing Organization" required value={values.issuing_organization} onChange={(v) => setValue('issuing_organization', v)} />
          <Field label="Issue Date" type="date" value={values.issue_date} onChange={(v) => setValue('issue_date', v)} />
          <Field label="Expiration Date" type="date" value={values.expiration_date} onChange={(v) => setValue('expiration_date', v)} />
          <Field label="Credential ID" value={values.credential_id} onChange={(v) => setValue('credential_id', v)} />
          <Field label="Credential URL" value={values.credential_url} onChange={(v) => setValue('credential_url', v)} />
        </>
      )} />

      <Section title="Career Preferences" icon={Target}>
        <PreferenceForm
          preferences={profile.career_preferences}
          emptyPreferences={emptyPreferences}
          saving={saving}
          save={save}
          setError={setError}
        />
      </Section>
    </div>
  );
}

function ScoreRing({ score }) {
  const safeScore = Math.max(0, Math.min(100, Number(score) || 0));
  return (
    <div className="flex h-32 w-32 shrink-0 items-center justify-center rounded-full border border-accent/30 bg-accent/10">
      <div className="flex h-24 w-24 flex-col items-center justify-center rounded-full bg-slate-950/80">
        <span className="text-3xl font-extrabold text-white">{safeScore}</span>
        <span className="text-xs font-semibold uppercase tracking-wide text-accent">/ 100</span>
      </div>
    </div>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  if (!text || typeof navigator === 'undefined' || !navigator.clipboard) return null;
  return (
    <button
      type="button"
      title="Copy suggestion"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1200);
      }}
      className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-slate-200 transition hover:border-accent/40 hover:text-accent"
    >
      <Copy className="h-3.5 w-3.5" />
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
}

function ProfileOptimizationPanel({ optimization, loading, onRefresh }) {
  if (loading && !optimization) {
    return (
      <section className="rounded-[2rem] border border-accent/20 bg-accent/10 p-6 shadow-glow backdrop-blur-xl">
        <div className="flex items-center gap-3 text-white">
          <Loader2 className="h-5 w-5 animate-spin text-accent" />
          <div>
            <h2 className="text-lg font-bold">AI Profile Optimization</h2>
            <p className="mt-1 text-sm text-slate-300">Analyzing your profile quality and career positioning...</p>
          </div>
        </div>
      </section>
    );
  }

  if (!optimization) return null;

  return (
    <section className="rounded-[2rem] border border-accent/20 bg-white/[0.04] p-5 shadow-glow backdrop-blur-xl sm:p-6">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
          <ScoreRing score={optimization.overall_score} />
          <div>
            <div className="flex items-center gap-2 text-lg font-bold text-white">
              <Sparkles className="h-5 w-5 text-accent" />
              <h2>AI Profile Optimization</h2>
            </div>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">{optimization.summary}</p>
            <p className="mt-2 text-xs uppercase tracking-wide text-slate-500">AI Profile Quality Score</p>
          </div>
        </div>
        <ActionButton icon={loading ? Loader2 : Sparkles} variant="ghost" onClick={onRefresh} disabled={loading}>
          {loading ? 'Optimizing...' : 'Optimize Again'}
        </ActionButton>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-5">
          <div className="mb-3 flex items-center gap-2 font-semibold text-white">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            Strengths
          </div>
          <ul className="space-y-2 text-sm text-slate-300">
            {(optimization.strengths || []).map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
        <div className="rounded-2xl border border-white/10 bg-slate-950/50 p-5">
          <div className="mb-3 flex items-center gap-2 font-semibold text-white">
            <Zap className="h-4 w-4 text-accent" />
            Improvements
          </div>
          <ul className="space-y-2 text-sm text-slate-300">
            {(optimization.recommended_improvements || []).map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
      </div>

      <div className="mt-5 space-y-3">
        {(optimization.sections || []).map((section) => (
          <div key={section.section} className="rounded-2xl border border-white/10 bg-slate-950/50 p-5">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-semibold capitalize text-white">{section.section.replaceAll('_', ' ')}</h3>
                  <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-xs font-semibold text-slate-300">{section.score}/100</span>
                  <span className="rounded-full border border-accent/20 bg-accent/10 px-2.5 py-1 text-xs font-semibold capitalize text-accent">{section.status.replaceAll('_', ' ')}</span>
                </div>
                {section.current ? <p className="mt-3 text-xs uppercase tracking-wide text-slate-500">Current</p> : null}
                {section.current ? <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-300">{section.current}</p> : null}
              </div>
              <CopyButton text={section.suggestion} />
            </div>
            <p className="mt-4 text-xs uppercase tracking-wide text-slate-500">Suggestion</p>
            <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-white">{section.suggestion}</p>
            <p className="mt-3 text-sm leading-6 text-slate-400">{section.reason}</p>
          </div>
        ))}
      </div>

      {(optimization.suggested_skills_to_learn || []).length ? (
        <div className="mt-5 rounded-2xl border border-white/10 bg-slate-950/50 p-5">
          <div className="mb-3 flex items-center gap-2 font-semibold text-white">
            <Target className="h-4 w-4 text-accent" />
            Recommended Skills to Learn
          </div>
          <div className="flex flex-wrap gap-2">
            {optimization.suggested_skills_to_learn.map((skill) => (
              <span key={skill} className="rounded-full border border-accent/20 bg-accent/10 px-3 py-1 text-sm text-accent">{skill}</span>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function Entry({ item, title, subtitle, meta }) {
  return (
    <div>
      <h3 className="font-semibold text-white">{title}</h3>
      {subtitle ? <p className="mt-1 text-sm text-accent">{subtitle}</p> : null}
      <p className="mt-1 text-xs text-slate-500">{meta}</p>
      {item.description ? <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-300">{item.description}</p> : null}
    </div>
  );
}

function EditableListSection({ title, icon, items, empty, formKey, emptyForm, forms, setForms, saving, save, addFn, updateFn, deleteFn, renderItem, fields, validate, prepare, hydrate }) {
  const active = forms[formKey];
  const setActive = (next) => setForms({ ...forms, [formKey]: next });
  const close = () => {
    const next = { ...forms };
    delete next[formKey];
    setForms(next);
  };
  const values = active?.values || emptyForm;
  const setValue = (key, value) => setActive({ ...active, values: { ...values, [key]: value } });
  const submit = async (event) => {
    event.preventDefault();
    const validation = validate ? validate(values) : '';
    if (validation) return setActive({ ...active, error: validation });
    const payload = prepare ? prepare(values) : compactPayload(values);
    const ok = await save(async () => active?.id ? updateFn(active.id, payload) : addFn(payload));
    if (ok) close();
  };

  return (
    <Section title={title} icon={icon} action={<ActionButton onClick={() => setActive({ id: null, values: emptyForm })}>Add</ActionButton>}>
      <div className="space-y-4">
        {items.length ? items.map((item) => (
          <div key={item.id} className="rounded-2xl border border-white/10 bg-slate-950/50 p-5">
            <div className="flex items-start justify-between gap-3">
              {renderItem(item)}
              <div className="flex gap-2">
                <button type="button" title="Edit" onClick={() => setActive({ id: item.id, values: hydrate ? hydrate(item) : { ...item } })} className="rounded-full border border-white/10 p-2 text-slate-300 hover:border-accent/40 hover:text-accent"><Edit3 className="h-4 w-4" /></button>
                <button type="button" title="Delete" onClick={() => window.confirm(`Delete ${title.toLowerCase()} item?`) && save(() => deleteFn(item.id))} className="rounded-full border border-white/10 p-2 text-slate-300 hover:border-rose-500/40 hover:text-rose-300"><Trash2 className="h-4 w-4" /></button>
              </div>
            </div>
          </div>
        )) : <EmptyState text={empty} />}
      </div>
      {active ? (
        <form onSubmit={submit} className="mt-5 grid gap-4 rounded-2xl border border-white/10 bg-slate-950/50 p-5">
          {active.error ? <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-100">{active.error}</div> : null}
          <div className="grid gap-4 sm:grid-cols-2">{fields(values, setValue)}</div>
          <div className="flex flex-wrap gap-3">
            <ActionButton type="submit" icon={Save} disabled={saving}>Save</ActionButton>
            <ActionButton variant="ghost" icon={X} onClick={close}>Cancel</ActionButton>
          </div>
        </form>
      ) : null}
    </Section>
  );
}

function PreferenceForm({ preferences, emptyPreferences, saving, save, setError }) {
  const [editing, setEditing] = useState(false);
  const [values, setValues] = useState(emptyPreferences);

  useEffect(() => {
    setValues({
      target_job_role: preferences?.target_job_role || '',
      preferred_industry: preferences?.preferred_industry || '',
      preferred_work_type: preferences?.preferred_work_type || '',
      preferred_locations: commaList(preferences?.preferred_locations),
      career_interests: commaList(preferences?.career_interests),
    });
  }, [preferences]);

  const display = [
    ['Target Role', preferences?.target_job_role],
    ['Industry', preferences?.preferred_industry],
    ['Work Type', preferences?.preferred_work_type],
    ['Preferred Locations', commaList(preferences?.preferred_locations)],
    ['Interests', commaList(preferences?.career_interests)],
  ];

  if (!editing) {
    return (
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          {display.map(([label, value]) => (
            <div key={label} className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
              <p className="mt-1 text-sm font-semibold text-white">{value || 'Not set'}</p>
            </div>
          ))}
        </div>
        <ActionButton icon={Edit3} variant="ghost" onClick={() => setEditing(true)}>Edit Preferences</ActionButton>
      </div>
    );
  }

  const setValue = (key, value) => setValues({ ...values, [key]: value });
  return (
    <form
      className="grid gap-4"
      onSubmit={async (event) => {
        event.preventDefault();
        setError('');
        const ok = await save(async () => updateCareerPreferences({
          target_job_role: values.target_job_role || null,
          preferred_industry: values.preferred_industry || null,
          preferred_work_type: values.preferred_work_type || null,
          preferred_locations: toList(values.preferred_locations),
          career_interests: toList(values.career_interests),
        }));
        if (ok) setEditing(false);
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Target Job Role" value={values.target_job_role} onChange={(v) => setValue('target_job_role', v)} />
        <Field label="Preferred Industry" value={values.preferred_industry} onChange={(v) => setValue('preferred_industry', v)} />
        <Field label="Preferred Work Type" as="select" options={['Remote', 'Hybrid', 'On-site', 'Flexible']} value={values.preferred_work_type} onChange={(v) => setValue('preferred_work_type', v)} />
        <Field label="Preferred Locations" value={values.preferred_locations} onChange={(v) => setValue('preferred_locations', v)} />
        <Field label="Career Interests" value={values.career_interests} onChange={(v) => setValue('career_interests', v)} />
      </div>
      <div className="flex flex-wrap gap-3">
        <ActionButton type="submit" icon={Save} disabled={saving}>Save Preferences</ActionButton>
        <ActionButton variant="ghost" icon={X} onClick={() => setEditing(false)}>Cancel</ActionButton>
      </div>
    </form>
  );
}
