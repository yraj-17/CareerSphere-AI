'use client';

import { motion } from 'framer-motion';
import SectionHeading from './SectionHeading';
import { securityCards } from '@/data/siteData';

export default function SecuritySection() {
  return (
    <section className="px-4 py-24 md:px-8 md:py-32">
      <div className="mx-auto max-w-7xl">
        <SectionHeading
          eyebrow="Privacy & Security"
          title="Your Career Data. Your Control."
          text="CareerSphere AI is presented as a privacy-aware career platform, with secure authentication, controlled access, clear storage layers, and scalable infrastructure."
          align="center"
        />
        <div className="mt-14 grid gap-6 md:grid-cols-3">
          {securityCards.map((card, index) => {
            const Icon = card.icon;
            return (
              <motion.div
                key={card.title}
                initial={{ opacity: 0, y: 18 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.3 }}
                transition={{ duration: 0.5, delay: index * 0.07 }}
                className="rounded-[2rem] border border-white/10 bg-white/[0.05] p-7 shadow-[0_20px_50px_rgba(0,0,0,0.25)] backdrop-blur-xl"
              >
                <div className="inline-flex rounded-[1.2rem] border border-accent/25 bg-accent/10 p-4 text-accent">
                  <Icon size={22} />
                </div>
                <h3 className="mt-5 text-xl font-semibold text-white">{card.title}</h3>
                <p className="mt-4 text-sm leading-7 text-slate-300">{card.text}</p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
