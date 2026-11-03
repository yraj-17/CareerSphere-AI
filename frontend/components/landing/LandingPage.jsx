'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BrainCircuit,
  BriefcaseBusiness,
  Check,
  ChevronRight,
  CircleCheck,
  Database,
  Github,
  Link2,
  Linkedin,
  LockKeyhole,
  Mail,
  Mic2,
  Menu,
  MessageCircleMore,
  Network,
  PanelTop,
  Server,
  ShieldCheck,
  Sparkles,
  Target,
  UsersRound,
  X,
  Zap,
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

const navLinks = [
  { label: 'Home', href: '#home', id: 'home' },
  { label: 'Platform', href: '#platform', id: 'platform' },
  { label: 'How It Works', href: '#how-it-works', id: 'how-it-works' },
  { label: 'AI Technology', href: '#ai-technology', id: 'ai-technology' },
  { label: 'Networking', href: '#networking', id: 'networking' },
  { label: 'About', href: '#about', id: 'about' },
];

const modules = [
  {
    title: 'AI Career Assistant',
    short: 'Ask better career questions',
    description: 'Have profile-aware conversations about career decisions, next steps, and professional positioning in a persistent assistant workspace.',
    route: '/dashboard/ai',
    icon: MessageCircleMore,
    tone: 'navy',
    details: ['Persistent conversations', 'Optional profile context', 'Grounded career guidance'],
  },
  {
    title: 'AI Profile Builder',
    short: 'Turn experience into signal',
    description: 'Shape your experience, education, projects, preferences, and skills into a professional profile that is easier to understand and improve.',
    route: '/dashboard/profile',
    icon: Sparkles,
    tone: 'gold',
    details: ['Experience and education', 'Career preferences', 'AI profile optimization'],
  },
  {
    title: 'Skill Analysis',
    short: 'See the gap to your target role',
    description: 'Compare your current skills against a target career and separate strengths, required gaps, and recommended areas to develop.',
    route: '/dashboard/skill-analysis',
    icon: Target,
    tone: 'blue',
    details: ['Target-role comparison', 'Required and recommended gaps', 'AI skill insights'],
  },
  {
    title: 'Career Matching',
    short: 'Find relevant directions',
    description: 'Retrieve opportunities through semantic search, rank them with deterministic fit signals, and optionally enrich the results with AI explanations.',
    route: '/dashboard/career-matching',
    icon: BriefcaseBusiness,
    tone: 'navy',
    details: ['Semantic retrieval', 'Deterministic scoring', 'Optional Gemini reranking'],
  },
  {
    title: 'AI Interviewer',
    short: 'Practice with structure',
    description: 'Configure role-aware technical, HR, or behavioral interviews, answer questions, and review feedback built around your performance.',
    route: '/dashboard/interview',
    icon: BrainCircuit,
    tone: 'gold',
    details: ['Technical and behavioral modes', 'Text interview workspace', 'Answer evaluation and reports'],
  },
  {
    title: 'Network & Communities',
    short: 'Grow through people',
    description: 'Build accepted connections, participate in communities, message people directly, and exchange resources around your career interests.',
    route: '/dashboard/networking',
    icon: Network,
    tone: 'blue',
    details: ['Connections and discovery', 'Communities and posts', 'Direct messaging'],
  },
];

const orbitCards = [
  { label: 'AI Profile', caption: 'Profile Builder', icon: Sparkles, position: 'left-[0%] top-[10%]' },
  { label: 'Networking', caption: 'Connections', icon: UsersRound, position: 'right-[0%] top-[14%]' },
  { label: 'Career Matching', caption: 'Relevant directions', icon: BriefcaseBusiness, position: 'left-[3%] bottom-[16%]' },
  { label: 'AI Interviewer', caption: 'Practice + feedback', icon: MessageCircleMore, position: 'right-[3%] bottom-[14%]' },
  { label: 'Skill Analysis', caption: 'Target-role gaps', icon: Target, position: 'left-[25%] -bottom-2' },
  { label: 'Career Assistant', caption: 'Profile-aware guidance', icon: BrainCircuit, position: 'right-[22%] top-[1%]' },
];

const journey = [
  ['01', 'Build your profile', 'Capture the experience, skills, education, and direction that make your career story specific.'],
  ['02', 'Understand your skills', 'Map what you know against a target role and see which gaps deserve attention first.'],
  ['03', 'Prepare with AI', 'Practice a focused interview and receive feedback you can act on immediately.'],
  ['04', 'Explore matches', 'Use semantic retrieval and fit signals to discover relevant career directions.'],
  ['05', 'Connect and grow', 'Bring the next step into your network through communities, messages, and shared resources.'],
];

const aiServices = [
  ['Ollama + Qwen', 'Model runtime for career conversations, interview questions, answer evaluation, and grounded explanations.'],
  ['Embeddings + Qdrant', 'Semantic retrieval for profile, career knowledge, and opportunity matching.'],
  ['Deterministic services', 'Explicit scoring and skill-gap logic keep important comparisons inspectable and repeatable.'],
  ['Optional Gemini', 'A second-stage reranking path for career matching when the configured integration is available.'],
];

const architectureNodes = [
  ['EXPERIENCE', 'Next.js client', 'Public landing and authenticated dashboard surfaces.', PanelTop, ['React', 'Tailwind CSS']],
  ['DOMAIN LAYER', 'FastAPI services', 'JWT-guarded APIs coordinate profile, AI, matching, networking, and messaging.', Server, ['SQLAlchemy', 'Pydantic']],
  ['OUTCOMES', 'Useful next action', 'Guidance, a match, feedback, or a realtime conversation.', CircleCheck, ['Assistant', 'Interview', 'Network']],
];

const architectureServices = [
  ['AI inference', 'Ollama + Qwen', 'Chat, insights, interviews, and explanations.', BrainCircuit],
  ['Semantic retrieval', 'Embeddings + Qdrant', 'Profile and career-content vectors for meaning-based search.', Target],
  ['Structured data', 'PostgreSQL', 'Users, profiles, conversations, messages, and opportunities.', Database],
  ['Realtime + files', 'Redis · WebSockets · MinIO', 'Cache, Pub/Sub, presence, and binary media objects.', Network],
];

const architecturePaths = [
  ['Assistant + interviews', 'FastAPI → Ollama / Qwen'],
  ['Career matching', 'Qdrant → deterministic score → optional Gemini → Qwen'],
  ['Messaging', 'FastAPI → PostgreSQL + WebSocket → Redis Pub/Sub'],
  ['Profile + media', 'FastAPI → PostgreSQL + MinIO'],
];

const techGroups = [
  {
    label: 'Experience',
    icon: PanelTop,
    items: [
      ['Next.js', 'App Router foundation for public and authenticated surfaces.'],
      ['React', 'Interactive product components and workflows.'],
      ['Tailwind CSS', 'Shared visual language and responsive layout system.'],
      ['Framer Motion', 'Subtle motion for the product story and interactions.'],
    ],
  },
  {
    label: 'API & domain',
    icon: Server,
    items: [
      ['FastAPI', 'Typed API boundary for product and AI workflows.'],
      ['Python', 'Domain services, orchestration, and matching pipelines.'],
      ['SQLAlchemy', 'ORM and database session layer.'],
      ['Pydantic', 'Request, response, and settings validation.'],
    ],
  },
  {
    label: 'AI & retrieval',
    icon: BrainCircuit,
    items: [
      ['Ollama', 'Local or remote model runtime.'],
      ['Qwen', 'Configured language model for explanations and assistant flows.'],
      ['Qdrant', 'Vector search for semantic retrieval.'],
      ['nomic-embed-text', 'Embedding model served through Ollama.'],
    ],
  },
  {
    label: 'Data & realtime',
    icon: Database,
    items: [
      ['PostgreSQL', 'Structured application data and metadata.'],
      ['Redis', 'Short-lived state, caching, presence, and pub/sub.'],
      ['MinIO', 'S3-compatible storage for files and media.'],
      ['WebSockets', 'Realtime direct messaging channel.'],
    ],
  },
];

function BrandMark({ inverse = false }) {
  return (
    <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-xs font-bold tracking-tight ${inverse ? 'bg-[#FFFFFF] text-[#17243A]' : 'bg-[#17243A] text-[#FFFFFF]'}`}>
      CS
    </span>
  );
}

function Reveal({ children, className = '', delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.18 }}
      transition={{ duration: 0.55, delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

function SectionIntro({ eyebrow, title, text, align = 'left', dark = false }) {
  return (
    <div className={`${align === 'center' ? 'mx-auto text-center' : ''} max-w-3xl`}>
      <p className={`text-xs font-bold uppercase tracking-[0.22em] ${dark ? 'text-[#D6B875]' : 'text-[#A47B2E]'}`}>{eyebrow}</p>
      <h2 className={`mt-4 text-3xl font-semibold tracking-[-0.04em] sm:text-4xl lg:text-[3.25rem] lg:leading-[1.06] ${dark ? 'text-[#FFFFFF]' : 'text-[#172033]'}`}>{title}</h2>
      <p className={`mt-5 max-w-2xl text-base leading-7 sm:text-lg ${align === 'center' ? 'mx-auto' : ''} ${dark ? 'text-[#B6C0D1]' : 'text-[#667085]'}`}>{text}</p>
    </div>
  );
}

function LandingNav() {
  const { isAuthenticated, user } = useAuth();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState('home');
  const ctaHref = isAuthenticated && user ? '/dashboard' : '/signup';
  const ctaLabel = isAuthenticated && user ? 'Open dashboard' : 'Get started';

  useEffect(() => {
    const sections = navLinks.map((item) => document.getElementById(item.id)).filter(Boolean);
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible?.target?.id) setActive(visible.target.id);
      },
      { rootMargin: '-28% 0px -62% 0px', threshold: [0.1, 0.35, 0.7] },
    );
    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, []);

  return (
    <header className="fixed inset-x-0 top-0 z-50 px-4 pt-4 sm:px-6 lg:px-8">
      <div className="mx-auto grid max-w-[1240px] grid-cols-[auto_1fr_auto] items-center rounded-2xl border border-[#E3E7ED]/90 bg-[#FFFFFF]/90 px-4 py-3 shadow-[0_10px_30px_rgba(23,36,58,0.06)] backdrop-blur-xl sm:px-5">
        <a href="#home" className="flex min-w-0 items-center gap-3" onClick={() => setOpen(false)}>
          <BrandMark />
          <span className="hidden min-w-0 sm:block">
            <span className="block truncate text-sm font-bold tracking-tight text-[#17243A]">CareerSphere AI</span>
            <span className="block text-[10px] font-medium uppercase tracking-[0.22em] text-[#667085]">AI career ecosystem</span>
          </span>
        </a>

        <nav className="hidden w-full max-w-[680px] items-center justify-between justify-self-center lg:flex" aria-label="Primary navigation">
          {navLinks.map((item) => (
            <a key={item.id} href={item.href} className={`rounded-lg px-2.5 py-2 text-xs font-semibold transition-colors ${active === item.id ? 'bg-[#EEF1F5] text-[#17243A]' : 'text-[#667085] hover:bg-[#F5F6F8] hover:text-[#17243A]'}`}>
              {item.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-2 lg:justify-self-end lg:flex">
          {!isAuthenticated && <Link href="/login" className="rounded-lg px-3 py-2 text-xs font-semibold text-[#475467] hover:bg-[#F5F6F8] hover:text-[#17243A]">Log in</Link>}
          <Link href={ctaHref} className="inline-flex items-center gap-2 rounded-lg bg-[#17243A] px-4 py-2.5 text-xs font-bold text-[#FFFFFF] transition-colors hover:bg-[#101B2D]">{ctaLabel}<ArrowUpRight className="h-3.5 w-3.5" /></Link>
        </div>

        <button type="button" className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-[#E3E7ED] bg-[#FFFFFF] text-[#17243A] lg:hidden" onClick={() => setOpen((value) => !value)} aria-expanded={open} aria-label="Toggle navigation">
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {open && (
        <div className="mx-auto mt-2 max-w-[1440px] rounded-2xl border border-[#E3E7ED] bg-[#FFFFFF] p-3 shadow-[0_16px_40px_rgba(23,36,58,0.1)] lg:hidden">
          <nav className="flex flex-col gap-1" aria-label="Mobile navigation">
            {navLinks.map((item) => <a key={item.id} href={item.href} onClick={() => setOpen(false)} className={`rounded-lg px-3 py-2.5 text-sm font-semibold ${active === item.id ? 'bg-[#EEF1F5] text-[#17243A]' : 'text-[#475467]'}`}>{item.label}</a>)}
          </nav>
          <div className="mt-3 flex gap-2 border-t border-[#E3E7ED] pt-3">
            {!isAuthenticated && <Link href="/login" onClick={() => setOpen(false)} className="flex-1 rounded-lg border border-[#D0D5DD] px-3 py-2.5 text-center text-sm font-semibold text-[#17243A]">Log in</Link>}
            <Link href={ctaHref} onClick={() => setOpen(false)} className="flex-1 rounded-lg bg-[#17243A] px-3 py-2.5 text-center text-sm font-semibold text-[#FFFFFF]">{ctaLabel}</Link>
          </div>
        </div>
      )}
    </header>
  );
}

function EcosystemOrbit() {
  return (
    <div className="relative mx-auto h-[30rem] w-full max-w-[38rem] sm:h-[34rem]">
      <div className="absolute -inset-8 rounded-[3rem] bg-[radial-gradient(circle,rgba(198,161,91,0.14),transparent_68%)] blur-2xl" />
      <div className="absolute inset-0 rounded-[2.5rem] border border-[#E3E7ED] bg-[#FFFFFF]/60 backdrop-blur-sm" />
      <div className="absolute inset-0 [transform-style:preserve-3d]">
        <motion.div animate={{ rotate: 360 }} transition={{ duration: 28, repeat: Infinity, ease: 'linear' }} className="absolute inset-8 rounded-full border border-dashed border-[#C6A15B]/40" />
        <motion.div animate={{ rotate: -360 }} transition={{ duration: 22, repeat: Infinity, ease: 'linear' }} className="absolute inset-16 rounded-full border border-dashed border-[#315E9B]/25" />
        <div className="absolute left-1/2 top-1/2 h-52 w-52 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle_at_30%_30%,rgba(255,255,255,0.9),rgba(198,161,91,0.55),rgba(16,27,45,0.98)_72%)] shadow-[0_0_70px_rgba(198,161,91,0.28)]">
          <div className="absolute inset-5 rounded-full border border-[#FFFFFF]/20 bg-[radial-gradient(circle_at_65%_35%,rgba(255,255,255,0.26),transparent_40%),linear-gradient(145deg,rgba(255,255,255,0.12),rgba(255,255,255,0.02))]" />
          <div className="absolute inset-0 flex flex-col items-center justify-center px-6 text-center">
            <div className="text-[10px] font-bold uppercase tracking-[0.28em] text-[#17243A]">AI career core</div>
            <div className="mt-2 text-2xl font-semibold text-[#FFFFFF]">CareerSphere</div>
            <div className="mt-1 max-w-[10rem] text-xs leading-5 text-[#E3E7ED]">Profile, skills, interviews, and network</div>
          </div>
        </div>
        {orbitCards.map((card, index) => {
          const Icon = card.icon;
          return (
            <motion.div key={card.label} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: [0, -8, 0] }} transition={{ delay: 0.2 + index * 0.08, duration: 7 + index, repeat: Infinity, ease: 'easeInOut' }} className={`absolute ${card.position} w-40 rounded-2xl border border-[#FFFFFF]/10 bg-[#17243A]/95 p-3.5 shadow-[0_16px_34px_rgba(16,27,45,0.16)] backdrop-blur-xl sm:w-44 sm:rounded-3xl sm:p-4`}>
              <div className="flex items-center justify-between"><Icon className="h-4 w-4 text-[#D6B875]" /><span className="rounded-full border border-[#FFFFFF]/10 bg-[#FFFFFF]/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.18em] text-[#B6C0D1]">Live</span></div>
              <div className="mt-4 text-[10px] font-bold uppercase tracking-[0.14em] text-[#9CA8BB]">{card.label}</div>
              <div className="mt-1 text-xs font-semibold leading-5 text-[#FFFFFF]">{card.caption}</div>
            </motion.div>
          );
        })}
        <div className="absolute left-1/2 top-[20%] -translate-x-1/2 rounded-full border border-[#E3E7ED] bg-[#FFFFFF]/90 px-3 py-1.5 text-[9px] font-bold uppercase tracking-[0.2em] text-[#667085] shadow-[0_8px_18px_rgba(23,36,58,0.06)] sm:top-[18%]">Professional AI ecosystem</div>
      </div>
    </div>
  );
}

function PlatformSection() {
  const [selected, setSelected] = useState(modules[0]);
  const SelectedIcon = selected.icon;
  return (
    <section id="platform" className="scroll-mt-28 bg-[#FFFFFF] px-4 py-24 sm:px-6 lg:px-8 lg:py-32">
      <div className="mx-auto max-w-[1240px]">
        <SectionIntro eyebrow="The platform" title="One connected system for the work between ambition and opportunity." text="CareerSphere AI combines the core activities of career development into a single product journey, so each decision can build on the context before it." />
        <div className="mt-14 grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1">
            {modules.map((module) => { const Icon = module.icon; const isSelected = selected.title === module.title; return <button key={module.title} type="button" onClick={() => setSelected(module)} className={`group flex items-center gap-3 rounded-xl border p-4 text-left transition ${isSelected ? 'border-[#17243A] bg-[#17243A] text-[#FFFFFF] shadow-[0_12px_26px_rgba(23,36,58,0.12)]' : 'border-[#E3E7ED] bg-[#FFFFFF] text-[#172033] hover:border-[#B9C2D0] hover:bg-[#F7F8FA]'}`}><span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${isSelected ? 'bg-[#FFFFFF]/10 text-[#D6B875]' : 'bg-[#EEF1F5] text-[#17243A]'}`}><Icon className="h-5 w-5" /></span><span className="min-w-0 flex-1"><span className="block text-sm font-bold">{module.title}</span><span className={`mt-0.5 block truncate text-xs ${isSelected ? 'text-[#C6CEDB]' : 'text-[#667085]'}`}>{module.short}</span></span><ChevronRight className={`h-4 w-4 shrink-0 transition-transform ${isSelected ? 'text-[#D6B875]' : 'text-[#98A2B3] group-hover:translate-x-0.5'}`} /></button>; })}
          </div>
          <div className="relative overflow-hidden rounded-[1.5rem] border border-[#E3E7ED] bg-[#F7F8FA] p-6 sm:p-8">
            <div className="absolute right-0 top-0 h-52 w-52 rounded-full bg-[#C6A15B]/10 blur-3xl" />
            <div className="relative flex h-full flex-col justify-between">
              <div><div className="flex items-center gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#17243A] text-[#D6B875]"><SelectedIcon className="h-5 w-5" /></span><div><p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#A47B2E]">Verified product area</p><h3 className="mt-1 text-2xl font-semibold tracking-tight text-[#172033]">{selected.title}</h3></div></div><p className="mt-6 max-w-xl text-base leading-7 text-[#475467]">{selected.description}</p><div className="mt-6 grid gap-3 sm:grid-cols-3">{selected.details.map((detail) => <div key={detail} className="rounded-xl border border-[#E3E7ED] bg-[#FFFFFF] p-4"><Check className="h-4 w-4 text-[#A47B2E]" /><p className="mt-3 text-xs font-semibold leading-5 text-[#172033]">{detail}</p></div>)}</div></div>
              <div className="mt-8 flex flex-wrap items-center gap-3"><Link href={selected.route} className="inline-flex items-center gap-2 rounded-lg bg-[#17243A] px-4 py-3 text-sm font-bold text-[#FFFFFF] hover:bg-[#101B2D]">Open {selected.title}<ArrowUpRight className="h-4 w-4" /></Link><span className="text-xs text-[#667085]">Uses existing CareerSphere functionality</span></div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function JourneySection() {
  return (
    <section id="how-it-works" className="scroll-mt-28 bg-[#F7F8FA] px-4 py-24 sm:px-6 lg:px-8 lg:py-32">
      <div className="mx-auto max-w-[1240px]"><SectionIntro eyebrow="How it works" title="From career goals to measurable progress." text="A simple loop: make your direction visible, understand the gap, practice the next step, then grow through better opportunities and people." />
        <div className="relative mt-14 grid gap-3 lg:grid-cols-5"><div className="absolute left-[10%] right-[10%] top-7 hidden h-px bg-[#D0D5DD] lg:block" />{journey.map(([number, title, text], index) => <Reveal key={number} delay={index * 0.05} className="relative"><div className="h-full rounded-2xl border border-[#E3E7ED] bg-[#FFFFFF] p-5"><div className="relative flex h-10 w-10 items-center justify-center rounded-lg bg-[#17243A] text-xs font-bold text-[#FFFFFF]">{number}</div><h3 className="mt-6 text-base font-bold text-[#172033]">{title}</h3><p className="mt-3 text-sm leading-6 text-[#667085]">{text}</p>{index < journey.length - 1 && <ArrowDownRight className="mt-5 hidden h-4 w-4 text-[#C6A15B] lg:block" />}</div></Reveal>)}</div>
      </div>
    </section>
  );
}

function AISection() {
  return (
    <section id="ai-technology" className="scroll-mt-28 bg-[#F7F8FA] px-4 py-24 sm:px-6 lg:px-8 lg:py-32">
      <div className="mx-auto max-w-[1240px]"><div className="overflow-hidden rounded-[1.5rem] border border-[#26344C] bg-[#101B2D] p-5 shadow-[0_18px_48px_rgba(23,36,58,0.12)] sm:p-8 lg:p-10"><div className="grid gap-12 lg:grid-cols-[0.85fr_1.15fr] lg:items-start"><div><SectionIntro dark eyebrow="AI technology" title="Intelligence behind every career decision." text="The AI layer is practical and inspectable: model inference, retrieval, deterministic comparisons, and optional reranking each have a clear responsibility." /><div className="mt-8 flex items-center gap-3 text-sm text-[#B6C0D1]"><span className="h-px w-10 bg-[#C6A15B]" />No black-box product claims. Just the services the repository actually uses.</div></div><div className="grid gap-3 sm:grid-cols-2">{aiServices.map(([title, text], index) => <Reveal key={title} delay={index * 0.05}><div className="h-full rounded-2xl border border-[#FFFFFF]/10 bg-[#FFFFFF]/[0.05] p-5"><div className="flex items-center gap-3"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#FFFFFF]/10 text-[#D6B875]"><Zap className="h-4 w-4" /></span><h3 className="text-sm font-bold text-[#FFFFFF]">{title}</h3></div><p className="mt-4 text-sm leading-6 text-[#B6C0D1]">{text}</p></div></Reveal>)}</div></div>
        <div className="mt-14 overflow-hidden rounded-[1.5rem] border border-[#FFFFFF]/10 bg-[#192238] p-5 sm:p-8">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#D6B875]">The decision layer</p>
              <h3 className="mt-2 max-w-2xl text-2xl font-semibold text-[#FFFFFF]">A service map, not a one-way pipeline</h3>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-[#B6C0D1]">The client reaches FastAPI domain services, which route each product path to the data, AI, retrieval, storage, or realtime capability it actually needs.</p>
            </div>
            <span className="rounded-full border border-[#FFFFFF]/10 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.16em] text-[#B6C0D1]">Verified project architecture</span>
          </div>

          <div className="relative mt-8 grid gap-3 lg:grid-cols-3">
            {architectureNodes.map(([eyebrow, title, text, Icon, tags], index) => <div key={title} className="relative rounded-2xl border border-[#FFFFFF]/10 bg-[#FFFFFF]/[0.06] p-5"><div className="flex items-start justify-between gap-4"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#C6A15B]/15 text-[#D6B875]"><Icon className="h-5 w-5" /></span><span className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#9CA8BB]">{eyebrow}</span></div><h4 className="mt-5 text-base font-bold text-[#FFFFFF]">{title}</h4><p className="mt-2 min-h-10 text-sm leading-6 text-[#B6C0D1]">{text}</p><div className="mt-4 flex flex-wrap gap-2">{tags.map((tag) => <span key={tag} className="rounded-full bg-[#FFFFFF]/10 px-2.5 py-1 text-[10px] font-semibold text-[#D0D7E4]">{tag}</span>)}</div>{index < architectureNodes.length - 1 && <span className="absolute -right-5 top-1/2 z-10 hidden h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full border border-[#C6A15B]/30 bg-[#192238] text-[#D6B875] lg:flex"><ArrowRight className="h-4 w-4" /></span>}</div>)}
          </div>

          <div className="mt-5 rounded-2xl border border-[#FFFFFF]/10 bg-[#101B2D]/55 p-4 sm:p-5">
            <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#D6B875]">Shared service plane</p><p className="mt-1 text-sm font-semibold text-[#FFFFFF]">Capabilities the domain layer can call by product path</p></div><span className="rounded-full bg-[#FFFFFF]/10 px-2.5 py-1 text-[10px] font-semibold text-[#B6C0D1]">Not every request uses every service</span></div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{architectureServices.map(([eyebrow, title, text, Icon]) => <div key={title} className="rounded-xl border border-[#FFFFFF]/10 bg-[#FFFFFF]/[0.04] p-4"><Icon className="h-5 w-5 text-[#D6B875]" /><p className="mt-4 text-sm font-bold text-[#FFFFFF]">{title}</p><p className="mt-1 text-[10px] font-bold uppercase tracking-[0.14em] text-[#9CA8BB]">{eyebrow}</p><p className="mt-3 text-xs leading-5 text-[#B6C0D1]">{text}</p></div>)}</div>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{architecturePaths.map(([label, path]) => <div key={label} className="rounded-xl border border-[#FFFFFF]/10 bg-[#FFFFFF]/[0.04] px-4 py-3"><p className="text-xs font-bold text-[#FFFFFF]">{label}</p><p className="mt-1 text-[11px] leading-5 text-[#9CA8BB]">{path}</p></div>)}</div>
        </div></div>
      </div>
    </section>
  );
}

function InterviewDemoSection() {
  return (
    <section className="bg-[#FFFFFF] px-4 py-24 sm:px-6 lg:px-8 lg:py-32"><div className="mx-auto max-w-[1240px]"><SectionIntro align="center" eyebrow="Product preview" title="Practice the answer, then understand the signal." text="The AI Interviewer is a real product area in the application. This interface preview makes the workflow concrete without pretending sample content is a live user result." /><div className="mt-14 grid gap-6 lg:grid-cols-[1.05fr_0.95fr]"><Reveal className="rounded-[1.5rem] border border-[#E3E7ED] bg-[#F7F8FA] p-5 sm:p-7"><div className="flex items-center justify-between border-b border-[#E3E7ED] pb-5"><div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#17243A] text-[#D6B875]"><BrainCircuit className="h-5 w-5" /></span><div><p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#A47B2E]">AI Interviewer</p><h3 className="mt-1 text-lg font-bold text-[#172033]">Technical practice workspace</h3></div></div><span className="rounded-full border border-[#D0D5DD] bg-[#FFFFFF] px-3 py-1 text-[10px] font-bold uppercase tracking-[0.15em] text-[#667085]">Illustrative</span></div><div className="mt-6 rounded-xl border border-[#E3E7ED] bg-[#FFFFFF] p-5"><p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#A47B2E]">Question</p><p className="mt-3 text-base font-semibold leading-7 text-[#172033]">Explain the difference between SQL JOIN and UNION with examples.</p></div><div className="mt-3 rounded-xl border border-[#D6E1F2] bg-[#F4F7FB] p-5"><p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#315E9B]">Candidate response</p><p className="mt-3 text-sm leading-6 text-[#475467]">JOIN combines columns from related tables, while UNION combines rows from compatible query results.</p></div><div className="mt-3 rounded-xl border border-[#EADDBF] bg-[#FCF8ED] p-5"><p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#A47B2E]">AI feedback</p><p className="mt-3 text-sm leading-6 text-[#475467]">A clear foundation. Strengthen the explanation with compatibility requirements and a practical example.</p></div></Reveal><Reveal delay={0.08} className="rounded-[1.5rem] bg-[#17243A] p-6 sm:p-7"><div className="flex items-center justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#D6B875]">Evaluation view</p><h3 className="mt-2 text-2xl font-semibold text-[#FFFFFF]">Feedback you can use</h3></div><CircleCheck className="h-6 w-6 text-[#D6B875]" /></div><div className="mt-8 space-y-4">{[['Technical reasoning', 'Explain the trade-off'], ['Clarity', 'Make the example concrete'], ['Confidence', 'Practice the opening sentence']].map(([label, text]) => <div key={label} className="rounded-xl border border-[#FFFFFF]/10 bg-[#FFFFFF]/[0.06] p-4"><div className="flex items-center justify-between gap-4"><span className="text-sm font-semibold text-[#FFFFFF]">{label}</span><span className="h-2 w-2 rounded-full bg-[#D6B875]" /></div><p className="mt-2 text-xs leading-5 text-[#B6C0D1]">{text}</p></div>)}</div><Link href="/dashboard/interview" className="mt-8 inline-flex items-center gap-2 text-sm font-bold text-[#D6B875] hover:text-[#FFFFFF]">Open the AI Interviewer<ArrowRight className="h-4 w-4" /></Link></Reveal></div></div></section>
  );
}

function NetworkingSection() {
  const nodes = [
    ['AI Assistant', 'Profile-aware guidance', BrainCircuit],
    ['Communities', 'Join conversations', Network],
    ['AI Interviewer', 'Practice + feedback', Mic2],
    ['Messages', 'Stay connected', MessageCircleMore],
    ['Peers', 'Discover people', UsersRound],
    ['Resources', 'Share knowledge', Link2],
    ['My Network', 'Connections + requests', Network],
    ['Career Matching', 'Relevant directions', BriefcaseBusiness],
  ];
  const nodePositions = [
    'left-[0%] top-[1%]',
    'left-[25%] top-[1%]',
    'right-[25%] top-[1%]',
    'right-[0%] top-[1%]',
    'left-[0%] top-[44%]',
    'right-[0%] top-[44%]',
    'left-[25%] bottom-[0%]',
    'right-[25%] bottom-[0%]',
  ];
  const connectorPoints = [[70, 60], [300, 60], [700, 60], [930, 60], [70, 280], [930, 280], [300, 505], [700, 505]];

  return (
    <section id="networking" className="scroll-mt-28 bg-[#F7F8FA] px-4 py-24 sm:px-6 lg:px-8 lg:py-32">
      <div className="mx-auto grid max-w-[1240px] gap-12 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
        <div>
          <SectionIntro eyebrow="Professional networking" title="Your career grows through better connections." text="Networking is not an extra tab. CareerSphere gives connections, communities, direct messaging, and resource sharing a place inside the same career workflow." />
          <div className="mt-8 space-y-3">
            {['Discover people aligned with your goals', 'Build accepted professional connections', 'Share resources and continue the conversation'].map((item) => <div key={item} className="flex items-center gap-3 text-sm font-semibold text-[#475467]"><CircleCheck className="h-4 w-4 shrink-0 text-[#A47B2E]" />{item}</div>)}
          </div>
          <Link href="/dashboard/networking" className="mt-9 inline-flex items-center gap-2 rounded-lg bg-[#17243A] px-4 py-3 text-sm font-bold text-[#FFFFFF] hover:bg-[#101B2D]">Explore networking<ArrowRight className="h-4 w-4" /></Link>
        </div>

        <div className="relative overflow-hidden rounded-[1.5rem] border border-[#E3E7ED] bg-[#FFFFFF] p-6 shadow-[0_16px_40px_rgba(23,36,58,0.06)] sm:p-8">
          <div className="absolute -right-24 -top-24 h-64 w-64 rounded-full bg-[#C6A15B]/10 blur-3xl" />
          <div className="relative flex flex-wrap items-start justify-between gap-4 border-b border-[#E3E7ED] pb-5">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#A47B2E]">Career graph</p>
              <h3 className="mt-2 max-w-md text-xl font-semibold tracking-tight text-[#172033]">People and resources around your next move</h3>
            </div>
            <span className="rounded-full border border-[#E3E7ED] bg-[#F7F8FA] px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.16em] text-[#667085]">Connected workflow</span>
          </div>

          <div className="relative mt-6 hidden min-h-[500px] sm:block">
            <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox="0 0 1000 560" preserveAspectRatio="none" aria-hidden="true">
              {connectorPoints.map(([x, y], index) => <line key={`${x}-${y}`} x1="500" y1="280" x2={x} y2={y} stroke={index % 2 === 0 ? 'rgba(198,161,91,0.45)' : 'rgba(49,94,155,0.3)'} strokeWidth="1.5" strokeDasharray="7 8" />)}
            </svg>
            <div className="absolute left-1/2 top-[50%] z-10 flex h-44 w-44 -translate-x-1/2 -translate-y-1/2 flex-col items-center justify-center rounded-full bg-[#17243A] px-5 text-center shadow-[0_18px_45px_rgba(23,36,58,0.2)]">
              <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#D6B875]">Your profile</span>
              <span className="mt-2 text-xl font-semibold text-[#FFFFFF]">One career graph</span>
              <span className="mt-2 text-[11px] leading-5 text-[#B6C0D1]">Skills · goals · growth</span>
            </div>
            {nodes.map(([label, description, Icon], index) => <motion.div key={label} initial={{ opacity: 0, y: 8 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.35 }} transition={{ duration: 0.45, delay: index * 0.08 }} className={`absolute ${nodePositions[index]} z-20 w-28 rounded-2xl border border-[#E3E7ED] bg-[#FFFFFF] p-3 text-center shadow-[0_10px_24px_rgba(23,36,58,0.08)] xl:w-32`}><span className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-[#EEF1F5] text-[#17243A]"><Icon className="h-4 w-4" /></span><span className="mt-2 block text-xs font-bold text-[#172033]">{label}</span><span className="mt-1 block text-[10px] leading-4 text-[#667085]">{description}</span></motion.div>)}
          </div>

          <div className="mt-6 grid gap-2 sm:hidden">
            {nodes.map(([label, description, Icon]) => <div key={label} className="flex items-center gap-3 rounded-xl border border-[#E3E7ED] bg-[#F7F8FA] p-3"><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#FFFFFF] text-[#17243A]"><Icon className="h-4 w-4" /></span><span><span className="block text-sm font-bold text-[#172033]">{label}</span><span className="block text-xs text-[#667085]">{description}</span></span></div>)}
          </div>

          <div className="relative mt-5 flex flex-wrap gap-2 border-t border-[#E3E7ED] pt-4 text-[10px] font-semibold text-[#667085]"><span className="rounded-full bg-[#EEF1F5] px-3 py-1.5">Discover</span><span className="rounded-full bg-[#EEF1F5] px-3 py-1.5">Connect</span><span className="rounded-full bg-[#EEF1F5] px-3 py-1.5">Share</span><span className="ml-auto rounded-full bg-[#FCF8ED] px-3 py-1.5 text-[#A47B2E]">Built into your workflow</span></div>
        </div>
      </div>
    </section>
  );
}

function ArchitectureSection() {
  const layers = [
    ['01', 'Client surfaces', 'Next.js App Router', 'React · Tailwind CSS · Axios', PanelTop],
    ['02', 'Domain API', 'FastAPI on /api', 'JWT · SQLAlchemy · Pydantic', Server],
    ['03', 'AI + retrieval', 'Ollama · Qwen · Qdrant', 'Chat · skills · interviews · matching', BrainCircuit],
    ['04', 'Data + realtime', 'PostgreSQL · Redis', 'WebSockets · Pub/Sub · MinIO', Database],
  ];
  const requestFlows = [
    ['AI assistant', '/api/ai/chat', 'Profile context → Ollama / Qwen', BrainCircuit],
    ['AI interviewer', '/api/interviews', 'Sessions, answers, evaluation → PostgreSQL + Qwen', Mic2],
    ['Skill analysis', '/api/skill-analysis', 'Profile skills → Qdrant similarity search + AI insight', Target],
    ['Career matching', '/api/career-matching', 'Qdrant → deterministic score → optional Gemini → Qwen', BriefcaseBusiness],
    ['Networking', '/api/networking', 'Profiles, connections, requests → PostgreSQL', UsersRound],
    ['Messaging', '/api/messaging/ws', 'WebSocket delivery with Redis Pub/Sub fanout', MessageCircleMore],
  ];
  return (
    <section id="architecture" className="scroll-mt-28 bg-[#FFFFFF] px-4 py-24 sm:px-6 lg:px-8 lg:py-32">
      <div className="mx-auto max-w-[1240px]">
        <div className="grid gap-8 lg:grid-cols-[1fr_0.78fr] lg:items-end">
          <SectionIntro eyebrow="System architecture" title="From a product action to a useful career output." text="CareerSphere is a Next.js client over a FastAPI domain API. Each workflow keeps its own responsibility while sharing profile context, structured data, AI inference, semantic retrieval, and realtime services." />
          <Reveal className="rounded-2xl border border-[#E3E7ED] bg-[#F7F8FA] p-5">
            <div className="flex items-center justify-between gap-4 border-b border-[#E3E7ED] pb-4">
              <div className="flex items-center gap-3"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#17243A] text-[#D6B875]"><Network className="h-4 w-4" /></span><div><p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#A47B2E]">Repository-aligned map</p><p className="mt-1 text-sm font-bold text-[#172033]">Shared services, focused workflows</p></div></div>
              <span className="rounded-full border border-[#D0D5DD] bg-[#FFFFFF] px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-[#667085]">Code-backed</span>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3">
              {[['API prefix', '/api'], ['AI runtime', 'Ollama · Qwen'], ['Realtime', 'WebSocket · Redis'], ['Storage', 'PostgreSQL · MinIO']].map(([label, value]) => <div key={label} className="rounded-xl border border-[#E3E7ED] bg-[#FFFFFF] px-3 py-3"><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#667085]">{label}</p><p className="mt-2 text-xs font-bold text-[#172033]">{value}</p></div>)}
            </div>
          </Reveal>
        </div>

        <div className="mt-12 overflow-hidden rounded-[1.5rem] bg-[#101B2D] p-5 sm:p-8">
          <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[#FFFFFF]/10 pb-5">
            <div><p className="text-[10px] font-bold uppercase tracking-[0.2em] text-[#D6B875]">Architecture map</p><h3 className="mt-2 text-2xl font-semibold tracking-tight text-[#FFFFFF]">One domain layer, several product paths.</h3><p className="mt-3 max-w-2xl text-sm leading-6 text-[#B6C0D1]">The browser does not talk directly to model or infrastructure services. Product actions enter through FastAPI, where authentication, validation, orchestration, and persistence stay explicit.</p></div>
            <span className="rounded-full border border-[#FFFFFF]/10 px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.16em] text-[#B6C0D1]">Verified from the repository</span>
          </div>

          <div className="mt-8 grid gap-3 lg:grid-cols-4">
            {layers.map(([number, title, primary, secondary, Icon], index) => <Reveal key={number} delay={index * 0.05} className="relative"><div className="h-full rounded-2xl border border-[#FFFFFF]/10 bg-[#FFFFFF]/[0.06] p-5"><div className="flex items-center justify-between"><span className="text-[10px] font-bold tracking-[0.18em] text-[#D6B875]">LAYER {number}</span><Icon className="h-5 w-5 text-[#D6B875]" /></div><h4 className="mt-7 text-base font-bold text-[#FFFFFF]">{title}</h4><p className="mt-2 text-sm font-semibold text-[#D0D7E4]">{primary}</p><p className="mt-2 text-xs leading-5 text-[#9CA8BB]">{secondary}</p></div>{index < layers.length - 1 && <span className="absolute -right-5 top-1/2 z-10 hidden h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full border border-[#C6A15B]/30 bg-[#101B2D] text-[#D6B875] lg:flex"><ArrowRight className="h-4 w-4" /></span>}</Reveal>)}
          </div>

          <div className="mt-8 border-t border-[#FFFFFF]/10 pt-6">
            <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#D6B875]">Actual product paths</p><p className="mt-1 text-sm font-semibold text-[#FFFFFF]">The architecture changes with the user’s action.</p></div><span className="rounded-full bg-[#FFFFFF]/10 px-2.5 py-1 text-[10px] font-semibold text-[#B6C0D1]">6 implemented route groups</span></div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{requestFlows.map(([title, route, text, Icon]) => <div key={title} className="rounded-xl border border-[#FFFFFF]/10 bg-[#FFFFFF]/[0.04] p-4"><div className="flex items-center gap-3"><span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#C6A15B]/15 text-[#D6B875]"><Icon className="h-4 w-4" /></span><p className="text-sm font-bold text-[#FFFFFF]">{title}</p></div><p className="mt-4 font-mono text-[10px] font-semibold text-[#D6B875]">{route}</p><p className="mt-2 text-xs leading-5 text-[#B6C0D1]">{text}</p></div>)}</div>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs font-semibold text-[#667085]"><span className="rounded-full bg-[#EEF1F5] px-3 py-1.5">Optional Gemini reranking</span><span className="rounded-full bg-[#EEF1F5] px-3 py-1.5">LanguageTool grammar check</span><span className="rounded-full bg-[#EEF1F5] px-3 py-1.5">Redis Pub/Sub fanout</span><span className="rounded-full bg-[#EEF1F5] px-3 py-1.5">Docker Compose services</span></div>
      </div>
    </section>
  );
}

function TechnologySection() {
  const [active, setActive] = useState('Next.js');
  const activeItem = techGroups.flatMap((group) => group.items).find(([name]) => name === active) || techGroups[0].items[0];
  return (
    <section id="technology" className="scroll-mt-28 bg-[#F7F8FA] px-4 py-24 sm:px-6 lg:px-8 lg:py-32"><div className="mx-auto max-w-[1240px]"><SectionIntro eyebrow="Technology stack" title="Built with technologies that do real work." text="The stack is presented by responsibility, so visitors can understand not only what CareerSphere uses, but why each layer exists." /><div className="mt-14 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]"> <div className="grid gap-3 sm:grid-cols-2">{techGroups.map((group) => { const Icon = group.icon; return <div key={group.label} className="rounded-2xl border border-[#E3E7ED] bg-[#FFFFFF] p-5"><div className="flex items-center gap-3"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#EEF1F5] text-[#17243A]"><Icon className="h-4 w-4" /></span><h3 className="text-sm font-bold text-[#172033]">{group.label}</h3></div><div className="mt-5 space-y-1">{group.items.map(([name]) => <button key={name} type="button" onClick={() => setActive(name)} className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-xs font-semibold transition ${active === name ? 'bg-[#17243A] text-[#FFFFFF]' : 'text-[#475467] hover:bg-[#F5F6F8]'}`}><span>{name}</span><ChevronRight className={`h-3.5 w-3.5 ${active === name ? 'text-[#D6B875]' : 'text-[#98A2B3]'}`} /></button>)}</div></div>; })}</div><div className="h-fit rounded-2xl bg-[#17243A] p-6 text-[#FFFFFF] shadow-[0_18px_42px_rgba(23,36,58,0.14)] lg:sticky lg:top-28"><p className="text-xs font-bold uppercase tracking-[0.2em] text-[#D6B875]">Selected technology</p><h3 className="mt-5 text-3xl font-semibold tracking-tight text-[#FFFFFF]">{activeItem[0]}</h3><p className="mt-4 text-sm leading-7 text-[#B6C0D1]">{activeItem[1]}</p><div className="mt-8 border-t border-[#FFFFFF]/10 pt-5"><p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#9CA8BB]">Architecture note</p><p className="mt-3 text-sm leading-6 text-[#FFFFFF]">CareerSphere keeps this layer focused, so the product can grow without turning every feature into one tightly coupled service.</p></div></div></div></div></section>
  );
}

function TrustSection() {
  const cards = [
    ['JWT + bcrypt', 'JWT identifies authenticated API requests, while bcrypt is used for password hashing and verification.', LockKeyhole],
    ['Controlled access', 'Backend dependencies and domain services enforce authentication, ownership, and accepted-connection boundaries.', ShieldCheck],
    ['Separated storage', 'PostgreSQL stores structured records while MinIO stores binary files and media metadata remains in the application database.', Database],
  ];
  return (
    <section id="about" className="scroll-mt-28 bg-[#FFFFFF] px-4 py-24 sm:px-6 lg:px-8 lg:py-32"><div className="mx-auto max-w-[1240px]"><SectionIntro align="center" eyebrow="Trust and control" title="Your professional data deserves careful protection." text="CareerSphere describes the security foundations that are present in the codebase—without claiming certifications or guarantees the project does not publish." /><div className="mt-14 grid gap-4 md:grid-cols-3">{cards.map(([title, text, Icon], index) => <Reveal key={title} delay={index * 0.06}><div className="h-full rounded-2xl border border-[#E3E7ED] bg-[#F7F8FA] p-6"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#17243A] text-[#D6B875]"><Icon className="h-5 w-5" /></span><h3 className="mt-5 text-lg font-bold text-[#172033]">{title}</h3><p className="mt-3 text-sm leading-6 text-[#667085]">{text}</p></div></Reveal>)}</div></div></section>
  );
}

function LandingFooter() {
  const groups = [
    { title: 'Platform', links: [['AI Career Assistant', '/dashboard/ai'], ['Profile Builder', '/dashboard/profile'], ['Skill Analysis', '/dashboard/skill-analysis'], ['Career Matching', '/dashboard/career-matching'], ['AI Interviewer', '/dashboard/interview'], ['Networking', '/dashboard/networking']] },
    { title: 'Explore', links: [['How it works', '#how-it-works'], ['AI technology', '#ai-technology'], ['Architecture', '#architecture'], ['Resources', '/dashboard/resources'], ['Communities', '/dashboard/communities']] },
    { title: 'Company', links: [['About CareerSphere', '#about'], ['Contact the team', 'mailto:aryanyadav23104212@gmail.com'], ['GitHub project', 'https://github.com/yraj-17/CareerSphere-AI']] },
    { title: 'Trust', links: [['Security foundations', '#about'], ['System architecture', '#architecture'], ['Product preview', '#platform']] },
  ];
  return (
    <footer className="border-t border-[#E3E7ED] bg-[#F7F8FA] px-4 pb-8 pt-16 sm:px-6 lg:px-8"><div className="mx-auto max-w-[1240px]"><div className="grid gap-10 lg:grid-cols-[1.25fr_2fr]"><div><a href="#home" className="flex items-center gap-3"><BrandMark /><span><span className="block text-sm font-bold text-[#17243A]">CareerSphere AI</span><span className="block text-[10px] uppercase tracking-[0.2em] text-[#667085]">AI career ecosystem</span></span></a><p className="mt-5 max-w-xs text-sm leading-6 text-[#667085]">An intelligent ecosystem for professional growth, career preparation, and meaningful connections.</p><div className="mt-6 flex items-center gap-2"><a href="https://github.com/yraj-17/CareerSphere-AI" target="_blank" rel="noreferrer" aria-label="CareerSphere AI GitHub" className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#D0D5DD] bg-[#FFFFFF] text-[#17243A] hover:border-[#17243A]"><Github className="h-4 w-4" /></a><a href="https://www.linkedin.com/in/raj-yadav-706b60397/" target="_blank" rel="noreferrer" aria-label="Raj Yadav on LinkedIn" className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#D0D5DD] bg-[#FFFFFF] text-[#17243A] hover:border-[#17243A]"><Linkedin className="h-4 w-4" /></a><a href="mailto:aryanyadav23104212@gmail.com" aria-label="Email CareerSphere AI" className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#D0D5DD] bg-[#FFFFFF] text-[#17243A] hover:border-[#17243A]"><Mail className="h-4 w-4" /></a></div></div><div className="grid grid-cols-2 gap-8 sm:grid-cols-4">{groups.map((group) => <div key={group.title}><h3 className="text-xs font-bold uppercase tracking-[0.16em] text-[#17243A]">{group.title}</h3><ul className="mt-4 space-y-3">{group.links.map(([label, href]) => <li key={label}><a href={href} className="text-sm text-[#667085] transition-colors hover:text-[#17243A]">{label}</a></li>)}</ul></div>)}</div></div><div className="mt-14 flex flex-col gap-3 border-t border-[#E3E7ED] pt-5 text-xs text-[#667085] sm:flex-row sm:items-center sm:justify-between"><span>© 2026 CareerSphere AI. All rights reserved.</span><span>Built for clearer career decisions.</span></div></div></footer>
  );
}

export default function LandingPage() {
  const { isAuthenticated, user } = useAuth();
  const ctaHref = isAuthenticated && user ? '/dashboard' : '/signup';
  const ctaLabel = isAuthenticated && user ? 'Open your dashboard' : 'Explore CareerSphere';

  return (
    <div className="landing-page min-h-screen overflow-x-clip bg-[#F7F8FA] text-[#172033]">
      <LandingNav />
      <main>
        <section id="home" className="scroll-mt-28 overflow-hidden bg-[#F7F8FA] px-4 pb-20 pt-36 sm:px-6 lg:px-8 lg:pb-28 lg:pt-44"><div className="mx-auto grid max-w-[1240px] items-center gap-14 xl:grid-cols-[0.95fr_1.05fr]"><Reveal><p className="inline-flex items-center gap-2 rounded-full border border-[#E3E7ED] bg-[#FFFFFF] px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.2em] text-[#A47B2E]"><span className="h-1.5 w-1.5 rounded-full bg-[#C6A15B]" />AI-powered career ecosystem</p><h1 className="mt-7 max-w-2xl text-5xl font-semibold leading-[0.98] tracking-[-0.06em] text-[#172033] sm:text-6xl lg:text-6xl xl:text-[5.25rem]">Your career.<span className="block text-[#17243A]">One intelligent ecosystem.</span></h1><p className="mt-7 max-w-xl text-lg leading-8 text-[#475467]">Build your professional identity, strengthen your skills, prepare for interviews, discover relevant directions, and connect with the right people—powered by AI.</p><div className="mt-9 flex flex-col gap-3 sm:flex-row"><Link href={ctaHref} className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#17243A] px-5 py-3.5 text-sm font-bold text-[#FFFFFF] shadow-[0_14px_26px_rgba(23,36,58,0.14)] transition hover:-translate-y-0.5 hover:bg-[#101B2D]">{ctaLabel}<ArrowRight className="h-4 w-4" /></Link><a href="#platform" className="inline-flex items-center justify-center gap-2 rounded-lg border border-[#D0D5DD] bg-[#FFFFFF] px-5 py-3.5 text-sm font-bold text-[#17243A] transition hover:border-[#17243A]">Discover the platform<ArrowDownRight className="h-4 w-4" /></a></div><div className="mt-10 flex flex-wrap gap-x-6 gap-y-3 text-xs font-semibold text-[#667085]"><span className="inline-flex items-center gap-2"><Check className="h-3.5 w-3.5 text-[#A47B2E]" />Profile intelligence</span><span className="inline-flex items-center gap-2"><Check className="h-3.5 w-3.5 text-[#A47B2E]" />Interview preparation</span><span className="inline-flex items-center gap-2"><Check className="h-3.5 w-3.5 text-[#A47B2E]" />Professional networking</span></div></Reveal><Reveal delay={0.1}><EcosystemOrbit /></Reveal></div></section>
        <PlatformSection />
        <JourneySection />
        <AISection />
        <InterviewDemoSection />
        <NetworkingSection />
        <ArchitectureSection />
        <TechnologySection />
        <TrustSection />
        <section id="cta" className="scroll-mt-28 bg-[#F7F8FA] px-4 py-24 sm:px-6 lg:px-8 lg:py-28"><div className="mx-auto max-w-[1240px]"><div className="flex flex-col items-start justify-between gap-8 rounded-[1.5rem] bg-[#17243A] px-6 py-12 shadow-[0_18px_48px_rgba(23,36,58,0.14)] sm:flex-row sm:items-end sm:px-10 lg:px-14"><div><p className="text-xs font-bold uppercase tracking-[0.2em] text-[#D6B875]">Start with clarity</p><h2 className="mt-4 max-w-2xl text-4xl font-semibold leading-tight tracking-[-0.04em] text-[#FFFFFF] sm:text-5xl">Your next career chapter starts here.</h2><p className="mt-5 max-w-xl text-base leading-7 text-[#B6C0D1]">Bring your skills, ambitions, preparation, and professional network into one intelligent ecosystem.</p></div><div className="flex shrink-0 flex-col gap-3 sm:items-end"><Link href={ctaHref} className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#C6A15B] px-5 py-3.5 text-sm font-bold text-[#172033] hover:bg-[#D6B875]">{isAuthenticated && user ? 'Open your dashboard' : 'Get started'}<ArrowUpRight className="h-4 w-4" /></Link><a href="#platform" className="text-center text-sm font-semibold text-[#D6B875] hover:text-[#FFFFFF]">Explore the platform</a></div></div></div></section>
      </main>
      <LandingFooter />
    </div>
  );
}
