"""
Seed the Phase 3.2 curated opportunity dataset.

Usage
-----
From the project root:

    python -m backend.scripts.seed_opportunities

From the backend/ directory:

    python -m scripts.seed_opportunities

The seed is deterministic and idempotent. Curated opportunities have
``source='curated'`` and ``external_id=NULL``, so identity is reconciled by the
stable ``source + title + company`` combination.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import os
import sys
from typing import Iterable

from sqlalchemy.orm import Session

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_HERE)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.db.models import (  # noqa: E402
    Opportunity,
    OpportunityPreferredSkill,
    OpportunityRequiredSkill,
)
from app.db.session import Base, SessionLocal, engine  # noqa: E402


VALID_TARGET_ROLES = {
    "Backend Engineer",
    "Full Stack Developer",
    "Frontend Developer",
    "DevOps Engineer",
    "Cloud Engineer",
    "Machine Learning Engineer",
    "Data Scientist",
    "Data Analyst",
    "Product Manager",
    "UI/UX Designer",
}


@dataclass(frozen=True)
class Skill:
    name: str
    normalized_name: str


@dataclass(frozen=True)
class OpportunitySeed:
    title: str
    company: str
    target_role: str
    opportunity_type: str
    location: str
    is_remote: bool
    experience_level: str
    industry: str
    salary_min: int | None
    salary_max: int | None
    application_slug: str
    published_at: datetime
    expires_at: datetime | None
    summary: str
    required_skills: tuple[Skill, ...]
    preferred_skills: tuple[Skill, ...]

    @property
    def application_url(self) -> str:
        return f"https://careersphere.local/opportunities/{self.application_slug}"

    @property
    def description(self) -> str:
        required = ", ".join(skill.name for skill in self.required_skills)
        preferred = ", ".join(skill.name for skill in self.preferred_skills)
        return (
            f"{self.company} is hiring a {self.title} for its {self.industry} team in "
            f"{self.location}. {self.summary} The role is suited to a "
            f"{self.experience_level.lower()} candidate who can work with {required}, "
            f"write maintainable documentation, participate in code or product reviews, "
            f"and collaborate with cross-functional teams. Additional exposure to "
            f"{preferred} is preferred because the team uses those tools while scaling "
            f"curated CareerSphere demo workflows."
        )


def _skill(name: str, normalized_name: str | None = None) -> Skill:
    return Skill(name=name, normalized_name=normalized_name or name.lower().replace(".js", "").replace(" ", "-"))


ROLE_SKILLS: dict[str, tuple[tuple[Skill, ...], tuple[Skill, ...]]] = {
    "Backend Engineer": (
        (_skill("Python"), _skill("FastAPI"), _skill("PostgreSQL"), _skill("REST APIs", "rest-apis"), _skill("Git")),
        (_skill("Docker"), _skill("Redis"), _skill("AWS"), _skill("Kubernetes")),
    ),
    "Full Stack Developer": (
        (_skill("React", "react"), _skill("Node.js", "node"), _skill("TypeScript"), _skill("PostgreSQL"), _skill("REST APIs", "rest-apis")),
        (_skill("Next.js", "nextjs"), _skill("Docker"), _skill("GraphQL", "graphql")),
    ),
    "Frontend Developer": (
        (_skill("React", "react"), _skill("JavaScript"), _skill("TypeScript"), _skill("HTML"), _skill("CSS")),
        (_skill("Next.js", "nextjs"), _skill("Tailwind CSS", "tailwind-css"), _skill("Accessibility", "accessibility")),
    ),
    "DevOps Engineer": (
        (_skill("Linux"), _skill("Docker"), _skill("Kubernetes"), _skill("CI/CD", "ci-cd"), _skill("Terraform")),
        (_skill("AWS"), _skill("Prometheus"), _skill("Grafana"), _skill("Python")),
    ),
    "Cloud Engineer": (
        (_skill("AWS"), _skill("Linux"), _skill("Terraform"), _skill("Networking"), _skill("Docker")),
        (_skill("Kubernetes"), _skill("CloudFormation", "cloudformation"), _skill("Security", "security")),
    ),
    "Machine Learning Engineer": (
        (_skill("Python"), _skill("Machine Learning", "machine-learning"), _skill("PyTorch", "pytorch"), _skill("SQL"), _skill("Git")),
        (_skill("TensorFlow", "tensorflow"), _skill("MLOps", "mlops"), _skill("Docker"), _skill("AWS")),
    ),
    "Data Scientist": (
        (_skill("Python"), _skill("SQL"), _skill("Statistics", "statistics"), _skill("Pandas", "pandas"), _skill("Machine Learning", "machine-learning")),
        (_skill("Tableau", "tableau"), _skill("A/B Testing", "ab-testing"), _skill("Spark", "spark")),
    ),
    "Data Analyst": (
        (_skill("SQL"), _skill("Excel", "excel"), _skill("Data Visualization", "data-visualization"), _skill("Python"), _skill("Dashboards", "dashboards")),
        (_skill("Power BI", "power-bi"), _skill("Tableau", "tableau"), _skill("Statistics", "statistics")),
    ),
    "Product Manager": (
        (_skill("Product Strategy", "product-strategy"), _skill("User Research", "user-research"), _skill("Roadmapping", "roadmapping"), _skill("Analytics", "analytics")),
        (_skill("SQL"), _skill("Figma", "figma"), _skill("Agile", "agile")),
    ),
    "UI/UX Designer": (
        (_skill("Figma", "figma"), _skill("User Research", "user-research"), _skill("Wireframing", "wireframing"), _skill("Prototyping", "prototyping"), _skill("Design Systems", "design-systems")),
        (_skill("Accessibility", "accessibility"), _skill("HTML"), _skill("Usability Testing", "usability-testing")),
    ),
}


SEED_ROWS: tuple[tuple[str, str, str, str, str, bool, str, str, int | None, int | None, str, str], ...] = (
    ("Backend API Engineer", "NimbusLedger Labs", "Backend Engineer", "job", "Bengaluru, India", False, "Mid Level", "FinTech", 1400000, 2200000, "backend-api-engineer-nimbusledger", "build payment reconciliation APIs, improve ledger consistency, and harden authentication flows for high-volume business accounts"),
    ("Backend Platform Engineer", "Medora Health", "Backend Engineer", "job", "Hyderabad, India", False, "Junior", "HealthTech", 800000, 1300000, "backend-platform-engineer-medora", "develop patient workflow services, maintain audit-friendly data models, and support integrations with appointment and claims systems"),
    ("Python Backend Engineer", "CartPilot Commerce", "Backend Engineer", "job", "Pune, India", False, "Junior", "E-commerce", 700000, 1200000, "python-backend-engineer-cartpilot", "extend catalog, order, and inventory services used by marketplace sellers during seasonal traffic spikes"),
    ("Backend Engineer - Developer Tools", "StackHarbor", "Backend Engineer", "job", "Remote - India", True, "Mid Level", "Developer Tools", 1500000, 2100000, "backend-engineer-developer-tools-stackharbor", "ship APIs for build insights, usage metering, and team administration in a developer productivity platform"),
    ("Backend Engineer - Logistics Systems", "RouteMint Logistics", "Backend Engineer", "job", "Chennai, India", False, "Mid Level", "Logistics", 1200000, 1900000, "backend-engineer-logistics-routemint", "maintain routing, dispatch, and shipment visibility services for regional logistics partners"),
    ("Backend Engineer - SaaS Integrations", "Flowdesk Cloud", "Backend Engineer", "job", "Gurugram, India", False, "Entry Level", "SaaS", 500000, 850000, "backend-engineer-saas-integrations-flowdesk", "create connector services, webhook handlers, and admin APIs for small-business workflow automation"),
    ("Backend Security Engineer", "CipherNest", "Backend Engineer", "job", "Noida, India", False, "Mid Level", "Cybersecurity", 1300000, 2000000, "backend-security-engineer-ciphernest", "build secure identity, policy, and event ingestion services for a cloud security monitoring product"),
    ("Backend Engineering Intern", "LearnGrid", "Backend Engineer", "internship", "Remote - India", True, "Intern", "EdTech", None, None, "backend-engineering-intern-learngrid", "assist with classroom API endpoints, automated tests, and small reliability fixes under senior engineer mentorship"),
    ("Junior Backend Engineer", "KiteWorks SaaS", "Backend Engineer", "job", "Mumbai, India", False, "Junior", "Enterprise Software", 650000, 1100000, "junior-backend-engineer-kiteworks", "implement account settings, reporting endpoints, and background jobs for enterprise operations teams"),
    ("Full Stack Developer", "BrightHire Studio", "Full Stack Developer", "job", "Bengaluru, India", False, "Junior", "SaaS", 800000, 1300000, "full-stack-developer-brighthire", "deliver user-facing hiring dashboards while improving server-side candidate workflow APIs"),
    ("Full Stack Engineer - FinTech", "MintBridge", "Full Stack Developer", "job", "Mumbai, India", False, "Mid Level", "FinTech", 1300000, 2100000, "full-stack-engineer-fintech-mintbridge", "own features across merchant onboarding, risk review screens, and payout service integrations"),
    ("Full Stack Developer - Health Portal", "CareLoop Systems", "Full Stack Developer", "job", "Hyderabad, India", False, "Entry Level", "HealthTech", 550000, 900000, "full-stack-developer-health-portal-careloop", "improve care-team portals, appointment notes, and secure API integrations for clinics"),
    ("Full Stack Engineer - EdTech", "SkillSpring", "Full Stack Developer", "job", "Remote - India", True, "Junior", "EdTech", 850000, 1400000, "full-stack-engineer-edtech-skillspring", "build learner progress views, content tooling, and subscription features for online education programs"),
    ("Full Stack Developer - Logistics", "FreightBee", "Full Stack Developer", "job", "Pune, India", False, "Mid Level", "Logistics", 1100000, 1800000, "full-stack-developer-logistics-freightbee", "create shipment planning screens and supporting APIs for warehouse and transport coordinators"),
    ("Full Stack Developer Intern", "OrbitClass", "Full Stack Developer", "internship", "Remote - India", True, "Intern", "EdTech", None, None, "full-stack-developer-intern-orbitclass", "support small product experiments, bug fixes, and internal admin tools for a cohort learning platform"),
    ("Entry Level Full Stack Developer", "DukaanWorks", "Full Stack Developer", "job", "Delhi, India", False, "Entry Level", "E-commerce", 450000, 750000, "entry-level-full-stack-developer-dukaanworks", "help modernize storefront templates, checkout workflows, and seller analytics features"),
    ("Full Stack Product Engineer", "AtlasOps", "Full Stack Developer", "job", "Remote - India", True, "Mid Level", "Enterprise Software", 1400000, 2200000, "full-stack-product-engineer-atlasops", "turn customer operations problems into polished workflows backed by reliable application services"),
    ("Frontend Engineer", "PixelPay", "Frontend Developer", "job", "Bengaluru, India", False, "Junior", "FinTech", 750000, 1250000, "frontend-engineer-pixelpay", "build responsive merchant dashboards, reusable UI components, and client-side validation for payment operations"),
    ("React Frontend Developer", "WellNest Health", "Frontend Developer", "job", "Pune, India", False, "Entry Level", "HealthTech", 500000, 850000, "react-frontend-developer-wellnest", "implement accessible patient intake flows, appointment screens, and data-heavy care summaries"),
    ("Frontend Developer - Commerce", "ShopTrail", "Frontend Developer", "job", "Remote - India", True, "Junior", "E-commerce", 800000, 1300000, "frontend-developer-commerce-shoptrail", "improve product discovery, cart interactions, and seller-facing catalog management views"),
    ("Frontend Platform Engineer", "CanvasRail", "Frontend Developer", "job", "Hyderabad, India", False, "Mid Level", "Developer Tools", 1200000, 1900000, "frontend-platform-engineer-canvasrail", "maintain a shared component library, frontend build tooling, and observability for multiple product teams"),
    ("Frontend Developer Intern", "EduVista", "Frontend Developer", "internship", "Remote - India", True, "Intern", "EdTech", None, None, "frontend-developer-intern-eduvista", "assist with learner dashboards, design handoff fixes, and browser testing for digital classroom features"),
    ("Junior Frontend Developer", "MetroMove", "Frontend Developer", "job", "Chennai, India", False, "Junior", "Logistics", 650000, 1000000, "junior-frontend-developer-metromove", "build dispatch interfaces, status timelines, and map-adjacent controls for transport operations teams"),
    ("Frontend Accessibility Engineer", "CivicSaaS", "Frontend Developer", "job", "Noida, India", False, "Mid Level", "SaaS", 1100000, 1700000, "frontend-accessibility-engineer-civicsaas", "raise accessibility quality across reporting, onboarding, and admin workflows used by public-sector clients"),
    ("DevOps Engineer", "CloudCartel", "DevOps Engineer", "job", "Bengaluru, India", False, "Mid Level", "Cloud Computing", 1400000, 2200000, "devops-engineer-cloudcartel", "operate container platforms, deployment pipelines, and infrastructure modules for multi-tenant SaaS products"),
    ("Junior DevOps Engineer", "InfraNest", "DevOps Engineer", "job", "Pune, India", False, "Junior", "Developer Tools", 700000, 1150000, "junior-devops-engineer-infranest", "support CI pipelines, container images, environment monitoring, and release checklists for engineering squads"),
    ("DevOps Engineer - FinTech Reliability", "RupeeRails", "DevOps Engineer", "job", "Mumbai, India", False, "Mid Level", "FinTech", 1500000, 2300000, "devops-engineer-fintech-reliability-rupeerails", "improve deployment safety, incident response, and service observability for transaction processing systems"),
    ("DevOps Engineer - Healthcare", "PulseOps", "DevOps Engineer", "job", "Hyderabad, India", False, "Mid Level", "HealthTech", 1300000, 2000000, "devops-engineer-healthcare-pulseops", "maintain compliant environments, release automation, and monitoring for care coordination services"),
    ("DevOps Intern", "PipelineFox", "DevOps Engineer", "internship", "Remote - India", True, "Intern", "Developer Tools", None, None, "devops-intern-pipelinefox", "assist with build automation, dashboard cleanup, and documentation for a managed CI platform"),
    ("Site Reliability Engineer", "StreamForge Media", "DevOps Engineer", "job", "Chennai, India", False, "Mid Level", "Media", 1400000, 2100000, "site-reliability-engineer-streamforge", "support high-traffic streaming services through capacity planning, alert tuning, and production readiness reviews"),
    ("Entry Level DevOps Engineer", "OpsKart", "DevOps Engineer", "job", "Noida, India", False, "Entry Level", "Enterprise Software", 500000, 850000, "entry-level-devops-engineer-opskart", "help automate internal environments, triage deployment failures, and maintain runbooks for support teams"),
    ("Cloud Engineer", "SkyLedger", "Cloud Engineer", "job", "Bengaluru, India", False, "Junior", "FinTech", 900000, 1500000, "cloud-engineer-skyledger", "provision secure cloud resources, tune cost visibility, and support platform migrations for finance workloads"),
    ("AWS Cloud Engineer", "HealthNimbus", "Cloud Engineer", "job", "Hyderabad, India", False, "Mid Level", "HealthTech", 1400000, 2100000, "aws-cloud-engineer-healthnimbus", "build resilient cloud foundations for healthcare data services with careful attention to compliance and access control"),
    ("Cloud Operations Engineer", "EduCloud Labs", "Cloud Engineer", "job", "Remote - India", True, "Junior", "EdTech", 850000, 1400000, "cloud-operations-engineer-educloud", "monitor cloud workloads, support environment requests, and improve deployment templates for learning platforms"),
    ("Cloud Engineer - E-commerce", "BazaarStack", "Cloud Engineer", "job", "Pune, India", False, "Mid Level", "E-commerce", 1300000, 2000000, "cloud-engineer-ecommerce-bazaarstack", "modernize storefront infrastructure, batch jobs, and scaling policies for online retail traffic"),
    ("Cloud Infrastructure Intern", "OrbitScale", "Cloud Engineer", "internship", "Remote - India", True, "Intern", "Cloud Computing", None, None, "cloud-infrastructure-intern-orbitscale", "learn cloud operations by helping document infrastructure modules, tagging standards, and sandbox deployments"),
    ("Entry Level Cloud Engineer", "NorthStar Systems", "Cloud Engineer", "job", "Delhi, India", False, "Entry Level", "Enterprise Software", 550000, 900000, "entry-level-cloud-engineer-northstar", "assist with cloud account setup, backup checks, and network configuration for customer implementations"),
    ("Machine Learning Engineer", "Auralytics AI", "Machine Learning Engineer", "job", "Bengaluru, India", False, "Mid Level", "AI/ML", 1600000, 2400000, "machine-learning-engineer-auralytics", "train and deploy recommendation models, evaluate model drift, and collaborate with data platform engineers"),
    ("ML Engineer - Search Ranking", "Findly Commerce", "Machine Learning Engineer", "job", "Remote - India", True, "Mid Level", "E-commerce", 1700000, 2500000, "ml-engineer-search-ranking-findly", "improve search ranking, feature pipelines, and offline evaluation for product discovery experiences"),
    ("Junior Machine Learning Engineer", "MedVision AI", "Machine Learning Engineer", "job", "Hyderabad, India", False, "Junior", "HealthTech", 900000, 1500000, "junior-machine-learning-engineer-medvision", "support clinical document classification models, data validation, and model monitoring under senior guidance"),
    ("ML Platform Engineer", "ModelDock", "Machine Learning Engineer", "job", "Pune, India", False, "Mid Level", "Developer Tools", 1500000, 2300000, "ml-platform-engineer-modeldock", "build model packaging, experiment tracking, and deployment workflows for internal data science teams"),
    ("Machine Learning Intern", "TutorMind", "Machine Learning Engineer", "internship", "Remote - India", True, "Intern", "EdTech", None, None, "machine-learning-intern-tutormind", "prototype learning analytics models, prepare labeled datasets, and summarize experiments for product stakeholders"),
    ("NLP Engineer", "LexiFlow", "Machine Learning Engineer", "job", "Noida, India", False, "Junior", "AI/ML", 1000000, 1600000, "nlp-engineer-lexiflow", "develop text classification, semantic search, and evaluation tooling for enterprise document workflows"),
    ("Computer Vision Engineer", "InspectAI", "Machine Learning Engineer", "job", "Chennai, India", False, "Mid Level", "AI/ML", 1500000, 2300000, "computer-vision-engineer-inspectai", "create image quality, object detection, and inference optimization features for industrial inspection products"),
    ("Data Scientist", "CreditVista", "Data Scientist", "job", "Mumbai, India", False, "Mid Level", "FinTech", 1400000, 2200000, "data-scientist-creditvista", "build risk models, analyze repayment behavior, and translate experiments into credit policy recommendations"),
    ("Junior Data Scientist", "CarePredict", "Data Scientist", "job", "Hyderabad, India", False, "Junior", "HealthTech", 850000, 1400000, "junior-data-scientist-carepredict", "analyze patient engagement signals, validate predictive features, and package notebooks into reproducible reports"),
    ("Data Scientist - Growth", "LearnLoop", "Data Scientist", "job", "Remote - India", True, "Mid Level", "EdTech", 1300000, 2000000, "data-scientist-growth-learnloop", "measure acquisition funnels, learner retention, and experiment outcomes for subscription education products"),
    ("Entry Level Data Scientist", "ShipSense", "Data Scientist", "job", "Pune, India", False, "Entry Level", "Logistics", 600000, 1000000, "entry-level-data-scientist-shipsense", "support ETA modeling, route analytics, and operational metric reviews for logistics planners"),
    ("Data Analyst", "RetailPulse", "Data Analyst", "job", "Bengaluru, India", False, "Entry Level", "E-commerce", 450000, 800000, "data-analyst-retailpulse", "prepare weekly commerce dashboards, investigate funnel changes, and keep stakeholder metric definitions consistent"),
    ("Business Data Analyst", "FinOpsly", "Data Analyst", "job", "Mumbai, India", False, "Junior", "FinTech", 700000, 1100000, "business-data-analyst-finopsly", "analyze transaction operations, reconcile reporting datasets, and support compliance-ready business reviews"),
    ("Product Data Analyst", "SaaSBeacon", "Data Analyst", "job", "Remote - India", True, "Junior", "SaaS", 750000, 1200000, "product-data-analyst-saasbeacon", "track feature adoption, cohort behavior, and customer health metrics for product and success teams"),
    ("Data Analyst Intern", "ClinicFlow", "Data Analyst", "internship", "Remote - India", True, "Intern", "HealthTech", None, None, "data-analyst-intern-clinicflow", "clean operational datasets, refresh dashboards, and document metric logic for care operations managers"),
    ("Product Manager", "TeamOrbit", "Product Manager", "job", "Bengaluru, India", False, "Mid Level", "SaaS", 1500000, 2300000, "product-manager-teamorbit", "own roadmap decisions for collaboration workflows, balancing customer discovery with delivery planning"),
    ("Associate Product Manager", "PayBridge", "Product Manager", "job", "Mumbai, India", False, "Entry Level", "FinTech", 800000, 1300000, "associate-product-manager-paybridge", "support merchant onboarding improvements, write clear requirements, and analyze launch metrics with engineering"),
    ("Product Manager - AI Tools", "PromptCraft", "Product Manager", "job", "Remote - India", True, "Mid Level", "AI/ML", 1600000, 2400000, "product-manager-ai-tools-promptcraft", "shape AI-assisted workflow features, evaluate user feedback, and coordinate responsible rollout decisions"),
    ("Entry Level Product Manager", "CampusStack", "Product Manager", "job", "Remote - India", True, "Entry Level", "EdTech", 600000, 950000, "entry-level-product-manager-campusstack", "help research learner problems, maintain product notes, and analyze small experiments for student engagement"),
    ("UI/UX Designer", "NovaBanking", "UI/UX Designer", "job", "Mumbai, India", False, "Junior", "FinTech", 700000, 1200000, "ui-ux-designer-novabanking", "design intuitive money movement flows, validate prototypes, and maintain reusable patterns with product teams"),
    ("Product Designer", "HealioDesk", "UI/UX Designer", "job", "Hyderabad, India", False, "Mid Level", "HealthTech", 1100000, 1800000, "product-designer-healiodesk", "improve clinician task flows, patient communication screens, and design system quality for healthcare teams"),
    ("UX Designer - Commerce", "Shelfwise", "UI/UX Designer", "job", "Remote - India", True, "Junior", "E-commerce", 800000, 1300000, "ux-designer-commerce-shelfwise", "research seller pain points, prototype checkout improvements, and partner with engineers on interaction details"),
    ("UI/UX Design Intern", "PathClass", "UI/UX Designer", "internship", "Remote - India", True, "Intern", "EdTech", None, None, "ui-ux-design-intern-pathclass", "support wireframes, usability notes, and component cleanup for a student learning experience team"),
)


def _published(index: int) -> datetime:
    return datetime(2026, 1 + (index % 6), 5 + (index % 20), 9, 0, tzinfo=timezone.utc)


def _expires(index: int) -> datetime:
    return datetime(2026, 10 + (index % 3), 10 + (index % 15), 23, 59, tzinfo=timezone.utc)


def get_curated_opportunities() -> tuple[OpportunitySeed, ...]:
    opportunities: list[OpportunitySeed] = []
    for index, row in enumerate(SEED_ROWS):
        (
            title,
            company,
            target_role,
            opportunity_type,
            location,
            is_remote,
            experience_level,
            industry,
            salary_min,
            salary_max,
            slug,
            summary,
        ) = row
        required, preferred = ROLE_SKILLS[target_role]
        opportunities.append(
            OpportunitySeed(
                title=title,
                company=company,
                target_role=target_role,
                opportunity_type=opportunity_type,
                location=location,
                is_remote=is_remote,
                experience_level=experience_level,
                industry=industry,
                salary_min=salary_min,
                salary_max=salary_max,
                application_slug=slug,
                published_at=_published(index),
                expires_at=_expires(index),
                summary=summary,
                required_skills=required,
                preferred_skills=preferred,
            )
        )
    return tuple(opportunities)


CURATED_OPPORTUNITIES = get_curated_opportunities()


def _normalized_set(skills: Iterable[Skill]) -> set[str]:
    return {skill.normalized_name for skill in skills}


def validate_seed_dataset(opportunities: tuple[OpportunitySeed, ...] = CURATED_OPPORTUNITIES) -> None:
    errors: list[str] = []
    if len(opportunities) != 60:
        errors.append(f"Expected exactly 60 opportunities, found {len(opportunities)}")

    identities = [(opp.title, opp.company) for opp in opportunities]
    duplicates = [identity for identity, count in Counter(identities).items() if count > 1]
    if duplicates:
        errors.append(f"Duplicate curated identities: {duplicates}")

    types = {opp.opportunity_type for opp in opportunities}
    remote_values = {opp.is_remote for opp in opportunities}
    experience_levels = {opp.experience_level for opp in opportunities}

    for opp in opportunities:
        if opp.target_role not in VALID_TARGET_ROLES:
            errors.append(f"{opp.title}: invalid target_role {opp.target_role!r}")
        if opp.opportunity_type not in {"job", "internship"}:
            errors.append(f"{opp.title}: invalid opportunity_type {opp.opportunity_type!r}")
        if opp.salary_min is not None and opp.salary_max is not None and opp.salary_min > opp.salary_max:
            errors.append(f"{opp.title}: salary_min is greater than salary_max")
        if len(opp.description.strip()) < 120:
            errors.append(f"{opp.title}: description is too short")
        required = _normalized_set(opp.required_skills)
        preferred = _normalized_set(opp.preferred_skills)
        if len(required) != len(opp.required_skills):
            errors.append(f"{opp.title}: duplicate required skills")
        if len(preferred) != len(opp.preferred_skills):
            errors.append(f"{opp.title}: duplicate preferred skills")
        if required & preferred:
            errors.append(f"{opp.title}: required/preferred overlap {sorted(required & preferred)}")
        if not 4 <= len(required) <= 8:
            errors.append(f"{opp.title}: required skill count outside 4-8")
        if not 2 <= len(preferred) <= 5:
            errors.append(f"{opp.title}: preferred skill count outside 2-5")

    if not {"job", "internship"}.issubset(types):
        errors.append("Both job and internship opportunity types must exist")
    if remote_values != {False, True}:
        errors.append("Both remote and non-remote opportunities must exist")
    if len(experience_levels) < 3:
        errors.append("Multiple experience levels must exist")

    if errors:
        raise ValueError("Curated opportunity dataset validation failed:\n- " + "\n- ".join(errors))


@dataclass(frozen=True)
class SeedResult:
    inserted: int
    updated: int
    curated_total: int
    required_skill_rows: int
    preferred_skill_rows: int
    role_distribution: dict[str, int]
    type_distribution: dict[str, int]
    remote_distribution: dict[str, int]
    experience_distribution: dict[str, int]


def _apply_skills(db: Session, opportunity: Opportunity, seed: OpportunitySeed) -> None:
    db.query(OpportunityRequiredSkill).filter(
        OpportunityRequiredSkill.opportunity_id == opportunity.id
    ).delete(synchronize_session=False)
    db.query(OpportunityPreferredSkill).filter(
        OpportunityPreferredSkill.opportunity_id == opportunity.id
    ).delete(synchronize_session=False)

    for skill in seed.required_skills:
        db.add(
            OpportunityRequiredSkill(
                opportunity_id=opportunity.id,
                name=skill.name,
                normalized_name=skill.normalized_name,
            )
        )
    for skill in seed.preferred_skills:
        db.add(
            OpportunityPreferredSkill(
                opportunity_id=opportunity.id,
                name=skill.name,
                normalized_name=skill.normalized_name,
            )
        )


def _update_opportunity(opp: Opportunity, seed: OpportunitySeed) -> None:
    opp.title = seed.title
    opp.company = seed.company
    opp.description = seed.description
    opp.opportunity_type = seed.opportunity_type
    opp.target_role = seed.target_role
    opp.location = seed.location
    opp.is_remote = seed.is_remote
    opp.experience_level = seed.experience_level
    opp.industry = seed.industry
    opp.salary_min = seed.salary_min
    opp.salary_max = seed.salary_max
    opp.application_url = seed.application_url
    opp.source = "curated"
    opp.external_id = None
    opp.published_at = seed.published_at
    opp.expires_at = seed.expires_at


def _validation_summary(db: Session) -> SeedResult:
    curated = db.query(Opportunity).filter(Opportunity.source == "curated").all()
    if len(curated) != 60:
        raise RuntimeError(f"Expected 60 curated opportunities after seeding, found {len(curated)}")

    curated_ids = [opp.id for opp in curated]
    required_count = (
        db.query(OpportunityRequiredSkill)
        .filter(OpportunityRequiredSkill.opportunity_id.in_(curated_ids))
        .count()
    )
    preferred_count = (
        db.query(OpportunityPreferredSkill)
        .filter(OpportunityPreferredSkill.opportunity_id.in_(curated_ids))
        .count()
    )
    if required_count == 0 or preferred_count == 0:
        raise RuntimeError("Curated opportunities must have required and preferred skills")

    for opp in curated:
        required = {skill.normalized_name for skill in opp.required_skills}
        preferred = {skill.normalized_name for skill in opp.preferred_skills}
        if required & preferred:
            raise RuntimeError(f"{opp.title} has overlapping required/preferred skills")
        if opp.target_role not in VALID_TARGET_ROLES:
            raise RuntimeError(f"{opp.title} has invalid target role {opp.target_role}")

    type_distribution = Counter(opp.opportunity_type for opp in curated)
    remote_distribution = Counter("remote" if opp.is_remote else "non_remote" for opp in curated)
    if not {"job", "internship"}.issubset(type_distribution):
        raise RuntimeError("Curated opportunities must include both jobs and internships")
    if not {"remote", "non_remote"}.issubset(remote_distribution):
        raise RuntimeError("Curated opportunities must include remote and non-remote roles")

    return SeedResult(
        inserted=0,
        updated=0,
        curated_total=len(curated),
        required_skill_rows=required_count,
        preferred_skill_rows=preferred_count,
        role_distribution=dict(sorted(Counter(opp.target_role for opp in curated).items())),
        type_distribution=dict(sorted(type_distribution.items())),
        remote_distribution=dict(sorted(remote_distribution.items())),
        experience_distribution=dict(sorted(Counter(opp.experience_level for opp in curated).items())),
    )


def seed_curated_opportunities(db: Session) -> SeedResult:
    validate_seed_dataset()
    if db.in_transaction():
        db.rollback()
    inserted = 0
    updated = 0

    with db.begin():
        for seed in CURATED_OPPORTUNITIES:
            opportunity = (
                db.query(Opportunity)
                .filter(
                    Opportunity.source == "curated",
                    Opportunity.title == seed.title,
                    Opportunity.company == seed.company,
                )
                .one_or_none()
            )
            if opportunity is None:
                opportunity = Opportunity()
                db.add(opportunity)
                inserted += 1
            else:
                updated += 1

            _update_opportunity(opportunity, seed)
            db.flush()
            _apply_skills(db, opportunity, seed)

    summary = _validation_summary(db)
    db.rollback()
    return SeedResult(
        inserted=inserted,
        updated=updated,
        curated_total=summary.curated_total,
        required_skill_rows=summary.required_skill_rows,
        preferred_skill_rows=summary.preferred_skill_rows,
        role_distribution=summary.role_distribution,
        type_distribution=summary.type_distribution,
        remote_distribution=summary.remote_distribution,
        experience_distribution=summary.experience_distribution,
    )


def main() -> int:
    print("Seeding curated opportunities...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        result = seed_curated_opportunities(db)
        print(f"Inserted: {result.inserted}")
        print(f"Updated: {result.updated}")
        print(f"Required skills: {result.required_skill_rows}")
        print(f"Preferred skills: {result.preferred_skill_rows}")
        print(f"Total curated opportunities: {result.curated_total}")
        print(f"Role distribution: {result.role_distribution}")
        print(f"Job/internship distribution: {result.type_distribution}")
        print(f"Remote/non-remote distribution: {result.remote_distribution}")
        print(f"Experience-level distribution: {result.experience_distribution}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"Seeding failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
