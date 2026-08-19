'use client';

import { usePathname } from 'next/navigation';
import Navbar from '@/components/common/Navbar';

export default function AppChrome({ children }) {
  const pathname = usePathname();
  const isLanding = pathname === '/';

  return (
    <>
      {isLanding ? null : <Navbar />}
      <main className="flex-1 flex flex-col">{children}</main>
      {isLanding ? null : (
        <footer className="border-t border-slate-800/80 bg-slate-950/60 py-6 text-center text-xs text-slate-500">
          <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
            <p>© {new Date().getFullYear()} CareerSphere AI. All rights reserved.</p>
            <p className="text-slate-500">
              Empowering next-generation career excellence with AI.
            </p>
          </div>
        </footer>
      )}
    </>
  );
}
