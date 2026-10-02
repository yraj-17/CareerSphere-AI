'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  AlertCircle,
  Check,
  Loader2,
  MessageCircle,
  RefreshCw,
  Send,
  Share2,
  Tag,
  Users,
} from 'lucide-react';
import {
  createCommunityPost,
  extractErrorMessage,
  getCommunity,
  joinCommunity,
  leaveCommunity,
  listCommunityMembers,
  listCommunityPosts,
} from '@/services/api';
import {
  CATEGORY_LABELS,
  normalizeCommunityMembers,
  normalizeCommunityPosts,
} from '@/components/communities/communityConstants';

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

function PostCard({ post }) {
  const author = post.author || post.user || {};
  const authorName = [author.first_name, author.last_name].filter(Boolean).join(' ') || author.name || 'Community member';
  return (
    <article className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
      <div className="mb-4 flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-accent/30 bg-accent/10 text-xs font-bold text-accent">
          {getInitials(authorName)}
        </div>
        <div className="min-w-0">
          <p className="font-semibold text-white">{authorName}</p>
          <p className="text-xs text-slate-500">{post.created_at || post.timestamp || 'Recently'}</p>
        </div>
      </div>
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-200">{post.content || post.text}</p>
      <div className="mt-5 flex flex-wrap gap-4 text-sm text-slate-400">
        <button type="button" className="hover:text-white">♡ {post.like_count ?? 0}</button>
        <button type="button" className="inline-flex items-center gap-1 hover:text-white">
          <MessageCircle className="h-4 w-4" /> {post.comment_count ?? 0}
        </button>
        <button type="button" className="inline-flex items-center gap-1 hover:text-white">
          <Share2 className="h-4 w-4" /> Share
        </button>
      </div>
    </article>
  );
}

function PostComposer({ joined, onSubmit, disabled }) {
  const [content, setContent] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  if (!joined) return null;

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setSuccess('');
    if (!content.trim()) {
      setError('Write something before posting.');
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit(content.trim());
      setContent('');
      setSuccess('Post submitted.');
    } catch (err) {
      setError(err?.message || 'Unable to create post.');
    } finally {
      setSubmitting(false);
    }
  };

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
      {(error || success) && (
        <p className={`mt-2 text-sm ${error ? 'text-rose-300' : 'text-emerald-300'}`} role="status">
          {error || success}
        </p>
      )}
      <div className="mt-4 flex justify-end gap-3">
        {content && (
          <button type="button" onClick={() => setContent('')} disabled={submitting} className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-200 hover:text-white">
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
    </form>
  );
}

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
  const categoryLabel = community?.category_label || CATEGORY_LABELS[community?.category] || community?.category || 'Other';
  const tags = Array.isArray(community?.tags) ? community.tags : [];

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

  const handleCreatePost = async (content) => {
    try {
      await createCommunityPost(communityId, { content });
      await loadTabData();
    } catch (err) {
      throw new Error(isEndpointMissing(err) ? 'Community posting is waiting for backend integration.' : extractErrorMessage(err));
    }
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
            <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-3xl border border-accent/30 bg-slate-950 text-xl font-bold text-accent shadow-[0_0_28px_rgba(255,143,50,0.18)]">
              {getInitials(community.name)}
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
              posts.map((post) => <PostCard key={post.id ?? post.created_at} post={post} />)
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
