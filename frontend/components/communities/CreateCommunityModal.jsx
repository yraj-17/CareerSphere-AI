'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Loader2, Plus, X } from 'lucide-react';
import { COMMUNITY_CATEGORIES } from '@/components/communities/communityConstants';

const MAX_NAME = 80;
const MAX_DESCRIPTION = 500;

export default function CreateCommunityModal({ open, onClose, onSubmit }) {
  const [form, setForm] = useState({
    name: '',
    description: '',
    category: 'technology',
    tagsText: '',
    visibility: 'public',
  });
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');

  useEffect(() => {
    if (!open) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleKeyDown = (event) => {
      if (event.key === 'Escape' && !submitting) onClose();
    };
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [onClose, open, submitting]);

  const tags = useMemo(
    () =>
      form.tagsText
        .split(',')
        .map((tag) => tag.trim())
        .filter(Boolean)
        .slice(0, 8),
    [form.tagsText]
  );

  if (!open) return null;

  const updateField = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: '' }));
    setSubmitError('');
  };

  const validate = () => {
    const nextErrors = {};
    if (!form.name.trim()) nextErrors.name = 'Community name is required.';
    if (form.name.trim().length > MAX_NAME) nextErrors.name = `Keep the name under ${MAX_NAME} characters.`;
    if (!form.description.trim()) nextErrors.description = 'Description is required.';
    if (form.description.trim().length > MAX_DESCRIPTION) {
      nextErrors.description = `Keep the description under ${MAX_DESCRIPTION} characters.`;
    }
    if (!form.category) nextErrors.category = 'Choose a category.';
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!validate()) return;

    setSubmitting(true);
    setSubmitError('');
    try {
      await onSubmit({
        name: form.name.trim(),
        description: form.description.trim(),
        category: form.category,
        tags,
        visibility: form.visibility,
      });
      setForm({ name: '', description: '', category: 'technology', tagsText: '', visibility: 'public' });
      onClose();
    } catch (error) {
      setSubmitError(error?.message || 'Community creation is not available yet.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Create Community">
      <button
        type="button"
        className="absolute inset-0 cursor-default bg-slate-950/75 backdrop-blur-sm"
        aria-label="Close modal"
        onClick={() => !submitting && onClose()}
      />
      <form
        onSubmit={handleSubmit}
        className="relative max-h-[calc(100vh-2rem)] w-full max-w-2xl overflow-y-auto rounded-3xl border border-white/10 bg-slate-950 p-5 shadow-[0_24px_80px_rgba(0,0,0,0.62)] sm:p-7"
      >
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-white">Create Community</h2>
            <p className="mt-1 text-sm text-slate-400">Prepare a professional space around a shared interest.</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            aria-label="Close"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-slate-300 hover:text-white disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {submitError && (
          <div role="alert" className="mb-5 flex items-start gap-3 rounded-2xl border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{submitError}</span>
          </div>
        )}

        <div className="space-y-5">
          <label className="block">
            <span className="text-sm font-medium text-slate-200">Community Name</span>
            <input
              value={form.name}
              onChange={(event) => updateField('name', event.target.value)}
              maxLength={MAX_NAME + 1}
              className="mt-2 w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-white outline-none transition-all placeholder:text-slate-500 focus:border-accent/45 focus:ring-1 focus:ring-accent/25"
              placeholder="AI & Machine Learning"
            />
            {errors.name && <span className="mt-1 block text-xs text-rose-300">{errors.name}</span>}
          </label>

          <label className="block">
            <span className="text-sm font-medium text-slate-200">Description</span>
            <textarea
              value={form.description}
              onChange={(event) => updateField('description', event.target.value)}
              maxLength={MAX_DESCRIPTION + 1}
              rows={4}
              className="mt-2 w-full resize-none rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-white outline-none transition-all placeholder:text-slate-500 focus:border-accent/45 focus:ring-1 focus:ring-accent/25"
              placeholder="Describe who this community is for and what members discuss."
            />
            <div className="mt-1 flex justify-between gap-3 text-xs">
              <span className="text-rose-300">{errors.description}</span>
              <span className="text-slate-500">{form.description.length}/{MAX_DESCRIPTION}</span>
            </div>
          </label>

          <label className="block">
            <span className="text-sm font-medium text-slate-200">Category</span>
            <select
              value={form.category}
              onChange={(event) => updateField('category', event.target.value)}
              className="mt-2 w-full rounded-2xl border border-white/10 bg-slate-900 px-4 py-3 text-sm text-white outline-none transition-all focus:border-accent/45 focus:ring-1 focus:ring-accent/25"
            >
              {COMMUNITY_CATEGORIES.filter((category) => category.id !== 'all').map((category) => (
                <option key={category.id} value={category.id}>
                  {category.label}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm font-medium text-slate-200">Topics / Tags</span>
            <input
              value={form.tagsText}
              onChange={(event) => updateField('tagsText', event.target.value)}
              className="mt-2 w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-white outline-none transition-all placeholder:text-slate-500 focus:border-accent/45 focus:ring-1 focus:ring-accent/25"
              placeholder="Python, AI, RAG"
            />
            {tags.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {tags.map((tag) => (
                  <span key={tag} className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.06] px-2.5 py-1 text-xs text-slate-300">
                    <Plus className="h-3 w-3" />
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </label>

          <fieldset>
            <legend className="text-sm font-medium text-slate-200">Visibility</legend>
            <div className="mt-2 grid gap-3 sm:grid-cols-2">
              {['public', 'private'].map((visibility) => (
                <label
                  key={visibility}
                  className={`flex cursor-pointer items-center gap-3 rounded-2xl border px-4 py-3 text-sm capitalize transition-all ${
                    form.visibility === visibility
                      ? 'border-accent/35 bg-accent/10 text-accent'
                      : 'border-white/10 bg-white/[0.04] text-slate-300 hover:bg-white/[0.06]'
                  }`}
                >
                  <input
                    type="radio"
                    name="visibility"
                    value={visibility}
                    checked={form.visibility === visibility}
                    onChange={(event) => updateField('visibility', event.target.value)}
                    className="accent-orange-400"
                  />
                  {visibility}
                </label>
              ))}
            </div>
          </fieldset>
        </div>

        <div className="mt-7 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="rounded-full border border-white/10 px-5 py-2.5 text-sm font-medium text-slate-200 transition-colors hover:border-white/25 hover:text-white disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center justify-center gap-2 rounded-full bg-accent px-6 py-2.5 text-sm font-semibold text-black shadow-[0_8px_30px_rgba(255,143,50,0.28)] transition-colors hover:bg-accentSoft disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Create Community
          </button>
        </div>
      </form>
    </div>
  );
}
