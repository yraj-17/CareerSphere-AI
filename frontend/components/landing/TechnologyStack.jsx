'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import Image from 'next/image';
import SectionHeading from './SectionHeading';
import { techLayers } from '@/data/siteData';

export default function TechnologyStack() {
  const [active, setActive] = useState('Next.js');
  const activeInfo = techLayers.flatMap((layer) => layer.items).find((item) => item.name === active) ?? techLayers[0].items[0];

  return (
    <section id="technology" className="px-4 py-24 md:px-8 md:py-32">
      <div className="mx-auto max-w-7xl rounded-[2.8rem] border border-white/10 bg-white/[0.04] p-6 shadow-glow backdrop-blur-2xl md:p-10">
        <SectionHeading
          eyebrow="Technology Architecture"
          title="Built as a Connected Stack, Not a Logo Wall"
          text="The poster's stack is preserved as an interactive layered system so each technology feels tied to a clear product role."
        />

        <div className="mt-14 grid gap-8 xl:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-5">
            {techLayers.map((layer, index) => {
              const Icon = layer.icon;
              return (
                <motion.div
                  key={layer.title}
                  initial={{ opacity: 0, y: 18 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.25 }}
                  transition={{ duration: 0.5, delay: index * 0.06 }}
                  className="rounded-[2rem] border border-white/10 bg-slate-950/65 p-6"
                >
                  <div className="flex items-center gap-4">
                    <div className="rounded-[1.2rem] border border-white/10 bg-white/[0.05] p-3 text-white">
                      <Icon size={20} />
                    </div>
                    <div>
                      <div className="text-sm uppercase tracking-[0.24em] text-slate-400">Layered Stack</div>
                      <div className="text-xl font-semibold text-white">{layer.title}</div>
                    </div>
                  </div>
                  <div className="mt-6 flex flex-wrap gap-3">
                    {layer.items.map((item) => (
                      <button
                        key={item.name}
                        onMouseEnter={() => setActive(item.name)}
                        onFocus={() => setActive(item.name)}
                        onClick={() => setActive(item.name)}
                        className={`rounded-full border px-4 py-2 text-sm transition ${
                          active === item.name
                            ? 'border-accent/40 bg-accent/10 text-white'
                            : 'border-white/10 bg-white/[0.04] text-slate-300 hover:border-white/20 hover:text-white'
                        }`}
                      >
                        {item.name}
                      </button>
                    ))}
                  </div>
                </motion.div>
              );
            })}
          </div>

          <div className="grid gap-6">
            <div className="rounded-[2rem] border border-white/10 bg-gradient-to-b from-white/[0.08] to-white/[0.03] p-7">
              <div className="text-sm uppercase tracking-[0.24em] text-accentSoft">Hovered Technology</div>
              <div className="mt-4 text-3xl font-semibold text-white">{activeInfo.name}</div>
              <p className="mt-4 text-base leading-8 text-slate-300">{activeInfo.role}</p>
            </div>
            <div className="overflow-hidden rounded-[2rem] border border-white/10 bg-slate-950/65 p-6">
              <div className="mb-4 text-sm uppercase tracking-[0.24em] text-slate-400">Reference Poster</div>
              <div className="rounded-[1.4rem] border border-white/10 bg-black/30 p-3">
                <Image
                  src="/careersphere-poster.png"
                  alt="CareerSphere AI project poster reference"
                  width={900}
                  height={560}
                  className="h-auto w-full rounded-[1rem] object-cover"
                />
              </div>
              <p className="mt-4 text-sm leading-7 text-slate-400">
                Included as the primary source reference for product concept, architecture, stack, features, team details, and visual identity.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
