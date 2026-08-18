'use client';

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import {
  Sparkles,
  User,
  Mail,
  Calendar,
  ShieldCheck,
  LogOut,
  Loader2,
  CheckCircle2,
  Briefcase,
  Layers,
} from 'lucide-react';

export default function DashboardPage() {
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 text-indigo-400 animate-spin mb-3" />
        <p className="text-sm text-slate-400">Verifying authenticated session...</p>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return null; // Will redirect via useEffect
  }

  const formattedDate = user.created_at
    ? new Date(user.created_at).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : 'Active Member';

  return (
    <div className="flex-1 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12 w-full space-y-8 animate-fade-in">
      {/* Welcome Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-indigo-900/60 via-slate-900/80 to-slate-950 p-8 sm:p-10 border border-indigo-500/20 shadow-2xl">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-semibold mb-3">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>Authenticated Session Active</span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
              Welcome, {user.first_name} {user.last_name}!
            </h1>
            <p className="mt-2 text-base text-indigo-200/80">
              You are successfully logged in. CareerSphere AI Dashboard
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={logout}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium text-slate-300 bg-slate-800/80 hover:bg-rose-500/20 hover:text-rose-200 border border-slate-700 hover:border-rose-500/30 transition-all shadow-md"
            >
              <LogOut className="h-4 w-4" />
              <span>Log Out</span>
            </button>
          </div>
        </div>

        {/* Decorative background glow */}
        <div className="pointer-events-none absolute -right-10 -bottom-10 h-64 w-64 rounded-full bg-indigo-500/10 blur-3xl" />
      </div>

      {/* Profile & Account Details Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* User Card */}
        <div className="glass-card rounded-2xl p-6 md:col-span-2 space-y-6">
          <div className="flex items-center gap-4 pb-6 border-b border-slate-800">
            <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-cyan-500 flex items-center justify-center text-2xl font-bold text-white shadow-lg shadow-indigo-500/30 uppercase">
              {user.first_name?.[0] || 'U'}
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">
                {user.first_name} {user.last_name}
              </h2>
              <p className="text-sm text-indigo-400 font-mono">@{user.username}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-1">
              <div className="flex items-center gap-2 text-slate-400 text-xs">
                <Mail className="h-4 w-4 text-indigo-400" />
                <span>Email Address</span>
              </div>
              <p className="font-semibold text-white truncate">{user.email}</p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-1">
              <div className="flex items-center gap-2 text-slate-400 text-xs">
                <User className="h-4 w-4 text-indigo-400" />
                <span>Username</span>
              </div>
              <p className="font-semibold text-white font-mono">{user.username}</p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-1">
              <div className="flex items-center gap-2 text-slate-400 text-xs">
                <Calendar className="h-4 w-4 text-indigo-400" />
                <span>Joined Date</span>
              </div>
              <p className="font-semibold text-white">{formattedDate}</p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-1">
              <div className="flex items-center gap-2 text-slate-400 text-xs">
                <ShieldCheck className="h-4 w-4 text-emerald-400" />
                <span>Account Status</span>
              </div>
              <p className="font-semibold text-emerald-400">Verified & Active</p>
            </div>
          </div>
        </div>

        {/* Security & Authentication Info */}
        <div className="glass-card rounded-2xl p-6 flex flex-col justify-between space-y-6">
          <div>
            <div className="flex items-center gap-2 text-base font-semibold text-white mb-4">
              <ShieldCheck className="h-5 w-5 text-indigo-400" />
              <span>Authentication Token</span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Your session is secured via JSON Web Token (JWT) with bcrypt password hashing stored in PostgreSQL.
            </p>
            <div className="mt-4 p-3 rounded-lg bg-slate-900 border border-slate-800 font-mono text-xs text-indigo-300 break-all">
              <span className="text-slate-500 block text-[10px] uppercase font-sans tracking-wider mb-1">User ID</span>
              {user.id}
            </div>
          </div>

          <div className="pt-4 border-t border-slate-800/80">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Security Level</span>
              <span className="text-emerald-400 font-medium">Bcrypt + JWT HS256</span>
            </div>
          </div>
        </div>
      </div>

      {/* Upcoming Modules Preview */}
      <div className="glass-card rounded-2xl p-6 sm:p-8 space-y-4">
        <div className="flex items-center gap-2 text-lg font-bold text-white">
          <Layers className="h-5 w-5 text-indigo-400" />
          <span>Platform Capabilities Status</span>
        </div>
        <p className="text-sm text-slate-400">
          Core authentication module is active. The following modules are staged for upcoming phases:
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
          <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/60 opacity-80">
            <h4 className="text-sm font-semibold text-white flex items-center gap-2">
              <Briefcase className="h-4 w-4 text-slate-400" /> AI Resume & Profile
            </h4>
            <span className="mt-2 inline-block px-2 py-0.5 rounded text-[11px] font-medium bg-slate-800 text-slate-400">
              Phase 2
            </span>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/60 opacity-80">
            <h4 className="text-sm font-semibold text-white flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-slate-400" /> AI Mock Interviewer
            </h4>
            <span className="mt-2 inline-block px-2 py-0.5 rounded text-[11px] font-medium bg-slate-800 text-slate-400">
              Phase 3
            </span>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/60 opacity-80">
            <h4 className="text-sm font-semibold text-white flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-slate-400" /> Mentorship & Network
            </h4>
            <span className="mt-2 inline-block px-2 py-0.5 rounded text-[11px] font-medium bg-slate-800 text-slate-400">
              Phase 4
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
