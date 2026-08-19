'use client';

import { motion } from 'framer-motion';
import SectionHeading from './SectionHeading';
import { networkRoles } from '@/data/siteData';

const rolePositions = [
  'left-[10%] top-[24%]',
  'left-[28%] top-[8%]',
  'right-[28%] top-[8%]',
  'right-[10%] top-[24%]',
  'left-[18%] bottom-[12%]',
  'right-[18%] bottom-[12%]'
];

export default function NetworkingSection() {
  return (
    <section id="networking" className="px-4 py-24 md:px-8 md:py-32">
      <div className="mx-auto grid max-w-7xl items-center gap-12 lg:grid-cols-[0.95fr_1.05fr]">
        <div>
          <SectionHeading
            eyebrow="Professional Networking"
            title="Don't Build Your Career Alone"
            text="CareerSphere AI turns networking into part of the product core — connecting students, mentors, recruiters, professionals, and communities through one visible growth graph."
          />
          <p className="mt-8 max-w-2xl text-base leading-8 text-slate-300">
            Connect with people who share your goals, skills, interests, and ambitions. The experience is designed to feel active, supportive, and opportunity-aware instead of static.
          </p>
          <a href="#cta" className="mt-10 inline-flex rounded-full border border-white/10 bg-white/[0.06] px-6 py-3 text-sm font-semibold text-white transition hover:border-accent/30 hover:bg-white/[0.10]">
            Explore Network
          </a>
        </div>

        <div className="relative min-h-[34rem] rounded-[2.5rem] border border-white/10 bg-white/[0.04] p-6 shadow-glow backdrop-blur-xl overflow-hidden">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_45%,rgba(255,143,50,0.12),transparent_26%),radial-gradient(circle_at_18%_18%,rgba(64,217,255,0.1),transparent_18%),radial-gradient(circle_at_82%_18%,rgba(155,124,255,0.1),transparent_18%)]" />
          <svg className="absolute inset-0 h-full w-full" viewBox="0 0 1000 700" preserveAspectRatio="none">
            {[
              [190, 200], [350, 90], [650, 90], [810, 200], [270, 570], [730, 570]
            ].map(([x, y], i) => (
              <line key={i} x1="500" y1="350" x2={x} y2={y} stroke={i % 2 === 0 ? 'rgba(255,143,50,0.45)' : 'rgba(64,217,255,0.35)'} strokeWidth="1.4" strokeDasharray="7 8" />
            ))}
          </svg>

          <div className="absolute left-1/2 top-1/2 h-44 w-44 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/10 bg-[radial-gradient(circle_at_45%_35%,rgba(255,255,255,0.76),rgba(255,143,50,0.4),rgba(6,10,20,1)_75%)] shadow-[0_0_70px_rgba(255,143,50,0.24)]">
            <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
              <div className="text-xs uppercase tracking-[0.26em] text-accentSoft">Central Profile</div>
              <div className="mt-2 text-2xl font-semibold text-white">You</div>
              <div className="mt-1 text-xs text-slate-300">Skills · Goals · Growth</div>
            </div>
          </div>

          <div className="relative hidden h-full lg:block">
            {networkRoles.map((role, index) => (
              <motion.div
                key={role}
                initial={{ opacity: 0, scale: 0.85 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true, amount: 0.3 }}
                transition={{ duration: 0.55, delay: index * 0.08 }}
                className={`absolute ${rolePositions[index]} rounded-full border border-white/10 bg-white/[0.06] px-5 py-3 text-sm font-medium text-white backdrop-blur-xl`}
              >
                {role}
              </motion.div>
            ))}
          </div>

          <div className="relative grid gap-3 lg:hidden">
            {networkRoles.map((role) => (
              <div key={role} className="rounded-full border border-white/10 bg-white/[0.06] px-4 py-3 text-sm text-white">
                {role}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
