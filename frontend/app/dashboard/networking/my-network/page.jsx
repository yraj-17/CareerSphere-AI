'use client';

import React, { Suspense, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import MyNetworkPage from '@/components/networking/MyNetworkPage';

function MyNetworkDashboardContent() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedTab = searchParams.get('tab');

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 text-accent animate-spin mb-3" />
        <p className="text-sm text-slate-400">Verifying authenticated session…</p>
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <div className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-10">
      <MyNetworkPage initialTab={requestedTab} />
    </div>
  );
}

function MyNetworkDashboardFallback() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center min-h-[60vh]">
      <Loader2 className="h-8 w-8 text-accent animate-spin mb-3" />
      <p className="text-sm text-slate-400">Opening your network...</p>
    </div>
  );
}

export default function MyNetworkDashboardPage() {
  return (
    <Suspense fallback={<MyNetworkDashboardFallback />}>
      <MyNetworkDashboardContent />
    </Suspense>
  );
}
