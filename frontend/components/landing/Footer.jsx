import { Github, Mail, Users } from 'lucide-react';
import { navItems, team } from '@/data/siteData';

const sectionMap = {
  Home: 'home',
  Features: 'features',
  'How It Works': 'how-it-works',
  'AI Engine': 'ai-engine',
  Networking: 'networking',
  Technology: 'technology',
  About: 'about'
};

export default function Footer() {
  return (
    <footer id="about" className="px-4 pb-12 pt-12 md:px-8">
      <div className="mx-auto max-w-7xl rounded-[2.4rem] border border-white/10 bg-slate-950/75 p-8 shadow-glow backdrop-blur-xl md:p-10">
        <div className="grid gap-10 lg:grid-cols-[1.15fr_0.85fr]">
          <div>
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-accent/30 bg-accent/10 font-bold text-accent">CS</div>
              <div>
                <div className="text-xl font-semibold text-white">{team.name}</div>
                <div className="text-sm text-slate-400">{team.tagline}</div>
              </div>
            </div>
            <p className="mt-6 max-w-2xl text-sm leading-7 text-slate-300">
              A premium 3D landing page concept based on the uploaded project poster, reimagined as a commercial-grade AI career ecosystem for final-year presentation, portfolio use, and placement interviews.
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              <a href={team.github} target="_blank" className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-sm text-white hover:border-white/20" rel="noreferrer">
                <Github size={16} /> GitHub
              </a>
              <a href={`mailto:${team.contact}`} className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 text-sm text-white hover:border-white/20">
                <Mail size={16} /> Contact
              </a>
            </div>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            <div>
              <div className="text-sm uppercase tracking-[0.24em] text-accent/80">Platform</div>
              <div className="mt-4 space-y-3">
                {navItems.map((item) => (
                  <a key={item} href={`#${sectionMap[item]}`} className="block text-sm text-slate-300 transition hover:text-white">
                    {item}
                  </a>
                ))}
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2 text-sm uppercase tracking-[0.24em] text-accent/80">
                <Users size={14} /> Team Information
              </div>
              <div className="mt-4 space-y-3 text-sm text-slate-300">
                {team.members.map((member) => (
                  <div key={member}>{member}</div>
                ))}
                <div className="pt-2 text-white">Project Guide: {team.projectGuide}</div>
                <div>GitHub: {team.github}</div>
                <div>Contact: {team.contact}</div>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-10 grid gap-6 border-t border-white/10 pt-8 md:grid-cols-2">
          <div>
            <div className="text-sm uppercase tracking-[0.24em] text-slate-400">Project References</div>
            <div className="mt-3 space-y-2 text-sm leading-7 text-slate-300">
              {team.references.map((reference) => (
                <div key={reference}>{reference}</div>
              ))}
            </div>
          </div>
          <div className="md:text-right">
            <div className="text-sm uppercase tracking-[0.24em] text-slate-400">Built For</div>
            <div className="mt-3 text-sm leading-7 text-slate-300">
              Final-year project presentation · project demonstration · portfolio showcase · placement interview discussions
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
