'use client';

import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import SectionHeading from './SectionHeading';
import { features } from '@/data/siteData';

const positions = [
  'left-[6%] top-[12%]',
  'left-[30%] top-[2%]',
  'right-[8%] top-[12%]',
  'left-[0%] top-[40%]',
  'right-[0%] top-[40%]',
  'left-[8%] bottom-[10%]',
  'left-[30%] bottom-[0%]',
  'right-[10%] bottom-[10%]',
  'right-[28%] bottom-[-2%]'
];

export default function FeaturesOrbit() {
  const [active, setActive] = useState(0);
  const feature = features[active];

  const orbitCards = useMemo(() => features.map((item, index) => ({ ...item, position: positions[index] })), []);

  return (
    <section id="features" className="px-4 py-24 md:px-8 md:py-32">
      <div className="mx-auto max-w-7xl">
        <SectionHeading
          eyebrow="Core Features"
          title="Everything You Need to Grow Your Career"
          text="CareerSphere AI connects profile building, interview preparation, insights, opportunities, networking, communities, and resource sharing through one AI-driven career core."
        />

        <div className="mt-16 grid gap-10 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="relative min-h-[46rem] rounded-[2.5rem] border border-white/10 bg-white/[0.03] p-6 shadow-glow backdrop-blur-xl">
            <div className="absolute inset-0 rounded-[2.5rem] bg-[radial-gradient(circle_at_50%_45%,rgba(255,143,50,0.12),transparent_24%),radial-gradient(circle_at_18%_14%,rgba(64,217,255,0.10),transparent_20%),radial-gradient(circle_at_82%_18%,rgba(155,124,255,0.12),transparent_20%)]" />

            <div className="absolute left-1/2 top-1/2 h-44 w-44 -translate-x-1/2 -translate-y-1/2 rounded-full border border-accent/30 bg-[radial-gradient(circle,rgba(255,143,50,0.35),rgba(255,143,50,0.08),rgba(8,12,22,1)_76%)] shadow-[0_0_60px_rgba(255,143,50,0.22)]">
              <div className="absolute inset-4 rounded-full border border-white/10" />
              <div className="absolute inset-0 flex items-center justify-center text-center">
                <div>
                  <div className="text-xs uppercase tracking-[0.28em] text-accentSoft">AI Career Core</div>
                  <div className="mt-2 text-2xl font-semibold text-white">CareerSphere</div>
                </div>
              </div>
            </div>

            <svg className="absolute inset-0 h-full w-full">
              {orbitCards.map((_, index) => {
                const points = [
                  ['22%', '20%'], ['44%', '10%'], ['79%', '20%'], ['14%', '48%'], ['85%', '48%'], ['22%', '80%'], ['45%', '88%'], ['78%', '80%'], ['67%', '92%']
                ][index];
                return (
                  <line
                    key={index}
                    x1="50%"
                    y1="50%"
                    x2={points[0]}
                    y2={points[1]}
                    stroke={index === active ? 'rgba(255,143,50,0.7)' : 'rgba(255,255,255,0.12)'}
                    strokeWidth={index === active ? 2 : 1}
                    strokeDasharray="6 8"
                  />
                );
              })}
            </svg>

            <div className="relative hidden h-full lg:block">
              {orbitCards.map((item, index) => {
                const Icon = item.icon;
                const isActive = active === index;
                return (
                  <motion.button
                    key={item.title}
                    onMouseEnter={() => setActive(index)}
                    onFocus={() => setActive(index)}
                    whileHover={{ y: -10, scale: 1.03 }}
                    className={`absolute ${item.position} w-52 rounded-[1.75rem] border p-5 text-left backdrop-blur-xl transition-all ${
                      isActive
                        ? 'border-accent/40 bg-white/[0.09] shadow-[0_0_50px_rgba(255,143,50,0.18)]'
                        : 'border-white/10 bg-white/[0.04]'
                    }`}
                    style={{ transform: `translateZ(${isActive ? 60 : 15}px)` }}
                  >
                    <div className={`inline-flex rounded-2xl border border-white/10 bg-gradient-to-br ${item.accent} p-3`}>
                      <Icon size={18} className="text-white" />
                    </div>
                    <div className="mt-4 text-base font-semibold text-white">{item.title}</div>
                    <div className="mt-2 text-sm leading-6 text-slate-300">{item.description}</div>
                  </motion.button>
                );
              })}
            </div>

            <div className="relative grid gap-4 lg:hidden">
              {features.map((item, index) => {
                const Icon = item.icon;
                const isActive = active === index;
                return (
                  <button
                    key={item.title}
                    onClick={() => setActive(index)}
                    className={`rounded-[1.6rem] border p-5 text-left transition ${isActive ? 'border-accent/40 bg-white/[0.08]' : 'border-white/10 bg-white/[0.04]'}`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`rounded-2xl border border-white/10 bg-gradient-to-br ${item.accent} p-3`}>
                        <Icon size={18} className="text-white" />
                      </div>
                      <div className="text-base font-semibold text-white">{item.title}</div>
                    </div>
                    <div className="mt-3 text-sm leading-6 text-slate-300">{item.description}</div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="rounded-[2.5rem] border border-white/10 bg-slate-950/60 p-8 shadow-glow backdrop-blur-xl">
            <div className="inline-flex rounded-full border border-accent/25 bg-accent/10 px-3 py-1 text-xs uppercase tracking-[0.24em] text-accent">
              Connected Experience
            </div>
            <div className="mt-6 flex items-center gap-4">
              <div className={`rounded-3xl border border-white/10 bg-gradient-to-br ${feature.accent} p-4`}>
                <feature.icon className="text-white" size={26} />
              </div>
              <div>
                <h3 className="text-2xl font-semibold text-white">{feature.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-300">{feature.description}</p>
              </div>
            </div>

            <div className="mt-8 grid gap-4">
              {feature.bullets.map((bullet) => (
                <div key={bullet} className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-4 text-sm text-slate-200">
                  {bullet}
                </div>
              ))}
            </div>

            <div className="mt-8 rounded-[2rem] border border-white/10 bg-gradient-to-br from-white/[0.08] to-white/[0.02] p-6">
              <div className="text-sm uppercase tracking-[0.25em] text-slate-400">Why it matters</div>
              <div className="mt-4 text-lg leading-8 text-white">
                Every module behaves like a node in one AI-powered career graph — hover depth, central-core reactions,
                and contextual detail make the platform feel like a unified career operating system instead of separate tools.
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
