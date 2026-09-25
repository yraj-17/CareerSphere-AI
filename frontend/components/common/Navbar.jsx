'use client';

import React, { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { LogOut, LayoutDashboard, Sparkles, UserRound, BarChart2, Briefcase, Users, Search, UsersRound, ChevronDown, MessageSquare } from 'lucide-react';

export default function Navbar() {
  const { user, isAuthenticated, logout } = useAuth();
  const pathname = usePathname();
  const [netOpen, setNetOpen] = useState(false);
  const netRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (netRef.current && !netRef.current.contains(e.target)) {
        setNetOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const isNetworkingActive = pathname.startsWith('/dashboard/networking');

  return (
    <header className="sticky top-0 z-50 w-full px-4 py-3 md:px-8">
      <div className="mx-auto flex max-w-7xl items-center justify-between rounded-full border border-white/10 bg-slate-950/70 px-5 py-3 shadow-glow backdrop-blur-xl transition-all duration-300">
        {/* Brand Logo */}
        <Link href="/" className="flex items-center gap-3 group">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-accent/30 bg-accent/10 text-sm font-bold text-accent shadow-[0_0_25px_rgba(255,143,50,0.25)] transition-transform duration-200 group-hover:scale-105">
            CS
          </div>
          <div>
            <div className="text-sm font-semibold tracking-wide text-white">CareerSphere AI</div>
            <div className="text-[11px] uppercase tracking-[0.24em] text-slate-400">AI Career Ecosystem</div>
          </div>
        </Link>

        {/* Navigation & Auth CTA */}
        <div className="flex items-center gap-3 sm:gap-4">
          {isAuthenticated && user ? (
            <div className="flex items-center gap-3">
              <Link
                href="/dashboard"
                className={`flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium transition-all ${pathname === '/dashboard'
                    ? 'bg-accent text-black shadow-[0_8px_30px_rgba(255,143,50,0.35)]'
                    : 'border border-white/10 text-slate-200 hover:border-white/20 hover:text-white'
                  }`}
              >
                <LayoutDashboard className="h-4 w-4" />
                <span className="hidden sm:inline">Dashboard</span>
              </Link>

              <Link
                href="/dashboard/ai"
                className={`flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium transition-all ${pathname === '/dashboard/ai' || pathname.startsWith('/dashboard/ai/')
                    ? 'bg-accent text-black shadow-[0_8px_30px_rgba(255,143,50,0.35)]'
                    : 'border border-white/10 text-slate-200 hover:border-white/20 hover:text-white'
                  }`}
              >
                <Sparkles className="h-4 w-4" />
                <span className="hidden sm:inline">AI Career Assistant</span>
              </Link>

              <Link
                href="/dashboard/skill-analysis"
                className={`flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium transition-all ${pathname === '/dashboard/skill-analysis'
                    ? 'bg-accent text-black shadow-[0_8px_30px_rgba(255,143,50,0.35)]'
                    : 'border border-white/10 text-slate-200 hover:border-white/20 hover:text-white'
                  }`}
              >
                <BarChart2 className="h-4 w-4" />
                <span className="hidden sm:inline">Skill Analysis</span>
              </Link>

              <Link
                href="/dashboard/career-matching"
                className={`flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium transition-all ${pathname === '/dashboard/career-matching'
                    ? 'bg-accent text-black shadow-[0_8px_30px_rgba(255,143,50,0.35)]'
                    : 'border border-white/10 text-slate-200 hover:border-white/20 hover:text-white'
                  }`}
              >
                <Briefcase className="h-4 w-4" />
                <span className="hidden sm:inline">Career Matching</span>
              </Link>

              {/* Networking dropdown */}
              <div className="relative" ref={netRef}>
                <button
                  type="button"
                  onClick={() => setNetOpen((v) => !v)}
                  aria-haspopup="true"
                  aria-expanded={netOpen}
                  aria-label="Networking menu"
                  className={`flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium transition-all ${
                    isNetworkingActive
                      ? 'bg-accent text-black shadow-[0_8px_30px_rgba(255,143,50,0.35)]'
                      : 'border border-white/10 text-slate-200 hover:border-white/20 hover:text-white'
                  }`}
                >
                  <Users className="h-4 w-4" />
                  <span className="hidden sm:inline">Networking</span>
                  <ChevronDown className={`h-3.5 w-3.5 hidden sm:block transition-transform duration-150 ${netOpen ? 'rotate-180' : ''}`} />
                </button>

                {netOpen && (
                  <div className="absolute right-0 top-full mt-2 w-52 rounded-2xl border border-white/10 bg-slate-900/95 backdrop-blur-xl shadow-[0_16px_40px_rgba(0,0,0,0.5)] overflow-hidden z-50">
                    <Link
                      href="/dashboard/networking"
                      onClick={() => setNetOpen(false)}
                      className={`flex items-center gap-3 px-4 py-3 text-sm transition-colors ${
                        pathname === '/dashboard/networking'
                          ? 'bg-accent/10 text-accent font-medium'
                          : 'text-slate-200 hover:bg-white/5 hover:text-white'
                      }`}
                    >
                      <Search className="h-4 w-4 flex-shrink-0" />
                      Discover People
                    </Link>
                    <Link
                      href="/dashboard/networking/my-network"
                      onClick={() => setNetOpen(false)}
                      className={`flex items-center gap-3 px-4 py-3 text-sm transition-colors ${
                        pathname === '/dashboard/networking/my-network'
                          ? 'bg-accent/10 text-accent font-medium'
                          : 'text-slate-200 hover:bg-white/5 hover:text-white'
                      }`}
                    >
                      <UsersRound className="h-4 w-4 flex-shrink-0" />
                      My Network
                    </Link>
                  </div>
                )}
              </div>

              <Link
                href="/dashboard/messaging"
                className={`flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium transition-all ${pathname.startsWith('/dashboard/messaging')
                    ? 'bg-accent text-black shadow-[0_8px_30px_rgba(255,143,50,0.35)]'
                    : 'border border-white/10 text-slate-200 hover:border-white/20 hover:text-white'
                  }`}
              >
                <MessageSquare className="h-4 w-4" />
                <span className="hidden sm:inline">Messages</span>
              </Link>

              <Link
                href="/dashboard/profile"
                className={`flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium transition-all ${pathname === '/dashboard/profile'
                    ? 'bg-accent text-black shadow-[0_8px_30px_rgba(255,143,50,0.35)]'
                    : 'border border-white/10 text-slate-200 hover:border-white/20 hover:text-white'
                  }`}
              >
                <UserRound className="h-4 w-4" />
                <span className="hidden sm:inline">Profile</span>
              </Link>

              <div className="hidden h-4 w-px bg-white/10 sm:block" />

              <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1">
                <div className="flex h-6 w-6 uppercase items-center justify-center rounded-full bg-accent/20 border border-accent/40 text-xs font-bold text-accent">
                  {user.first_name?.[0] || user.username?.[0] || 'U'}
                </div>
                <span className="hidden text-xs font-medium text-slate-200 md:inline">
                  {user.first_name} {user.last_name}
                </span>
              </div>

              <button
                type="button"
                onClick={logout}
                title="Log out"
                className="flex items-center gap-1.5 rounded-full border border-white/10 px-3.5 py-1.5 text-xs text-slate-300 hover:border-rose-500/30 hover:bg-rose-500/10 hover:text-rose-300 transition-all"
              >
                <LogOut className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Logout</span>
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 sm:gap-3">
              <Link
                href="/login"
                className={`rounded-full px-4 py-2 text-sm font-medium transition-all ${pathname === '/login'
                    ? 'border border-accent/40 bg-accent/10 text-accent shadow-[0_0_15px_rgba(255,143,50,0.2)]'
                    : 'border border-white/10 text-slate-200 hover:border-white/20 hover:text-white'
                  }`}
              >
                Login
              </Link>
              <Link
                href="/signup"
                className={`rounded-full px-5 py-2 text-sm font-medium transition-all ${pathname === '/signup'
                    ? 'bg-accent text-black shadow-[0_8px_30px_rgba(255,143,50,0.35)]'
                    : 'bg-accent text-black shadow-[0_8px_30px_rgba(255,143,50,0.35)] hover:-translate-y-0.5 hover:bg-accentSoft'
                  }`}
              >
                Create Account
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
