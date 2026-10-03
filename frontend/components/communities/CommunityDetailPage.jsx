'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import {
  AlertCircle,
  Camera,
  Check,
  Image as ImageIcon,
  Loader2,
  MessageCircle,
  MoreVertical,
  RefreshCw,
  Send,
  Share2,
  Tag,
  Trash2,
  Users,
  X,
} from 'lucide-react';
import {
  createCommunityPost,
  createCommunityPostComment,
  deleteCommunityPost,
  extractErrorMessage,
  getCommunity,
  joinCommunity,
  leaveCommunity,
  listCommunityPostComments,
  listCommunityMembers,
  listCommunityPosts,
  removeCommunityImage,
  setCommunityPostReaction,
  uploadCommunityImage,
} from '@/services/api';
import {
  CATEGORY_LABELS,
  normalizeCommunityPostComments,
  normalizeCommunityMembers,
  normalizeCommunityPosts,
} from '@/components/communities/communityConstants';

const REACTIONS = [
  { type: 'LIKE', label: 'Like', emoji: '👍' },
  { type: 'LOVE', label: 'Love', emoji: '❤️' },
  { type: 'CELEBRATE', label: 'Celebrate', emoji: '🎉' },
  { type: 'SUPPORT', label: 'Support', emoji: '🤝' },
  { type: 'INSIGHTFUL', label: 'Insightful', emoji: '💡' },
  { type: 'FUNNY', label: 'Funny', emoji: '😂' },
];

const REACTION_BY_TYPE = REACTIONS.reduce((acc, reaction) => {
  acc[reaction.type] = reaction;
  return acc;
}, {});

const MAX_POST_IMAGES = 4;
const MAX_POST_IMAGE_MB = 5;
const MAX_POST_TAGS = 5;
const MAX_POST_TAG_LENGTH = 30;
const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_COMMUNITY_IMAGE_MB = 5;

function isEndpointMissing(error) {
  return [404, 405, 501].includes(error?.response?.status);
}

function getId(item) {
  return item?.id ?? item?.community_id;
}

function getInitials(name = 'Community') {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase() || 'CS';
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6" data-testid="community-detail-loading">
      <div className="h-56 animate-pulse rounded-[2.5rem] border border-white/10 bg-white/[0.05]" />
      <div className="h-72 animate-pulse rounded-3xl border border-white/10 bg-white/[0.04]" />
    </div>
  );
}

function EmptyPanel({ title, description }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.035] px-6 py-16 text-center" data-testid="community-empty-panel">
      <p className="text-base font-bold text-white">{title}</p>
      <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-slate-400">{description}</p>
    </div>
  );
}

// ── Post image grid ─────────────────────────────────────────────────────────

function PostImageGrid({ media }) {
  const [lightboxUrl, setLightboxUrl] = useState(null);
  if (!media || media.length === 0) return null;

  const gridClass =
    media.length === 1
      ? 'grid grid-cols-1'
      : media.length === 2
      ? 'grid grid-cols-2 gap-1'
      : media.length === 3
      ? 'grid grid-cols-2 gap-1'
      : 'grid grid-cols-2 gap-1';

  return (
    <>
      <div className={`mt-3 overflow-hidden rounded-2xl ${gridClass}`}>
        {media.map((item, idx) => (
          <button
            key={item.id || idx}
            type="button"
            aria-label={`View image ${idx + 1}`}
            onClick={() => setLightboxUrl(item.url)}
            className={`relative block overflow-hidden bg-slate-900 ${
              media.length === 3 && idx === 0 ? 'row-span-2' : ''
            }`}
            style={{ aspectRatio: media.length === 1 ? '16/9' : '1/1' }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={item.url}
              alt={`Post image ${idx + 1}`}
              className="h-full w-full object-cover transition-transform hover:scale-[1.02]"
              loading="lazy"
            />
          </button>
        ))}
      </div>

      {lightboxUrl && (
        <div
          className="fixed inset-0 z-[80] flex items-center justify-center bg-black/85 backdrop-blur-sm"
          onClick={() => setLightboxUrl(null)}
          role="dialog"
          aria-modal="true"
          aria-label="Image preview"
        >
          <button
            type="button"
            aria-label="Close preview"
            className="absolute right-4 top-4 flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20"
            onClick={() => setLightboxUrl(null)}
          >
            <X className="h-5 w-5" />
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={lightboxUrl}
            alt="Full size preview"
            className="max-h-[90vh] max-w-[90vw] rounded-2xl object-contain shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  );
}

// ── Post tags display ────────────────────────────────────────────────────────

function PostTagList({ tags }) {
  if (!tags || tags.length === 0) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-1.5">
      {tags.map((tag) => (
        <span
          key={tag}
          className="inline-block rounded-full border border-accent/20 bg-accent/8 px-2.5 py-0.5 text-xs font-medium text-accent/80"
        >
          #{tag}
        </span>
      ))}
    </div>
  );
}

// ── PostCard ─────────────────────────────────────────────────────────────────

function PostCard({ post, onReactionUpdated, onCommentCreated, onDeleted, onError }) {
  const author = post.author || post.user || {};
  const authorName = [author.first_name, author.last_name].filter(Boolean).join(' ') || author.name || 'Community member';
  const [reactionOpen, setReactionOpen] = useState(false);
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [comments, setComments] = useState([]);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [commentsError, setCommentsError] = useState('');
  const [commentText, setCommentText] = useState('');
  const [commentSubmitting, setCommentSubmitting] = useState(false);
  const [shareStatus, setShareStatus] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const activeReaction = REACTION_BY_TYPE[post.my_reaction] || null;
  const reactionLabel = activeReaction ? activeReaction.label : 'Like';
  const reactionEmoji = activeReaction ? activeReaction.emoji : '👍';
  const reactionTotal = post.total_reactions ?? post.like_count ?? 0;
  const commentCount = post.comment_count ?? comments.length ?? 0;
  const media = post.media || [];
  const tags = post.tags || [];

  const loadComments = async () => {
    setCommentsLoading(true);
    setCommentsError('');
    try {
      const payload = await listCommunityPostComments(post.id);
      setComments(normalizeCommunityPostComments(payload));
    } catch (err) {
      setCommentsError(extractErrorMessage(err) || 'Unable to load comments.');
    } finally {
      setCommentsLoading(false);
    }
  };

  const handleToggleComments = async () => {
    const nextOpen = !commentsOpen;
    setCommentsOpen(nextOpen);
    if (nextOpen && comments.length === 0) await loadComments();
  };

  const handleReaction = async (reactionType) => {
    setReactionOpen(false);
    try {
      const summary = await setCommunityPostReaction(post.id, reactionType);
      onReactionUpdated(post.id, summary);
    } catch (err) {
      onError(extractErrorMessage(err) || 'Unable to update reaction.');
    }
  };

  const handleSubmitComment = async (event) => {
    event.preventDefault();
    const content = commentText.trim();
    if (!content) return;
    setCommentSubmitting(true);
    setCommentsError('');
    try {
      const comment = await createCommunityPostComment(post.id, { content });
      setComments((prev) => [...prev, comment]);
      setCommentText('');
      onCommentCreated(post.id, comment);
    } catch (err) {
      setCommentsError(extractErrorMessage(err) || 'Unable to post comment.');
    } finally {
      setCommentSubmitting(false);
    }
  };

  const postUrl = () => {
    const path = `/dashboard/communities/${post.community_id}?post=${post.id}`;
    if (typeof window === 'undefined') return path;
    return `${window.location.origin}${path}`;
  };

  const handleShare = async () => {
    const url = postUrl();
    setShareStatus('');
    try {
      if (navigator?.share) {
        await navigator.share({ title: 'CareerSphere community post', text: post.content || '', url });
        setShareStatus('Shared');
      } else if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
        setShareStatus('Link copied');
      } else {
        setShareStatus(url);
      }
    } catch (err) {
      if (err?.name !== 'AbortError') setShareStatus('Unable to share');
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await deleteCommunityPost(post.id);
      onDeleted(post.id);
      setConfirmDelete(false);
    } catch (err) {
      onError(extractErrorMessage(err) || 'Unable to delete post.');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <article id={`community-post-${post.id}`} className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
      <div className="mb-4 flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-accent/30 bg-accent/10 text-xs font-bold text-accent">
          {getInitials(authorName)}
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-white">{authorName}</p>
          <p className="text-xs text-slate-500">{post.created_at || post.timestamp || 'Recently'}</p>
        </div>
        {post.can_delete && (
          <div className="relative">
            <button
              type="button"
              aria-label="Post options"
              onClick={() => setMenuOpen((value) => !value)}
              className="rounded-full p-1.5 text-slate-400 hover:bg-white/[0.06] hover:text-white"
            >
              <MoreVertical className="h-4 w-4" />
            </button>
            {menuOpen && (
              <div className="absolute right-0 top-8 z-20 w-32 rounded-2xl border border-white/10 bg-slate-950 p-1 shadow-[0_18px_60px_rgba(0,0,0,0.45)]">
                <button
                  type="button"
                  onClick={() => {
                    setMenuOpen(false);
                    setConfirmDelete(true);
                  }}
                  className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm text-rose-200 hover:bg-rose-500/10"
                >
                  <Trash2 className="h-4 w-4" /> Delete
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Post content text */}
      {post.content && (
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-200">{post.content}</p>
      )}

      {/* Post images */}
      <PostImageGrid media={media} />

      {/* Post topic tags */}
      <PostTagList tags={tags} />

      <div hidden>
        <button type="button" className="hover:text-white">♡ {post.like_count ?? 0}</button>
        <button type="button" className="inline-flex items-center gap-1 hover:text-white">
          <MessageCircle className="h-4 w-4" /> {post.comment_count ?? 0}
        </button>
        <button type="button" className="inline-flex items-center gap-1 hover:text-white">
          <Share2 className="h-4 w-4" /> Share
        </button>
      </div>
      <div className="mt-5 flex flex-wrap gap-4 text-sm text-slate-400">
        <div className="relative">
          <button
            type="button"
            onClick={() => setReactionOpen((value) => !value)}
            className={`inline-flex items-center gap-1 hover:text-white ${activeReaction ? 'text-accent' : ''}`}
          >
            <span aria-hidden="true">{reactionEmoji}</span> {reactionLabel} {reactionTotal}
          </button>
          {reactionOpen && (
            <div className="absolute bottom-8 left-0 z-20 flex flex-wrap gap-1 rounded-2xl border border-white/10 bg-slate-950 p-2 shadow-[0_18px_60px_rgba(0,0,0,0.45)] sm:flex-nowrap">
              {REACTIONS.map((reaction) => (
                <button
                  key={reaction.type}
                  type="button"
                  onClick={() => handleReaction(reaction.type)}
                  className={`flex items-center gap-1 rounded-xl px-2.5 py-1.5 text-xs transition-colors hover:bg-white/[0.08] ${
                    post.my_reaction === reaction.type ? 'bg-accent/15 text-accent' : 'text-slate-200'
                  }`}
                  title={reaction.label}
                >
                  <span aria-hidden="true">{reaction.emoji}</span>
                  <span>{reaction.label}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <button type="button" onClick={handleToggleComments} className="inline-flex items-center gap-1 hover:text-white">
          <MessageCircle className="h-4 w-4" /> {commentCount}
        </button>
        <button type="button" onClick={handleShare} className="inline-flex items-center gap-1 hover:text-white">
          <Share2 className="h-4 w-4" /> Share
        </button>
        {shareStatus && <span className="text-xs text-emerald-300">{shareStatus}</span>}
      </div>

      {commentsOpen && (
        <div className="mt-5 border-t border-white/10 pt-4">
          <h3 className="text-sm font-semibold text-white">Comments</h3>
          {commentsLoading ? (
            <div className="mt-3 h-16 animate-pulse rounded-2xl bg-white/[0.04]" />
          ) : commentsError ? (
            <p className="mt-3 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">{commentsError}</p>
          ) : comments.length === 0 ? (
            <p className="mt-3 rounded-2xl border border-white/10 bg-white/[0.035] px-3 py-3 text-sm text-slate-400">No comments yet.</p>
          ) : (
            <div className="mt-3 space-y-3">
              {comments.map((comment) => {
                const commentAuthor = comment.author || {};
                const commentAuthorName = [commentAuthor.first_name, commentAuthor.last_name].filter(Boolean).join(' ') || commentAuthor.username || 'Community member';
                return (
                  <div key={comment.id} className="rounded-2xl border border-white/10 bg-white/[0.035] px-3 py-3">
                    <p className="text-xs font-semibold text-white">{commentAuthorName}</p>
                    <p className="mt-1 whitespace-pre-wrap text-sm text-slate-300">{comment.content}</p>
                  </div>
                );
              })}
            </div>
          )}
          <form onSubmit={handleSubmitComment} className="mt-4 flex flex-col gap-2 sm:flex-row">
            <input
              value={commentText}
              onChange={(event) => setCommentText(event.target.value)}
              placeholder="Write a comment..."
              className="min-w-0 flex-1 rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-2.5 text-sm text-white outline-none placeholder:text-slate-500 focus:border-accent/45 focus:ring-1 focus:ring-accent/25"
            />
            <button
              type="submit"
              disabled={commentSubmitting || !commentText.trim()}
              className="inline-flex items-center justify-center gap-2 rounded-full bg-accent px-4 py-2 text-sm font-semibold text-black hover:bg-accentSoft disabled:opacity-60"
            >
              {commentSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Post
            </button>
          </form>
        </div>
      )}

      {confirmDelete && (
        <div className="fixed inset-0 z-[75] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Delete post">
          <button type="button" aria-label="Cancel delete" onClick={() => setConfirmDelete(false)} className="absolute inset-0 cursor-default bg-slate-950/75 backdrop-blur-sm" />
          <div className="relative w-full max-w-sm rounded-3xl border border-white/10 bg-slate-950 p-6 shadow-[0_24px_70px_rgba(0,0,0,0.58)]">
            <h2 className="text-base font-bold text-white">Delete this post?</h2>
            <p className="mt-2 text-sm text-slate-400">This action cannot be undone.</p>
            <div className="mt-6 flex justify-end gap-3">
              <button type="button" onClick={() => setConfirmDelete(false)} disabled={deleting} className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-200 hover:text-white disabled:opacity-60">
                Cancel
              </button>
              <button type="button" onClick={handleDelete} disabled={deleting} className="inline-flex items-center gap-2 rounded-full bg-rose-500 px-5 py-2 text-sm font-semibold text-white hover:bg-rose-600 disabled:opacity-60">
                {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </article>
  );
}

// ── PostComposer with image + tag support ─────────────────────────────────────

function PostComposer({ joined, onSubmit, disabled }) {
  const [content, setContent] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Images
  const [images, setImages] = useState([]); // Array of { file: File, previewUrl: string }
  const imageInputRef = useRef(null);

  // Tags
  const [tagInput, setTagInput] = useState('');
  const [tags, setTags] = useState([]);
  const [tagError, setTagError] = useState('');

  if (!joined) return null;

  // ── Image helpers ──

  const handleImageSelect = (event) => {
    const files = Array.from(event.target.files || []);
    const remaining = MAX_POST_IMAGES - images.length;
    const toAdd = files.slice(0, remaining);
    const newImages = [];
    let newError = '';

    for (const file of toAdd) {
      if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
        newError = `"${file.name}" is not a supported image type. Use JPEG, PNG, or WebP.`;
        break;
      }
      if (file.size > MAX_POST_IMAGE_MB * 1024 * 1024) {
        newError = `"${file.name}" exceeds the ${MAX_POST_IMAGE_MB} MB limit.`;
        break;
      }
      newImages.push({ file, previewUrl: URL.createObjectURL(file) });
    }

    if (newError) {
      setError(newError);
    } else {
      setImages((prev) => [...prev, ...newImages]);
    }

    // Reset input so same file can be re-selected after removal
    if (imageInputRef.current) imageInputRef.current.value = '';
  };

  const handleRemoveImage = (index) => {
    setImages((prev) => {
      const next = [...prev];
      URL.revokeObjectURL(next[index].previewUrl);
      next.splice(index, 1);
      return next;
    });
  };

  // ── Tag helpers ──

  const addTag = () => {
    const raw = tagInput.trim().replace(/^#+/, '');
    if (!raw) return;
    if (raw.length > MAX_POST_TAG_LENGTH) {
      setTagError(`Tag must be ${MAX_POST_TAG_LENGTH} characters or fewer.`);
      return;
    }
    if (tags.some((t) => t.toLowerCase() === raw.toLowerCase())) {
      setTagError('That tag is already added.');
      return;
    }
    if (tags.length >= MAX_POST_TAGS) {
      setTagError(`Maximum ${MAX_POST_TAGS} tags allowed.`);
      return;
    }
    setTags((prev) => [...prev, raw]);
    setTagInput('');
    setTagError('');
  };

  const handleTagKeyDown = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      addTag();
    }
  };

  const handleRemoveTag = (index) => {
    setTags((prev) => prev.filter((_, i) => i !== index));
  };

  // ── Submit ──

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setSuccess('');
    setTagError('');
    const trimmedContent = content.trim();
    if (!trimmedContent && images.length === 0) {
      setError('Write something or add at least one image before posting.');
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit({ content: trimmedContent, tags, images: images.map((i) => i.file) });
      // Cleanup previews
      images.forEach((i) => URL.revokeObjectURL(i.previewUrl));
      setContent('');
      setImages([]);
      setTags([]);
      setTagInput('');
      setSuccess('Post submitted.');
    } catch (err) {
      setError(err?.message || 'Unable to create post.');
    } finally {
      setSubmitting(false);
    }
  };

  const hasContent = content.trim() || images.length > 0;

  return (
    <form onSubmit={handleSubmit} className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
      <label className="block">
        <span className="text-sm font-semibold text-white">What&apos;s on your mind?</span>
        <textarea
          value={content}
          onChange={(event) => setContent(event.target.value)}
          disabled={disabled || submitting}
          rows={3}
          placeholder="Write a post..."
          className="mt-3 w-full resize-none rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-accent/45 focus:ring-1 focus:ring-accent/25 disabled:opacity-60"
        />
      </label>

      {/* Image previews */}
      {images.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {images.map((img, idx) => (
            <div key={idx} className="relative h-20 w-20 overflow-hidden rounded-xl border border-white/10">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={img.previewUrl} alt={`Selected image ${idx + 1}`} className="h-full w-full object-cover" />
              <button
                type="button"
                aria-label={`Remove image ${idx + 1}`}
                onClick={() => handleRemoveImage(idx)}
                className="absolute right-0.5 top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-black/70 text-white hover:bg-black"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Tag chips */}
      {tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {tags.map((tag, idx) => (
            <span key={idx} className="inline-flex items-center gap-1 rounded-full border border-accent/25 bg-accent/10 px-2.5 py-0.5 text-xs text-accent">
              #{tag}
              <button
                type="button"
                aria-label={`Remove tag ${tag}`}
                onClick={() => handleRemoveTag(idx)}
                className="ml-0.5 rounded-full hover:text-white"
              >
                <X className="h-2.5 w-2.5" />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Tag input */}
      <div className="mt-3 flex gap-2">
        <div className="relative flex-1">
          <Tag className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
          <input
            value={tagInput}
            onChange={(e) => { setTagInput(e.target.value); setTagError(''); }}
            onKeyDown={handleTagKeyDown}
            placeholder="Add topic tag"
            disabled={disabled || submitting || tags.length >= MAX_POST_TAGS}
            className="w-full rounded-2xl border border-white/10 bg-slate-950/40 py-2 pl-8 pr-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-accent/45 focus:ring-1 focus:ring-accent/25 disabled:opacity-50"
          />
        </div>
        <button
          type="button"
          onClick={addTag}
          disabled={!tagInput.trim() || tags.length >= MAX_POST_TAGS || disabled || submitting}
          className="rounded-full border border-white/10 px-3 py-2 text-xs text-slate-300 hover:border-accent/30 hover:text-accent disabled:opacity-40"
        >
          Add
        </button>
      </div>
      {tagError && <p className="mt-1 text-xs text-rose-300">{tagError}</p>}

      {(error || success) && (
        <p className={`mt-2 text-sm ${error ? 'text-rose-300' : 'text-emerald-300'}`} role="status">
          {error || success}
        </p>
      )}

      <div className="mt-4 flex items-center justify-between gap-3">
        {/* Image add button */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => imageInputRef.current?.click()}
            disabled={disabled || submitting || images.length >= MAX_POST_IMAGES}
            title={images.length >= MAX_POST_IMAGES ? `Maximum ${MAX_POST_IMAGES} images` : 'Add photo'}
            className="flex items-center gap-1.5 rounded-full border border-white/10 px-3 py-2 text-xs text-slate-300 hover:border-accent/30 hover:text-accent disabled:opacity-40"
          >
            <ImageIcon className="h-3.5 w-3.5" />
            Photo {images.length > 0 ? `(${images.length}/${MAX_POST_IMAGES})` : ''}
          </button>
          <input
            ref={imageInputRef}
            type="file"
            accept={ALLOWED_IMAGE_TYPES.join(',')}
            multiple
            className="hidden"
            onChange={handleImageSelect}
          />
        </div>

        <div className="flex gap-3">
          {hasContent && (
            <button
              type="button"
              onClick={() => {
                images.forEach((i) => URL.revokeObjectURL(i.previewUrl));
                setContent('');
                setImages([]);
                setTags([]);
                setTagInput('');
                setError('');
              }}
              disabled={submitting}
              className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-200 hover:text-white"
            >
              Cancel
            </button>
          )}
          <button
            type="submit"
            disabled={disabled || submitting}
            className="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2 text-sm font-semibold text-black hover:bg-accentSoft disabled:opacity-60"
          >
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            Post
          </button>
        </div>
      </div>
    </form>
  );
}

// ── Community Photo Controls (owner-only) ─────────────────────────────────────

function CommunityPhotoControls({ communityId, isOwner, currentImageUrl, onImageUpdated }) {
  const fileRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  if (!isOwner) return null;

  const handleFile = async (event) => {
    const file = event.target.files?.[0];
    if (!fileRef.current) return;
    fileRef.current.value = '';
    if (!file) return;

    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      setError('Unsupported image type. Use JPEG, PNG, or WebP.');
      return;
    }
    if (file.size > MAX_COMMUNITY_IMAGE_MB * 1024 * 1024) {
      setError(`Image exceeds the ${MAX_COMMUNITY_IMAGE_MB} MB limit.`);
      return;
    }

    setError('');
    setBusy(true);
    try {
      const result = await uploadCommunityImage(communityId, file);
      onImageUpdated(result.image_url || null);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to upload photo.');
    } finally {
      setBusy(false);
    }
  };

  const handleRemove = async () => {
    setError('');
    setBusy(true);
    try {
      await removeCommunityImage(communityId);
      onImageUpdated(null);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to remove photo.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => fileRef.current?.click()}
        disabled={busy}
        className="flex items-center gap-1.5 rounded-full border border-white/15 bg-white/[0.06] px-3 py-1.5 text-xs text-slate-300 hover:border-accent/30 hover:text-accent disabled:opacity-50"
      >
        {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Camera className="h-3 w-3" />}
        {currentImageUrl ? 'Change photo' : 'Add photo'}
      </button>
      {currentImageUrl && (
        <button
          type="button"
          onClick={handleRemove}
          disabled={busy}
          className="flex items-center gap-1.5 rounded-full border border-rose-500/25 bg-rose-500/10 px-3 py-1.5 text-xs text-rose-300 hover:bg-rose-500/15 disabled:opacity-50"
        >
          <Trash2 className="h-3 w-3" />
          Remove photo
        </button>
      )}
      <input ref={fileRef} type="file" accept={ALLOWED_IMAGE_TYPES.join(',')} className="hidden" onChange={handleFile} />
      {error && <span className="text-xs text-rose-300">{error}</span>}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function CommunityDetailPage({ communityId }) {
  const [community, setCommunity] = useState(null);
  const [posts, setPosts] = useState([]);
  const [members, setMembers] = useState([]);
  const [activeTab, setActiveTab] = useState('posts');
  const [loading, setLoading] = useState(true);
  const [tabLoading, setTabLoading] = useState(false);
  const [error, setError] = useState('');
  const [backendReady, setBackendReady] = useState(true);
  const [membershipBusy, setMembershipBusy] = useState(false);

  const joined = !!(community?.joined || community?.is_joined || community?.membership_status === 'joined');
  const isOwner = !!(community?.is_owner);
  const categoryLabel = community?.category_label || CATEGORY_LABELS[community?.category] || community?.category || 'Other';
  const tags = Array.isArray(community?.tags) ? community.tags : [];
  const communityImageUrl = community?.image_url || null;

  const loadCommunity = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getCommunity(communityId);
      setCommunity(data);
      setBackendReady(true);
    } catch (err) {
      if (isEndpointMissing(err)) {
        setBackendReady(false);
        setCommunity(null);
        setError('');
      } else {
        setError(extractErrorMessage(err) || 'Unable to load community.');
      }
    } finally {
      setLoading(false);
    }
  }, [communityId]);

  const loadTabData = useCallback(async () => {
    if (!backendReady || !communityId) return;
    setTabLoading(true);
    try {
      if (activeTab === 'posts') {
        setPosts(normalizeCommunityPosts(await listCommunityPosts(communityId)));
      }
      if (activeTab === 'members') {
        setMembers(normalizeCommunityMembers(await listCommunityMembers(communityId)));
      }
    } catch (err) {
      if (!isEndpointMissing(err)) setError(extractErrorMessage(err) || `Unable to load ${activeTab}.`);
    } finally {
      setTabLoading(false);
    }
  }, [activeTab, backendReady, communityId]);

  useEffect(() => {
    loadCommunity();
  }, [loadCommunity]);

  useEffect(() => {
    loadTabData();
  }, [loadTabData]);

  useEffect(() => {
    if (activeTab !== 'posts' || posts.length === 0 || typeof window === 'undefined') return;
    const targetPostId = new URLSearchParams(window.location.search).get('post');
    if (!targetPostId || !posts.some((post) => post.id === targetPostId)) return;
    window.requestAnimationFrame(() => {
      document.getElementById(`community-post-${targetPostId}`)?.scrollIntoView({ block: 'center' });
    });
  }, [activeTab, posts]);

  const handleJoin = async () => {
    setMembershipBusy(true);
    try {
      await joinCommunity(getId(community));
      setCommunity((prev) => ({ ...prev, joined: true }));
    } catch (err) {
      setError(isEndpointMissing(err) ? 'Community join is waiting for backend integration.' : extractErrorMessage(err));
    } finally {
      setMembershipBusy(false);
    }
  };

  const handleLeave = async () => {
    setMembershipBusy(true);
    try {
      await leaveCommunity(getId(community));
      setCommunity((prev) => ({ ...prev, joined: false }));
    } catch (err) {
      setError(isEndpointMissing(err) ? 'Community leave is waiting for backend integration.' : extractErrorMessage(err));
    } finally {
      setMembershipBusy(false);
    }
  };

  const handleCreatePost = async ({ content, tags: postTags, images }) => {
    try {
      await createCommunityPost(communityId, { content, tags: postTags, images });
      await loadTabData();
    } catch (err) {
      throw new Error(isEndpointMissing(err) ? 'Community posting is waiting for backend integration.' : extractErrorMessage(err));
    }
  };

  const handleReactionUpdated = (postId, summary) => {
    setPosts((prev) =>
      prev.map((post) =>
        post.id === postId
          ? {
              ...post,
              my_reaction: summary.my_reaction,
              reaction_counts: summary.counts,
              total_reactions: summary.total,
              like_count: summary.counts?.LIKE ?? 0,
            }
          : post
      )
    );
  };

  const handleCommentCreated = (postId) => {
    setPosts((prev) =>
      prev.map((post) =>
        post.id === postId
          ? { ...post, comment_count: (post.comment_count ?? 0) + 1 }
          : post
      )
    );
  };

  const handlePostDeleted = (postId) => {
    setPosts((prev) => prev.filter((post) => post.id !== postId));
  };

  const handleCommunityImageUpdated = (newImageUrl) => {
    setCommunity((prev) => ({ ...prev, image_url: newImageUrl }));
  };

  const memberCount = useMemo(() => {
    if (typeof community?.member_count !== 'number') return 'Members unavailable';
    return `${community.member_count.toLocaleString()} ${community.member_count === 1 ? 'member' : 'members'}`;
  }, [community?.member_count]);

  if (loading) return <LoadingSkeleton />;

  if (error && !community) {
    return (
      <div className="rounded-3xl border border-rose-500/20 bg-rose-500/10 px-6 py-16 text-center">
        <AlertCircle className="mx-auto mb-4 h-10 w-10 text-rose-300" />
        <h1 className="text-xl font-bold text-white">Community failed to load</h1>
        <p className="mx-auto mt-2 max-w-md text-sm text-rose-100/85">{error}</p>
        <button type="button" onClick={loadCommunity} className="mt-5 inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2 text-sm font-semibold text-black">
          <RefreshCw className="h-4 w-4" /> Try Again
        </button>
      </div>
    );
  }

  if (!community) {
    return (
      <EmptyPanel
        title={backendReady ? 'Community not found.' : 'Community backend is not connected yet.'}
        description={backendReady ? 'This community may have been removed or is unavailable.' : 'This route is ready for real community detail data once the backend phase lands.'}
      />
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      {error && (
        <div className="flex items-start gap-3 rounded-2xl border border-rose-500/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-200" role="alert">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      <section className="overflow-hidden rounded-[2.5rem] border border-white/10 bg-white/[0.04] shadow-glow backdrop-blur-2xl">
        <div className="h-36 bg-[radial-gradient(circle_at_20%_0%,rgba(255,143,50,0.20),transparent_42%),linear-gradient(135deg,rgba(15,23,42,0.95),rgba(2,6,23,0.95))]" />
        <div className="-mt-10 flex flex-col gap-5 p-6 sm:p-8 md:flex-row md:items-end md:justify-between">
          <div className="flex flex-col gap-4 sm:flex-row">
            {/* Community avatar / photo */}
            <div className="relative shrink-0">
              {communityImageUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={communityImageUrl}
                  alt={`${community.name} community photo`}
                  className="h-20 w-20 rounded-3xl border-2 border-accent/30 bg-slate-950 object-cover shadow-[0_0_28px_rgba(255,143,50,0.18)]"
                />
              ) : (
                <div className="flex h-20 w-20 items-center justify-center rounded-3xl border border-accent/30 bg-slate-950 text-xl font-bold text-accent shadow-[0_0_28px_rgba(255,143,50,0.18)]">
                  {getInitials(community.name)}
                </div>
              )}
            </div>

            <div className="min-w-0 pt-2">
              <h1 className="text-2xl font-extrabold text-white sm:text-3xl">{community.name}</h1>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-400">{community.description}</p>
              <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-300">
                <span className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.05] px-3 py-1">
                  <Users className="h-3.5 w-3.5" /> {memberCount}
                </span>
                <span className="inline-flex items-center gap-1 rounded-full border border-accent/25 bg-accent/10 px-3 py-1 text-accent">
                  <Tag className="h-3.5 w-3.5" /> {categoryLabel}
                </span>
              </div>

              {/* Owner photo controls */}
              <CommunityPhotoControls
                communityId={community.id}
                isOwner={isOwner}
                currentImageUrl={communityImageUrl}
                onImageUpdated={handleCommunityImageUpdated}
              />
            </div>
          </div>

          {joined ? (
            <button type="button" onClick={handleLeave} disabled={membershipBusy || !backendReady} className="inline-flex items-center justify-center gap-2 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-5 py-2.5 text-sm font-semibold text-emerald-200 disabled:opacity-60">
              {membershipBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
              Joined
            </button>
          ) : (
            <button type="button" onClick={handleJoin} disabled={membershipBusy || !backendReady} className="inline-flex items-center justify-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-black hover:bg-accentSoft disabled:opacity-60">
              {membershipBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Join Community
            </button>
          )}
        </div>
      </section>

      <div className="flex gap-2 overflow-x-auto border-b border-white/10 pb-1" role="tablist" aria-label="Community tabs">
        {['posts', 'about', 'members'].map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={activeTab === tab}
            onClick={() => setActiveTab(tab)}
            className={`shrink-0 rounded-t-xl border-b-2 px-4 py-2.5 text-sm font-semibold capitalize transition-colors ${
              activeTab === tab ? 'border-accent bg-accent/5 text-accent' : 'border-transparent text-slate-400 hover:bg-white/[0.05] hover:text-white'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      <div role="tabpanel" aria-label={activeTab} className="space-y-5">
        {activeTab === 'posts' && (
          <>
            <PostComposer joined={joined} disabled={!backendReady} onSubmit={handleCreatePost} />
            {tabLoading ? (
              <div className="h-40 animate-pulse rounded-3xl border border-white/10 bg-white/[0.04]" />
            ) : posts.length === 0 ? (
              <EmptyPanel title="No posts yet." description="Be the first to start the conversation." />
            ) : (
              posts.map((post) => (
                <PostCard
                  key={post.id ?? post.created_at}
                  post={post}
                  onReactionUpdated={handleReactionUpdated}
                  onCommentCreated={handleCommentCreated}
                  onDeleted={handlePostDeleted}
                  onError={setError}
                />
              ))
            )}
          </>
        )}

        {activeTab === 'about' && (
          <section className="rounded-3xl border border-white/10 bg-white/[0.04] p-6">
            <h2 className="text-lg font-bold text-white">About this community</h2>
            <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-slate-500">Description</dt>
                <dd className="mt-1 text-slate-200">{community.description || 'No description provided.'}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Category</dt>
                <dd className="mt-1 text-slate-200">{categoryLabel}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Visibility</dt>
                <dd className="mt-1 capitalize text-slate-200">{community.visibility || 'Public'}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Created</dt>
                <dd className="mt-1 text-slate-200">{community.created_at || 'Not provided'}</dd>
              </div>
            </dl>
            {tags.length > 0 && (
              <div className="mt-5 flex flex-wrap gap-2">
                {tags.map((tag) => (
                  <span key={tag} className="rounded-full border border-white/10 bg-white/[0.06] px-3 py-1 text-xs text-slate-300">
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </section>
        )}

        {activeTab === 'members' && (
          tabLoading ? (
            <div className="h-44 animate-pulse rounded-3xl border border-white/10 bg-white/[0.04]" />
          ) : members.length === 0 ? (
            <EmptyPanel title="No members to show yet." description="Members will appear here after the backend returns community membership." />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {members.map((member) => {
                const user = member.user || member;
                const name = [user.first_name, user.last_name].filter(Boolean).join(' ') || user.name || user.username || 'Community member';
                return (
                  <article key={user.id ?? name} className="flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                    <div className="flex min-w-0 items-center gap-3">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-accent/30 bg-accent/10 text-xs font-bold text-accent">
                        {getInitials(name)}
                      </div>
                      <div className="min-w-0">
                        <p className="truncate font-semibold text-white">{name}</p>
                        <p className="truncate text-sm text-slate-500">{user.headline || 'Professional profile'}</p>
                      </div>
                    </div>
                    {user.id && (
                      <Link href={`/dashboard/networking/${user.id}`} className="shrink-0 rounded-full border border-white/10 px-3 py-1.5 text-xs font-medium text-slate-200 hover:text-white">
                        View Profile
                      </Link>
                    )}
                  </article>
                );
              })}
            </div>
          )
        )}
      </div>
    </div>
  );
}
