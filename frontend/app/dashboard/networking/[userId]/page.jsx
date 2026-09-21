'use client';

/**
 * Public profile stub — Phase 5.4
 *
 * Placeholder route for /dashboard/networking/:userId.
 * Provides a clear destination for "View Profile" links from PersonCard.
 * Full public profile display is out of scope for Phase 5.4.
 */

import React, { useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { Loader2, ArrowLeft, User, Construction } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

export default function PublicProfilePage() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const params = useParams();
  const userId = params?.userId;

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 text-accent animate-spin mb-3" />
        <p className="text-sm text-slate-400">Loading…</p>
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <div className="flex-1 w-full max-w-3xl mx-auto px-4 sm:px-6 py-10 space-y-8 animate-fade-in">
      {/* Back */}
      <Link
        href="/dashboard/networking"
        className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Discover People
      </Link>

      {/* Stub card */}
      <div className="rounded-[2rem] border border-white/10 bg-white/[0.04] backdrop-blur-xl shadow-glow p-10 flex flex-col items-center text-center space-y-5">
        <div className="h-16 w-16 rounded-2xl bg-accent/10 border border-accent/20 flex items-center justify-center">
          <Construction className="h-8 w-8 text-accent" />
        </div>
        <div className="space-y-2">
          <h1 className="text-xl font-bold text-white">Public Profile</h1>
          <p className="text-sm text-slate-400 max-w-sm leading-relaxed">
            Full public profile pages will be available in a future phase.
            You can still connect with this person from the Discover People page.
          </p>
          {userId && (
            <p className="text-xs font-mono text-slate-600 mt-1 break-all">
              User ID: {userId}
            </p>
          )}
        </div>
        <Link
          href="/dashboard/networking"
          className="flex items-center gap-2 px-6 py-2.5 rounded-full bg-accent text-black text-sm font-semibold shadow-[0_8px_30px_rgba(255,143,50,0.3)] hover:bg-accentSoft transition-all"
        >
          <User className="h-4 w-4" />
          Back to Networking
        </Link>
      </div>
    </div>
  );
}
