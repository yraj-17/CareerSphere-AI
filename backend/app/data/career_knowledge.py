"""
Multi-domain career knowledge dataset for CareerSphere AI.

This module is the structured source-of-truth for career domains, roles, and
skills.  It is intentionally plain Python (no DB, no network) so it is:

  - Fast to load (imported once at startup of the indexer)
  - Easily readable and extendable by humans
  - Independent of any external service

Qdrant stores the *vectorised* representation of this knowledge.
PostgreSQL stores *user* data.
This module is the structured knowledge layer that feeds both.

Architecture:
    career_knowledge.py (here)
          ↓  build documents
    career_indexing_service.py
          ↓  embed_text / embed_texts
    embedding_service.py  →  nomic-embed-text
          ↓  upsert_vectors
    qdrant_service.py  →  Qdrant career_content collection
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SkillEntry:
    """A single reusable skill in the catalog."""

    id: str                      # slug, e.g. "postgresql"
    name: str                    # display name, e.g. "PostgreSQL"
    category: str                # broad grouping, e.g. "database"
    description: str             # 1–3 sentence description (used for embedding text)
    aliases: List[str] = field(default_factory=list)


@dataclass
class RoleEntry:
    """A career role with its domain and skill requirements."""

    id: str                          # slug, e.g. "backend-engineer"
    name: str                        # display name
    domain: str                      # must be a value from DOMAINS
    description: str                 # rich description for semantic embedding
    required_skills: List[str]       # skill IDs from SKILLS
    recommended_skills: List[str]    # skill IDs from SKILLS


# ---------------------------------------------------------------------------
# Career domains
# ---------------------------------------------------------------------------

DOMAINS: List[str] = [
    "Software Engineering & Technology",
    "Cloud & DevOps",
    "AI, Machine Learning & Data",
    "Product & Business",
    "Design & Creative",
    "Marketing & Communications",
    "Finance & Accounting",
    "Human Resources",
    "Sales & Business Development",
    "Operations & Supply Chain",
    "Education & Learning",
    "Engineering",
    "Healthcare & Health Administration",
    "Legal, Compliance & Risk",
]

# ---------------------------------------------------------------------------
# Skill catalog
# ---------------------------------------------------------------------------
# Keys are stable slugs.  Names, descriptions, and aliases are human-readable.

SKILLS: dict[str, SkillEntry] = {
    # ── Programming & Backend ──────────────────────────────────────────────
    "python": SkillEntry(
        id="python",
        name="Python",
        category="programming",
        description=(
            "General-purpose, high-level programming language widely used for "
            "backend development, data science, scripting, and automation. "
            "Known for its readable syntax and rich ecosystem of libraries."
        ),
        aliases=["Python 3"],
    ),
    "javascript": SkillEntry(
        id="javascript",
        name="JavaScript",
        category="programming",
        description=(
            "Dynamic programming language that runs in the browser and on servers "
            "via Node.js. Core technology of web development used for both "
            "frontend interactivity and backend services."
        ),
        aliases=["JS"],
    ),
    "typescript": SkillEntry(
        id="typescript",
        name="TypeScript",
        category="programming",
        description=(
            "Strongly-typed superset of JavaScript that compiles to plain JS. "
            "Improves developer experience with static type checking, IDE "
            "support, and safer large-scale application development."
        ),
        aliases=["TS"],
    ),
    "java": SkillEntry(
        id="java",
        name="Java",
        category="programming",
        description=(
            "Object-oriented programming language commonly used for enterprise "
            "backend services, Android development, and large-scale distributed "
            "systems. Runs on the JVM."
        ),
    ),
    "fastapi": SkillEntry(
        id="fastapi",
        name="FastAPI",
        category="framework",
        description=(
            "Modern, high-performance Python web framework for building REST APIs. "
            "Uses Python type hints for automatic validation, serialization, and "
            "interactive documentation generation."
        ),
    ),
    "react": SkillEntry(
        id="react",
        name="React",
        category="framework",
        description=(
            "JavaScript library for building component-based user interfaces. "
            "Uses a virtual DOM for efficient rendering and supports a rich "
            "ecosystem of state management and routing libraries."
        ),
        aliases=["React.js", "ReactJS"],
    ),
    "nextjs": SkillEntry(
        id="nextjs",
        name="Next.js",
        category="framework",
        description=(
            "Full-stack React framework supporting server-side rendering, static "
            "site generation, and API routes. Widely used for building "
            "production-ready web applications."
        ),
        aliases=["Next"],
    ),
    # ── Databases ────────────────────────────────────────────────────────
    "postgresql": SkillEntry(
        id="postgresql",
        name="PostgreSQL",
        category="database",
        description=(
            "Open-source relational database management system known for "
            "robustness, ACID compliance, and advanced features like JSON "
            "support, full-text search, and extensibility."
        ),
        aliases=["Postgres"],
    ),
    "sql": SkillEntry(
        id="sql",
        name="SQL",
        category="database",
        description=(
            "Structured Query Language used to query, insert, update, and "
            "manage relational databases. Fundamental skill for data access, "
            "reporting, and database administration."
        ),
    ),
    "redis": SkillEntry(
        id="redis",
        name="Redis",
        category="database",
        description=(
            "In-memory data structure store used as a cache, message broker, "
            "and session store. Supports strings, hashes, lists, sets, and "
            "pub/sub messaging with sub-millisecond latency."
        ),
    ),
    # ── APIs & Architecture ───────────────────────────────────────────────
    "rest_apis": SkillEntry(
        id="rest_apis",
        name="REST APIs",
        category="architecture",
        description=(
            "Design and implementation of RESTful HTTP APIs following "
            "stateless request/response patterns, proper use of HTTP verbs, "
            "status codes, and resource-based routing."
        ),
        aliases=["RESTful APIs", "REST"],
    ),
    "system_design": SkillEntry(
        id="system_design",
        name="System Design",
        category="architecture",
        description=(
            "Ability to architect scalable, reliable, and maintainable software "
            "systems. Covers load balancing, caching, database sharding, "
            "microservices, event-driven architecture, and API design."
        ),
    ),
    "microservices": SkillEntry(
        id="microservices",
        name="Microservices",
        category="architecture",
        description=(
            "Software architecture pattern where applications are composed of "
            "small, independently deployable services communicating via APIs or "
            "message queues, enabling independent scaling and deployment."
        ),
    ),
    # ── Cloud & DevOps ────────────────────────────────────────────────────
    "docker": SkillEntry(
        id="docker",
        name="Docker",
        category="devops",
        description=(
            "Containerization platform that packages applications and their "
            "dependencies into portable containers. Enables consistent "
            "deployments across development, staging, and production environments."
        ),
    ),
    "kubernetes": SkillEntry(
        id="kubernetes",
        name="Kubernetes",
        category="devops",
        description=(
            "Open-source container orchestration system for automating "
            "deployment, scaling, and management of containerized applications. "
            "Industry standard for cloud-native infrastructure."
        ),
        aliases=["K8s"],
    ),
    "aws": SkillEntry(
        id="aws",
        name="AWS",
        category="cloud",
        description=(
            "Amazon Web Services — the leading cloud platform providing compute, "
            "storage, networking, machine learning, and managed services for "
            "building and scaling applications globally."
        ),
        aliases=["Amazon Web Services"],
    ),
    "gcp": SkillEntry(
        id="gcp",
        name="GCP",
        category="cloud",
        description=(
            "Google Cloud Platform — cloud computing services offering compute "
            "engines, BigQuery analytics, Kubernetes Engine, AI/ML services, and "
            "managed infrastructure for modern applications."
        ),
        aliases=["Google Cloud", "Google Cloud Platform"],
    ),
    "azure": SkillEntry(
        id="azure",
        name="Azure",
        category="cloud",
        description=(
            "Microsoft Azure — enterprise cloud platform with services covering "
            "virtual machines, serverless functions, DevOps pipelines, AI, "
            "databases, and hybrid cloud solutions."
        ),
        aliases=["Microsoft Azure"],
    ),
    "ci_cd": SkillEntry(
        id="ci_cd",
        name="CI/CD",
        category="devops",
        description=(
            "Continuous Integration and Continuous Delivery pipelines that "
            "automate building, testing, and deploying code. Reduces manual "
            "effort and accelerates reliable software delivery."
        ),
        aliases=["Continuous Integration", "Continuous Delivery"],
    ),
    "linux": SkillEntry(
        id="linux",
        name="Linux",
        category="devops",
        description=(
            "Open-source operating system widely used on servers and cloud "
            "infrastructure. Proficiency includes shell scripting, process "
            "management, networking, and system administration."
        ),
    ),
    "git": SkillEntry(
        id="git",
        name="Git",
        category="devops",
        description=(
            "Distributed version control system for tracking code changes, "
            "collaborating on software projects, and managing branching, "
            "merging, and release workflows."
        ),
    ),
    "terraform": SkillEntry(
        id="terraform",
        name="Terraform",
        category="devops",
        description=(
            "Infrastructure-as-Code tool for provisioning and managing cloud "
            "resources across AWS, Azure, GCP, and other providers using "
            "declarative configuration files."
        ),
    ),
    "monitoring": SkillEntry(
        id="monitoring",
        name="Monitoring & Observability",
        category="devops",
        description=(
            "Practices and tools for tracking application health, performance "
            "metrics, logs, and distributed traces. Includes tools like "
            "Prometheus, Grafana, Datadog, and ELK Stack."
        ),
        aliases=["Observability", "Prometheus", "Grafana"],
    ),
    # ── AI / ML / Data ───────────────────────────────────────────────────
    "machine_learning": SkillEntry(
        id="machine_learning",
        name="Machine Learning",
        category="ai_ml",
        description=(
            "Development and deployment of algorithms that learn patterns from "
            "data to make predictions or decisions. Covers supervised, "
            "unsupervised, and reinforcement learning approaches."
        ),
        aliases=["ML"],
    ),
    "deep_learning": SkillEntry(
        id="deep_learning",
        name="Deep Learning",
        category="ai_ml",
        description=(
            "Subset of machine learning using neural networks with many layers "
            "to learn complex representations from data. Powers image recognition, "
            "NLP, speech synthesis, and generative AI models."
        ),
    ),
    "nlp": SkillEntry(
        id="nlp",
        name="Natural Language Processing",
        category="ai_ml",
        description=(
            "AI techniques for understanding, generating, and processing human "
            "language. Covers text classification, sentiment analysis, "
            "named entity recognition, language models, and embeddings."
        ),
        aliases=["NLP"],
    ),
    "data_analysis": SkillEntry(
        id="data_analysis",
        name="Data Analysis",
        category="analytics",
        description=(
            "Inspecting, cleaning, transforming, and modelling data to discover "
            "insights, support decision-making, and communicate findings through "
            "visualisations and statistical summaries."
        ),
    ),
    "data_visualization": SkillEntry(
        id="data_visualization",
        name="Data Visualization",
        category="analytics",
        description=(
            "Representing data graphically using charts, dashboards, and "
            "interactive visuals to communicate patterns and trends. Tools "
            "include Tableau, Power BI, matplotlib, and Plotly."
        ),
        aliases=["Data Viz"],
    ),
    "statistics": SkillEntry(
        id="statistics",
        name="Statistics",
        category="analytics",
        description=(
            "Mathematical foundations for data analysis including probability "
            "distributions, hypothesis testing, regression, A/B testing, and "
            "inferential statistics used in research and data science."
        ),
    ),
    "pytorch": SkillEntry(
        id="pytorch",
        name="PyTorch",
        category="ai_ml",
        description=(
            "Open-source deep learning framework widely used for research and "
            "production ML model development. Supports dynamic computation "
            "graphs and is popular for NLP and computer vision."
        ),
    ),
    "mlops": SkillEntry(
        id="mlops",
        name="MLOps",
        category="ai_ml",
        description=(
            "Practices and tooling for operationalising machine learning: model "
            "training pipelines, experiment tracking, model versioning, "
            "deployment, and monitoring in production environments."
        ),
    ),
    # ── Product & Business ────────────────────────────────────────────────
    "product_strategy": SkillEntry(
        id="product_strategy",
        name="Product Strategy",
        category="product",
        description=(
            "Defining the vision, goals, and roadmap for a product. Involves "
            "market analysis, competitive research, user needs assessment, and "
            "aligning product decisions with business objectives."
        ),
    ),
    "product_roadmapping": SkillEntry(
        id="product_roadmapping",
        name="Product Roadmapping",
        category="product",
        description=(
            "Planning and communicating the sequence of product initiatives, "
            "features, and milestones over time. Balances stakeholder priorities, "
            "technical constraints, and user value delivery."
        ),
    ),
    "market_research": SkillEntry(
        id="market_research",
        name="Market Research",
        category="product",
        description=(
            "Gathering and analysing information about markets, customers, and "
            "competitors to inform product positioning, pricing strategies, and "
            "go-to-market decisions."
        ),
    ),
    "stakeholder_management": SkillEntry(
        id="stakeholder_management",
        name="Stakeholder Management",
        category="product",
        description=(
            "Identifying, engaging, and aligning expectations of stakeholders "
            "including executives, customers, engineers, and partners throughout "
            "a project or product lifecycle."
        ),
    ),
    "agile": SkillEntry(
        id="agile",
        name="Agile",
        category="product",
        description=(
            "Iterative software development methodology emphasising flexibility, "
            "collaboration, and incremental delivery. Includes Scrum, Kanban, "
            "sprint planning, retrospectives, and continuous improvement."
        ),
        aliases=["Scrum", "Agile Methodologies"],
    ),
    "requirements_analysis": SkillEntry(
        id="requirements_analysis",
        name="Requirements Analysis",
        category="product",
        description=(
            "Eliciting, documenting, and validating business and technical "
            "requirements. Ensures solutions address actual needs before "
            "development begins, reducing costly rework."
        ),
    ),
    "business_analysis": SkillEntry(
        id="business_analysis",
        name="Business Analysis",
        category="product",
        description=(
            "Analysing business processes, identifying improvement opportunities, "
            "and translating business needs into structured requirements for "
            "technology or process change initiatives."
        ),
    ),
    # ── Design ────────────────────────────────────────────────────────────
    "ui_design": SkillEntry(
        id="ui_design",
        name="UI Design",
        category="design",
        description=(
            "Designing visual interfaces including layout, typography, colour, "
            "iconography, and interactive components to create aesthetically "
            "pleasing and functional user experiences."
        ),
        aliases=["User Interface Design"],
    ),
    "ux_research": SkillEntry(
        id="ux_research",
        name="UX Research",
        category="design",
        description=(
            "Studying user behaviours, needs, and motivations through interviews, "
            "usability testing, surveys, and analytics to inform and validate "
            "design decisions."
        ),
        aliases=["User Experience Research", "User Research"],
    ),
    "wireframing": SkillEntry(
        id="wireframing",
        name="Wireframing",
        category="design",
        description=(
            "Creating low-fidelity skeletal representations of UI layouts to "
            "explore structure, navigation, and content hierarchy before "
            "high-fidelity visual design begins."
        ),
    ),
    "prototyping": SkillEntry(
        id="prototyping",
        name="Prototyping",
        category="design",
        description=(
            "Building interactive mockups of user interfaces to test concepts, "
            "gather user feedback, and validate design decisions before full "
            "implementation."
        ),
    ),
    "figma": SkillEntry(
        id="figma",
        name="Figma",
        category="design",
        description=(
            "Browser-based collaborative design tool for creating wireframes, "
            "UI designs, and interactive prototypes. Industry standard for "
            "product and UX design teams."
        ),
    ),
    "design_systems": SkillEntry(
        id="design_systems",
        name="Design Systems",
        category="design",
        description=(
            "Creating and maintaining reusable component libraries, style guides, "
            "and design tokens that ensure consistency across products and "
            "accelerate UI development."
        ),
    ),
    # ── Marketing ─────────────────────────────────────────────────────────
    "seo": SkillEntry(
        id="seo",
        name="SEO",
        category="marketing",
        description=(
            "Search Engine Optimisation — practices for improving organic "
            "visibility of web content in search engines through keyword "
            "research, on-page optimisation, and link building."
        ),
        aliases=["Search Engine Optimization"],
    ),
    "content_marketing": SkillEntry(
        id="content_marketing",
        name="Content Marketing",
        category="marketing",
        description=(
            "Creating and distributing valuable, relevant content to attract, "
            "engage, and retain a target audience with the goal of driving "
            "profitable customer actions."
        ),
    ),
    "social_media_marketing": SkillEntry(
        id="social_media_marketing",
        name="Social Media Marketing",
        category="marketing",
        description=(
            "Promoting brands, products, and services on social platforms such "
            "as LinkedIn, Instagram, Twitter/X, and TikTok through organic "
            "content, paid ads, and community engagement."
        ),
    ),
    "email_marketing": SkillEntry(
        id="email_marketing",
        name="Email Marketing",
        category="marketing",
        description=(
            "Designing and executing email campaigns to nurture leads, retain "
            "customers, and drive conversions. Includes list segmentation, "
            "A/B testing, deliverability, and analytics."
        ),
    ),
    "analytics": SkillEntry(
        id="analytics",
        name="Analytics",
        category="marketing",
        description=(
            "Using data tools such as Google Analytics, Mixpanel, or Amplitude "
            "to measure campaign performance, user behaviour, conversion funnels, "
            "and return on marketing investment."
        ),
    ),
    "copywriting": SkillEntry(
        id="copywriting",
        name="Copywriting",
        category="marketing",
        description=(
            "Writing persuasive, clear, and engaging text for ads, websites, "
            "emails, and social media to drive audience action and communicate "
            "brand value."
        ),
    ),
    "brand_strategy": SkillEntry(
        id="brand_strategy",
        name="Brand Strategy",
        category="marketing",
        description=(
            "Defining and managing a brand's identity, positioning, tone of "
            "voice, and messaging to differentiate it in the market and build "
            "long-term customer loyalty."
        ),
    ),
    # ── Finance ───────────────────────────────────────────────────────────
    "financial_analysis": SkillEntry(
        id="financial_analysis",
        name="Financial Analysis",
        category="finance",
        description=(
            "Evaluating financial data, statements, and ratios to assess "
            "business performance, identify trends, and support investment or "
            "operational decision-making."
        ),
    ),
    "financial_modeling": SkillEntry(
        id="financial_modeling",
        name="Financial Modeling",
        category="finance",
        description=(
            "Building quantitative representations of a business's financial "
            "performance, including DCF models, scenario analysis, and "
            "forecasting to guide strategic decisions."
        ),
    ),
    "accounting": SkillEntry(
        id="accounting",
        name="Accounting",
        category="finance",
        description=(
            "Recording, classifying, and summarising financial transactions to "
            "produce accurate financial statements. Covers accounts payable, "
            "receivable, general ledger, and compliance."
        ),
    ),
    "excel": SkillEntry(
        id="excel",
        name="Excel",
        category="finance",
        description=(
            "Microsoft Excel for financial analysis, data manipulation, pivot "
            "tables, advanced formulas, and financial modelling. Core tool for "
            "finance, accounting, and operations professionals."
        ),
        aliases=["Microsoft Excel"],
    ),
    "financial_reporting": SkillEntry(
        id="financial_reporting",
        name="Financial Reporting",
        category="finance",
        description=(
            "Preparing and presenting financial statements — income statement, "
            "balance sheet, and cash flow statement — in compliance with "
            "accounting standards such as GAAP or IFRS."
        ),
    ),
    "budgeting": SkillEntry(
        id="budgeting",
        name="Budgeting",
        category="finance",
        description=(
            "Planning and allocating financial resources across business units "
            "or projects, setting spending limits, and tracking actual vs. "
            "planned expenditure to maintain fiscal discipline."
        ),
    ),
    "forecasting": SkillEntry(
        id="forecasting",
        name="Forecasting",
        category="finance",
        description=(
            "Predicting future financial performance or operational outcomes "
            "using historical data, statistical methods, and business "
            "assumptions to guide planning and strategy."
        ),
    ),
    # ── HR ────────────────────────────────────────────────────────────────
    "recruitment": SkillEntry(
        id="recruitment",
        name="Recruitment",
        category="hr",
        description=(
            "End-to-end process of attracting, screening, and selecting "
            "qualified candidates for open roles. Includes job posting, "
            "sourcing, interviewing, offer management, and onboarding."
        ),
    ),
    "talent_acquisition": SkillEntry(
        id="talent_acquisition",
        name="Talent Acquisition",
        category="hr",
        description=(
            "Strategic approach to identifying, attracting, and hiring talented "
            "individuals aligned with long-term organisational goals, including "
            "employer branding and talent pipeline development."
        ),
    ),
    "employee_relations": SkillEntry(
        id="employee_relations",
        name="Employee Relations",
        category="hr",
        description=(
            "Managing the employer-employee relationship through conflict "
            "resolution, policy enforcement, performance management, and "
            "creating a positive and compliant workplace culture."
        ),
    ),
    "hr_operations": SkillEntry(
        id="hr_operations",
        name="HR Operations",
        category="hr",
        description=(
            "Day-to-day administration of HR functions including payroll "
            "processing, benefits administration, HRIS management, onboarding, "
            "offboarding, and HR policy compliance."
        ),
    ),
    "communication": SkillEntry(
        id="communication",
        name="Communication",
        category="soft_skills",
        description=(
            "Clear and effective verbal and written communication skills for "
            "presenting ideas, writing reports, conducting interviews, and "
            "collaborating with diverse teams and stakeholders."
        ),
    ),
    "interviewing": SkillEntry(
        id="interviewing",
        name="Interviewing",
        category="hr",
        description=(
            "Conducting structured or behavioural interviews to assess candidate "
            "competencies, cultural fit, and role suitability. Includes question "
            "design, evaluation frameworks, and bias reduction."
        ),
    ),
    # ── Sales ─────────────────────────────────────────────────────────────
    "lead_generation": SkillEntry(
        id="lead_generation",
        name="Lead Generation",
        category="sales",
        description=(
            "Identifying and attracting potential customers through outbound "
            "prospecting, inbound marketing, networking, and referrals to build "
            "a qualified sales pipeline."
        ),
    ),
    "crm": SkillEntry(
        id="crm",
        name="CRM",
        category="sales",
        description=(
            "Customer Relationship Management — using platforms like Salesforce, "
            "HubSpot, or Zoho to manage customer interactions, track the sales "
            "pipeline, and analyse customer data."
        ),
        aliases=["Customer Relationship Management", "Salesforce"],
    ),
    "negotiation": SkillEntry(
        id="negotiation",
        name="Negotiation",
        category="sales",
        description=(
            "Reaching mutually beneficial agreements through structured "
            "dialogue, understanding counterpart interests, and presenting "
            "value propositions effectively in sales and business contexts."
        ),
    ),
    "sales_strategy": SkillEntry(
        id="sales_strategy",
        name="Sales Strategy",
        category="sales",
        description=(
            "Developing plans for achieving revenue targets through market "
            "segmentation, account targeting, pricing strategies, and "
            "optimisation of the sales process and team structure."
        ),
    ),
    "client_relationship_management": SkillEntry(
        id="client_relationship_management",
        name="Client Relationship Management",
        category="sales",
        description=(
            "Building and maintaining long-term relationships with clients "
            "through regular communication, understanding evolving needs, "
            "delivering value, and managing account health."
        ),
    ),
    # ── Operations ────────────────────────────────────────────────────────
    "operations_management": SkillEntry(
        id="operations_management",
        name="Operations Management",
        category="operations",
        description=(
            "Planning, organising, and supervising business processes to "
            "maximise efficiency, quality, and productivity across manufacturing, "
            "services, or administrative functions."
        ),
    ),
    "process_improvement": SkillEntry(
        id="process_improvement",
        name="Process Improvement",
        category="operations",
        description=(
            "Identifying and implementing changes to business processes using "
            "methodologies such as Lean, Six Sigma, or Kaizen to eliminate "
            "waste, reduce cost, and improve quality."
        ),
        aliases=["Lean", "Six Sigma", "Continuous Improvement"],
    ),
    "supply_chain_management": SkillEntry(
        id="supply_chain_management",
        name="Supply Chain Management",
        category="operations",
        description=(
            "Overseeing the flow of goods, information, and finances from "
            "supplier to customer, including procurement, manufacturing "
            "coordination, logistics, and demand planning."
        ),
    ),
    "inventory_management": SkillEntry(
        id="inventory_management",
        name="Inventory Management",
        category="operations",
        description=(
            "Controlling stock levels, tracking inventory movements, and "
            "optimising reorder points to balance carrying costs with service "
            "level requirements."
        ),
    ),
    "logistics": SkillEntry(
        id="logistics",
        name="Logistics",
        category="operations",
        description=(
            "Planning and executing the movement and storage of goods from "
            "origin to final destination, including transportation, warehousing, "
            "customs compliance, and last-mile delivery."
        ),
    ),
    "project_management": SkillEntry(
        id="project_management",
        name="Project Management",
        category="operations",
        description=(
            "Planning, executing, and closing projects within scope, budget, "
            "and timeline constraints using frameworks such as PMP, PRINCE2, "
            "or Agile to deliver defined outcomes."
        ),
        aliases=["PMP"],
    ),
    # ── Education ─────────────────────────────────────────────────────────
    "teaching": SkillEntry(
        id="teaching",
        name="Teaching",
        category="education",
        description=(
            "Designing and delivering instructional content to learners of "
            "varying ages and abilities. Includes classroom management, "
            "differentiated instruction, and formative assessment."
        ),
    ),
    "curriculum_development": SkillEntry(
        id="curriculum_development",
        name="Curriculum Development",
        category="education",
        description=(
            "Designing structured learning programmes, courses, and materials "
            "aligned with learning objectives, educational standards, and "
            "the needs of target learner populations."
        ),
    ),
    "instructional_design": SkillEntry(
        id="instructional_design",
        name="Instructional Design",
        category="education",
        description=(
            "Applying learning science principles (ADDIE, SAM, Bloom's taxonomy) "
            "to create effective training materials, e-learning modules, and "
            "blended learning experiences."
        ),
    ),
    "assessment": SkillEntry(
        id="assessment",
        name="Assessment",
        category="education",
        description=(
            "Designing and administering evaluations — quizzes, exams, rubrics, "
            "and performance tasks — to measure learner progress and learning "
            "outcomes."
        ),
    ),
    "lms": SkillEntry(
        id="lms",
        name="Learning Management Systems",
        category="education",
        description=(
            "Administering and delivering online learning via platforms such as "
            "Moodle, Canvas, or Blackboard. Includes content upload, enrolment "
            "management, and learner progress tracking."
        ),
        aliases=["LMS", "Moodle", "Canvas"],
    ),
    # ── Engineering ───────────────────────────────────────────────────────
    "cad": SkillEntry(
        id="cad",
        name="CAD",
        category="engineering",
        description=(
            "Computer-Aided Design tools such as AutoCAD, SolidWorks, or "
            "CATIA used to create 2D drawings and 3D models of mechanical, "
            "civil, or electrical components and systems."
        ),
        aliases=["Computer-Aided Design", "AutoCAD", "SolidWorks"],
    ),
    "engineering_design": SkillEntry(
        id="engineering_design",
        name="Engineering Design",
        category="engineering",
        description=(
            "Applying mathematical, scientific, and domain-specific principles "
            "to design systems, components, or processes that meet defined "
            "functional, safety, and economic requirements."
        ),
    ),
    "technical_drawing": SkillEntry(
        id="technical_drawing",
        name="Technical Drawing",
        category="engineering",
        description=(
            "Creating precise 2D representations of engineering designs using "
            "standardised conventions for dimensions, tolerances, and views to "
            "guide manufacturing and construction."
        ),
    ),
    "structural_analysis": SkillEntry(
        id="structural_analysis",
        name="Structural Analysis",
        category="engineering",
        description=(
            "Analysing the behaviour of structures under loads to verify "
            "strength, stability, and deflection limits. Includes static, "
            "dynamic, and finite element analysis methods."
        ),
    ),
    "electrical_systems": SkillEntry(
        id="electrical_systems",
        name="Electrical Systems",
        category="engineering",
        description=(
            "Design, analysis, and maintenance of electrical circuits, power "
            "distribution systems, control systems, and electronic components "
            "in industrial or building environments."
        ),
    ),
    "problem_solving": SkillEntry(
        id="problem_solving",
        name="Problem Solving",
        category="soft_skills",
        description=(
            "Analytical and creative ability to identify root causes of problems, "
            "generate solution options, evaluate trade-offs, and implement "
            "effective resolutions in complex technical and business contexts."
        ),
    ),
    # ── Healthcare Administration ─────────────────────────────────────────
    "healthcare_operations": SkillEntry(
        id="healthcare_operations",
        name="Healthcare Operations",
        category="healthcare",
        description=(
            "Managing the day-to-day operational functions of healthcare "
            "facilities including patient flow, staffing, resource allocation, "
            "quality improvement, and regulatory compliance."
        ),
    ),
    "medical_records": SkillEntry(
        id="medical_records",
        name="Medical Records",
        category="healthcare",
        description=(
            "Managing patient health information and electronic health records "
            "(EHR/EMR) systems including data accuracy, privacy compliance "
            "(HIPAA), and health information exchange."
        ),
        aliases=["EHR", "EMR", "Electronic Health Records"],
    ),
    "healthcare_compliance": SkillEntry(
        id="healthcare_compliance",
        name="Healthcare Compliance",
        category="healthcare",
        description=(
            "Ensuring healthcare operations adhere to regulatory requirements "
            "including HIPAA, CMS guidelines, accreditation standards, and "
            "patient safety regulations."
        ),
    ),
    "healthcare_management": SkillEntry(
        id="healthcare_management",
        name="Healthcare Management",
        category="healthcare",
        description=(
            "Strategic and operational leadership of healthcare organisations "
            "covering financial management, human resources, quality assurance, "
            "strategic planning, and stakeholder relations."
        ),
    ),
    # ── Legal, Compliance & Risk ──────────────────────────────────────────
    "regulatory_compliance": SkillEntry(
        id="regulatory_compliance",
        name="Regulatory Compliance",
        category="legal",
        description=(
            "Ensuring organisational activities comply with applicable laws, "
            "regulations, and standards. Includes monitoring regulatory changes, "
            "implementing controls, and preparing compliance reports."
        ),
    ),
    "risk_assessment": SkillEntry(
        id="risk_assessment",
        name="Risk Assessment",
        category="legal",
        description=(
            "Identifying, analysing, and evaluating potential risks to an "
            "organisation's operations, finances, or reputation to inform "
            "mitigation strategies and risk appetite decisions."
        ),
    ),
    "legal_research": SkillEntry(
        id="legal_research",
        name="Legal Research",
        category="legal",
        description=(
            "Researching statutes, case law, regulations, and legal precedents "
            "using databases such as Westlaw or LexisNexis to support legal "
            "analysis, compliance, and advisory work."
        ),
    ),
    "policy_analysis": SkillEntry(
        id="policy_analysis",
        name="Policy Analysis",
        category="legal",
        description=(
            "Evaluating existing and proposed policies for their legal, "
            "operational, and economic implications, and recommending changes "
            "to improve outcomes and manage risk."
        ),
    ),
    "documentation": SkillEntry(
        id="documentation",
        name="Documentation",
        category="soft_skills",
        description=(
            "Writing clear, accurate, and well-structured technical, legal, or "
            "operational documents including policies, procedures, specifications, "
            "reports, and compliance records."
        ),
    ),
    "risk_management": SkillEntry(
        id="risk_management",
        name="Risk Management",
        category="legal",
        description=(
            "Developing frameworks and strategies to identify, assess, monitor, "
            "and mitigate organisational risks across operational, financial, "
            "legal, and reputational dimensions."
        ),
    ),
}

# ---------------------------------------------------------------------------
# Career roles
# ---------------------------------------------------------------------------

ROLES: List[RoleEntry] = [
    # ── Software Engineering & Technology ─────────────────────────────────
    RoleEntry(
        id="backend-engineer",
        name="Backend Engineer",
        domain="Software Engineering & Technology",
        description=(
            "Backend Engineers design and build the server-side components of "
            "software applications. They develop REST APIs, manage databases, "
            "implement authentication and authorisation systems, and architect "
            "scalable services. Core responsibilities include building reliable "
            "API endpoints, integrating with databases, optimising query "
            "performance, ensuring security, and writing maintainable backend "
            "code. They collaborate closely with frontend developers and "
            "DevOps engineers to deliver full-featured products."
        ),
        required_skills=["python", "rest_apis", "postgresql", "git", "system_design"],
        recommended_skills=["fastapi", "docker", "redis", "aws", "ci_cd", "microservices"],
    ),
    RoleEntry(
        id="full-stack-developer",
        name="Full Stack Developer",
        domain="Software Engineering & Technology",
        description=(
            "Full Stack Developers work across the entire web application stack — "
            "frontend user interfaces and backend services. They build and "
            "maintain both the client-side experience and server-side logic, "
            "manage databases, integrate APIs, and deploy applications. They need "
            "breadth across multiple technologies and the ability to architect "
            "complete solutions from database schema to UI component."
        ),
        required_skills=["javascript", "react", "python", "rest_apis", "sql", "git"],
        recommended_skills=["typescript", "nextjs", "postgresql", "docker", "redis", "ci_cd"],
    ),
    RoleEntry(
        id="frontend-developer",
        name="Frontend Developer",
        domain="Software Engineering & Technology",
        description=(
            "Frontend Developers build the user-facing layer of web applications. "
            "They implement responsive, accessible, and performant user interfaces "
            "using modern JavaScript frameworks, manage application state, consume "
            "REST APIs, and collaborate with designers to translate visual designs "
            "into functional code. They are responsible for cross-browser "
            "compatibility, performance optimisation, and delivering polished "
            "user experiences."
        ),
        required_skills=["javascript", "react", "typescript", "git"],
        recommended_skills=["nextjs", "rest_apis", "figma", "ci_cd"],
    ),
    # ── Cloud & DevOps ────────────────────────────────────────────────────
    RoleEntry(
        id="devops-engineer",
        name="DevOps Engineer",
        domain="Cloud & DevOps",
        description=(
            "DevOps Engineers bridge software development and IT operations by "
            "automating infrastructure, build, test, and deployment pipelines. "
            "They maintain CI/CD systems, manage containerised workloads with "
            "Kubernetes and Docker, configure cloud infrastructure, implement "
            "monitoring and alerting, and ensure high availability and reliability "
            "of production systems. They reduce friction between development "
            "velocity and operational stability."
        ),
        required_skills=["docker", "kubernetes", "ci_cd", "linux", "git"],
        recommended_skills=["aws", "terraform", "monitoring", "python", "microservices"],
    ),
    RoleEntry(
        id="cloud-engineer",
        name="Cloud Engineer",
        domain="Cloud & DevOps",
        description=(
            "Cloud Engineers design, build, and maintain cloud infrastructure "
            "on platforms such as AWS, GCP, or Azure. They provision compute, "
            "networking, and storage resources using Infrastructure-as-Code tools, "
            "implement security controls, optimise cost and performance, and "
            "support cloud migration projects. They ensure cloud environments "
            "are secure, scalable, and aligned with architectural best practices."
        ),
        required_skills=["aws", "terraform", "linux", "docker", "git"],
        recommended_skills=["kubernetes", "azure", "gcp", "ci_cd", "monitoring", "python"],
    ),
    # ── AI, Machine Learning & Data ───────────────────────────────────────
    RoleEntry(
        id="machine-learning-engineer",
        name="Machine Learning Engineer",
        domain="AI, Machine Learning & Data",
        description=(
            "Machine Learning Engineers design, train, and productionise machine "
            "learning models. They build data pipelines, select and tune "
            "algorithms, evaluate model performance, and deploy models as scalable "
            "services. They bridge data science research and software engineering, "
            "ensuring models are reliable, maintainable, and performant in "
            "production. MLOps practices, experiment tracking, and model "
            "versioning are core parts of the role."
        ),
        required_skills=["machine_learning", "python", "sql", "git"],
        recommended_skills=["deep_learning", "pytorch", "mlops", "docker", "aws", "statistics"],
    ),
    RoleEntry(
        id="data-scientist",
        name="Data Scientist",
        domain="AI, Machine Learning & Data",
        description=(
            "Data Scientists extract insights from large datasets using statistical "
            "analysis, machine learning, and data visualisation. They formulate "
            "hypotheses, design experiments, build predictive models, and "
            "communicate findings to business stakeholders. They work with "
            "structured and unstructured data, apply NLP or computer vision "
            "techniques where relevant, and drive data-informed decisions."
        ),
        required_skills=["python", "machine_learning", "statistics", "sql", "data_analysis"],
        recommended_skills=["deep_learning", "nlp", "data_visualization", "pytorch", "mlops"],
    ),
    RoleEntry(
        id="data-analyst",
        name="Data Analyst",
        domain="AI, Machine Learning & Data",
        description=(
            "Data Analysts collect, clean, and analyse structured datasets to "
            "answer business questions and support decision-making. They create "
            "dashboards, reports, and visualisations using SQL and BI tools, "
            "identify trends and anomalies, and collaborate with business teams "
            "to define and track key performance metrics. Strong communication "
            "of data-driven insights to non-technical audiences is essential."
        ),
        required_skills=["sql", "data_analysis", "excel", "data_visualization"],
        recommended_skills=["python", "statistics", "analytics"],
    ),
    # ── Product & Business ────────────────────────────────────────────────
    RoleEntry(
        id="product-manager",
        name="Product Manager",
        domain="Product & Business",
        description=(
            "Product Managers define the vision, strategy, and roadmap for a "
            "product. They gather and prioritise requirements from customers and "
            "stakeholders, work with engineering teams to deliver features, "
            "analyse product metrics to inform decisions, and align product "
            "direction with business objectives. They own the product lifecycle "
            "from discovery through delivery and iteration."
        ),
        required_skills=["product_strategy", "product_roadmapping", "stakeholder_management", "agile"],
        recommended_skills=["market_research", "requirements_analysis", "data_analysis", "communication"],
    ),
    RoleEntry(
        id="business-analyst",
        name="Business Analyst",
        domain="Product & Business",
        description=(
            "Business Analysts bridge the gap between business needs and technical "
            "solutions. They analyse current processes, elicit and document "
            "requirements, model business rules, and work with stakeholders and "
            "development teams to design and validate solutions. They produce "
            "specifications, process flows, and user stories to guide delivery "
            "and measure outcomes against business goals."
        ),
        required_skills=["business_analysis", "requirements_analysis", "stakeholder_management", "documentation"],
        recommended_skills=["agile", "sql", "data_analysis", "communication", "excel"],
    ),
    # ── Design & Creative ─────────────────────────────────────────────────
    RoleEntry(
        id="ui-ux-designer",
        name="UI/UX Designer",
        domain="Design & Creative",
        description=(
            "UI/UX Designers create user interfaces that are both visually "
            "appealing and easy to use. They conduct user research, develop "
            "personas, build wireframes and prototypes, run usability tests, "
            "and collaborate with product and engineering teams to implement "
            "designs. They balance aesthetic quality with functional usability "
            "and accessibility standards."
        ),
        required_skills=["ui_design", "ux_research", "wireframing", "figma"],
        recommended_skills=["prototyping", "design_systems", "communication"],
    ),
    RoleEntry(
        id="product-designer",
        name="Product Designer",
        domain="Design & Creative",
        description=(
            "Product Designers own the end-to-end design of digital products "
            "from concept to shipped feature. They integrate UX research, "
            "interaction design, and visual design into cohesive product "
            "experiences. They contribute to design systems, define design "
            "principles, partner with PMs and engineers, and champion "
            "user-centred thinking across the product organisation."
        ),
        required_skills=["ui_design", "ux_research", "prototyping", "figma", "design_systems"],
        recommended_skills=["wireframing", "stakeholder_management", "communication"],
    ),
    # ── Marketing & Communications ────────────────────────────────────────
    RoleEntry(
        id="digital-marketing-specialist",
        name="Digital Marketing Specialist",
        domain="Marketing & Communications",
        description=(
            "Digital Marketing Specialists plan and execute online marketing "
            "campaigns across channels such as search, social media, email, "
            "and display advertising. They analyse campaign performance using "
            "analytics tools, optimise for conversions and ROI, manage budgets, "
            "and stay current with platform changes and digital marketing trends."
        ),
        required_skills=["seo", "analytics", "social_media_marketing", "email_marketing"],
        recommended_skills=["content_marketing", "copywriting", "brand_strategy"],
    ),
    RoleEntry(
        id="content-strategist",
        name="Content Strategist",
        domain="Marketing & Communications",
        description=(
            "Content Strategists plan, develop, and govern content that supports "
            "business goals and audience needs. They define content frameworks, "
            "editorial calendars, tone of voice guidelines, and distribution "
            "strategies. They work across SEO, brand, and product teams to "
            "ensure content is valuable, consistent, and aligned with the "
            "customer journey."
        ),
        required_skills=["content_marketing", "copywriting", "seo", "brand_strategy"],
        recommended_skills=["analytics", "social_media_marketing", "communication"],
    ),
    # ── Finance & Accounting ──────────────────────────────────────────────
    RoleEntry(
        id="financial-analyst",
        name="Financial Analyst",
        domain="Finance & Accounting",
        description=(
            "Financial Analysts evaluate financial performance, build models to "
            "forecast revenue and costs, and provide analysis to support "
            "investment, budgeting, and strategic decisions. They prepare "
            "financial reports, conduct variance analysis, track key financial "
            "metrics, and present recommendations to management. Strong Excel "
            "modelling and data interpretation skills are central to the role."
        ),
        required_skills=["financial_analysis", "financial_modeling", "excel", "financial_reporting"],
        recommended_skills=["budgeting", "forecasting", "sql", "data_visualization"],
    ),
    RoleEntry(
        id="accountant",
        name="Accountant",
        domain="Finance & Accounting",
        description=(
            "Accountants maintain accurate financial records, prepare financial "
            "statements, ensure tax compliance, and support auditing processes. "
            "They manage the general ledger, reconcile accounts, process payroll, "
            "oversee accounts payable and receivable, and ensure adherence to "
            "accounting standards such as GAAP or IFRS."
        ),
        required_skills=["accounting", "financial_reporting", "excel", "documentation"],
        recommended_skills=["financial_analysis", "budgeting", "sql"],
    ),
    # ── Human Resources ───────────────────────────────────────────────────
    RoleEntry(
        id="hr-specialist",
        name="HR Specialist",
        domain="Human Resources",
        description=(
            "HR Specialists manage core human resources functions including "
            "employee relations, onboarding, benefits administration, policy "
            "compliance, and HR record management. They act as a point of "
            "contact for employee queries, support performance management "
            "processes, and partner with managers on workforce-related matters. "
            "Strong interpersonal and communication skills are essential."
        ),
        required_skills=["hr_operations", "employee_relations", "communication", "documentation"],
        recommended_skills=["recruitment", "interviewing", "agile"],
    ),
    RoleEntry(
        id="talent-acquisition-specialist",
        name="Talent Acquisition Specialist",
        domain="Human Resources",
        description=(
            "Talent Acquisition Specialists manage the full recruiting lifecycle — "
            "from job posting and candidate sourcing to interviewing, offer "
            "negotiation, and onboarding. They build talent pipelines, partner "
            "with hiring managers to define requirements, and use data to "
            "improve hiring quality and speed. Employer branding and candidate "
            "experience are key areas of focus."
        ),
        required_skills=["talent_acquisition", "recruitment", "interviewing", "communication"],
        recommended_skills=["stakeholder_management", "hr_operations", "crm"],
    ),
    # ── Sales & Business Development ──────────────────────────────────────
    RoleEntry(
        id="sales-executive",
        name="Sales Executive",
        domain="Sales & Business Development",
        description=(
            "Sales Executives drive revenue by identifying prospects, building "
            "relationships, presenting solutions, and closing deals. They manage "
            "a territory or named accounts, maintain accurate CRM records, meet "
            "or exceed sales quotas, and collaborate with marketing and solutions "
            "teams to progress opportunities through the pipeline."
        ),
        required_skills=["lead_generation", "negotiation", "crm", "communication"],
        recommended_skills=["sales_strategy", "client_relationship_management"],
    ),
    RoleEntry(
        id="business-development-manager",
        name="Business Development Manager",
        domain="Sales & Business Development",
        description=(
            "Business Development Managers identify and pursue new revenue "
            "opportunities through partnerships, new market entry, product "
            "expansion, and strategic alliances. They conduct market research, "
            "develop go-to-market plans, negotiate agreements, and build "
            "long-term relationships with key partners and clients to drive "
            "sustainable business growth."
        ),
        required_skills=["sales_strategy", "negotiation", "market_research", "stakeholder_management"],
        recommended_skills=["lead_generation", "crm", "communication", "client_relationship_management"],
    ),
    # ── Operations & Supply Chain ─────────────────────────────────────────
    RoleEntry(
        id="operations-manager",
        name="Operations Manager",
        domain="Operations & Supply Chain",
        description=(
            "Operations Managers oversee the day-to-day running of business "
            "operations. They optimise workflows, manage teams, control budgets, "
            "implement process improvements, and ensure operational targets for "
            "quality, efficiency, and cost are met. They liaise across "
            "departments to resolve bottlenecks and drive continuous "
            "improvement initiatives."
        ),
        required_skills=["operations_management", "process_improvement", "project_management", "communication"],
        recommended_skills=["supply_chain_management", "budgeting", "stakeholder_management", "excel"],
    ),
    RoleEntry(
        id="supply-chain-analyst",
        name="Supply Chain Analyst",
        domain="Operations & Supply Chain",
        description=(
            "Supply Chain Analysts monitor and analyse supply chain data to "
            "improve efficiency, reduce costs, and identify risks. They track "
            "inventory levels, evaluate supplier performance, forecast demand, "
            "support logistics planning, and produce operational reports. "
            "Proficiency in data analysis and supply chain modelling is key."
        ),
        required_skills=["supply_chain_management", "data_analysis", "excel", "inventory_management"],
        recommended_skills=["logistics", "sql", "forecasting", "process_improvement"],
    ),
    # ── Education & Learning ──────────────────────────────────────────────
    RoleEntry(
        id="teacher-educator",
        name="Teacher / Educator",
        domain="Education & Learning",
        description=(
            "Teachers and Educators design and deliver instruction that supports "
            "student learning. They develop lesson plans aligned to curriculum "
            "standards, use a variety of pedagogical strategies to engage "
            "diverse learners, assess progress, provide feedback, and create "
            "an inclusive and supportive classroom environment."
        ),
        required_skills=["teaching", "curriculum_development", "assessment", "communication"],
        recommended_skills=["instructional_design", "lms"],
    ),
    RoleEntry(
        id="instructional-designer",
        name="Instructional Designer",
        domain="Education & Learning",
        description=(
            "Instructional Designers apply learning theory and design principles "
            "to create effective training programmes, e-learning courses, and "
            "blended learning solutions. They conduct needs analyses, define "
            "learning objectives, develop content and assessments, and evaluate "
            "programme effectiveness. They collaborate with subject matter "
            "experts and use authoring tools and LMS platforms."
        ),
        required_skills=["instructional_design", "curriculum_development", "assessment", "lms"],
        recommended_skills=["teaching", "communication", "documentation"],
    ),
    # ── Engineering ───────────────────────────────────────────────────────
    RoleEntry(
        id="mechanical-engineer",
        name="Mechanical Engineer",
        domain="Engineering",
        description=(
            "Mechanical Engineers design, analyse, and oversee the manufacturing "
            "of mechanical systems and components. They use CAD software to "
            "create detailed designs, apply engineering principles to solve "
            "mechanical problems, conduct structural and thermal analysis, "
            "and collaborate with manufacturing teams to bring designs to "
            "production while ensuring quality and safety standards."
        ),
        required_skills=["engineering_design", "cad", "structural_analysis", "technical_drawing"],
        recommended_skills=["problem_solving", "project_management", "documentation"],
    ),
    RoleEntry(
        id="civil-engineer",
        name="Civil Engineer",
        domain="Engineering",
        description=(
            "Civil Engineers design and oversee the construction of infrastructure "
            "projects such as roads, bridges, buildings, dams, and water systems. "
            "They apply structural and geotechnical analysis, manage project "
            "timelines and budgets, ensure regulatory compliance, and coordinate "
            "with contractors, architects, and local authorities."
        ),
        required_skills=["engineering_design", "structural_analysis", "technical_drawing", "project_management"],
        recommended_skills=["cad", "problem_solving", "documentation", "regulatory_compliance"],
    ),
    RoleEntry(
        id="electrical-engineer",
        name="Electrical Engineer",
        domain="Engineering",
        description=(
            "Electrical Engineers design, develop, and test electrical systems "
            "and components including power distribution systems, control "
            "systems, circuit boards, and embedded electronics. They apply "
            "electrical theory and CAD tools to create schematics, conduct "
            "system analysis, ensure safety compliance, and commission "
            "electrical installations."
        ),
        required_skills=["electrical_systems", "engineering_design", "technical_drawing", "problem_solving"],
        recommended_skills=["cad", "project_management", "documentation", "regulatory_compliance"],
    ),
    # ── Healthcare & Health Administration ────────────────────────────────
    RoleEntry(
        id="healthcare-administrator",
        name="Healthcare Administrator",
        domain="Healthcare & Health Administration",
        description=(
            "Healthcare Administrators manage the operational, financial, and "
            "regulatory aspects of healthcare facilities. They oversee staffing, "
            "budgets, patient services, compliance with healthcare regulations, "
            "and quality improvement programmes. They coordinate across clinical "
            "and administrative departments to ensure efficient, safe, and "
            "patient-centred care delivery."
        ),
        required_skills=["healthcare_operations", "healthcare_compliance", "healthcare_management", "communication"],
        recommended_skills=["medical_records", "budgeting", "project_management", "stakeholder_management"],
    ),
    # ── Legal, Compliance & Risk ──────────────────────────────────────────
    RoleEntry(
        id="compliance-analyst",
        name="Compliance Analyst",
        domain="Legal, Compliance & Risk",
        description=(
            "Compliance Analysts monitor organisational activities to ensure "
            "adherence to laws, regulations, and internal policies. They conduct "
            "compliance assessments, review controls, draft policies and "
            "procedures, support internal audits, and maintain compliance "
            "documentation. They stay current with regulatory changes and "
            "communicate compliance requirements to business units."
        ),
        required_skills=["regulatory_compliance", "policy_analysis", "documentation", "risk_assessment"],
        recommended_skills=["legal_research", "risk_management", "communication"],
    ),
    RoleEntry(
        id="risk-analyst",
        name="Risk Analyst",
        domain="Legal, Compliance & Risk",
        description=(
            "Risk Analysts identify, evaluate, and monitor risks that could "
            "affect organisational objectives. They perform quantitative and "
            "qualitative risk assessments, develop risk registers, model "
            "scenarios to estimate potential losses, and recommend mitigation "
            "strategies. They collaborate with business units to embed risk "
            "awareness and support risk-informed decision-making."
        ),
        required_skills=["risk_assessment", "risk_management", "data_analysis", "documentation"],
        recommended_skills=["financial_analysis", "policy_analysis", "excel", "communication"],
    ),
]
