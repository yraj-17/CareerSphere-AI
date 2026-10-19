'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowUpRight,
  Bookmark,
  BriefcaseBusiness,
  Check,
  ChevronDown,
  ImagePlus,
  Link2,
  Loader2,
  MessageCircle,
  MoreHorizontal,
  Pencil,
  Send,
  Sparkles,
  Trash2,
  Users,
  X,
  Heart,
} from 'lucide-react';
import ProfileAvatar from '@/components/common/ProfileAvatar';
import { useAuth } from '@/context/AuthContext';
import {
  createPost,
  createPostComment,
  deleteMedia,
  deletePost,
  deletePostComment,
  getMyProfile,
  getNetworkingUsers,
  listPostComments,
  listPosts,
  listResources,
  likePost,
  sendConnectionRequest,
  unlikePost,
  updatePost,
  uploadMedia,
} from '@/services/api';
import { extractErrorMessage } from '@/services/api';

const MAX_CONTENT = 3000;

function relativeTime(value) {
  if (!value) return 'Just now';
  const seconds = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return 'Just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d`;
  return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function displayName(user) {
  return [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.username || 'CareerSphere member';
}

function profilePhoto(profile, user) {
  return profile?.profile_photo?.url || user?.profile_photo_url || user?.profile_photo?.url || null;
}

function Avatar({ user, profile, size = 'h-11 w-11' }) {
  return (
    <ProfileAvatar
      src={profilePhoto(profile, user)}
      name={displayName(user)}
      username={user?.username}
      alt={displayName(user)}
      className={size}
    />
  );
}

function LoadingLine({ label = 'Loading your Home feed…' }) {
  return (
    <div className="flex items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white p-10 text-sm text-slate-500 shadow-sm">
      <Loader2 className="h-4 w-4 animate-spin text-brand-500" /> {label}
    </div>
  );
}

function Composer({ user, profile, resources, onCreated }) {
  const [content, setContent] = useState('');
  const [files, setFiles] = useState([]);
  const [selectedResource, setSelectedResource] = useState('');
  const [resourceOpen, setResourceOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const fileRef = useRef(null);

  const handleFiles = (event) => {
    const nextFiles = Array.from(event.target.files || []).filter((file) => file.type.startsWith('image/'));
    if (nextFiles.length) setFiles((current) => [...current, ...nextFiles].slice(0, 4));
    event.target.value = '';
  };

  const removeFile = (index) => setFiles((current) => current.filter((_, itemIndex) => itemIndex !== index));

  const submit = async (event) => {
    event.preventDefault();
    const trimmed = content.trim();
    if (!trimmed) {
      setError('Write something before publishing your post.');
      return;
    }
    if (trimmed.length > MAX_CONTENT) {
      setError(`Keep your post under ${MAX_CONTENT} characters.`);
      return;
    }
    setSubmitting(true);
    setError('');
    setStatus(files.length ? 'Uploading images…' : 'Publishing…');
    const uploaded = [];
    try {
      for (const file of files) {
        const media = await uploadMedia(file, 'post_image');
        uploaded.push(media);
      }
      const post = await createPost({
        content: trimmed,
        resource_id: selectedResource || null,
        image_media_ids: uploaded.map((media) => media.id),
      });
      setContent('');
      setFiles([]);
      setSelectedResource('');
      setResourceOpen(false);
      setExpanded(false);
      setStatus('Published');
      onCreated(post);
      setTimeout(() => setStatus(''), 1800);
    } catch (submitError) {
      await Promise.all(uploaded.map((media) => deleteMedia(media.id).catch(() => null)));
      setError(extractErrorMessage(submitError));
      setStatus('');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      {!expanded ? (
        <div className="flex items-center gap-3">
          <Avatar user={user} profile={profile} size="h-10 w-10 sm:h-11 sm:w-11" />
          <button type="button" onClick={() => setExpanded(true)} className="flex min-h-11 flex-1 items-center rounded-xl border border-slate-200 bg-slate-50 px-4 text-left text-sm text-slate-500 transition hover:border-brand-300 hover:bg-brand-50 focus:outline-none focus:ring-4 focus:ring-brand-100">
            Share something with your network…
          </button>
          {status && <span className="shrink-0 text-xs font-medium text-emerald-700">{status}</span>}
        </div>
      ) : (
        <div className="flex gap-3">
          <Avatar user={user} profile={profile} size="h-10 w-10 sm:h-11 sm:w-11" />
          <textarea
            value={content}
            onChange={(event) => { setContent(event.target.value); setError(''); setExpanded(true); }}
            onFocus={() => setExpanded(true)}
            placeholder="Share something with your network…"
            maxLength={MAX_CONTENT}
            rows={2}
            disabled={submitting}
            className="min-h-[76px] flex-1 resize-y rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-900 outline-none transition focus:border-brand-400 focus:bg-white focus:ring-4 focus:ring-brand-100 disabled:opacity-60"
            aria-label="Post content"
            autoFocus
          />
        </div>
      )}

      {files.length > 0 && (
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {files.map((file, index) => (
            <div key={`${file.name}-${index}`} className="relative overflow-hidden rounded-xl border border-slate-200 bg-slate-100">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={URL.createObjectURL(file)} alt={file.name} className="h-24 w-full object-cover" />
              <button type="button" onClick={() => removeFile(index)} className="absolute right-1 top-1 rounded-full bg-slate-950/75 p-1 text-white" aria-label={`Remove ${file.name}`}>
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {resourceOpen && (
        <div className="mt-3 rounded-xl border border-brand-100 bg-brand-50 p-3">
          <div className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-brand-700">
            <span>Attach a resource</span>
            <button type="button" onClick={() => setResourceOpen(false)} aria-label="Close resource picker"><X className="h-4 w-4" /></button>
          </div>
          <select value={selectedResource} onChange={(event) => setSelectedResource(event.target.value)} className="input-base bg-white" aria-label="Select a resource">
            <option value="">Choose a resource…</option>
            {resources.map((resource) => <option key={resource.id} value={resource.id}>{resource.title}</option>)}
          </select>
        </div>
      )}

      {error && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs font-medium text-red-700" role="alert">{error}</p>}

      {expanded && <div className="mt-3 flex flex-col gap-3 border-t border-slate-100 pt-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-1">
          <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" multiple className="hidden" onChange={handleFiles} />
          <button type="button" onClick={() => fileRef.current?.click()} className="btn-ghost min-h-10 px-3 py-2 text-xs" disabled={submitting || files.length >= 4}>
            <ImagePlus className="h-4 w-4" /> Image
          </button>
          <button type="button" onClick={() => setResourceOpen((open) => !open)} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs font-semibold text-brand-700 transition hover:bg-brand-100 disabled:cursor-not-allowed disabled:opacity-50" disabled={submitting || !resources.length}>
            <Link2 className="h-4 w-4" /> Resource
          </button>
          <span className="ml-2 text-xs text-slate-400">{content.length}/{MAX_CONTENT}</span>
        </div>
        <div className="flex items-center justify-between gap-3 sm:justify-end">
          {status && <span className="text-xs font-medium text-emerald-700">{status}</span>}
          <button type="submit" className="btn-primary min-h-10 w-full px-4 py-2 text-xs sm:w-auto" disabled={submitting}>
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Publish
          </button>
        </div>
      </div>}
    </form>
  );
}

function ResourceAttachment({ resource }) {
  if (!resource) return null;
  return (
    <Link href={`/dashboard/resources/${resource.id}`} className="mt-4 flex items-start gap-3 rounded-xl border border-brand-100 bg-brand-50 p-4 transition hover:border-brand-300">
      <div className="rounded-lg bg-white p-2 text-brand-600"><Link2 className="h-4 w-4" /></div>
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-brand-600">CareerSphere resource</p>
        <p className="mt-1 truncate text-sm font-semibold text-slate-900">{resource.title}</p>
        <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{resource.description || resource.source_domain || resource.url}</p>
      </div>
      <ArrowUpRight className="mt-1 h-4 w-4 shrink-0 text-brand-500" />
    </Link>
  );
}

function CommentList({ post, onCountChange }) {
  const [comments, setComments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [content, setContent] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    listPostComments(post.id).then((result) => { if (active) setComments(result.comments || []); }).catch(() => { if (active) setError('Comments could not be loaded.'); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [post.id]);

  const addComment = async (event) => {
    event.preventDefault();
    if (!content.trim()) return;
    try {
      const comment = await createPostComment(post.id, content.trim());
      setComments((current) => [...current, comment]);
      setContent('');
      onCountChange(1);
    } catch (commentError) {
      setError(extractErrorMessage(commentError));
    }
  };

  return (
    <div className="mt-4 border-t border-slate-100 pt-4">
      {loading ? <p className="text-xs text-slate-500">Loading comments…</p> : comments.length ? (
        <div className="space-y-3">
          {comments.map((comment) => (
            <div key={comment.id} className="flex gap-2.5">
              <ProfileAvatar src={comment.author?.profile_photo_url} name={displayName(comment.author)} username={comment.author?.username} className="h-7 w-7" />
              <div className="min-w-0 flex-1 rounded-xl bg-slate-50 px-3 py-2">
                <div className="flex items-baseline justify-between gap-2"><p className="text-xs font-semibold text-slate-900">{displayName(comment.author)}</p><span className="text-[10px] text-slate-400">{relativeTime(comment.created_at)}</span></div>
                <p className="mt-1 whitespace-pre-wrap text-xs leading-5 text-slate-600">{comment.content}</p>
              </div>
            </div>
          ))}
        </div>
      ) : <p className="text-xs text-slate-500">Start the conversation.</p>}
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      <form onSubmit={addComment} className="mt-3 flex gap-2">
        <input value={content} onChange={(event) => setContent(event.target.value)} maxLength={1000} placeholder="Add a thoughtful comment…" className="input-base flex-1 bg-slate-50" aria-label="Comment" />
        <button type="submit" className="btn-primary px-3" aria-label="Post comment" disabled={!content.trim()}><Send className="h-4 w-4" /></button>
      </form>
    </div>
  );
}

function PostCard({ post, onChanged, onDeleted }) {
  const [liked, setLiked] = useState(post.liked_by_me);
  const [likeCount, setLikeCount] = useState(post.like_count);
  const [commentCount, setCommentCount] = useState(post.comment_count);
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState(post.content);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const toggleLike = async () => {
    const next = !liked;
    setLiked(next);
    setLikeCount((count) => count + (next ? 1 : -1));
    try {
      const result = next ? await likePost(post.id) : await unlikePost(post.id);
      setLiked(result.liked_by_me);
      setLikeCount(result.like_count);
    } catch (likeError) {
      setLiked(!next);
      setLikeCount((count) => count + (next ? -1 : 1));
      setError(extractErrorMessage(likeError));
    }
  };

  const saveEdit = async () => {
    if (!editContent.trim()) return;
    setBusy(true);
    try {
      const updated = await updatePost(post.id, { content: editContent.trim(), resource_id: post.resource?.id || null });
      setEditing(false);
      onChanged(updated);
    } catch (editError) { setError(extractErrorMessage(editError)); } finally { setBusy(false); }
  };

  const removePost = async () => {
    if (!window.confirm('Delete this post? This cannot be undone.')) return;
    setBusy(true);
    try { await deletePost(post.id); onDeleted(post.id); } catch (deleteError) { setError(extractErrorMessage(deleteError)); setBusy(false); }
  };

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 gap-3">
          <Avatar user={post.author} />
          <div className="min-w-0">
            <p className="truncate text-sm font-bold text-slate-900">{displayName(post.author)}</p>
            <p className="truncate text-xs text-slate-500">{post.author?.headline || 'CareerSphere member'}</p>
            <p className="mt-1 text-[11px] text-slate-400">{relativeTime(post.created_at)}{post.updated_at !== post.created_at ? ' · Edited' : ''}</p>
          </div>
        </div>
        {post.is_owner && <div className="relative"><button type="button" onClick={() => setMenuOpen((open) => !open)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="Post options"><MoreHorizontal className="h-5 w-5" /></button>{menuOpen && <div className="absolute right-0 z-10 mt-1 w-32 rounded-xl border border-slate-200 bg-white p-1 shadow-lg"><button type="button" onClick={() => { setEditing(true); setMenuOpen(false); }} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs font-medium text-slate-700 hover:bg-slate-50"><Pencil className="h-3.5 w-3.5" /> Edit</button><button type="button" onClick={removePost} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs font-medium text-red-600 hover:bg-red-50"><Trash2 className="h-3.5 w-3.5" /> Delete</button></div>}</div>}
      </div>

      {editing ? <div className="mt-4"><textarea value={editContent} onChange={(event) => setEditContent(event.target.value)} maxLength={MAX_CONTENT} rows={4} className="input-base resize-y" aria-label="Edit post" /><div className="mt-2 flex justify-end gap-2"><button type="button" onClick={() => setEditing(false)} className="btn-ghost px-3 py-2 text-xs">Cancel</button><button type="button" onClick={saveEdit} className="btn-primary px-3 py-2 text-xs" disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} Save</button></div></div> : <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-slate-700">{post.content}</p>}

      {!!post.media?.length && <div className={`mt-4 grid gap-2 ${post.media.length === 1 ? 'grid-cols-1' : 'grid-cols-2'}`}>{post.media.map((media) => media.url ? <a key={media.id} href={media.url} target="_blank" rel="noreferrer" className="flex max-h-[28rem] items-center justify-center overflow-hidden rounded-xl border border-slate-100 bg-slate-50"><img src={media.url} alt="Post attachment" className="max-h-[28rem] w-full object-contain" /></a> : null)}</div>}
      <ResourceAttachment resource={post.resource} />

      <div className="mt-4 flex items-center justify-between border-b border-slate-100 pb-3 text-xs text-slate-500"><span>{likeCount ? `${likeCount} ${likeCount === 1 ? 'like' : 'likes'}` : 'Be the first to like this'}</span><button type="button" onClick={() => setCommentsOpen((open) => !open)} className="hover:text-brand-600">{commentCount} {commentCount === 1 ? 'comment' : 'comments'}</button></div>
      <div className="flex items-center gap-1 pt-2"><button type="button" onClick={toggleLike} className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold transition ${liked ? 'bg-brand-50 text-brand-700' : 'text-slate-500 hover:bg-slate-50 hover:text-brand-700'}`}><Heart className={`h-4 w-4 ${liked ? 'fill-current' : ''}`} /> {liked ? 'Liked' : 'Like'}</button><button type="button" onClick={() => setCommentsOpen((open) => !open)} className="flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs font-semibold text-slate-500 hover:bg-slate-50 hover:text-brand-700"><MessageCircle className="h-4 w-4" /> Comment</button></div>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      {commentsOpen && <CommentList post={post} onCountChange={(change) => setCommentCount((count) => count + change)} />}
    </article>
  );
}

function SideCard({ children, className = '' }) { return <div className={`rounded-2xl border border-slate-200 bg-white p-4 shadow-sm ${className}`}>{children}</div>; }

export default function HomeFeedPage() {
  const { user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const [profile, setProfile] = useState(null);
  const [posts, setPosts] = useState([]);
  const [resources, setResources] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(true);
  const [suggestionsError, setSuggestionsError] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [hasMore, setHasMore] = useState(false);

  useEffect(() => { if (!isLoading && !isAuthenticated) router.push('/login'); }, [isAuthenticated, isLoading, router]);

  useEffect(() => {
    if (!isAuthenticated) return undefined;
    let active = true;
    Promise.allSettled([listPosts(), getMyProfile(), listResources({ limit: 8 }), getNetworkingUsers({ limit: 20 })]).then((results) => {
      if (!active) return;
      const [feed, profileResult, resourceResult, peopleResult] = results;
      if (feed.status === 'fulfilled') { setPosts(feed.value.posts || []); setHasMore((feed.value.offset || 0) + (feed.value.posts || []).length < (feed.value.total || 0)); } else setError(extractErrorMessage(feed.reason));
      if (profileResult.status === 'fulfilled') setProfile(profileResult.value);
      if (resourceResult.status === 'fulfilled') setResources(resourceResult.value.resources || resourceResult.value.items || []);
      if (peopleResult.status === 'fulfilled') {
        setSuggestions((peopleResult.value.users || []).filter((person) => person.connection_status === 'none').slice(0, 3));
        setSuggestionsError('');
      } else {
        setSuggestionsError(extractErrorMessage(peopleResult.reason));
      }
      setSuggestionsLoading(false);
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [isAuthenticated]);

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const result = await listPosts({ offset: posts.length });
      const nextPosts = result.posts || [];
      const seen = new Set(posts.map((post) => post.id));
      const merged = [...posts, ...nextPosts.filter((post) => !seen.has(post.id))];
      setPosts(merged);
      setHasMore(merged.length < (result.total || 0));
    } catch (loadError) { setError(extractErrorMessage(loadError)); } finally { setLoadingMore(false); }
  };

  const currentUserProfile = profile || {};
  const headline = currentUserProfile.headline || 'Add a headline to help your network understand your focus.';
  const memberSince = useMemo(() => user?.created_at ? new Date(user.created_at).getFullYear() : null, [user?.created_at]);

  if (isLoading || !isAuthenticated || !user) return <div className="flex min-h-[70vh] items-center justify-center"><Loader2 className="h-7 w-7 animate-spin text-brand-500" /></div>;

  return (
    <div className="min-h-screen bg-[#f3f5f7] px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="mb-6 flex items-end justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[0.2em] text-amber-600">Your professional network</p><h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">Home</h1><p className="mt-1 text-sm text-slate-500">A focused space for progress, ideas, and meaningful connections.</p></div><Link href="/dashboard/profile" className="btn-outline hidden px-3 py-2 text-xs sm:inline-flex"><Pencil className="h-3.5 w-3.5" /> Update profile</Link></div>
        <div className="grid gap-6 lg:grid-cols-[230px_minmax(0,1fr)_260px]">
          <aside className="hidden space-y-4 lg:block">
            <SideCard className="overflow-hidden p-0"><div className="h-14 bg-gradient-to-r from-[#0B2A5B] to-[#102F6B]" /><div className="px-4 pb-4"><div className="-mt-7"><Avatar user={user} profile={profile} size="h-14 w-14 ring-4 ring-white" /></div><p className="mt-3 truncate text-sm font-bold text-slate-900">{displayName(user)}</p><p className="mt-1 text-xs leading-5 text-slate-500">{headline}</p>{currentUserProfile.location && <p className="mt-2 truncate text-xs text-slate-400">{currentUserProfile.location}</p>}{currentUserProfile.skills?.length > 0 && <div className="mt-3 flex flex-wrap gap-1.5">{currentUserProfile.skills.slice(0, 3).map((skill) => <span key={skill.id || skill.name} className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-600">{skill.name}</span>)}</div>}<Link href="/dashboard/profile" className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3 text-xs font-semibold text-brand-600 hover:text-brand-800">View profile <ArrowUpRight className="h-3.5 w-3.5" /></Link></div></SideCard>
            <SideCard><p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-400">Shortcuts</p><nav className="mt-3 space-y-1"><Link href="/dashboard" className="flex items-center gap-2 rounded-lg px-2 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50 hover:text-brand-700"><BriefcaseBusiness className="h-4 w-4" /> Dashboard overview</Link><Link href="/dashboard/resources?filter=saved" className="flex items-center gap-2 rounded-lg px-2 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50 hover:text-brand-700"><Bookmark className="h-4 w-4" /> Saved resources</Link><Link href="/dashboard/networking/my-network" className="flex items-center gap-2 rounded-lg px-2 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50 hover:text-brand-700"><Users className="h-4 w-4" /> My network</Link><Link href="/dashboard/ai" className="flex items-center gap-2 rounded-lg px-2 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50 hover:text-brand-700"><Sparkles className="h-4 w-4" /> AI Career Assistant</Link></nav></SideCard>
            {memberSince && <p className="px-2 text-[11px] text-slate-400">Member since {memberSince}</p>}
          </aside>

          <main className="min-w-0 space-y-4"><Composer user={user} profile={profile} resources={resources} onCreated={(post) => setPosts((current) => [post, ...current.filter((item) => item.id !== post.id)])} /><div className="flex items-center justify-between px-1"><div className="flex items-center gap-2 text-xs font-semibold text-slate-500"><span className="h-px w-8 bg-slate-300" /> Latest updates</div><span className="text-[11px] text-slate-400">Newest first</span></div>{loading ? <LoadingLine /> : error && !posts.length ? <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">{error}</div> : posts.length ? <>{posts.map((post) => <PostCard key={post.id} post={post} onChanged={(updated) => setPosts((current) => current.map((item) => item.id === updated.id ? updated : item))} onDeleted={(postId) => setPosts((current) => current.filter((item) => item.id !== postId))} />)}{hasMore && <button type="button" onClick={loadMore} disabled={loadingMore} className="btn-outline w-full py-3 text-xs">{loadingMore ? <Loader2 className="h-4 w-4 animate-spin" /> : <ChevronDown className="h-4 w-4" />} Load more posts</button>}</> : <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-7 text-center shadow-sm sm:p-8"><div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-brand-50 text-brand-600"><Sparkles className="h-4 w-4" /></div><h2 className="mt-3 text-base font-bold text-slate-900">Share your first update</h2><p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-slate-500">Be the first to share an update with your network.</p></div>}</main>

          <aside className="space-y-4">
            <SideCard><div className="flex items-center justify-between"><p className="text-sm font-bold text-slate-900">People to connect with</p><Users className="h-4 w-4 text-amber-600" /></div>{suggestionsLoading ? <div className="mt-4 space-y-3" aria-label="Loading connection suggestions"><div className="h-9 animate-pulse rounded-lg bg-slate-100" /><div className="h-9 animate-pulse rounded-lg bg-slate-100" /></div> : suggestionsError ? <p className="mt-3 text-xs leading-5 text-red-600">{suggestionsError}</p> : suggestions.length > 0 ? <><div className="mt-4 space-y-4">{suggestions.map((person) => <Suggestion key={person.id} person={person} />)}</div><Link href="/dashboard/networking" className="mt-4 block border-t border-slate-100 pt-3 text-center text-xs font-semibold text-brand-600 hover:text-brand-800">Explore more people</Link></> : <p className="mt-3 text-xs leading-5 text-slate-500">No new connection suggestions right now.</p>}</SideCard>
            <SideCard><p className="text-sm font-bold text-slate-900">Keep growing</p><p className="mt-1 text-xs leading-5 text-slate-500">Use CareerSphere tools to turn your next step into a plan.</p><div className="mt-3 space-y-2"><Link href="/dashboard/skill-analysis" className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 hover:bg-brand-50 hover:text-brand-700"><BriefcaseBusiness className="h-4 w-4 text-amber-600" /> Review skill gaps <ArrowUpRight className="ml-auto h-3.5 w-3.5" /></Link><Link href="/dashboard/career-matching" className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 hover:bg-brand-50 hover:text-brand-700"><Sparkles className="h-4 w-4 text-amber-600" /> Explore career matches <ArrowUpRight className="ml-auto h-3.5 w-3.5" /></Link></div></SideCard>
          </aside>
        </div>
      </div>
    </div>
  );
}

function Suggestion({ person }) {
  const [status, setStatus] = useState('none');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const requestInFlight = useRef(false);
  const connect = async () => {
    if (requestInFlight.current || status !== 'none') return;
    requestInFlight.current = true;
    setBusy(true);
    setError('');
    try {
      await sendConnectionRequest(person.id);
      setStatus('pending');
    } catch (connectionError) {
      setError(extractErrorMessage(connectionError));
    } finally {
      requestInFlight.current = false;
      setBusy(false);
    }
  };
  return <div className="flex items-start gap-2.5"><ProfileAvatar src={person.profile_photo_url} name={displayName(person)} username={person.username} className="h-9 w-9" /><div className="min-w-0 flex-1"><p className="truncate text-xs font-semibold text-slate-900">{displayName(person)}</p><p className="truncate text-[11px] text-slate-500">{person.headline || (person.username ? `@${person.username}` : 'CareerSphere member')}</p>{error && <p className="mt-1 text-[10px] leading-4 text-red-600" role="alert">{error}</p>}</div>{status === 'pending' ? <span className="pt-1 text-[10px] font-semibold text-emerald-700">Sent</span> : <button type="button" onClick={connect} disabled={busy} aria-label={`Connect with ${displayName(person)}`} className="min-h-8 shrink-0 rounded-lg border border-brand-200 px-2 py-1 text-[10px] font-bold text-brand-700 transition hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-60">{busy ? '…' : 'Connect'}</button>}</div>;
}
