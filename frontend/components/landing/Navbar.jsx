'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Menu, X } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { navItems } from '@/data/siteData';

const sectionMap = {
  Home: 'home',
  Features: 'features',
  'How It Works': 'how-it-works',
  'AI Engine': 'ai-engine',
  Networking: 'networking',
  Technology: 'technology',
  About: 'about'
};

export default function Navbar() {
  const { isAuthenticated, user } = useAuth();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const ctaHref = isAuthenticated && user ? '/dashboard' : '/signup';
  const ctaLabel = isAuthenticated && user ? 'Dashboard' : 'Get Started';

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    onScroll();
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header className="fixed inset-x-0 top-0 z-50 px-4 py-4 md:px-8">
      <div
        className={`mx-auto flex max-w-7xl items-center justify-between rounded-full border px-5 py-3 transition-all duration-300 ${
          scrolled
            ? 'border-white/10 bg-slate-950/70 shadow-glow backdrop-blur-xl'
            : 'border-white/8 bg-slate-950/35 backdrop-blur-md'
        }`}
      >
        <a href="#home" className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-accent/30 bg-accent/10 text-sm font-bold text-accent shadow-[0_0_25px_rgba(255,143,50,0.25)]">
            CS
          </div>
          <div>
            <div className="text-sm font-semibold tracking-wide text-white">CareerSphere AI</div>
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-400">AI Career Ecosystem</div>
          </div>
        </a>

        <nav className="hidden items-center gap-7 lg:flex">
          {navItems.map((item) => (
            <a key={item} href={`#${sectionMap[item]}`} className="text-sm text-slate-300 transition hover:text-white">
              {item}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-3 lg:flex">
          {isAuthenticated && user ? null : (
            <Link href="/login" className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-200 transition hover:border-white/20 hover:text-white">
              Login
            </Link>
          )}
          <Link href={ctaHref} className="rounded-full bg-accent px-5 py-2 text-sm font-medium text-black shadow-[0_8px_30px_rgba(255,143,50,0.35)] transition hover:-translate-y-0.5 hover:bg-accentSoft">
            {ctaLabel}
          </Link>
        </div>

        <button
          className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white lg:hidden"
          onClick={() => setOpen((v) => !v)}
          aria-label="Toggle navigation"
        >
          {open ? <X size={18} /> : <Menu size={18} />}
        </button>
      </div>

      {open ? (
        <div className="mx-auto mt-3 max-w-7xl rounded-3xl border border-white/10 bg-slate-950/90 p-5 shadow-glow backdrop-blur-xl lg:hidden">
          <div className="flex flex-col gap-4">
            {navItems.map((item) => (
              <a
                key={item}
                href={`#${sectionMap[item]}`}
                className="text-sm text-slate-300"
                onClick={() => setOpen(false)}
              >
                {item}
              </a>
            ))}
            <div className="mt-2 flex gap-3">
              {isAuthenticated && user ? null : (
                <Link href="/login" className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-200" onClick={() => setOpen(false)}>
                  Login
                </Link>
              )}
              <Link href={ctaHref} className="rounded-full bg-accent px-4 py-2 text-sm font-medium text-black" onClick={() => setOpen(false)}>
                {ctaLabel}
              </Link>
            </div>
          </div>
        </div>
      ) : null}
    </header>
  );
}
