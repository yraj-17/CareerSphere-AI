'use client';

import { motion } from 'framer-motion';
import SectionHeading from './SectionHeading';
import { problems } from '@/data/siteData';

export default function ProblemSection() {
  return (
    <section className="px-4 py-24 md:px-8 md:py-32">
      <div className="mx-auto max-w-7xl">
        <SectionHeading
          eyebrow="Problem"
          title="Your Career Journey Shouldn't Be Fragmented"
          text="Students and professionals often bounce between disconnected tools for profiles, interview preparation, opportunities, networking, and feedback. CareerSphere AI reframes those scattered moments into one intelligent ecosystem."
          align="center"
        />

        <div className="relative mt-16 grid gap-6 lg:grid-cols-[1fr_20rem_1fr]">
          <div className="grid gap-6 md:grid-cols-2">
            {problems.slice(0, 3).map((problem, index) => (
              <motion.div
                key={problem}
                initial={{ opacity: 0, x: -30 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, amount: 0.25 }}
                transition={{ duration: 0.5, delay: index * 0.08 }}
                className="rounded-[2rem] border border-white/10 bg-white/5 p-6 backdrop-blur-xl"
              >
                <div className="text-sm uppercase tracking-[0.22em] text-accent/80">Challenge</div>
                <div className="mt-4 text-lg font-medium text-white">{problem}</div>
              </motion.div>
            ))}
          </div>

          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.7 }}
            className="relative mx-auto flex h-80 w-full max-w-xs items-center justify-center"
          >
            <div className="absolute inset-4 rounded-full border border-accent/20 bg-accent/8 blur-3xl" />
            <div className="absolute inset-10 rounded-full border border-cyan/10" />
            <div className="absolute inset-14 rounded-full border border-white/10 bg-[radial-gradient(circle,rgba(255,143,50,0.28),rgba(7,9,15,0.92)_70%)] shadow-[0_0_60px_rgba(255,143,50,0.22)]" />
            <div className="relative z-10 text-center">
              <div className="text-xs uppercase tracking-[0.3em] text-accentSoft">Transition</div>
              <div className="mt-4 text-3xl font-semibold text-white">One intelligent ecosystem.</div>
            </div>
          </motion.div>

          <div className="grid gap-6 md:grid-cols-2">
            {problems.slice(3).map((problem, index) => (
              <motion.div
                key={problem}
                initial={{ opacity: 0, x: 30 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, amount: 0.25 }}
                transition={{ duration: 0.5, delay: index * 0.08 }}
                className="rounded-[2rem] border border-white/10 bg-white/5 p-6 backdrop-blur-xl"
              >
                <div className="text-sm uppercase tracking-[0.22em] text-cyan/80">Gap</div>
                <div className="mt-4 text-lg font-medium text-white">{problem}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
