'use client';

import { motion } from 'framer-motion';
import SectionHeading from './SectionHeading';
import { aiNodes } from '@/data/siteData';

const positions = [
  'left-[6%] top-[22%]',
  'left-[24%] top-[5%]',
  'right-[24%] top-[5%]',
  'right-[6%] top-[22%]',
  'left-[10%] bottom-[18%]',
  'right-[10%] bottom-[18%]',
  'left-1/2 bottom-[2%] -translate-x-1/2'
];

export default function AIEngine() {
  return (
    <section id="ai-engine" className="px-4 py-24 md:px-8 md:py-32">
      <div className="mx-auto max-w-7xl rounded-[2.8rem] border border-white/10 bg-white/[0.04] p-6 shadow-glow backdrop-blur-2xl md:p-10">
        <SectionHeading
          eyebrow="AI Layer"
          title="The Intelligence Behind CareerSphere"
          text="CareerSphere AI uses an open-source-friendly intelligence layer for question generation, answer evaluation, profile understanding, matching, and personalized recommendations."
        />

        <div className="mt-14 grid gap-10 lg:grid-cols-[1fr_0.9fr]">
          <div className="relative min-h-[34rem] rounded-[2.4rem] border border-white/10 bg-slate-950/65 p-6 overflow-hidden">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_40%,rgba(255,143,50,0.14),transparent_28%),radial-gradient(circle_at_18%_16%,rgba(64,217,255,0.12),transparent_18%),radial-gradient(circle_at_78%_18%,rgba(155,124,255,0.12),transparent_18%)]" />
            <div className="absolute left-1/2 top-1/2 h-48 w-48 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle_at_45%_38%,rgba(255,255,255,0.72),rgba(255,143,50,0.48),rgba(6,9,18,1)_74%)] shadow-[0_0_70px_rgba(255,143,50,0.26)]">
              <div className="absolute inset-4 rounded-full border border-white/15" />
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <div className="text-xs uppercase tracking-[0.3em] text-accentSoft">AI Engine</div>
                <div className="mt-2 text-3xl font-semibold text-white">Ollama + LLMs</div>
              </div>
            </div>

            <svg className="absolute inset-0 h-full w-full" viewBox="0 0 1000 720" preserveAspectRatio="none">
              {[
                [130, 180],
                [320, 84],
                [680, 84],
                [870, 180],
                [180, 560],
                [820, 560],
                [500, 670]
              ].map(([x, y], i) => (
                <line key={i} x1="500" y1="360" x2={x} y2={y} stroke="rgba(255,255,255,0.14)" strokeDasharray="6 8" />
              ))}
            </svg>

            <div className="relative hidden h-full lg:block">
              {aiNodes.map((node, index) => (
                <motion.div
                  key={node}
                  initial={{ opacity: 0, scale: 0.88 }}
                  whileInView={{ opacity: 1, scale: 1 }}
                  viewport={{ once: true, amount: 0.3 }}
                  transition={{ duration: 0.55, delay: index * 0.08 }}
                  className={`absolute ${positions[index]} rounded-full border border-white/10 bg-white/[0.06] px-5 py-3 text-sm font-medium text-white shadow-[0_0_35px_rgba(255,255,255,0.03)] backdrop-blur-xl`}
                >
                  {node}
                </motion.div>
              ))}
            </div>

            <div className="relative grid gap-3 lg:hidden">
              {aiNodes.map((node) => (
                <div key={node} className="rounded-full border border-white/10 bg-white/[0.06] px-4 py-3 text-sm text-white">
                  {node}
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-5">
            <div className="rounded-[2rem] border border-white/10 bg-white/[0.05] p-6 backdrop-blur-xl">
              <div className="text-sm uppercase tracking-[0.25em] text-accent/80">Open-Source AI Stack</div>
              <div className="mt-4 text-xl font-semibold text-white">Built with practical, extensible model options</div>
              <p className="mt-4 text-sm leading-7 text-slate-300">
                The poster architecture references Ollama with model choices such as Qwen, Llama, and Mistral.
                That keeps the concept credible for student projects, prototypes, and privacy-sensitive deployments.
              </p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {['Question Generation', 'Answer Evaluation', 'Feedback & Scoring', 'Profile Analysis & Matching'].map((item) => (
                <div key={item} className="rounded-[1.7rem] border border-white/10 bg-slate-950/60 p-5">
                  <div className="text-base font-semibold text-white">{item}</div>
                  <div className="mt-2 text-sm leading-6 text-slate-400">
                    Purpose-built intelligence blocks that connect user activity with live recommendations and measurable outcomes.
                  </div>
                </div>
              ))}
            </div>
            <div className="rounded-[2rem] border border-accent/20 bg-accent/10 p-6">
              <div className="text-sm uppercase tracking-[0.25em] text-accentSoft">Product Story</div>
              <div className="mt-3 text-lg leading-8 text-white">
                The AI layer is not shown as a black box — it is visualized as an active decision engine powering every career interaction across the platform.
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
