import {
  Activity,
  Briefcase,
  Brain,
  ChartColumnBig,
  Compass,
  GitBranch,
  Layers3,
  MessageSquareMore,
  Network,
  ShieldCheck,
  Sparkles,
  Users,
  Workflow,
  Bot,
  Gauge,
  ScanSearch,
  Trophy,
  FolderKanban,
  UserRoundSearch,
  BookOpen,
  Lock,
  Database,
  Cpu,
  Server,
  MonitorSmartphone,
  Radio,
  Blocks
} from 'lucide-react';

export const navItems = [
  'Home',
  'Features',
  'How It Works',
  'AI Engine',
  'Networking',
  'Technology',
  'About'
];

export const problems = [
  'Generic resumes that fail to stand out',
  'Interview anxiety without guided practice',
  'No personalized feedback after mock prep',
  'Too many scattered job and learning resources',
  'Limited access to professional networking',
  'Disconnected communities and career guidance'
];

export const heroCards = [
  { label: 'AI Profile Score', value: '96%', tone: 'orange' },
  { label: 'Interview Readiness', value: '85%', tone: 'cyan' },
  { label: 'Career Match', value: '12 roles', tone: 'violet' },
  { label: 'Community Reach', value: '+48 peers', tone: 'orange' },
  { label: 'Mentor Signals', value: '6 active', tone: 'cyan' },
  { label: 'AI Feedback', value: 'Real-time', tone: 'violet' }
];

export const features = [
  {
    title: 'AI Profile Builder',
    description: 'Create optimized professional profiles aligned with your skills, interests, experience, and career goals.',
    bullets: ['Skill-aware positioning', 'Career-goal optimization', 'Professional summary generation'],
    icon: Sparkles,
    accent: 'from-accent/70 to-accentSoft/20'
  },
  {
    title: 'AI Interviewer',
    description: 'Run HR, technical, and behavioral mock interviews with real-time scoring, feedback, and AI-generated questions.',
    bullets: ['Technical + HR + Behavioral', 'Live evaluation', 'Actionable feedback loop'],
    icon: Bot,
    accent: 'from-cyan/70 to-cyan/10'
  },
  {
    title: 'Performance Analytics',
    description: 'Track readiness, strengths, weaknesses, and continuous improvement using elegant analytics surfaces.',
    bullets: ['Interview score tracking', 'Strength/weakness detection', 'Improvement prompts'],
    icon: Gauge,
    accent: 'from-violet/70 to-violet/10'
  },
  {
    title: 'Skill Analysis',
    description: 'Analyze strong skills, missing skills, and skill gaps to surface the next steps in your growth journey.',
    bullets: ['Gap analysis', 'Recommended skills', 'Growth priority mapping'],
    icon: ScanSearch,
    accent: 'from-accent/70 to-violet/20'
  },
  {
    title: 'Career Matching',
    description: 'Recommend jobs, projects, courses, opportunities, people, and communities based on fit.',
    bullets: ['Role matching', 'Project discovery', 'Opportunity ranking'],
    icon: Briefcase,
    accent: 'from-cyan/70 to-violet/15'
  },
  {
    title: 'Content Recommendation',
    description: 'Surface the most relevant learning resources, career content, projects, articles, and opportunities.',
    bullets: ['Relevant articles', 'Learning resources', 'Contextual recommendations'],
    icon: BookOpen,
    accent: 'from-violet/70 to-accent/15'
  },
  {
    title: 'Professional Networking',
    description: 'Connect, follow, message, and discover professionals who align with your goals and interests.',
    bullets: ['Meaningful connections', 'Messaging and discovery', 'Network growth signals'],
    icon: Network,
    accent: 'from-accent/70 to-cyan/15'
  },
  {
    title: 'Communities',
    description: 'Join or create interest-based communities for collaboration, mentoring, knowledge sharing, and growth.',
    bullets: ['Topic communities', 'Knowledge exchange', 'Collaboration spaces'],
    icon: Users,
    accent: 'from-cyan/70 to-accent/15'
  },
  {
    title: 'Resource Sharing',
    description: 'Share projects, achievements, resources, opportunities, and career experiences across the ecosystem.',
    bullets: ['Projects & achievements', 'Opportunities', 'Peer visibility'],
    icon: FolderKanban,
    accent: 'from-violet/70 to-cyan/15'
  }
];

export const steps = [
  {
    number: '01',
    title: 'Build Your Profile',
    text: 'Create and optimize your professional identity with AI guidance.'
  },
  {
    number: '02',
    title: 'Prepare With AI',
    text: 'Practice realistic mock interviews across technical, HR, and behavioral scenarios.'
  },
  {
    number: '03',
    title: 'Get Insights',
    text: 'Receive performance analysis, skill-gap detection, and personalized feedback.'
  },
  {
    number: '04',
    title: 'Explore Opportunities',
    text: 'Discover jobs, projects, communities, and curated career resources.'
  },
  {
    number: '05',
    title: 'Connect & Grow',
    text: 'Build your network and participate in communities that move your career forward.'
  }
];

export const aiNodes = [
  'Question Generation',
  'Answer Evaluation',
  'Profile Analysis',
  'Skill Analysis',
  'Career Matching',
  'Content Recommendation',
  'Personalized Feedback'
];

export const analytics = [
  { label: 'Career Readiness', value: '82%', icon: Trophy },
  { label: 'Interview Performance', value: '87%', icon: Activity },
  { label: 'Technical Skills', value: '79%', icon: Cpu },
  { label: 'Communication', value: '91%', icon: MessageSquareMore },
  { label: 'Network Growth', value: '+24%', icon: UserRoundSearch }
];

export const networkRoles = [
  'Developers',
  'Recruiters',
  'Mentors',
  'Students',
  'Professionals',
  'Communities'
];

export const techLayers = [
  {
    title: 'Frontend Layer',
    icon: MonitorSmartphone,
    items: [
      { name: 'Next.js', role: 'Modern web app framework for responsive product experience.' },
      { name: 'Tailwind CSS', role: 'Utility-first styling system for premium UI consistency.' }
    ]
  },
  {
    title: 'Backend Layer',
    icon: Server,
    items: [
      { name: 'FastAPI', role: 'High-performance Python backend for APIs and services.' },
      { name: 'Python', role: 'Core language powering orchestration and application logic.' }
    ]
  },
  {
    title: 'AI Engine',
    icon: Brain,
    items: [
      { name: 'Ollama', role: 'Local/open-source LLM runtime for model serving.' },
      { name: 'Qwen / Llama / Mistral', role: 'Open-source model options for question generation and evaluation.' },
      { name: 'Sentence Transformers', role: 'Embeddings and semantic understanding across user data.' }
    ]
  },
  {
    title: 'Data & Storage',
    icon: Database,
    items: [
      { name: 'PostgreSQL', role: 'Stores user, profile, and community data.' },
      { name: 'Qdrant', role: 'Vector database for semantic retrieval and embeddings.' },
      { name: 'Redis', role: 'Caching and session acceleration.' },
      { name: 'MinIO', role: 'File and media object storage.' }
    ]
  },
  {
    title: 'Security & Real-Time',
    icon: Radio,
    items: [
      { name: 'Keycloak', role: 'Secure authentication and identity management.' },
      { name: 'Socket.IO', role: 'Live chat, notifications, and community updates.' },
      { name: 'Docker', role: 'Portable deployment and scalable infrastructure packaging.' }
    ]
  },
  {
    title: 'Support Services',
    icon: Blocks,
    items: [
      { name: 'Faster-Whisper', role: 'Speech-to-text support for interview workflows.' },
      { name: 'LanguageTool', role: 'Grammar and language assistance.' },
      { name: 'GitHub', role: 'Project import and portfolio linking.' },
      { name: 'Email / SMTP', role: 'Notifications and communication events.' }
    ]
  }
];

export const architectureFlow = [
  {
    title: 'Users',
    icon: Users,
    bullets: ['Students', 'Professionals', 'Recruiters', 'Mentors']
  },
  {
    title: 'Web / Mobile Interface',
    icon: MonitorSmartphone,
    bullets: ['Dashboard', 'Profile Builder', 'Interview Module', 'Communities', 'Messaging', 'Notifications']
  },
  {
    title: 'Backend Services',
    icon: Server,
    bullets: ['User & Profile Service', 'Interview Service', 'Community Service', 'Recommendation Service', 'Notification Service', 'Analytics Service']
  },
  {
    title: 'AI Engine',
    icon: Brain,
    bullets: ['LLM runtime via Ollama', 'Question generation', 'Answer evaluation', 'Feedback & scoring', 'Profile analysis & matching', 'Content recommendation']
  },
  {
    title: 'AI Capabilities',
    icon: Workflow,
    bullets: ['Profile Optimization', 'AI Interviewer', 'Skill Analysis', 'Career Matching', 'Content Recommendation']
  },
  {
    title: 'Data & Storage Layer',
    icon: Layers3,
    bullets: ['PostgreSQL', 'Qdrant', 'Redis', 'MinIO']
  },
  {
    title: 'External Integrations',
    icon: GitBranch,
    bullets: ['GitHub', 'Email / SMTP', 'Keycloak', 'LanguageTool', 'Faster-Whisper']
  }
];

export const securityCards = [
  {
    title: 'Secure Authentication',
    text: 'Identity and access flows are designed around secure authentication and controlled entry points.',
    icon: Lock
  },
  {
    title: 'Privacy-Focused Data Control',
    text: 'Career data, profiles, and performance insights are managed with controlled storage layers and clear boundaries.',
    icon: ShieldCheck
  },
  {
    title: 'Scalable Infrastructure',
    text: 'Docker-based deployment, caching, storage separation, and modular services support growth responsibly.',
    icon: Compass
  }
];

export const team = {
  name: 'CareerSphere AI',
  tagline: 'AI-Powered Career & Professional Networking Platform',
  github: 'https://github.com/aryanyadav-dev/CareerSphere-AI',
  contact: 'aryanyadav23104212@gmail.com',
  projectGuide: 'Sachin S Kasare',
  members: [
    'Ritesh Yadav (23104058)',
    'Raj Yadav (23104117)',
    'Anand Yadav (23104042)',
    'Aryan Yadav (23104212)'
  ],
  references: [
    'A Survey on LLM-Based Multi-Agent Systems: Workflow, Infrastructure, and Challenges (2024)',
    'A Survey on LLM-Based Multi-Agent System: Recent Advances and New Frontiers in Applications (2024)'
  ]
};
