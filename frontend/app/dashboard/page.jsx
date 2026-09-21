'use client';

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import Link from 'next/link';
import {
  Sparkles,
  User,
  Mail,
  Calendar,
  ShieldCheck,
  LogOut,
  Loader2,
  CheckCircle2,
  Layers,
  BarChart2,
  Briefcase,
  Users,
} from 'lucide-react';
import Dashboard3DVisual from '@/components/dashboard/Dashboard3DVisual';

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
        <Loader2 className="h-8 w-8 text-accent animate-spin mb-3" />
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
      <div className="relative overflow-hidden rounded-[2.5rem] border border-white/10 bg-white/[0.04] p-8 sm:p-10 shadow-glow backdrop-blur-2xl">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(255,143,50,0.18),transparent_55%),radial-gradient(circle_at_85%_20%,rgba(64,217,255,0.12),transparent_35%)] pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-semibold mb-3">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>Authenticated Session Active</span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
              Welcome,{' '}
              <span className="bg-gradient-to-r from-accent via-white to-cyan bg-clip-text text-transparent">
                {user.first_name} {user.last_name}!
              </span>
            </h1>
            <p className="mt-2 text-base text-slate-300">
              You are successfully logged in. CareerSphere AI Ecosystem
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={logout}
              className="flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold text-slate-200 border border-white/10 bg-white/5 backdrop-blur hover:border-rose-500/40 hover:bg-rose-500/10 hover:text-rose-200 transition-all"
            >
              <LogOut className="h-4 w-4" />
              <span>Log Out</span>
            </button>
          </div>
        </div>
      </div>

      {/* 3D Visual Component */}
      <Dashboard3DVisual user={user} />

      {/* Profile & Account Details Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* User Card */}
        <div className="rounded-[2.2rem] border border-white/10 bg-white/[0.04] p-6 shadow-glow backdrop-blur-xl md:col-span-2 space-y-6">
          <div className="flex items-center gap-4 pb-6 border-b border-white/10">
            <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-accent via-accentSoft to-cyan flex items-center justify-center text-2xl font-extrabold text-black shadow-[0_0_30px_rgba(255,143,50,0.3)] uppercase">
              {user.first_name?.[0] || 'U'}
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">
                {user.first_name} {user.last_name}
              </h2>
              <p className="text-sm text-accent font-mono">@{user.username}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
            <div className="p-4 rounded-2xl bg-slate-950/60 border border-white/10 space-y-1">
              <div className="flex items-center gap-2 text-slate-400 text-xs">
                <Mail className="h-4 w-4 text-accent" />
                <span>Email Address</span>
              </div>
              <p className="font-semibold text-white truncate">{user.email}</p>
            </div>

            <div className="p-4 rounded-2xl bg-slate-950/60 border border-white/10 space-y-1">
              <div className="flex items-center gap-2 text-slate-400 text-xs">
                <User className="h-4 w-4 text-accent" />
                <span>Username</span>
              </div>
              <p className="font-semibold text-white font-mono">{user.username}</p>
            </div>

            <div className="p-4 rounded-2xl bg-slate-950/60 border border-white/10 space-y-1">
              <div className="flex items-center gap-2 text-slate-400 text-xs">
                <Calendar className="h-4 w-4 text-accent" />
                <span>Joined Date</span>
              </div>
              <p className="font-semibold text-white">{formattedDate}</p>
            </div>

            <div className="p-4 rounded-2xl bg-slate-950/60 border border-white/10 space-y-1">
              <div className="flex items-center gap-2 text-slate-400 text-xs">
                <ShieldCheck className="h-4 w-4 text-emerald-400" />
                <span>Account Status</span>
              </div>
              <p className="font-semibold text-emerald-400">Verified & Active</p>
            </div>
          </div>
        </div>

        {/* Security & Authentication Info */}
        <div className="rounded-[2.2rem] border border-white/10 bg-white/[0.04] p-6 shadow-glow backdrop-blur-xl flex flex-col justify-between space-y-6">
          <div>
            <div className="flex items-center gap-2 text-base font-semibold text-white mb-4">
              <ShieldCheck className="h-5 w-5 text-accent" />
              <span>Authentication Token</span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Your session is secured via JSON Web Token (JWT) with bcrypt password hashing stored in PostgreSQL.
            </p>
            <div className="mt-4 p-3.5 rounded-xl bg-slate-950 border border-white/10 font-mono text-xs text-accentSoft break-all">
              <span className="text-slate-500 block text-[10px] uppercase font-sans tracking-wider mb-1">User ID</span>
              {user.id}
            </div>
          </div>

          <div className="pt-4 border-t border-white/10">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Security Level</span>
              <span className="text-emerald-400 font-medium">Bcrypt + JWT HS256</span>
            </div>
          </div>
        </div>
      </div>

      {/* Upcoming Modules Preview */}
      <div className="rounded-[2.2rem] border border-white/10 bg-white/[0.04] p-6 sm:p-8 space-y-4 shadow-glow backdrop-blur-xl">
        <div className="flex items-center gap-2 text-lg font-bold text-white">
          <Layers className="h-5 w-5 text-accent" />
          <span>Platform Capabilities Status</span>
        </div>
        <p className="text-sm text-slate-400">
          Core authentication is active. The AI Career Assistant is available now; additional modules are staged for upcoming phases:
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-2">
          <Link
            href="/dashboard/ai"
            className="p-4 rounded-2xl bg-white/[0.05] border border-accent/30 hover:border-accent/60 transition-all shadow-[0_0_25px_rgba(255,143,50,0.15)] group"
          >
            <h4 className="text-sm font-semibold text-white flex items-center gap-2 group-hover:text-accent transition-colors">
              <Sparkles className="h-4 w-4 text-accent" /> AI Career Assistant
            </h4>
            <span className="mt-2 inline-block px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
              Available Now
            </span>
          </Link>

          <Link
            href="/dashboard/skill-analysis"
            className="p-4 rounded-2xl bg-white/[0.05] border border-accent/30 hover:border-accent/60 transition-all shadow-[0_0_25px_rgba(255,143,50,0.15)] group"
          >
            <h4 className="text-sm font-semibold text-white flex items-center gap-2 group-hover:text-accent transition-colors">
              <BarChart2 className="h-4 w-4 text-accent" /> Skill Analysis
            </h4>
            <span className="mt-2 inline-block px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
              Available Now
            </span>
          </Link>

          <Link
            href="/dashboard/career-matching"
            className="p-4 rounded-2xl bg-white/[0.05] border border-accent/30 hover:border-accent/60 transition-all shadow-[0_0_25px_rgba(255,143,50,0.15)] group"
          >
            <h4 className="text-sm font-semibold text-white flex items-center gap-2 group-hover:text-accent transition-colors">
              <Briefcase className="h-4 w-4 text-accent" /> Career Matching
            </h4>
            <span className="mt-2 inline-block px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
              Available Now
            </span>
          </Link>

          <Link
            href="/dashboard/networking"
            className="p-4 rounded-2xl bg-white/[0.05] border border-accent/30 hover:border-accent/60 transition-all shadow-[0_0_25px_rgba(255,143,50,0.15)] group"
          >
            <h4 className="text-sm font-semibold text-white flex items-center gap-2 group-hover:text-accent transition-colors">
              <Users className="h-4 w-4 text-accent" /> Networking
            </h4>
            <span className="mt-2 inline-block px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
              Available Now
            </span>
          </Link>
        </div>
      </div>
    </div>
  );
}

