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
    title: 'Client Experience',
    icon: MonitorSmartphone,
    items: [
      { name: 'Next.js', role: 'App Router foundation for the public landing page and authenticated product surfaces.' },
      { name: 'React', role: 'Component model for interactive dashboards, profiles, communities, messaging, and AI workflows.' },
      { name: 'Tailwind CSS', role: 'Utility-first styling system for the shared CareerSphere visual language.' },
      { name: 'Framer Motion', role: 'Motion layer for landing-page storytelling and responsive product interactions.' },
      { name: 'Axios', role: 'Shared HTTP client for authenticated communication with the FastAPI API.' },
      { name: 'Lucide React', role: 'Consistent icon system used across the marketing and application interfaces.' }
    ]
  },
  {
    title: 'API & Domain Services',
    icon: Server,
    items: [
      { name: 'FastAPI', role: 'Typed API layer for authentication, profiles, matching, communities, media, and messaging.' },
      { name: 'Python', role: 'Application language for orchestration, matching pipelines, AI services, and background logic.' },
      { name: 'Pydantic', role: 'Request, response, and configuration validation at the API boundary.' },
      { name: 'SQLAlchemy', role: 'ORM and database session layer for the application domain model.' },
      { name: 'Alembic', role: 'Versioned PostgreSQL schema migrations for repeatable environment setup.' },
      { name: 'Uvicorn', role: 'ASGI server used to run the FastAPI application.' }
    ]
  },
  {
    title: 'AI & Semantic Search',
    icon: Brain,
    items: [
      { name: 'Ollama', role: 'Local or remote model runtime for the career assistant, skill insights, and explanations.' },
      { name: 'Qwen', role: 'Configured language model for grounded career conversations and AI explanations.' },
      { name: 'Gemini', role: 'Optional second-stage semantic reranker for career-matching results.' },
      { name: 'Qdrant', role: 'Vector search layer for profile, career knowledge, and opportunity retrieval.' },
      { name: 'nomic-embed-text', role: 'Embedding model served through Ollama for semantic indexing and retrieval.' }
    ]
  },
  {
    title: 'Data & Object Storage',
    icon: Database,
    items: [
      { name: 'PostgreSQL', role: 'Source of truth for users, profiles, communities, conversations, opportunities, and metadata.' },
      { name: 'Redis', role: 'Short-lived OTP state, availability checks, response caching, presence, and pub/sub.' },
      { name: 'MinIO', role: 'S3-compatible object storage for resumes, profile images, and shared media.' },
      { name: 'psycopg', role: 'PostgreSQL driver connecting the Python services to the relational data layer.' }
    ]
  },
  {
    title: 'Auth & Real-Time',
    icon: ShieldCheck,
    items: [
      { name: 'JWT / PyJWT', role: 'Stateless access tokens used to identify authenticated API requests.' },
      { name: 'bcrypt', role: 'Password hashing and verification for account security.' },
      { name: 'WebSocket', role: 'Native browser-to-FastAPI channel for real-time direct messaging.' },
      { name: 'Redis Pub/Sub', role: 'Cross-instance event fanout for presence and messaging updates.' },
      { name: 'SMTP / OTP', role: 'Email verification flow for new account signup.' }
    ]
  },
  {
    title: 'Operations & Integrations',
    icon: Blocks,
    items: [
      { name: 'Docker Compose', role: 'Reproducible local infrastructure for Redis, Qdrant, MinIO, Ollama, and LanguageTool.' },
      { name: 'LanguageTool', role: 'Optional grammar and spelling service for writing assistance.' },
      { name: 'pytest', role: 'Backend test suite covering authentication, matching, messaging, communities, and reliability.' },
      { name: 'AWS-ready Ollama', role: 'The model endpoint can run locally or on a GPU host without changing the application flow.' }
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
    title: 'Supporting Services',
    icon: GitBranch,
    bullets: ['Gemini reranking', 'LanguageTool', 'SMTP email verification', 'Redis Pub/Sub', 'Ollama runtime']
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
