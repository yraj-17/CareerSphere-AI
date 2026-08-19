'use client';

import { motion } from 'framer-motion';
import SectionHeading from './SectionHeading';

const scores = [
  { label: 'Technical Knowledge', value: 84 },
  { label: 'Clarity', value: 91 },
  { label: 'Confidence', value: 78 },
  { label: 'Overall Score', value: 85 }
];

export default function InterviewDemo() {
  return (
    <section className="px-4 py-24 md:px-8 md:py-32">
      <div className="mx-auto max-w-7xl">
        <SectionHeading
          eyebrow="Interactive Demo"
          title="Experience the AI Interviewer"
          text="A product moment that makes CareerSphere AI feel usable: real interview prompts, response space, instant evaluation, and precise feedback."
        />

        <div className="mt-16 grid gap-8 lg:grid-cols-[0.92fr_1.08fr]">
          <motion.div
            initial={{ opacity: 0, x: -24 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, amount: 0.25 }}
            transition={{ duration: 0.6 }}
            className="relative overflow-hidden rounded-[2.4rem] border border-white/10 bg-gradient-to-b from-white/[0.08] to-white/[0.03] p-7 shadow-glow backdrop-blur-xl"
          >
            <div className="absolute right-6 top-6 rounded-full border border-accent/20 bg-accent/10 px-3 py-1 text-[11px] uppercase tracking-[0.26em] text-accent">Live Simulation</div>
            <div className="flex items-start gap-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-[1.6rem] border border-white/10 bg-[radial-gradient(circle_at_30%_30%,rgba(255,255,255,0.6),rgba(255,143,50,0.42),rgba(8,12,22,1)_72%)] text-white shadow-[0_0_45px_rgba(255,143,50,0.25)]">
                AI
              </div>
              <div>
                <div className="text-sm uppercase tracking-[0.26em] text-slate-400">AI Interviewer</div>
                <div className="mt-2 text-2xl font-semibold text-white">Technical + HR + Behavioral</div>
                <div className="mt-2 text-sm leading-7 text-slate-300">
                  A guided interview surface designed to ask role-aware questions, track performance, and deliver actionable feedback in real time.
                </div>
              </div>
            </div>
            <div className="mt-8 space-y-4">
              <div className="rounded-[1.7rem] border border-white/10 bg-white/[0.06] p-5 text-sm leading-7 text-white">
                <span className="mb-2 block text-xs uppercase tracking-[0.24em] text-accentSoft">Prompt</span>
                Explain the difference between SQL JOIN and UNION with examples.
              </div>
              <div className="rounded-[1.7rem] border border-cyan/20 bg-cyan/10 p-5 text-sm leading-7 text-slate-100">
                <span className="mb-2 block text-xs uppercase tracking-[0.24em] text-cyan">Candidate response</span>
                JOIN combines columns from multiple tables based on a related key, while UNION combines rows from two queries with compatible column structures.
              </div>
              <div className="rounded-[1.7rem] border border-white/10 bg-white/[0.04] p-5 text-sm leading-7 text-slate-300">
                <span className="mb-2 block text-xs uppercase tracking-[0.24em] text-violet">AI feedback</span>
                Good understanding of relational concepts. Improve your explanation of UNION compatibility requirements.
              </div>
            </div>
            <a href="#cta" className="mt-8 inline-flex rounded-full bg-accent px-6 py-3 text-sm font-semibold text-black transition hover:-translate-y-0.5 hover:bg-accentSoft">
              Try AI Interview
            </a>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 24 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, amount: 0.25 }}
            transition={{ duration: 0.6, delay: 0.05 }}
            className="rounded-[2.4rem] border border-white/10 bg-slate-950/65 p-7 shadow-glow backdrop-blur-xl"
          >
            <div className="text-sm uppercase tracking-[0.25em] text-accent/80">AI Evaluation</div>
            <div className="mt-6 grid gap-4 md:grid-cols-2">
              {scores.map((score, index) => (
                <div key={score.label} className="rounded-[1.7rem] border border-white/10 bg-white/[0.05] p-5">
                  <div className="text-sm text-slate-400">{score.label}</div>
                  <div className="mt-4 flex items-end justify-between gap-4">
                    <div className="text-3xl font-semibold text-white">{score.value}%</div>
                    <div className="h-12 w-12 rounded-full border border-white/10 bg-white/[0.06] p-1">
                      <svg viewBox="0 0 36 36" className="h-full w-full -rotate-90">
                        <path d="M18 2.5a15.5 15.5 0 1 1 0 31a15.5 15.5 0 1 1 0-31" fill="none" stroke="rgba(255,255,255,0.09)" strokeWidth="2.8" />
                        <path
                          d="M18 2.5a15.5 15.5 0 1 1 0 31a15.5 15.5 0 1 1 0-31"
                          fill="none"
                          stroke={index % 2 === 0 ? 'rgba(255,143,50,0.9)' : 'rgba(64,217,255,0.9)'}
                          strokeWidth="2.8"
                          strokeDasharray={`${score.value}, 100`}
                          strokeLinecap="round"
                        />
                      </svg>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-6 rounded-[1.8rem] border border-white/10 bg-gradient-to-br from-white/[0.08] to-white/[0.03] p-6">
              <div className="text-sm uppercase tracking-[0.22em] text-slate-400">Why this section matters</div>
              <div className="mt-3 text-lg leading-8 text-white">
                Instead of presenting CareerSphere AI as a static concept, this section demonstrates how the product can realistically evaluate interview performance and guide improvement.
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
