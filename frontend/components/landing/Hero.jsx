'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowRight, BrainCircuit, BriefcaseBusiness, MessageSquareCode, Sparkles, Users } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { heroCards } from '@/data/siteData';

const iconMap = [Sparkles, Users, BriefcaseBusiness, MessageSquareCode, BrainCircuit, Sparkles];

export default function Hero() {
  const { isAuthenticated, user } = useAuth();
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const ctaHref = isAuthenticated && user ? '/dashboard' : '/signup';
  const ctaLabel = isAuthenticated && user ? 'Go to Dashboard' : 'Get Started';

  const cards = useMemo(
    () =>
      heroCards.map((card, index) => ({
        ...card,
        icon: iconMap[index],
        className: [
          'left-[2%] top-[8%]',
          'right-[0%] top-[12%]',
          'left-[6%] bottom-[16%]',
          'right-[5%] bottom-[14%]',
          'left-[28%] -bottom-2',
          'right-[28%] -top-2'
        ][index]
      })),
    []
  );

  return (
    <section id="home" className="relative overflow-hidden px-4 pt-32 md:px-8 md:pt-36">
      <div className="mx-auto grid max-w-7xl items-center gap-16 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7 }}
            className="inline-flex items-center rounded-full border border-accent/30 bg-accent/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.28em] text-accent"
          >
            AI-Powered Career Platform
          </motion.div>
          <motion.h1
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.08 }}
            className="mt-7 max-w-3xl text-5xl font-semibold leading-[0.96] tracking-tight text-white md:text-7xl"
          >
            Build Your Career.
            <span className="mt-2 block bg-gradient-to-r from-accent via-white to-cyan bg-clip-text text-transparent">
              Powered by AI.
            </span>
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.14 }}
            className="mt-7 max-w-2xl text-lg leading-8 text-slate-300"
          >
            CareerSphere AI helps you build a stronger professional profile, prepare for interviews,
            discover opportunities, and connect with the right people — all in one intelligent platform.
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="mt-10 flex flex-col gap-4 sm:flex-row"
          >
            <Link href={ctaHref} className="group inline-flex items-center justify-center rounded-full bg-accent px-7 py-4 text-base font-semibold text-black shadow-[0_20px_45px_rgba(255,143,50,0.28)] transition hover:-translate-y-1 hover:bg-accentSoft">
              {ctaLabel}
              <ArrowRight className="ml-2 transition group-hover:translate-x-1" size={18} />
            </Link>
            <a href="#features" className="inline-flex items-center justify-center rounded-full border border-white/10 bg-white/5 px-7 py-4 text-base font-semibold text-white backdrop-blur transition hover:border-accent/40 hover:bg-white/10">
              Explore Platform
            </a>
          </motion.div>
          <div className="mt-12 grid max-w-2xl gap-4 sm:grid-cols-3">
            {[
              ['AI Profile Optimization', 'Skills + goals + experience'],
              ['Live Interview Intelligence', 'Questioning, scoring, feedback'],
              ['Career Networking Layer', 'Peers, mentors, communities']
            ].map(([title, caption]) => (
              <div key={title} className="rounded-3xl border border-white/10 bg-white/5 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] backdrop-blur-sm">
                <div className="text-sm font-semibold text-white">{title}</div>
                <div className="mt-2 text-sm leading-6 text-slate-400">{caption}</div>
              </div>
            ))}
          </div>
        </div>

        <motion.div
          className="relative mx-auto h-[34rem] w-full max-w-[38rem] perspective-[2000px]"
          initial={{ opacity: 0, scale: 0.96, y: 18 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ duration: 0.9, delay: 0.18 }}
          onMouseMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const x = ((e.clientX - rect.left) / rect.width - 0.5) * 16;
            const y = ((e.clientY - rect.top) / rect.height - 0.5) * -16;
            setTilt({ x, y });
          }}
          onMouseLeave={() => setTilt({ x: 0, y: 0 })}
        >
          <div
            className="absolute inset-0 rounded-[2.5rem] border border-white/10 bg-gradient-to-b from-white/8 to-white/[0.03] backdrop-blur-sm"
            style={{ transform: `rotateX(${tilt.y}deg) rotateY(${tilt.x}deg)` }}
          />
          <div className="absolute inset-0 [transform-style:preserve-3d]" style={{ transform: `rotateX(${tilt.y}deg) rotateY(${tilt.x}deg)` }}>
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 28, repeat: Infinity, ease: 'linear' }}
              className="absolute inset-8 rounded-full border border-dashed border-accent/20"
            />
            <motion.div
              animate={{ rotate: -360 }}
              transition={{ duration: 22, repeat: Infinity, ease: 'linear' }}
              className="absolute inset-16 rounded-full border border-dashed border-cyan/15"
            />
            <div className="absolute left-1/2 top-1/2 h-52 w-52 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle_at_30%_30%,rgba(255,255,255,0.9),rgba(255,143,50,0.55),rgba(14,20,34,0.98)_72%)] shadow-[0_0_70px_rgba(255,143,50,0.28)]">
              <div className="absolute inset-5 rounded-full border border-white/20 bg-[radial-gradient(circle_at_65%_35%,rgba(255,255,255,0.26),transparent_40%),linear-gradient(145deg,rgba(255,255,255,0.12),rgba(255,255,255,0.02))]" />
              <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                <div className="text-xs uppercase tracking-[0.3em] text-accentSoft">AI Core</div>
                <div className="mt-2 text-2xl font-semibold text-white">CareerSphere</div>
                <div className="mt-1 max-w-[10rem] text-xs leading-5 text-slate-300">Profile, interviews, growth, networking</div>
              </div>
            </div>

            {cards.map((card, index) => {
              const Icon = card.icon;
              const tint = card.tone === 'orange' ? 'from-accent/30 to-accent/5' : card.tone === 'cyan' ? 'from-cyan/25 to-cyan/5' : 'from-violet/25 to-violet/5';
              const glow = card.tone === 'orange' ? 'shadow-[0_0_30px_rgba(255,143,50,0.18)]' : card.tone === 'cyan' ? 'shadow-[0_0_30px_rgba(64,217,255,0.16)]' : 'shadow-[0_0_30px_rgba(155,124,255,0.16)]';
              return (
                <motion.div
                  key={card.label}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: [0, -10, 0] }}
                  transition={{ delay: 0.25 + index * 0.08, duration: 7 + index, repeat: Infinity, ease: 'easeInOut' }}
                  className={`absolute ${card.className} w-44 rounded-3xl border border-white/10 bg-gradient-to-b ${tint} p-4 backdrop-blur-xl ${glow}`}
                  style={{ transform: `translateZ(${index % 2 === 0 ? 30 : 60}px)` }}
                >
                  <div className="flex items-center justify-between">
                    <Icon size={16} className="text-white" />
                    <span className="rounded-full border border-white/10 bg-white/10 px-2 py-0.5 text-[10px] uppercase tracking-[0.24em] text-slate-200">
                      Live
                    </span>
                  </div>
                  <div className="mt-5 text-xs uppercase tracking-[0.2em] text-slate-400">{card.label}</div>
                  <div className="mt-2 text-2xl font-semibold text-white">{card.value}</div>
                </motion.div>
              );
            })}

            <div className="absolute left-1/2 top-[17%] -translate-x-1/2 rounded-full border border-white/10 bg-slate-950/60 px-4 py-2 text-xs uppercase tracking-[0.25em] text-slate-300 backdrop-blur-xl">
              Professional AI Ecosystem
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
