'use client';

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
  const isDedicatedChat = isAIChat || isMessaging;

  return (
    <>
      {isLanding || isDedicatedChat || isCommunities || isResources ? null : <BackgroundFX />}
      {isLanding || isDedicatedChat ? null : <Navbar />}
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


