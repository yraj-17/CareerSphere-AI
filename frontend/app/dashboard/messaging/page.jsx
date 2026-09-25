'use client';

import React, { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import MessagingPage from '@/components/messaging/MessagingPage';
import { getOrCreateConversation } from '@/services/api';

export default function MessagingRoute() {
  const { user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  // ?with=<userId> — open a conversation with a specific user immediately
  const withUserId = searchParams.get('with');
  const [resolvedConvId, setResolvedConvId] = useState(null);
  const [resolving, setResolving] = useState(false);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  // Resolve ?with= param to a conversation ID
  useEffect(() => {
    if (!withUserId || !isAuthenticated) return;
    setResolving(true);
    getOrCreateConversation(withUserId)
      .then((conv) => setResolvedConvId(conv.id))
      .catch(() => {
        // If creating fails (no connection), just show conversations list
        setResolvedConvId(null);
      })
      .finally(() => setResolving(false));
  }, [withUserId, isAuthenticated]);

  if (isLoading || resolving) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 text-accent animate-spin mb-3" />
        <p className="text-sm text-slate-400">
          {resolving ? 'Opening conversation…' : 'Verifying authenticated session...'}
        </p>
      </div>
    );
  }

  if (!isAuthenticated || !user) return null;

  return (
    <div
      className="flex-1 w-full max-w-7xl mx-auto px-3 sm:px-4 lg:px-6 py-4 sm:py-6 flex flex-col"
      style={{ height: 'calc(100vh - 10rem)' }}
    >
      <MessagingPage currentUser={user} initialConvId={resolvedConvId} />
    </div>
  );
}
