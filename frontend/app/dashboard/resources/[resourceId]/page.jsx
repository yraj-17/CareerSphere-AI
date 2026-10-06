'use client';

import React, { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import ResourceDetailPage from '@/components/resources/ResourceDetailPage';

export default function ResourceDetailDashboardPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const params = useParams();
  const resourceId = params?.resourceId;

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

  if (!isAuthenticated || !resourceId) return null;

  return (
    <div className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 sm:py-10 lg:px-8">
      <ResourceDetailPage resourceId={resourceId} />
    </div>
  );
}
