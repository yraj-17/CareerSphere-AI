'use client';

import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, BrainCircuit, Activity, ShieldCheck, Zap } from 'lucide-react';

export default function Dashboard3DVisual({ user }) {
  const [tilt, setTilt] = useState({ x: 0, y: 0 });

  return (
    <div className="relative overflow-hidden rounded-[2.5rem] border border-white/10 bg-white/[0.03] p-6 sm:p-8 shadow-glow backdrop-blur-2xl">
      {/* Background ambient radial gradients matching Landing Page */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_45%,rgba(255,143,50,0.15),transparent_35%),radial-gradient(circle_at_15%_15%,rgba(64,217,255,0.12),transparent_25%),radial-gradient(circle_at_85%_15%,rgba(155,124,255,0.12),transparent_25%)]" />

      <div className="relative z-10 flex flex-col lg:flex-row items-center justify-between gap-8">
        <div className="max-w-md space-y-4">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-accent/30 bg-accent/10 text-accent text-xs font-semibold uppercase tracking-[0.22em]">
            <Sparkles className="h-3.5 w-3.5" />
            <span>Interactive AI Workspace</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Your Personal AI Career Matrix
          </h2>
          <p className="text-sm leading-relaxed text-slate-300">
            Real-time synchronization active for <span className="text-white font-semibold">{user?.first_name || 'User'}</span>. The AI engine powers continuous profile feedback, interview preparedness analytics, and networking matches.
          </p>

          <div className="grid grid-cols-2 gap-3 pt-2">
            <div className="p-3.5 rounded-2xl border border-white/10 bg-white/[0.04] backdrop-blur-md">
              <div className="flex items-center gap-2 text-accent text-xs font-semibold uppercase tracking-wider">
                <Zap className="h-3.5 w-3.5 text-accent" /> Status
              </div>
              <p className="mt-1 text-sm font-bold text-white">System Active</p>
            </div>
            <div className="p-3.5 rounded-2xl border border-white/10 bg-white/[0.04] backdrop-blur-md">
              <div className="flex items-center gap-2 text-cyan text-xs font-semibold uppercase tracking-wider">
                <Activity className="h-3.5 w-3.5 text-cyan" /> Core Sync
              </div>
              <p className="mt-1 text-sm font-bold text-white">100% Ready</p>
            </div>
          </div>
        </div>

        {/* 3D Visual Element */}
        <motion.div
          className="relative h-[22rem] w-full max-w-[24rem] sm:max-w-[26rem] perspective-[2000px]"
          onMouseMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const x = ((e.clientX - rect.left) / rect.width - 0.5) * 20;
            const y = ((e.clientY - rect.top) / rect.height - 0.5) * -20;
            setTilt({ x, y });
          }}
          onMouseLeave={() => setTilt({ x: 0, y: 0 })}
        >
          {/* Glass Card Container with tilt effect */}
          <div
            className="absolute inset-0 rounded-[2.2rem] border border-white/10 bg-gradient-to-b from-white/10 to-white/[0.02] backdrop-blur-xl shadow-2xl transition-transform duration-200 ease-out"
            style={{ transform: `rotateX(${tilt.y}deg) rotateY(${tilt.x}deg)` }}
          />

          <div
            className="absolute inset-0 [transform-style:preserve-3d] transition-transform duration-200 ease-out"
            style={{ transform: `rotateX(${tilt.y}deg) rotateY(${tilt.x}deg)` }}
          >
            {/* Outer Orbit Ring 1 */}
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 25, repeat: Infinity, ease: 'linear' }}
              className="absolute inset-6 rounded-full border border-dashed border-accent/30 pointer-events-none"
            />

            {/* Outer Orbit Ring 2 */}
            <motion.div
              animate={{ rotate: -360 }}
              transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
              className="absolute inset-12 rounded-full border border-dashed border-cyan/25 pointer-events-none"
            />

            {/* Glowing Central AI Orb */}
            <div className="absolute left-1/2 top-1/2 h-36 w-36 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle_at_30%_30%,rgba(255,255,255,0.9),rgba(255,143,50,0.6),rgba(7,9,15,0.98)_72%)] shadow-[0_0_60px_rgba(255,143,50,0.35)] flex flex-col items-center justify-center text-center p-2">
              <div className="absolute inset-3 rounded-full border border-white/20 bg-[radial-gradient(circle_at_65%_35%,rgba(255,255,255,0.3),transparent_40%)]" />
              <BrainCircuit className="h-6 w-6 text-white mb-1 drop-shadow" />
              <div className="text-[10px] uppercase tracking-[0.24em] text-accentSoft font-bold">AI Core</div>
              <div className="text-xs font-extrabold text-white">CareerSphere</div>
            </div>

            {/* Floating Live Card 1 - Upper Left */}
            <motion.div
              animate={{ y: [0, -8, 0] }}
              transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
              className="absolute top-[8%] left-[2%] w-36 rounded-2xl border border-white/10 bg-slate-950/80 p-3 shadow-[0_0_25px_rgba(255,143,50,0.2)] backdrop-blur-xl"
              style={{ transform: 'translateZ(40px)' }}
            >
              <div className="flex items-center justify-between">
                <Sparkles className="h-4 w-4 text-accent" />
                <span className="text-[9px] uppercase tracking-wider text-emerald-400 font-semibold bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">Live</span>
              </div>
              <div className="mt-2 text-[10px] uppercase tracking-widest text-slate-400">AI Assistant</div>
              <div className="text-xs font-bold text-white truncate">Online & Ready</div>
            </motion.div>

            {/* Floating Live Card 2 - Lower Right */}
            <motion.div
              animate={{ y: [0, 8, 0] }}
              transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
              className="absolute bottom-[10%] right-[2%] w-38 rounded-2xl border border-white/10 bg-slate-950/80 p-3 shadow-[0_0_25px_rgba(64,217,255,0.2)] backdrop-blur-xl"
              style={{ transform: 'translateZ(50px)' }}
            >
              <div className="flex items-center justify-between">
                <ShieldCheck className="h-4 w-4 text-cyan" />
                <span className="text-[9px] uppercase tracking-wider text-cyan font-semibold bg-cyan/10 px-1.5 py-0.5 rounded border border-cyan/20">Active</span>
              </div>
              <div className="mt-2 text-[10px] uppercase tracking-widest text-slate-400">Security</div>
              <div className="text-xs font-bold text-white truncate">JWT Session</div>
            </motion.div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
