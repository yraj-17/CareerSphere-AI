'use client';

import React from 'react';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import { Sparkles, ArrowRight, ShieldCheck, Zap, Users, BrainCircuit } from 'lucide-react';

export default function HomePage() {
  const { isAuthenticated, user } = useAuth();

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4 py-16 sm:py-24 max-w-5xl mx-auto w-full text-center">
      {/* Badge */}
      <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-semibold mb-8 shadow-sm">
        <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
        <span>Next-Generation Career Intelligence</span>
      </div>

      {/* Hero Headline */}
      <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white max-w-3xl leading-tight">
        Elevate Your Career with{' '}
        <span className="bg-gradient-to-r from-indigo-400 via-sky-300 to-cyan-400 bg-clip-text text-transparent">
          CareerSphere AI
        </span>
      </h1>

      {/* Subheadline */}
      <p className="mt-6 text-base sm:text-lg text-slate-300 max-w-2xl leading-relaxed">
        The intelligent professional platform for students, fresh graduates, and seasoned professionals.
        Unlock AI-powered career growth, verified credentials, and high-impact networks.
      </p>

      {/* CTA Buttons */}
      <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4 w-full sm:w-auto">
        {isAuthenticated && user ? (
          <Link
            href="/dashboard"
            className="w-full sm:w-auto flex items-center justify-center gap-2 px-7 py-3.5 rounded-xl font-semibold text-white bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 shadow-lg shadow-indigo-600/30 hover:shadow-indigo-600/40 transition-all text-base"
          >
            <span>Go to Dashboard</span>
            <ArrowRight className="h-4 w-4" />
          </Link>
        ) : (
          <>
            <Link
              href="/signup"
              className="w-full sm:w-auto flex items-center justify-center gap-2 px-7 py-3.5 rounded-xl font-semibold text-white bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 shadow-lg shadow-indigo-600/30 hover:shadow-indigo-600/40 transition-all text-base"
            >
              <span>Get Started Free</span>
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/login"
              className="w-full sm:w-auto px-7 py-3.5 rounded-xl font-semibold text-slate-200 bg-slate-900/80 hover:bg-slate-800 border border-slate-700/80 hover:border-slate-600 transition-all text-base"
            >
              Sign In
            </Link>
          </>
        )}
      </div>

      {/* Features preview cards */}
      <div className="mt-20 grid grid-cols-1 sm:grid-cols-3 gap-6 w-full text-left">
        <div className="glass-card rounded-2xl p-6">
          <div className="h-10 w-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4">
            <BrainCircuit className="h-5 w-5" />
          </div>
          <h3 className="text-base font-semibold text-white">AI Career Co-Pilot</h3>
          <p className="mt-2 text-xs sm:text-sm text-slate-400">
            Personalized guidance tailored for your target roles, skills, and industry trends.
          </p>
        </div>

        <div className="glass-card rounded-2xl p-6">
          <div className="h-10 w-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-4">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <h3 className="text-base font-semibold text-white">Secure Authentication</h3>
          <p className="mt-2 text-xs sm:text-sm text-slate-400">
            Enterprise-grade bcrypt password encryption and JWT session tokens.
          </p>
        </div>

        <div className="glass-card rounded-2xl p-6">
          <div className="h-10 w-10 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 mb-4">
            <Users className="h-5 w-5" />
          </div>
          <h3 className="text-base font-semibold text-white">Verified Networking</h3>
          <p className="mt-2 text-xs sm:text-sm text-slate-400">
            Connect directly with mentors, alumni, and top hiring managers in tech.
          </p>
        </div>
      </div>
    </div>
  );
}
