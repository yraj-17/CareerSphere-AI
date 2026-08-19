'use client';

import { motion } from 'framer-motion';
import SectionHeading from './SectionHeading';
import { architectureFlow } from '@/data/siteData';

export default function ArchitectureFlow() {
  return (
    <section className="px-4 py-24 md:px-8 md:py-32">
      <div className="mx-auto max-w-7xl">
        <SectionHeading
          eyebrow="System Architecture"
          title="A Premium Interpretation of the Poster's Architecture"
          text="The uploaded poster's system flow is transformed into a layered product narrative, making it easier to understand how users, interfaces, services, AI, and storage fit together."
        />

        <div className="relative mt-16 space-y-5">
          {architectureFlow.map((layer, index) => {
            const Icon = layer.icon;
            return (
              <motion.div
                key={layer.title}
                initial={{ opacity: 0, y: 18 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.25 }}
                transition={{ duration: 0.55, delay: index * 0.06 }}
                className="relative rounded-[2rem] border border-white/10 bg-white/[0.05] p-6 shadow-[0_18px_50px_rgba(0,0,0,0.28)] backdrop-blur-xl"
              >
                <div className="grid gap-6 lg:grid-cols-[16rem_1fr] lg:items-center">
                  <div className="flex items-center gap-4">
                    <div className="rounded-[1.35rem] border border-accent/25 bg-accent/10 p-4 text-accent">
                      <Icon size={24} />
                    </div>
                    <div>
                      <div className="text-sm uppercase tracking-[0.24em] text-slate-400">Layer {index + 1}</div>
                      <div className="mt-1 text-xl font-semibold text-white">{layer.title}</div>
                    </div>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    {layer.bullets.map((bullet) => (
                      <div key={bullet} className="rounded-[1.2rem] border border-white/10 bg-slate-950/60 px-4 py-4 text-sm text-slate-200">
                        {bullet}
                      </div>
                    ))}
                  </div>
                </div>
                {index < architectureFlow.length - 1 ? (
                  <div className="pointer-events-none absolute left-1/2 top-full hidden h-5 w-px -translate-x-1/2 bg-gradient-to-b from-accent/70 to-transparent lg:block" />
                ) : null}
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
