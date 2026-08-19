'use client';

import { motion } from 'framer-motion';
import SectionHeading from './SectionHeading';
import { analytics } from '@/data/siteData';

const lineHeights = [60, 78, 70, 92, 84, 106, 96, 118, 130, 120];
const skillBars = [
  { label: 'System Design', value: 74 },
  { label: 'DSA', value: 88 },
  { label: 'SQL', value: 81 },
  { label: 'Communication', value: 91 }
];

export default function AnalyticsDashboard() {
  return (
    <section className="px-4 py-24 md:px-8 md:py-32">
      <div className="mx-auto max-w-7xl rounded-[2.8rem] border border-white/10 bg-white/[0.04] p-6 shadow-glow backdrop-blur-2xl md:p-10">
        <SectionHeading
          eyebrow="Career Analytics"
          title="A Dashboard That Feels Like a Real SaaS Product"
          text="Readiness, interview performance, skills, communication, and network growth are visualized with high-contrast metrics, charts, and recommendation layers."
        />

        <div className="mt-14 grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="grid gap-6">
            <div className="grid gap-4 md:grid-cols-5">
              {analytics.map((metric, index) => {
                const Icon = metric.icon;
                return (
                  <motion.div
                    key={metric.label}
                    initial={{ opacity: 0, y: 18 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, amount: 0.3 }}
                    transition={{ duration: 0.45, delay: index * 0.06 }}
                    className="rounded-[1.9rem] border border-white/10 bg-slate-950/65 p-5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="rounded-2xl border border-white/10 bg-white/[0.05] p-3">
                        <Icon size={18} className="text-white" />
                      </div>
                      <span className="text-[11px] uppercase tracking-[0.22em] text-accent/80">Live</span>
                    </div>
                    <div className="mt-5 text-sm text-slate-400">{metric.label}</div>
                    <div className="mt-2 text-3xl font-semibold text-white">{metric.value}</div>
                  </motion.div>
                );
              })}
            </div>

            <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
              <div className="rounded-[2rem] border border-white/10 bg-slate-950/60 p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm uppercase tracking-[0.24em] text-slate-400">Progress Timeline</div>
                    <div className="mt-2 text-xl font-semibold text-white">Career Readiness Trend</div>
                  </div>
                  <div className="rounded-full border border-accent/20 bg-accent/10 px-3 py-1 text-xs uppercase tracking-[0.24em] text-accentSoft">AI Updated</div>
                </div>
                <div className="mt-8 h-64 rounded-[1.6rem] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.04),rgba(255,255,255,0.01))] p-5">
                  <div className="flex h-full items-end gap-3">
                    {lineHeights.map((height, index) => (
                      <div key={index} className="relative flex-1">
                        <div className="absolute bottom-0 left-1/2 h-full w-px -translate-x-1/2 bg-white/5" />
                        <motion.div
                          initial={{ height: 0 }}
                          whileInView={{ height }}
                          viewport={{ once: true, amount: 0.3 }}
                          transition={{ duration: 0.7, delay: index * 0.05 }}
                          className={`mx-auto rounded-full ${index > 6 ? 'bg-gradient-to-t from-accent to-cyan' : 'bg-gradient-to-t from-white/10 to-white/35'}`}
                          style={{ width: '0.7rem' }}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="rounded-[2rem] border border-white/10 bg-slate-950/60 p-6">
                <div className="text-sm uppercase tracking-[0.24em] text-slate-400">Skill Graph</div>
                <div className="mt-2 text-xl font-semibold text-white">Priority Improvement Areas</div>
                <div className="mt-8 space-y-5">
                  {skillBars.map((item) => (
                    <div key={item.label}>
                      <div className="mb-2 flex items-center justify-between text-sm text-slate-300">
                        <span>{item.label}</span>
                        <span>{item.value}%</span>
                      </div>
                      <div className="h-3 rounded-full bg-white/6">
                        <motion.div
                          initial={{ width: 0 }}
                          whileInView={{ width: `${item.value}%` }}
                          viewport={{ once: true, amount: 0.4 }}
                          transition={{ duration: 0.9 }}
                          className="h-3 rounded-full bg-gradient-to-r from-accent via-accentSoft to-cyan"
                        />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-8 rounded-[1.6rem] border border-accent/20 bg-accent/10 p-5 text-sm leading-7 text-slate-100">
                  Recommendation: Strengthen system design and consistency in technical articulation to unlock stronger role matches and interview confidence.
                </div>
              </div>
            </div>
          </div>

          <div className="grid gap-6">
            <div className="rounded-[2rem] border border-white/10 bg-slate-950/65 p-6">
              <div className="text-sm uppercase tracking-[0.24em] text-slate-400">Readiness Ring</div>
              <div className="mt-4 flex items-center justify-center">
                <div className="relative h-56 w-56">
                  <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
                    <circle cx="60" cy="60" r="48" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="10" />
                    <circle cx="60" cy="60" r="48" fill="none" stroke="url(#ringGradient)" strokeWidth="10" strokeDasharray="302" strokeDashoffset="54" strokeLinecap="round" />
                    <defs>
                      <linearGradient id="ringGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stopColor="rgba(255,143,50,1)" />
                        <stop offset="100%" stopColor="rgba(64,217,255,1)" />
                      </linearGradient>
                    </defs>
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                    <div className="text-xs uppercase tracking-[0.25em] text-slate-400">Career Readiness</div>
                    <div className="mt-3 text-5xl font-semibold text-white">82%</div>
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-[2rem] border border-white/10 bg-gradient-to-b from-white/[0.08] to-white/[0.03] p-6">
              <div className="text-sm uppercase tracking-[0.24em] text-accentSoft">AI Recommendations</div>
              <div className="mt-5 space-y-4">
                {['Practice one intermediate SQL round this week', 'Improve union vs join edge-case explanation', 'Join backend engineering community discussions', 'Upload one portfolio project from GitHub'].map((item) => (
                  <div key={item} className="rounded-[1.4rem] border border-white/10 bg-slate-950/50 px-4 py-4 text-sm text-slate-200">
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
