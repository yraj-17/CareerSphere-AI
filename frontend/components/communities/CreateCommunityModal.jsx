'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Loader2, Plus, X } from 'lucide-react';
import { COMMUNITY_CATEGORIES } from '@/components/communities/communityConstants';

const MAX_NAME = 80;
const MAX_DESCRIPTION = 500;
const MAX_TAGS = 8;

const normalizeTagKey = (tag) => tag.trim().toLowerCase();

const uniqueTags = (rawTags) => {
  const seen = new Set();
  const nextTags = [];

  rawTags.forEach((rawTag) => {
    const tag = rawTag.trim();
    if (!tag) return;

    const tagKey = normalizeTagKey(tag);
    if (seen.has(tagKey)) return;

    seen.add(tagKey);
    nextTags.push(tag);
  });

  return nextTags.slice(0, MAX_TAGS);
};

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
      uniqueTags(form.tagsText.split(',')),
    [form.tagsText]
  );
  const renderedTags = useMemo(() => uniqueTags(tags), [tags]);

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
        className="absolute inset-0 cursor-default bg-black/30 backdrop-blur-sm"
        aria-label="Close modal"
        onClick={() => !submitting && onClose()}
      />
      <form
        onSubmit={handleSubmit}
        className="relative flex max-h-[calc(100vh-2rem)] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[var(--shadow-popover)]"
      >
        <div className="shrink-0 border-b border-slate-200 p-5 sm:p-7 sm:pb-5">
          <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">Create Community</h2>
            <p className="mt-1 text-sm text-slate-500">Prepare a professional space around a shared interest.</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            aria-label="Close"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-slate-50 text-slate-500 hover:bg-slate-100 hover:text-slate-800 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
          >
            <X className="h-5 w-5" />
          </button>
          </div>
        </div>

        <div className="scrollbar-hidden min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-7">
          {submitError && (
            <div role="alert" className="mb-5 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{submitError}</span>
            </div>
          )}

          <div className="space-y-5">
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Community Name</span>
            <input
              value={form.name}
              onChange={(event) => updateField('name', event.target.value)}
              maxLength={MAX_NAME + 1}
              className="input-base mt-2"
              placeholder="AI & Machine Learning"
            />
            {errors.name && <span className="mt-1 block text-xs text-red-700">{errors.name}</span>}
          </label>

          <label className="block">
            <span className="text-sm font-medium text-slate-700">Description</span>
            <textarea
              value={form.description}
              onChange={(event) => updateField('description', event.target.value)}
              maxLength={MAX_DESCRIPTION + 1}
              rows={4}
              className="input-base mt-2 resize-y"
              placeholder="Describe who this community is for and what members discuss."
            />
            <div className="mt-1 flex justify-between gap-3 text-xs">
              <span className="text-red-700">{errors.description}</span>
              <span className="text-slate-500">{form.description.length}/{MAX_DESCRIPTION}</span>
            </div>
          </label>

          <label className="block">
            <span className="text-sm font-medium text-slate-700">Category</span>
            <select
              value={form.category}
              onChange={(event) => updateField('category', event.target.value)}
              className="input-base mt-2"
            >
              {COMMUNITY_CATEGORIES.filter((category) => category.id !== 'all').map((category) => (
                <option key={category.id} value={category.id}>
                  {category.label}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm font-medium text-slate-700">Topics / Tags</span>
            <input
              value={form.tagsText}
              onChange={(event) => updateField('tagsText', event.target.value)}
              className="input-base mt-2"
              placeholder="Python, AI, RAG"
            />
            {renderedTags.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {renderedTags.map((tag) => (
                  <span key={normalizeTagKey(tag)} className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
                    <Plus className="h-3 w-3" />
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </label>

          <fieldset>
            <legend className="text-sm font-medium text-slate-700">Visibility</legend>
            <div className="mt-2 grid gap-3 sm:grid-cols-2">
              {['public', 'private'].map((visibility) => (
                <label
                  key={visibility}
                  className={`flex cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 text-sm capitalize transition-all ${
                    form.visibility === visibility
                      ? 'border-brand-200 bg-brand-50 text-brand-600'
                      : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  <input
                    type="radio"
                    name="visibility"
                    value={visibility}
                    checked={form.visibility === visibility}
                    onChange={(event) => updateField('visibility', event.target.value)}
                    className="accent-blue-700"
                  />
                  {visibility}
                </label>
              ))}
            </div>
          </fieldset>
          </div>
        </div>

        <div className="shrink-0 flex flex-col-reverse gap-3 border-t border-slate-200 p-5 sm:flex-row sm:justify-end sm:px-7">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="btn-outline"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="btn-primary"
          >
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Create Community
          </button>
        </div>
      </form>
    </div>
  );
}
