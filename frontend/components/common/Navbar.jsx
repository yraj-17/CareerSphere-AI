'use client';

import React, { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  BarChart2,
  Bell,
  Briefcase,
  ChevronDown,
  Globe2,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  Search,
  Sparkles,
  UserRound,
  Users,
  UsersRound,
  X,
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import ProfileAvatar from '@/components/common/ProfileAvatar';

const primaryNav = [
  {
    label: 'Dashboard',
    href: '/dashboard',
    icon: LayoutDashboard,
    isActive: (pathname) => pathname === '/dashboard',
  },
  {
    label: 'AI Career Assistant',
    href: '/dashboard/ai',
    icon: Sparkles,
    isActive: (pathname) => pathname === '/dashboard/ai' || pathname.startsWith('/dashboard/ai/'),
  },
  {
    label: 'Skill Analysis',
    href: '/dashboard/skill-analysis',
    icon: BarChart2,
    isActive: (pathname) => pathname === '/dashboard/skill-analysis',
  },
  {
    label: 'Career Matching',
    href: '/dashboard/career-matching',
    icon: Briefcase,
    isActive: (pathname) => pathname === '/dashboard/career-matching',
  },
];

const networkingLinks = [
  {
    label: 'Discover People',
    href: '/dashboard/networking',
    icon: Search,
    isActive: (pathname) => pathname === '/dashboard/networking',
  },
  {
    label: 'My Network',
    href: '/dashboard/networking/my-network',
    icon: UsersRound,
    isActive: (pathname) => pathname === '/dashboard/networking/my-network',
  },
  {
    label: 'Communities',
    href: '/dashboard/communities',
    icon: Globe2,
    isActive: (pathname) => pathname.startsWith('/dashboard/communities'),
  },
];

const messageNav = {
  label: 'Messages',
  href: '/dashboard/messaging',
  icon: MessageSquare,
  isActive: (pathname) => pathname.startsWith('/dashboard/messaging'),
};

const profileNav = {
  label: 'Profile',
  href: '/dashboard/profile',
  icon: UserRound,
  isActive: (pathname) => pathname === '/dashboard/profile',
};

function getUserName(user) {
  const fullName = [user?.first_name, user?.last_name].filter(Boolean).join(' ').trim();
  return fullName || user?.username || 'User';
}

function getInitial(user) {
  return (user?.first_name?.[0] || user?.username?.[0] || 'U').toUpperCase();
}

function getProfilePhotoUrl(user) {
  return user?.profile_photo_url || user?.profile_photo?.url || null;
}

function Brand({ compact = false, href = '/dashboard' }) {
  return (
    <Link
      href={href}
      className="group flex min-w-0 shrink-0 items-center gap-3 rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
      aria-label="CareerSphere AI dashboard"
    >
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-accent/35 bg-accent/10 text-xs font-bold text-accent shadow-[0_0_20px_rgba(255,143,50,0.18)] transition-transform duration-200 group-hover:scale-105">
        CS
      </div>
      <div className={compact ? 'min-w-0' : 'hidden min-w-0 sm:block'}>
        <div className="truncate text-sm font-semibold tracking-wide text-white">CareerSphere AI</div>
        {!compact && (
          <div className="hidden text-[10px] uppercase tracking-[0.22em] text-slate-500 xl:block">
            AI Career Ecosystem
          </div>
        )}
      </div>
    </Link>
  );
}

function NavLink({ item, pathname, onClick, compact = false }) {
  const Icon = item.icon;
  const active = item.isActive(pathname);

  return (
    <Link
      href={item.href}
      onClick={onClick}
      aria-current={active ? 'page' : undefined}
      className={`group flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70 ${
        active
          ? 'border-accent/35 bg-accent/15 text-accent shadow-[inset_0_-2px_0_rgba(255,143,50,0.85)]'
          : 'border-transparent text-slate-300 hover:border-white/10 hover:bg-white/[0.04] hover:text-white'
      } ${compact ? 'justify-start' : 'justify-center'}`}
    >
      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span className={compact ? 'truncate' : 'hidden min-[1180px]:inline'}>{item.label}</span>
    </Link>
  );
}

export default function Navbar() {
  const { user, isAuthenticated, logout } = useAuth();
  const pathname = usePathname();
  const [netOpen, setNetOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchValue, setSearchValue] = useState('');
  const netRef = useRef(null);
  const userRef = useRef(null);
  const searchRef = useRef(null);

  const userName = getUserName(user);
  const userInitial = getInitial(user);
  const profilePhotoUrl = getProfilePhotoUrl(user);
  const isNetworkingActive = pathname.startsWith('/dashboard/networking') || pathname.startsWith('/dashboard/communities');

  useEffect(() => {
    const handlePointerDown = (event) => {
      if (netRef.current && !netRef.current.contains(event.target)) {
        setNetOpen(false);
      }
      if (userRef.current && !userRef.current.contains(event.target)) {
        setUserOpen(false);
      }
      if (searchRef.current && !searchRef.current.contains(event.target)) {
        setSearchOpen(false);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, []);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        setNetOpen(false);
        setUserOpen(false);
        setMobileOpen(false);
        setSearchOpen(false);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  useEffect(() => {
    setNetOpen(false);
    setUserOpen(false);
    setMobileOpen(false);
    setSearchOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!mobileOpen) return undefined;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [mobileOpen]);

  const handleLogout = () => {
    setUserOpen(false);
    setMobileOpen(false);
    logout();
  };

  if (!isAuthenticated || !user) {
    return (
      <header className="sticky top-0 z-50 w-full px-4 py-3 md:px-8">
        <div className="mx-auto flex max-w-7xl items-center justify-between rounded-full border border-white/10 bg-slate-950/70 px-5 py-3 shadow-glow backdrop-blur-xl transition-all duration-300">
          <Brand href="/" />
          <div className="flex items-center gap-2 sm:gap-3">
            <Link
              href="/login"
              className={`rounded-full px-4 py-2 text-sm font-medium transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70 ${
                pathname === '/login'
                  ? 'border border-accent/40 bg-accent/10 text-accent shadow-[0_0_15px_rgba(255,143,50,0.2)]'
                  : 'border border-white/10 text-slate-200 hover:border-white/20 hover:text-white'
              }`}
            >
              Login
            </Link>
            <Link
              href="/signup"
              className="rounded-full bg-accent px-5 py-2 text-sm font-medium text-black shadow-[0_8px_30px_rgba(255,143,50,0.35)] transition-all hover:-translate-y-0.5 hover:bg-accentSoft focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
            >
              Create Account
            </Link>
          </div>
        </div>
      </header>
    );
  }

  return (
    <header className="sticky top-0 z-50 w-full border-b border-white/10 bg-slate-950/88 shadow-[0_18px_45px_rgba(0,0,0,0.28),0_0_24px_rgba(255,143,50,0.08)] backdrop-blur-xl">
      <div className="hidden w-full items-center gap-5 px-4 py-3 lg:grid lg:grid-cols-[minmax(190px,auto)_minmax(0,1fr)_auto] lg:px-6 2xl:px-8">
        <Brand />

        <nav className="flex min-w-0 items-center justify-center gap-1.5" aria-label="Primary navigation">
          {primaryNav.map((item) => (
            <NavLink key={item.href} item={item} pathname={pathname} />
          ))}

          <div className="relative" ref={netRef}>
            <button
              type="button"
              onClick={() => setNetOpen((open) => !open)}
              aria-haspopup="menu"
              aria-expanded={netOpen}
              aria-label="Networking menu"
              className={`group flex items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70 ${
                isNetworkingActive
                  ? 'border-accent/35 bg-accent/15 text-accent shadow-[inset_0_-2px_0_rgba(255,143,50,0.85)]'
                  : 'border-transparent text-slate-300 hover:border-white/10 hover:bg-white/[0.04] hover:text-white'
              }`}
            >
              <Users className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span className="hidden min-[1180px]:inline">Networking</span>
              <ChevronDown
                className={`hidden h-3.5 w-3.5 transition-transform duration-150 min-[1180px]:block ${
                  netOpen ? 'rotate-180' : ''
                }`}
                aria-hidden="true"
              />
            </button>

            {netOpen && (
              <div
                role="menu"
                className="absolute left-1/2 top-full z-50 mt-3 w-56 -translate-x-1/2 overflow-hidden rounded-xl border border-white/10 bg-slate-900/98 py-1 shadow-[0_18px_45px_rgba(0,0,0,0.55)] backdrop-blur-xl"
              >
                {networkingLinks.map((item) => {
                  const Icon = item.icon;
                  const active = item.isActive(pathname);

                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      role="menuitem"
                      onClick={() => setNetOpen(false)}
                      aria-current={active ? 'page' : undefined}
                      className={`flex items-center gap-3 px-4 py-3 text-sm transition-colors focus:outline-none focus-visible:bg-white/10 ${
                        active ? 'bg-accent/10 text-accent' : 'text-slate-200 hover:bg-white/[0.06] hover:text-white'
                      }`}
                    >
                      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            )}
          </div>

          <NavLink item={messageNav} pathname={pathname} />
        </nav>

        <div className="flex min-w-0 items-center justify-end gap-2">
          <label className="hidden min-[1180px]:flex w-52 items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-slate-400 transition-colors focus-within:border-accent/45 focus-within:bg-white/[0.07] focus-within:text-slate-200 2xl:w-72">
            <Search className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span className="sr-only">Global search</span>
            <input
              type="search"
              value={searchValue}
              onChange={(event) => setSearchValue(event.target.value)}
              placeholder="Search people, skills, careers..."
              className="min-w-0 flex-1 bg-transparent text-sm text-white placeholder:text-slate-500 focus:outline-none"
            />
          </label>

          <div className="relative min-[1180px]:hidden" ref={searchRef}>
            <button
              type="button"
              aria-label="Open global search"
              aria-expanded={searchOpen}
              onClick={() => setSearchOpen((open) => !open)}
              className="flex h-10 w-10 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-slate-300 transition-colors hover:border-white/20 hover:bg-white/[0.07] hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
            >
              <Search className="h-4 w-4" aria-hidden="true" />
            </button>

            {searchOpen && (
              <label className="absolute right-0 top-full z-50 mt-3 flex w-72 items-center gap-2 rounded-xl border border-white/10 bg-slate-900/98 px-3 py-2 text-sm text-slate-400 shadow-[0_18px_45px_rgba(0,0,0,0.55)] backdrop-blur-xl focus-within:border-accent/45 focus-within:text-slate-200">
                <Search className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="sr-only">Global search</span>
                <input
                  type="search"
                  value={searchValue}
                  onChange={(event) => setSearchValue(event.target.value)}
                  placeholder="Search people, skills, careers..."
                  className="min-w-0 flex-1 bg-transparent text-sm text-white placeholder:text-slate-500 focus:outline-none"
                  autoFocus
                />
              </label>
            )}
          </div>

          <button
            type="button"
            aria-label="Notifications"
            className="relative flex h-10 w-10 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-slate-300 transition-colors hover:border-white/20 hover:bg-white/[0.07] hover:text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
          >
            <Bell className="h-4 w-4" aria-hidden="true" />
          </button>

          <div className="relative" ref={userRef}>
            <button
              type="button"
              onClick={() => setUserOpen((open) => !open)}
              aria-haspopup="menu"
              aria-expanded={userOpen}
              aria-label="User profile menu"
              className="flex max-w-[220px] items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-left transition-colors hover:border-white/20 hover:bg-white/[0.07] focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
            >
              <ProfileAvatar
                src={profilePhotoUrl}
                name={userName}
                username={user?.username}
                alt={userName}
                fallback={userInitial}
                className="h-7 w-7"
              />
              <span className="hidden min-w-0 text-sm font-medium text-slate-100 xl:block">
                <span className="block truncate">{userName}</span>
              </span>
              <ChevronDown
                className={`h-3.5 w-3.5 shrink-0 text-slate-400 transition-transform duration-150 ${
                  userOpen ? 'rotate-180' : ''
                }`}
                aria-hidden="true"
              />
            </button>

            {userOpen && (
              <div
                role="menu"
                className="absolute right-0 top-full z-50 mt-3 w-56 overflow-hidden rounded-xl border border-white/10 bg-slate-900/98 py-1 shadow-[0_18px_45px_rgba(0,0,0,0.55)] backdrop-blur-xl"
              >
                <Link
                  href={profileNav.href}
                  role="menuitem"
                  onClick={() => setUserOpen(false)}
                  className="flex items-center gap-3 px-4 py-3 text-sm text-slate-200 transition-colors hover:bg-white/[0.06] hover:text-white focus:outline-none focus-visible:bg-white/10"
                >
                  <UserRound className="h-4 w-4 shrink-0" aria-hidden="true" />
                  Profile
                </Link>
                <div className="my-1 h-px bg-white/10" />
                <button
                  type="button"
                  role="menuitem"
                  onClick={handleLogout}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm text-rose-200 transition-colors hover:bg-rose-500/10 hover:text-rose-100 focus:outline-none focus-visible:bg-rose-500/10"
                >
                  <LogOut className="h-4 w-4 shrink-0" aria-hidden="true" />
                  Logout
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between gap-3 px-4 py-3 lg:hidden">
        <button
          type="button"
          onClick={() => setMobileOpen(true)}
          aria-label="Open navigation menu"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-slate-200 transition-colors hover:bg-white/[0.07] focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
        >
          <Menu className="h-5 w-5" aria-hidden="true" />
        </button>

        <Brand compact />

        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            aria-label="Notifications"
            className="flex h-10 w-10 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-slate-200 transition-colors hover:bg-white/[0.07] focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
          >
            <Bell className="h-4 w-4" aria-hidden="true" />
          </button>
          <Link
            href={profileNav.href}
            aria-label="Profile"
            className="flex h-10 w-10 items-center justify-center rounded-lg border border-accent/30 bg-accent/10 text-xs font-bold uppercase text-accent transition-colors hover:bg-accent/15 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
          >
            <ProfileAvatar
              src={profilePhotoUrl}
              name={userName}
              username={user?.username}
              alt={userName}
              fallback={userInitial}
              className="h-7 w-7"
              fallbackClassName="bg-transparent text-xs font-bold uppercase text-accent"
            />
          </Link>
        </div>
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation menu">
          <button
            type="button"
            className="absolute inset-0 cursor-default bg-slate-950/72 backdrop-blur-sm"
            aria-label="Close navigation menu"
            onClick={() => setMobileOpen(false)}
          />
          <div className="relative flex h-full w-[min(22rem,calc(100vw-2rem))] flex-col border-r border-white/10 bg-slate-950 px-4 py-4 shadow-[20px_0_55px_rgba(0,0,0,0.45)]">
            <div className="flex items-center justify-between gap-3">
              <Brand compact />
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                aria-label="Close navigation menu"
                className="flex h-10 w-10 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-slate-200 transition-colors hover:bg-white/[0.07] focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
              >
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>

            <label className="mt-5 flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-slate-400 focus-within:border-accent/45 focus-within:text-slate-200">
              <Search className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span className="sr-only">Global search</span>
              <input
                type="search"
                value={searchValue}
                onChange={(event) => setSearchValue(event.target.value)}
                placeholder="Search people, skills, careers..."
                className="min-w-0 flex-1 bg-transparent text-sm text-white placeholder:text-slate-500 focus:outline-none"
              />
            </label>

            <nav className="mt-5 flex flex-1 flex-col gap-1" aria-label="Mobile primary navigation">
              {primaryNav.map((item) => (
                <NavLink
                  key={item.href}
                  item={item}
                  pathname={pathname}
                  onClick={() => setMobileOpen(false)}
                  compact
                />
              ))}

              <div className="mt-2 px-3 pb-1 pt-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Networking
              </div>
              {networkingLinks.map((item) => (
                <NavLink
                  key={item.href}
                  item={item}
                  pathname={pathname}
                  onClick={() => setMobileOpen(false)}
                  compact
                />
              ))}

              <NavLink item={messageNav} pathname={pathname} onClick={() => setMobileOpen(false)} compact />
              <NavLink item={profileNav} pathname={pathname} onClick={() => setMobileOpen(false)} compact />
            </nav>

            <div className="border-t border-white/10 pt-4">
              <div className="mb-3 flex items-center gap-3 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2">
                <ProfileAvatar
                  src={profilePhotoUrl}
                  name={userName}
                  username={user?.username}
                  alt={userName}
                  fallback={userInitial}
                  className="h-8 w-8"
                />
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-white">{userName}</div>
                  <div className="text-xs text-slate-500">Signed in</div>
                </div>
              </div>
              <button
                type="button"
                onClick={handleLogout}
                className="flex w-full items-center gap-3 rounded-lg border border-rose-500/20 px-3 py-2 text-left text-sm font-medium text-rose-200 transition-colors hover:bg-rose-500/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-400/70"
              >
                <LogOut className="h-4 w-4 shrink-0" aria-hidden="true" />
                Logout
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
