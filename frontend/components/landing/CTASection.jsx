'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { useAuth } from '@/context/AuthContext';

export default function CTASection() {
  const { isAuthenticated, user } = useAuth();
  const ctaHref = isAuthenticated && user ? '/dashboard' : '/signup';
  const ctaLabel = isAuthenticated && user ? 'Open Your Dashboard' : 'Start Your Career Journey';

  return (
    <section id="cta" className="px-4 py-24 md:px-8 md:py-32">
      <div className="mx-auto max-w-7xl overflow-hidden rounded-[2.8rem] border border-white/10 bg-gradient-to-br from-[#140d08] via-[#0b1220] to-[#090c15] p-10 shadow-glow md:p-14">
        <div className="relative grid gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
          <div>
            <div className="inline-flex rounded-full border border-accent/25 bg-accent/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.28em] text-accent">
              Final Call To Action
            </div>
            <h2 className="mt-6 text-4xl font-semibold tracking-tight text-white md:text-6xl">
              Your Next Career Move Starts Here.
            </h2>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
              Build smarter. Prepare better. Connect further. Grow faster.
            </p>
            <div className="mt-10 flex flex-col gap-4 sm:flex-row">
              <Link href={ctaHref} className="inline-flex items-center justify-center rounded-full bg-accent px-7 py-4 text-base font-semibold text-black transition hover:-translate-y-0.5 hover:bg-accentSoft">
                {ctaLabel}
              </Link>
              <a href="#features" className="inline-flex items-center justify-center rounded-full border border-white/10 bg-white/[0.05] px-7 py-4 text-base font-semibold text-white transition hover:border-white/20 hover:bg-white/[0.1]">
                Explore CareerSphere AI
              </a>
            </div>
          </div>

          <div className="relative min-h-[22rem]">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 30, repeat: Infinity, ease: 'linear' }}
              className="absolute left-1/2 top-1/2 h-80 w-80 -translate-x-1/2 -translate-y-1/2 rounded-full border border-dashed border-accent/20"
            />
            <motion.div
              animate={{ rotate: -360 }}
              transition={{ duration: 24, repeat: Infinity, ease: 'linear' }}
              className="absolute left-1/2 top-1/2 h-60 w-60 -translate-x-1/2 -translate-y-1/2 rounded-full border border-dashed border-cyan/16"
            />
            <div className="absolute left-1/2 top-1/2 h-52 w-52 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle_at_35%_35%,rgba(255,255,255,0.8),rgba(255,143,50,0.48),rgba(7,9,15,1)_72%)] shadow-[0_0_70px_rgba(255,143,50,0.25)]">
              <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                <div className="text-xs uppercase tracking-[0.3em] text-accentSoft">CareerSphere AI</div>
                <div className="mt-3 text-3xl font-semibold text-white">Launch Ready</div>
              </div>
            </div>
            <div className="absolute left-[15%] top-[18%] rounded-full border border-white/10 bg-white/[0.06] px-4 py-3 text-sm text-white backdrop-blur-xl">
              AI Profiles
            </div>
            <div className="absolute right-[8%] top-[24%] rounded-full border border-white/10 bg-white/[0.06] px-4 py-3 text-sm text-white backdrop-blur-xl">
              Interview Scoring
            </div>
            <div className="absolute left-[10%] bottom-[18%] rounded-full border border-white/10 bg-white/[0.06] px-4 py-3 text-sm text-white backdrop-blur-xl">
              Network Growth
            </div>
            <div className="absolute right-[14%] bottom-[14%] rounded-full border border-white/10 bg-white/[0.06] px-4 py-3 text-sm text-white backdrop-blur-xl">
              Opportunity Matching
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
