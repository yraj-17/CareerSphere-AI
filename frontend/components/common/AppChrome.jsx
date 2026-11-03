'use client';

import { Suspense } from 'react';
import { usePathname } from 'next/navigation';
import Navbar from '@/components/common/Navbar';
import BackgroundFX from '@/components/landing/BackgroundFX';

export default function AppChrome({ children }) {
  const pathname = usePathname();
  const isLanding = pathname === '/';
  const isAIChat = pathname.startsWith('/dashboard/ai');
  const isMessaging = pathname.startsWith('/dashboard/messaging');
  const isCommunities = pathname === '/dashboard/communities';
  const isResources = pathname.startsWith('/dashboard/resources');
  const isSignup = pathname === '/signup';
  const isLogin = pathname === '/login';
  const isAuthPage = isSignup || isLogin;
  const isDedicatedChat = isAIChat || isMessaging;

  return (
    <>
      {isLanding || isDedicatedChat || isCommunities || isResources || isAuthPage ? null : <BackgroundFX />}
      {/* Signup renders its own single, minimal header. */}
      {isLanding || isDedicatedChat || isSignup ? null : (
        <Suspense fallback={<div className="h-[68px] border-b border-slate-200 bg-white min-[1360px]:h-[76px]" aria-hidden="true" />}>
          <Navbar />
        </Suspense>
      )}
      <main
        className={isDedicatedChat
          ? 'flex h-screen min-h-0 flex-none flex-col overflow-hidden'
          : 'flex flex-1 flex-col'}
      >
        {children}
      </main>
    </>
  );
}


