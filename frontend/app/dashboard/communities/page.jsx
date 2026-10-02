'use client';

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import CommunitiesPage from '@/components/communities/CommunitiesPage';

export default function CommunitiesDashboardPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] flex-1 flex-col items-center justify-center">
        <Loader2 className="mb-3 h-8 w-8 animate-spin text-accent" />
        <p className="text-sm text-slate-400">Verifying authenticated session...</p>
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <div className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 sm:py-10 lg:px-8">
      <CommunitiesPage />
    </div>
  );
}
