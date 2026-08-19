'use client';

import { motion } from 'framer-motion';
import SectionHeading from './SectionHeading';
import { steps } from '@/data/siteData';

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="px-4 py-24 md:px-8 md:py-32">
      <div className="mx-auto max-w-7xl">
        <SectionHeading
          eyebrow="Journey"
          title="How CareerSphere AI Works"
          text="A guided product story that moves from profile building to interview preparation, insights, opportunity discovery, and network growth."
          align="center"
        />

        <div className="relative mt-16 grid gap-6 lg:grid-cols-5">
          <div className="absolute left-8 right-8 top-1/2 hidden -translate-y-1/2 lg:block">
            <div className="h-px bg-gradient-to-r from-transparent via-accent/60 to-transparent" />
          </div>
          {steps.map((step, index) => (
            <motion.div
              key={step.number}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{ duration: 0.55, delay: index * 0.07 }}
              className="relative rounded-[2rem] border border-white/10 bg-white/[0.05] p-6 shadow-[0_20px_50px_rgba(0,0,0,0.24)] backdrop-blur-xl"
            >
              <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-accent/30 bg-accent/10 text-sm font-bold text-accent">
                {step.number}
              </div>
              <h3 className="mt-5 text-xl font-semibold text-white">{step.title}</h3>
              <p className="mt-4 text-sm leading-7 text-slate-300">{step.text}</p>
              {index < steps.length - 1 ? (
                <div className="mt-6 text-xs uppercase tracking-[0.28em] text-accent/80 lg:hidden">Next ↓</div>
              ) : null}
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
