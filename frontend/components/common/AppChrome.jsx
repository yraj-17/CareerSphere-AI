'use client';

import { usePathname } from 'next/navigation';
import Navbar from '@/components/common/Navbar';
import BackgroundFX from '@/components/landing/BackgroundFX';

export default function AppChrome({ children }) {
  const pathname = usePathname();
  const isLanding = pathname === '/';

  return (
    <>
      {isLanding ? null : <BackgroundFX />}
      {isLanding ? null : <Navbar />}
      <main className="flex-1 flex flex-col">{children}</main>
    </>
  );
}


