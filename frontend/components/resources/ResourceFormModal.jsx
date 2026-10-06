'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Loader2, Plus, X } from 'lucide-react';
import {
  CATEGORY_OPTIONS,
  RESOURCE_TYPE_OPTIONS,
  normalizeResourceTags,
} from '@/components/resources/resourceConstants';

const EMPTY_FORM = {
  title: '',
  description: '',
  url: '',
  resource_type: 'ARTICLE',
  category: 'frontend',
  tags: [],
};

function isValidUrl(value) {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol);
  } catch {
    return false;
  }
}

export default function ResourceFormModal({ open, mode = 'create', resource = null, onClose, onSubmit }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [tagInput, setTagInput] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    if (resource) {
      setForm({
        title: resource.title || '',
        description: resource.description || '',
        url: resource.url || '',
        resource_type: resource.resource_type || 'ARTICLE',
        category: resource.category || 'frontend',
        tags: normalizeResourceTags(resource.tags || []),
      });
    } else {
      setForm(EMPTY_FORM);
    }
    setTagInput('');
    setError('');
    setSubmitting(false);
  }, [open, resource]);

  const title = mode === 'edit' ? 'Edit resource' : 'Share a resource';
  const submitLabel = mode === 'edit' ? 'Save changes' : 'Share Resource';

  const canSubmit = useMemo(() => {
    return form.title.trim() && form.url.trim() && isValidUrl(form.url) && form.resource_type;
  }, [form.resource_type, form.title, form.url]);

  if (!open) return null;

  const updateField = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const addTag = () => {
    const tag = tagInput.trim();
    if (!tag) return;
    if (tag.length > 40) {
      setError('Tags must be 40 characters or fewer.');
      return;
    }
    const next = normalizeResourceTags([...form.tags, tag]);
    if (next.length > 8) {
      setError('Resources support at most 8 tags.');
      return;
    }
    setForm((prev) => ({ ...prev, tags: next }));
    setTagInput('');
    setError('');
  };

  const handleTagKeyDown = (event) => {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault();
      addTag();
    }
    if (event.key === 'Backspace' && !tagInput && form.tags.length > 0) {
      setForm((prev) => ({ ...prev, tags: prev.tags.slice(0, -1) }));
    }
  };

  const removeTag = (tag) => {
    setForm((prev) => ({ ...prev, tags: prev.tags.filter((item) => item.toLowerCase() !== tag.toLowerCase()) }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!form.title.trim()) {
      setError('Title is required.');
      return;
    }
    if (!isValidUrl(form.url)) {
      setError('Enter a valid http(s) URL.');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      await onSubmit({
        title: form.title.trim(),
        description: form.description.trim() || null,
        url: form.url.trim(),
        resource_type: form.resource_type,
        category: form.category || null,
        tags: normalizeResourceTags(form.tags),
      });
      onClose();
    } catch (err) {
      setError(err?.message || 'Unable to save resource.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={title}>
      <button type="button" aria-label="Close resource form" onClick={onClose} className="absolute inset-0 cursor-default bg-slate-950/75 backdrop-blur-sm" />
      <form onSubmit={handleSubmit} className="relative max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-[2rem] border border-white/10 bg-slate-950 p-6 shadow-[0_30px_80px_rgba(0,0,0,0.58)]">
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-white">{title}</h2>
            <p className="mt-1 text-sm text-slate-400">Add a useful article, course, tool, repo, or tutorial for the CareerSphere community.</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-full p-2 text-slate-400 hover:bg-white/10 hover:text-white" aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>

        {error && (
          <div className="mb-4 flex items-start gap-2 rounded-2xl border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-100" role="alert">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="grid gap-4">
          <label className="grid gap-2 text-sm font-semibold text-slate-200">
            Title
            <input
              value={form.title}
              onChange={(event) => updateField('title', event.target.value)}
              maxLength={180}
              className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-white outline-none focus:border-accent/45"
              placeholder="e.g. The FastAPI deployment checklist"
              required
            />
          </label>

          <label className="grid gap-2 text-sm font-semibold text-slate-200">
            URL
            <input
              value={form.url}
              onChange={(event) => updateField('url', event.target.value)}
              className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-white outline-none focus:border-accent/45"
              placeholder="https://..."
              required
            />
          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="grid gap-2 text-sm font-semibold text-slate-200">
              Resource type
              <select
                value={form.resource_type}
                onChange={(event) => updateField('resource_type', event.target.value)}
                className="rounded-2xl border border-white/10 bg-slate-950 px-4 py-3 text-white outline-none focus:border-accent/45"
              >
                {RESOURCE_TYPE_OPTIONS.map((item) => (
                  <option key={item.id} value={item.id}>{item.label}</option>
                ))}
              </select>
            </label>

            <label className="grid gap-2 text-sm font-semibold text-slate-200">
              Category
              <select
                value={form.category}
                onChange={(event) => updateField('category', event.target.value)}
                className="rounded-2xl border border-white/10 bg-slate-950 px-4 py-3 text-white outline-none focus:border-accent/45"
              >
                {CATEGORY_OPTIONS.map((item) => (
                  <option key={item.id} value={item.id}>{item.label}</option>
                ))}
              </select>
            </label>
          </div>

          <label className="grid gap-2 text-sm font-semibold text-slate-200">
            Description
            <textarea
              value={form.description}
              onChange={(event) => updateField('description', event.target.value)}
              rows={4}
              maxLength={1200}
              className="resize-none rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-white outline-none focus:border-accent/45"
              placeholder="What makes this resource useful?"
            />
          </label>

          <div className="grid gap-2 text-sm font-semibold text-slate-200">
            Tags
            <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-3 focus-within:border-accent/45">
              <div className="flex flex-wrap gap-2">
                {form.tags.map((tag) => (
                  <span key={tag.toLowerCase()} className="inline-flex items-center gap-1 rounded-full border border-accent/25 bg-accent/10 px-3 py-1 text-xs font-semibold text-accent">
                    {tag}
                    <button type="button" onClick={() => removeTag(tag)} aria-label={`Remove ${tag}`} className="text-accent/70 hover:text-white">
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
                <input
                  value={tagInput}
                  onChange={(event) => setTagInput(event.target.value)}
                  onBlur={addTag}
                  onKeyDown={handleTagKeyDown}
                  className="min-w-[140px] flex-1 bg-transparent px-1 py-1 text-sm text-white outline-none placeholder:text-slate-500"
                  placeholder="Add tag and press Enter"
                />
              </div>
            </div>
            <p className="text-xs font-normal text-slate-500">Up to 8 tags. Duplicate tags are ignored case-insensitively.</p>
          </div>
        </div>

        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button type="button" onClick={onClose} className="rounded-full border border-white/10 px-5 py-2.5 text-sm font-semibold text-slate-200 hover:text-white">
            Cancel
          </button>
          <button
            type="submit"
            disabled={!canSubmit || submitting}
            className="inline-flex items-center justify-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-black hover:bg-accentSoft disabled:opacity-60"
          >
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            {submitLabel}
          </button>
        </div>
      </form>
    </div>
  );
}
