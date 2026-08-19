'use client';

import { motion } from 'framer-motion';

const particles = Array.from({ length: 18 }, (_, i) => ({
  id: i,
  left: `${(i * 7 + 9) % 100}%`,
  top: `${(i * 11 + 13) % 100}%`,
  delay: (i % 6) * 0.3,
  duration: 6 + (i % 5)
}));

export default function BackgroundFX() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-bg">
      <div className="absolute inset-0 bg-hero-radial" />
      <div className="absolute inset-0 opacity-[0.12] [background-image:linear-gradient(rgba(255,255,255,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.08)_1px,transparent_1px)] [background-size:90px_90px]" />
      <div className="absolute inset-x-0 top-0 h-[32rem] bg-[radial-gradient(circle_at_50%_0%,rgba(255,143,50,0.18),transparent_55%)]" />
      <div className="absolute left-1/2 top-40 h-80 w-80 -translate-x-1/2 rounded-full bg-accent/10 blur-[110px]" />
      <div className="absolute right-[8%] top-[18%] h-64 w-64 rounded-full bg-cyan/10 blur-[100px]" />
      <div className="absolute left-[7%] top-[45%] h-72 w-72 rounded-full bg-violet/10 blur-[120px]" />
      {particles.map((particle) => (
        <motion.div
          key={particle.id}
          className="absolute h-1.5 w-1.5 rounded-full bg-accent/80 shadow-[0_0_18px_rgba(255,143,50,0.8)]"
          style={{ left: particle.left, top: particle.top }}
          animate={{ y: [0, -18, 0], opacity: [0.3, 1, 0.3], scale: [1, 1.15, 1] }}
          transition={{ repeat: Infinity, duration: particle.duration, delay: particle.delay, ease: 'easeInOut' }}
        />
      ))}
      <svg className="absolute inset-0 h-full w-full opacity-30" viewBox="0 0 1440 1200" preserveAspectRatio="none">
        <path d="M100 220 C280 130, 420 280, 620 210 S980 110, 1240 250" stroke="rgba(255,143,50,0.24)" strokeWidth="1.2" fill="none" />
        <path d="M130 720 C360 640, 520 840, 760 720 S1110 580, 1320 770" stroke="rgba(64,217,255,0.16)" strokeWidth="1" fill="none" />
        <path d="M80 990 C260 900, 450 1020, 680 930 S1040 850, 1300 980" stroke="rgba(155,124,255,0.16)" strokeWidth="1" fill="none" />
      </svg>
    </div>
  );
}
