"""
Interview role catalog for the AI Interviewer.

Plain, versioned Python data (the same pattern as career_knowledge.py) so roles
are configuration rather than if/else logic. Adding a role means adding one
entry here — no frontend or service changes.

Each role defines the competencies an interview for that role must cover:

* weight      — relative share of conceptual question slots (higher = more often)
* focus       — the focus-area group shown on the setup page
* practical   — which practical assessment this competency supports, if any:
                  coding       executable code judged by test cases (Judge0)
                  sql          executable SQL judged by result sets
                  calculation  deterministic, computed answers (e.g. subnetting)
                  scenario     written practical task, AI-reviewed against a rubric
* keywords    — technology names that belong to this competency. They are used
                to (a) keep only role-relevant profile skills and (b) detect
                questions that drift into another role's technologies.

This catalog is separate from career_knowledge.py on purpose: that file lists
skills for Skill Analysis and Career Matching; this one lists interview
competencies. `career_role_id` links the two where a role exists in both.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

PRACTICAL_KINDS = ("coding", "sql", "calculation", "scenario")
CODING_LANGUAGES = ("CPP", "JAVA", "PYTHON", "JAVASCRIPT")
LANGUAGE_LABELS = {"CPP": "C++17", "JAVA": "Java 17", "PYTHON": "Python 3", "JAVASCRIPT": "JavaScript (Node.js)"}


@dataclass(frozen=True)
class Competency:
    id: str
    name: str
    focus: str
    weight: float = 1.0
    practical: Optional[str] = None
    keywords: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class InterviewRole:
    slug: str
    title: str
    family: str
    summary: str
    competencies: tuple[Competency, ...]
    practical_kinds: tuple[str, ...]  # preferred order when allocating practical slots
    aliases: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    career_role_id: Optional[str] = None

    @property
    def focus_areas(self) -> list[str]:
        seen: list[str] = []
        for competency in self.competencies:
            if competency.focus not in seen:
                seen.append(competency.focus)
        return seen

    @property
    def allowed_terms(self) -> set[str]:
        return {kw.lower() for c in self.competencies for kw in c.keywords}


def C(id: str, name: str, focus: str, weight: float = 1.0, practical: Optional[str] = None,
      keywords: tuple[str, ...] = (), description: str = "") -> Competency:
    return Competency(id, name, focus, weight, practical, keywords, description)


# ---------------------------------------------------------------------------
# Behavioral competencies (shared by every role; the role is used as context)
# ---------------------------------------------------------------------------

BEHAVIORAL_COMPETENCIES: tuple[Competency, ...] = (
    C("teamwork", "Teamwork & Collaboration", "Behavioral"),
    C("communication", "Communication", "Behavioral"),
    C("conflict-resolution", "Conflict Resolution", "Behavioral"),
    C("ownership", "Ownership & Accountability", "Behavioral"),
    C("adaptability", "Adaptability & Learning", "Behavioral"),
    C("judgment", "Decision Making & Professional Judgment", "Behavioral"),
)

# ---------------------------------------------------------------------------
# Distinctive technology terms.
# A generated question that mentions one of these terms is "off-role" when the
# term is not part of the selected role's competencies (or the user's own
# focus areas / notes). Generic words (api, cache, testing, performance) are
# deliberately excluded so legitimate questions are not rejected, as are terms
# that double as ordinary English words (express, swift, spark, rip, dom).
# Those still appear in competency keywords, which only drive profile matching.
# ---------------------------------------------------------------------------

TECH_TERMS: tuple[str, ...] = (
    # frontend
    "react", "angular", "vue", "svelte", "redux", "next.js", "jsx", "html", "css", "sass",
    "tailwind", "webpack", "vite",
    # backend / languages
    "node.js", "express.js", "django", "flask", "fastapi", "spring boot", "hibernate",
    "java", "python", "kotlin", "swiftui", "c++", "golang", ".net", "c#",
    "graphql", "grpc", "jwt", "oauth",
    # data stores
    "sql", "postgresql", "mysql", "oracle", "sql server", "mongodb", "redis", "cassandra",
    "stored procedure", "stored procedures", "plsql", "pl/sql", "t-sql",
    # networking
    "ospf", "bgp", "eigrp", "vlan", "vlans", "subnet", "subnets", "subnetting", "cidr",
    "dhcp", "stp", "mpls", "cisco", "tcp/ip",
    # infrastructure / devops / cloud
    "linux", "bash", "docker", "kubernetes", "terraform", "ansible", "jenkins", "helm",
    "prometheus", "grafana", "ci/cd", "github actions", "aws", "azure", "gcp", "ec2", "s3",
    # data / ml
    "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "pyspark", "apache spark", "hadoop", "airflow",
    "kafka", "tableau", "power bi", "transformers", "bert", "llm", "llms",
    # security
    "owasp", "burp suite", "metasploit", "nmap", "wireshark", "siem", "splunk", "xss",
    "sql injection", "csrf",
    # testing
    "selenium", "cypress", "playwright", "jmeter", "gatling", "junit", "pytest", "postman",
    # mobile
    "android", "ios", "flutter", "react native", "jetpack compose", "xcode",
)

# ---------------------------------------------------------------------------
# Reusable competency blocks
# ---------------------------------------------------------------------------

_DSA = (
    C("data-structures", "Data Structures", "Data Structures & Algorithms", 2.5, "coding",
      ("data structures",), "Arrays, linked lists, stacks, queues, hash maps, trees, graphs, heaps."),
    C("algorithms", "Algorithms & Problem Solving", "Data Structures & Algorithms", 2.5, "coding",
      ("algorithms", "dsa"), "Searching, sorting, recursion, two pointers, dynamic programming, complexity analysis."),
    C("arrays-strings", "Arrays & Strings", "Data Structures & Algorithms", 1.5, "coding",
      (), "Array and string manipulation, sliding windows, hashing."),
)

_SQL_CORE = (
    C("sql-queries", "SQL Queries", "SQL", 3, "sql", ("sql", "postgresql", "mysql", "sql server", "oracle", "t-sql"),
      "SELECT, filtering, grouping, aggregation, window functions."),
    C("joins-subqueries", "Joins & Subqueries", "SQL", 2, "sql", ("sql",), "Inner/outer joins, self joins, correlated subqueries, CTEs."),
    C("database-design", "Database Design & Normalization", "Database Design", 2, "scenario", ("sql",),
      "ER modelling, keys, normal forms, denormalization trade-offs."),
    C("indexing", "Indexing", "Performance & Optimization", 1.5, None, ("sql", "postgresql", "mysql"),
      "B-tree and hash indexes, composite indexes, selectivity, write cost."),
    C("transactions", "Transactions & ACID", "Transactions & Concurrency", 1.5, None, ("sql",),
      "ACID, isolation levels, locking, deadlocks, MVCC."),
    C("query-optimization", "Query Optimization", "Performance & Optimization", 1.5, "sql", ("sql", "postgresql", "mysql"),
      "Execution plans, rewriting queries, statistics, avoiding N+1 patterns."),
)

_NETWORK_CORE = (
    C("network-models", "OSI & TCP/IP Models", "Networking Fundamentals", 1.5, None, ("osi", "tcp/ip"),
      "Layers, encapsulation, TCP vs UDP, ports."),
    C("ip-subnetting", "IP Addressing & Subnetting", "IP Addressing & Subnetting", 2.5, "calculation",
      ("subnet", "subnets", "subnetting", "cidr", "nat"), "IPv4/IPv6 addressing, CIDR, VLSM, NAT."),
    C("routing-switching", "Routing & Switching", "Routing & Switching", 2, "scenario",
      ("ospf", "bgp", "eigrp", "rip", "vlan", "vlans", "stp", "mpls", "cisco"),
      "Static and dynamic routing, OSPF, BGP basics, VLANs, STP, inter-VLAN routing."),
    C("network-services", "Network Services (DNS, DHCP)", "Network Protocols", 1.5, None, ("dhcp", "nat"),
      "DNS resolution, DHCP, ARP, ICMP, NTP."),
    C("network-troubleshooting", "Network Troubleshooting", "Troubleshooting", 2, "scenario",
      ("wireshark", "linux", "cisco"), "Methodical diagnosis with ping, traceroute, packet captures, interface counters."),
    C("network-security-basics", "Firewalls & Network Security", "Network Security", 1, None,
      ("vlan", "nat"), "ACLs, firewalls, VPNs, segmentation."),
)

_DEVOPS_CORE = (
    C("linux", "Linux Administration", "Linux & Scripting", 2, None, ("linux", "bash"), "Processes, permissions, systemd, logs, networking tools."),
    C("scripting-automation", "Scripting & Automation", "Linux & Scripting", 2, "coding", ("bash", "python", "linux"),
      "Bash and Python automation, text processing, idempotent scripts."),
    C("containers", "Docker & Containers", "Containers & Orchestration", 2, "scenario", ("docker",), "Images, layers, networking, debugging containers."),
    C("kubernetes", "Kubernetes", "Containers & Orchestration", 1.5, "scenario", ("kubernetes", "helm", "docker"),
      "Pods, deployments, services, probes, troubleshooting workloads."),
    C("ci-cd", "CI/CD Pipelines", "CI/CD", 2, "scenario", ("ci/cd", "jenkins", "github actions", "docker"),
      "Pipeline design, build/test/deploy stages, rollbacks, artifacts."),
    C("iac", "Infrastructure as Code", "Infrastructure as Code", 1.5, "scenario", ("terraform", "ansible"),
      "Terraform/Ansible concepts, state, drift, modules."),
    C("monitoring", "Monitoring & Troubleshooting", "Observability", 1.5, None, ("prometheus", "grafana", "linux"),
      "Metrics, logs, alerts, incident triage."),
)

_CLOUD_CORE = (
    C("cloud-compute", "Cloud Compute & Storage", "Cloud Services", 2, "scenario", ("aws", "azure", "gcp", "ec2", "s3"),
      "Virtual machines, object storage, managed services, autoscaling."),
    C("cloud-networking", "Cloud Networking", "Cloud Networking", 1.5, "scenario", ("aws", "azure", "gcp", "subnet", "subnets", "cidr", "nat"),
      "VPCs/VNets, subnets, routing, security groups, load balancers."),
    C("cloud-iam", "Identity & Access Management", "Cloud Security", 1.5, None, ("aws", "azure", "gcp"), "Least privilege, roles, policies."),
    C("cloud-architecture", "Cloud Architecture & Reliability", "Architecture", 1.5, None, ("aws", "azure", "gcp"),
      "High availability, disaster recovery, cost trade-offs."),
)

_SECURITY_CORE = (
    C("security-fundamentals", "Security Fundamentals", "Security Fundamentals", 1.5, None, (), "CIA triad, threat models, defence in depth."),
    C("vulnerability-assessment", "Vulnerability Assessment", "Vulnerability Management", 2, "scenario",
      ("owasp", "nmap", "xss", "sql injection", "csrf"), "Identifying and prioritizing vulnerabilities, CVSS."),
    C("log-analysis", "Log Analysis & Security Monitoring", "Security Monitoring", 2, "scenario", ("siem", "splunk", "linux"),
      "Reading logs, detecting suspicious activity, SIEM use."),
    C("incident-response", "Incident Response", "Incident Response", 1.5, "scenario", (), "Detection, containment, eradication, recovery, lessons learned."),
    C("access-control", "Authentication & Access Control", "Identity & Access", 1, None, ("oauth", "jwt"), "MFA, least privilege, session security."),
    C("network-security", "Network Security", "Network Security", 1, None, ("wireshark", "nmap", "vlan"), "Firewalls, IDS/IPS, segmentation."),
)

_TESTING_CORE = (
    C("testing-fundamentals", "Testing Fundamentals", "Testing Fundamentals", 2, None, (), "Test levels, types, SDLC/STLC, defect lifecycle."),
    C("test-design", "Test Case Design", "Test Design", 2, "scenario", (),
      "Equivalence partitioning, boundary values, decision tables, exploratory testing."),
    C("bug-reporting", "Defect Analysis & Reporting", "Test Design", 1, "scenario", (), "Reproducible bug reports, severity vs priority, root cause."),
    C("api-testing", "API Testing", "API Testing", 1.5, None, ("postman",), "Status codes, contract checks, negative testing."),
)

_ML_CORE = (
    C("ml-fundamentals", "Machine Learning Fundamentals", "Machine Learning", 2.5, None, ("scikit-learn",),
      "Supervised vs unsupervised learning, bias-variance, overfitting, regularization."),
    C("model-evaluation", "Model Evaluation", "Model Evaluation", 2, "scenario", ("scikit-learn",),
      "Metrics, validation strategies, leakage, imbalanced data."),
    C("feature-engineering", "Feature Engineering", "Data Preparation", 1.5, "coding", ("pandas", "numpy", "python"),
      "Encoding, scaling, missing values, feature selection."),
    C("python-data", "Python for Data", "Python & Data Manipulation", 2, "coding", ("python", "pandas", "numpy"),
      "Data manipulation and analysis in Python."),
)


def _replace(block: tuple[Competency, ...], **weights: float) -> tuple[Competency, ...]:
    """Reuse a block with role-specific weights (keyword args map competency id → weight)."""
    out = []
    for comp in block:
        key = comp.id.replace("-", "_")
        out.append(Competency(comp.id, comp.name, comp.focus, weights.get(key, comp.weight), comp.practical, comp.keywords, comp.description))
    return tuple(out)


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

ROLES: tuple[InterviewRole, ...] = (
    # --- Software & development ------------------------------------------------
    InterviewRole(
        "software-development-engineer", "Software Development Engineer", "Software Development",
        "Builds software with strong computer-science fundamentals; interviews emphasize DSA and core CS.",
        _DSA + (
            C("oop", "Object-Oriented Design", "OOP & Design", 1.5, None, ("java", "c++", "python"), "Classes, SOLID, design patterns."),
            C("dbms", "DBMS Fundamentals", "Core CS", 1, None, ("sql",), "Relational model, normalization, indexing, transactions."),
            C("operating-systems", "Operating Systems", "Core CS", 1, None, ("linux",), "Processes, threads, scheduling, memory, deadlocks."),
            C("computer-networks", "Computer Networks", "Core CS", 1, None, ("tcp/ip", "osi"), "TCP/IP, HTTP, DNS, sockets."),
            C("system-design-basics", "System Design Basics", "System Design", 1, None, ("redis",), "Scalability, caching, load balancing at an introductory level."),
        ),
        ("coding",), ("sde", "sde 1", "sde 2", "sde i", "sde ii", "sde-1", "sde-2"),
        CODING_LANGUAGES,
    ),
    InterviewRole(
        "software-engineer", "Software Engineer", "Software Development",
        "General software engineering across design, implementation, testing and maintenance.",
        _DSA + (
            C("oop", "Object-Oriented Design", "OOP & Design", 1.5, None, ("java", "c++", "python"), "Classes, SOLID, design patterns."),
            C("testing", "Testing & Code Quality", "Engineering Practices", 1, None, ("junit", "pytest"), "Unit tests, refactoring, code review."),
            C("system-design-basics", "System Design Basics", "System Design", 1.5, None, ("redis",), "Components, scalability, trade-offs."),
            C("version-control", "Version Control & Collaboration", "Engineering Practices", 0.5, None, (), "Git workflows, branching, code review."),
        ),
        ("coding",), ("software developer", "programmer", "application developer", "swe"),
        CODING_LANGUAGES,
    ),
    InterviewRole(
        "frontend-developer", "Frontend Developer", "Frontend",
        "Builds user interfaces for the web: JavaScript, frameworks, browser behaviour, accessibility and performance.",
        (
            C("javascript", "JavaScript & TypeScript", "JavaScript & TypeScript", 3, "coding", ("javascript", "typescript", "dom"),
              "Closures, prototypes, async/await, event loop, ES modules, typing."),
            C("react", "React & Component Design", "React & State Management", 2, "scenario", ("react", "jsx", "next.js", "redux"),
              "Components, props/state, hooks, rendering, composition."),
            C("html-css", "HTML, CSS & Responsive Design", "HTML, CSS & Responsive Design", 1.5, "scenario",
              ("html", "css", "sass", "tailwind"), "Semantic HTML, layout (flexbox/grid), responsive design, accessibility."),
            C("browser-fundamentals", "Browser Fundamentals & DOM", "Browser & Performance", 1.5, None, ("dom", "html", "javascript"),
              "Rendering pipeline, DOM events, storage, security basics (CORS, XSS)."),
            C("state-management", "State Management", "React & State Management", 1, None, ("react", "redux"), "Local vs global state, data flow, caching server state."),
            C("api-integration", "API Integration", "API Integration", 1, None, ("javascript", "graphql"), "fetch, error/loading states, REST and GraphQL clients."),
            C("frontend-performance", "Frontend Performance", "Browser & Performance", 1, None, ("webpack", "vite", "react"),
              "Bundle size, lazy loading, memoization, Core Web Vitals."),
        ),
        ("coding", "scenario"), ("front end developer", "front-end developer", "frontend engineer", "front end engineer",
                                  "front-end engineer", "ui developer", "web developer", "frontend web developer"),
        ("JAVASCRIPT",), "frontend-developer",
    ),
    InterviewRole(
        "backend-developer", "Backend Developer", "Backend",
        "Builds server-side services: APIs, data storage, authentication, reliability and scale.",
        (
            C("programming", "Programming Fundamentals", "Programming", 2, "coding", ("python", "java", "node.js", "golang", "c#"),
              "Language fundamentals, data handling, error handling."),
            C("rest-apis", "REST API Design", "APIs", 2, "coding", ("fastapi", "django", "flask", "spring", "spring boot", "express", "node.js", "graphql", "grpc"),
              "Resources, status codes, idempotency, pagination, versioning."),
            C("database-integration", "Databases & Data Modelling", "Databases", 2, None, ("sql", "postgresql", "mysql", "mongodb", "redis"),
              "Schema design, ORM trade-offs, transactions, indexing."),
            C("auth", "Authentication & Authorization", "Security", 1.5, None, ("jwt", "oauth"), "Sessions vs tokens, OAuth, RBAC."),
            C("caching", "Caching", "Performance & Scalability", 1, None, ("redis",), "Cache strategies, invalidation, TTLs."),
            C("backend-architecture", "Backend Architecture & Scalability", "Performance & Scalability", 1.5, None, ("kafka", "docker"),
              "Layering, queues, horizontal scaling, failure handling."),
            C("error-handling", "Error Handling & Observability", "Reliability", 1, None, (), "Error contracts, retries, logging, monitoring."),
        ),
        ("coding",), ("back end developer", "back-end developer", "backend engineer", "back end engineer", "server side developer",
                      "api developer"),
        CODING_LANGUAGES, "backend-engineer",
    ),
    InterviewRole(
        "full-stack-developer", "Full Stack Developer", "Full Stack",
        "Works across frontend and backend to deliver complete features.",
        (
            C("javascript", "JavaScript & TypeScript", "Frontend", 2, "coding", ("javascript", "typescript", "node.js", "dom"), "Language fundamentals and async programming."),
            C("frontend-frameworks", "Frontend Frameworks", "Frontend", 1.5, "scenario", ("react", "angular", "vue", "next.js", "html", "css", "jsx", "redux"),
              "Component design, state, rendering."),
            C("rest-apis", "API Design & Implementation", "Backend", 2, "coding", ("node.js", "express", "fastapi", "django", "spring", "graphql"),
              "Designing and implementing APIs."),
            C("databases", "Databases", "Backend", 1.5, None, ("sql", "postgresql", "mysql", "mongodb", "redis"), "Modelling, queries, transactions."),
            C("auth", "Authentication & Security", "Security", 1, None, ("jwt", "oauth", "xss", "csrf"), "Auth flows, common web vulnerabilities."),
            C("deployment", "Deployment & DevOps Basics", "Delivery", 0.5, None, ("docker", "ci/cd"), "Builds, environments, CI/CD."),
        ),
        ("coding", "scenario"), ("fullstack developer", "full-stack developer", "full stack engineer", "fullstack engineer", "mern developer",
                                  "mean developer"),
        CODING_LANGUAGES, "full-stack-developer",
    ),
    InterviewRole(
        "react-developer", "React Developer", "Frontend",
        "Specialist in building React applications.",
        (
            C("react", "React Fundamentals & Hooks", "React", 3, "scenario", ("react", "jsx", "next.js"), "Components, hooks, effects, rendering."),
            C("javascript", "JavaScript & TypeScript", "JavaScript & TypeScript", 2, "coding", ("javascript", "typescript", "dom"), "Language core and async."),
            C("state-management", "State Management", "State Management", 1.5, None, ("react", "redux"), "Context, Redux, server-state libraries."),
            C("react-performance", "Rendering Performance", "Performance", 1.5, None, ("react",), "Memoization, reconciliation, profiling."),
            C("react-testing", "Testing React Apps", "Testing", 1, None, ("react", "cypress", "playwright"), "Component and end-to-end tests."),
            C("html-css", "HTML & CSS", "HTML & CSS", 1, "scenario", ("html", "css", "tailwind", "sass"), "Layout, responsiveness, accessibility."),
        ),
        ("scenario", "coding"), ("react.js developer", "reactjs developer", "react js developer", "react engineer", "react frontend developer"),
        ("JAVASCRIPT",), "frontend-developer",
    ),
    InterviewRole(
        "java-developer", "Java Developer", "Backend",
        "Builds applications and services on the Java platform.",
        (
            C("core-java", "Core Java", "Core Java", 3, "coding", ("java",), "OOP, collections, generics, exceptions, streams."),
            C("java-concurrency", "Concurrency & JVM", "JVM & Concurrency", 1.5, None, ("java",), "Threads, executors, memory model, GC basics."),
            C("spring", "Spring & Spring Boot", "Frameworks", 2, None, ("spring", "spring boot", "hibernate", "java"), "DI, REST controllers, configuration."),
            C("java-data", "Data Access (JPA/JDBC)", "Data Access", 1.5, None, ("hibernate", "sql", "java"), "ORM mapping, transactions, N+1."),
            C("dsa-java", "Problem Solving in Java", "Problem Solving", 2, "coding", ("java",), "Algorithms implemented in Java."),
            C("java-testing", "Testing (JUnit)", "Testing", 1, None, ("junit", "java"), "Unit and integration tests."),
        ),
        ("coding",), ("java engineer", "java backend developer", "j2ee developer", "spring boot developer", "java software engineer"),
        ("JAVA",),
    ),
    InterviewRole(
        "python-developer", "Python Developer", "Backend",
        "Builds applications, services and automation in Python.",
        (
            C("core-python", "Core Python", "Core Python", 3, "coding", ("python",), "Data model, iterators, generators, comprehensions, exceptions."),
            C("python-advanced", "Advanced Python", "Advanced Python", 1.5, None, ("python",), "Decorators, context managers, typing, asyncio."),
            C("python-web", "Web Frameworks", "Frameworks", 1.5, None, ("django", "flask", "fastapi", "python"), "Building APIs and web apps."),
            C("python-data-access", "Data Access", "Data Access", 1, None, ("sql", "postgresql", "python"), "ORMs, SQL, transactions."),
            C("problem-solving-python", "Problem Solving in Python", "Problem Solving", 2, "coding", ("python",), "Algorithms implemented in Python."),
            C("python-testing", "Testing & Packaging", "Testing", 1, None, ("pytest", "python"), "pytest, fixtures, packaging."),
        ),
        ("coding",), ("python engineer", "python backend developer", "django developer", "python software engineer"),
        ("PYTHON",),
    ),
    InterviewRole(
        "mobile-app-developer", "Mobile Application Developer", "Mobile",
        "Builds mobile applications for Android and/or iOS.",
        (
            C("mobile-fundamentals", "Mobile App Fundamentals", "Mobile Fundamentals", 2, None, ("android", "ios", "flutter", "react native"),
              "App lifecycle, navigation, permissions, offline behaviour."),
            C("mobile-ui", "Mobile UI Development", "UI", 2, "scenario", ("android", "ios", "flutter", "react native", "jetpack compose", "swiftui"),
              "Layouts, lists, state, accessibility."),
            C("mobile-programming", "Programming for Mobile", "Programming", 2, "coding", ("kotlin", "swift", "java", "javascript"), "Language fundamentals."),
            C("mobile-networking", "Networking & Data Persistence", "Data", 1.5, None, ("android", "ios"), "REST clients, caching, local storage."),
            C("mobile-performance", "Performance & Debugging", "Quality", 1, None, ("android", "ios", "xcode"), "Profiling, memory, crashes."),
        ),
        ("coding", "scenario"), ("mobile developer", "mobile app developer", "mobile engineer", "app developer", "flutter developer",
                                  "react native developer"),
        ("JAVA", "JAVASCRIPT"),
    ),
    InterviewRole(
        "android-developer", "Android Developer", "Mobile",
        "Builds native Android applications.",
        (
            C("kotlin-java", "Kotlin & Java", "Language", 2.5, "coding", ("kotlin", "java", "android"), "Language fundamentals, coroutines."),
            C("android-components", "Android Components & Lifecycle", "Android Platform", 2, None, ("android",), "Activities, fragments, services, lifecycle."),
            C("android-ui", "Android UI", "UI", 2, "scenario", ("android", "jetpack compose"), "Views, Compose, RecyclerView, state."),
            C("android-architecture", "App Architecture", "Architecture", 1.5, None, ("android", "kotlin"), "MVVM, repositories, dependency injection."),
            C("android-data", "Networking & Persistence", "Data", 1, None, ("android", "sql"), "Retrofit, Room, caching."),
        ),
        ("coding", "scenario"), ("android engineer", "android app developer", "kotlin developer"),
        ("JAVA",),
    ),
    InterviewRole(
        "ios-developer", "iOS Developer", "Mobile",
        "Builds native iOS applications.",
        (
            # Swift is not an executable language in the assessment engine, so Swift tasks are AI-reviewed scenarios.
            C("swift", "Swift", "Language", 2.5, "scenario", ("swift", "ios"), "Optionals, protocols, value vs reference types, concurrency."),
            C("ios-ui", "UIKit & SwiftUI", "UI", 2, "scenario", ("ios", "swiftui", "xcode"), "Views, layout, state, navigation."),
            C("ios-lifecycle", "App Lifecycle & Platform", "iOS Platform", 1.5, None, ("ios",), "App states, background work, permissions."),
            C("ios-architecture", "App Architecture", "Architecture", 1.5, None, ("ios", "swift"), "MVC/MVVM, dependency management."),
            C("ios-data", "Networking & Persistence", "Data", 1, None, ("ios",), "URLSession, Codable, Core Data."),
        ),
        ("scenario",), ("ios engineer", "iphone developer", "swift developer", "ios app developer"),
    ),

    # --- Database ----------------------------------------------------------------
    InterviewRole(
        "database-developer", "Database Developer", "Database",
        "Designs and implements database schemas, queries and stored logic.",
        _SQL_CORE + (
            C("stored-procedures", "Stored Procedures & Functions", "Database Programming", 1, None,
              ("stored procedure", "stored procedures", "plsql", "pl/sql", "t-sql", "sql"), "Procedural SQL, triggers, functions."),
        ),
        ("sql",), ("db developer", "database engineer", "database programmer", "pl/sql developer", "plsql developer"),
        (), None,
    ),
    InterviewRole(
        "database-administrator", "Database Administrator", "Database",
        "Operates databases: availability, performance, backups, security.",
        (
            C("dba-backup", "Backup & Recovery", "Backup & Recovery", 2, "scenario", ("postgresql", "mysql", "oracle", "sql server"),
              "Backup strategies, point-in-time recovery, RPO/RTO."),
            C("dba-performance", "Performance Tuning", "Performance & Optimization", 2, "sql", ("sql", "postgresql", "mysql", "oracle", "sql server"),
              "Execution plans, indexes, configuration, vacuum/statistics."),
            C("dba-ha", "High Availability & Replication", "Availability", 1.5, None, ("postgresql", "mysql", "oracle", "sql server"),
              "Replication, failover, clustering."),
            C("dba-security", "Database Security & Access", "Security", 1.5, None, ("sql",), "Roles, privileges, auditing, encryption."),
            C("sql-queries", "SQL Queries", "SQL", 1.5, "sql", ("sql",), "Querying system and user data."),
            C("transactions", "Transactions & Concurrency", "Transactions & Concurrency", 1.5, None, ("sql",), "Isolation, locking, deadlocks."),
            C("dba-monitoring", "Monitoring & Troubleshooting", "Operations", 1, "scenario", ("linux", "sql"), "Diagnosing slowdowns and outages."),
        ),
        ("sql", "scenario"), ("dba", "db administrator", "database admin", "postgres dba", "oracle dba", "sql server dba", "mysql dba"),
    ),
    InterviewRole(
        "sql-developer", "SQL Developer", "Database",
        "Writes and optimizes SQL for applications and reporting.",
        _replace(_SQL_CORE, sql_queries=3.5, joins_subqueries=2.5, database_design=1),
        ("sql",), ("sql programmer", "sql engineer", "t-sql developer", "sql server developer"),
    ),
    InterviewRole(
        "postgresql-developer", "PostgreSQL Developer", "Database",
        "Develops on PostgreSQL: SQL, schema design, PL/pgSQL and performance.",
        _SQL_CORE + (
            C("postgres-features", "PostgreSQL Features", "PostgreSQL", 1.5, None, ("postgresql",), "JSONB, CTEs, window functions, extensions, MVCC, VACUUM."),
        ),
        ("sql",), ("postgres developer", "postgresql engineer", "postgres engineer", "pl/pgsql developer"),
    ),
    InterviewRole(
        "mysql-developer", "MySQL Developer", "Database",
        "Develops on MySQL: SQL, schema design and performance.",
        _SQL_CORE + (
            C("mysql-features", "MySQL Engines & Features", "MySQL", 1.5, None, ("mysql",), "InnoDB, replication basics, MySQL-specific SQL."),
        ),
        ("sql",), ("mysql engineer", "mysql database developer"),
    ),
    InterviewRole(
        "data-engineer", "Data Engineer", "Data",
        "Builds data pipelines, warehouses and data platforms.",
        (
            C("sql-queries", "SQL & Data Modelling", "SQL & Modelling", 2.5, "sql", ("sql", "postgresql", "mysql"), "Analytical SQL, star schemas, slowly changing dimensions."),
            C("etl-pipelines", "ETL/ELT Pipelines", "Pipelines", 2, "coding", ("python", "airflow", "spark"), "Ingestion, transformation, orchestration, idempotency."),
            C("data-processing", "Distributed Processing", "Big Data", 1.5, None, ("spark", "hadoop", "kafka"), "Batch vs streaming, partitioning, shuffles."),
            C("data-warehousing", "Data Warehousing", "Warehousing", 1.5, None, ("sql",), "Warehouse vs lake, columnar storage, modelling."),
            C("data-quality", "Data Quality & Reliability", "Reliability", 1, "scenario", ("airflow",), "Validation, monitoring, backfills."),
            C("python-data", "Python for Data", "Programming", 1.5, "coding", ("python", "pandas"), "Data transformation in Python."),
        ),
        ("sql", "coding"), ("big data engineer", "etl developer", "data pipeline engineer", "analytics engineer"),
        ("PYTHON",), None,
    ),

    # --- Networking & infrastructure ---------------------------------------------
    InterviewRole(
        "network-engineer", "Network Engineer", "Networking",
        "Designs, operates and troubleshoots enterprise networks.",
        _NETWORK_CORE + (
            C("network-automation", "Network Automation", "Automation", 0.5, None, ("python", "ansible"), "Scripting configuration and checks."),
        ),
        ("calculation", "scenario"), ("networking engineer", "ccna engineer", "network support engineer", "lan/wan engineer"),
    ),
    InterviewRole(
        "network-administrator", "Network Administrator", "Networking",
        "Maintains day-to-day network operations, devices and users.",
        _replace(_NETWORK_CORE, network_troubleshooting=2.5, routing_switching=1.5),
        ("calculation", "scenario"), ("network admin", "networking administrator"),
    ),
    InterviewRole(
        "system-administrator", "System Administrator", "Infrastructure",
        "Operates servers, users, storage and services.",
        (
            C("os-administration", "Server Administration (Linux/Windows)", "Server Administration", 2.5, "scenario", ("linux", "bash"),
              "Users, permissions, services, package management, Active Directory basics."),
            C("sysadmin-networking", "Networking for Sysadmins", "Networking", 1.5, None, ("dhcp", "subnet", "linux"), "DNS, DHCP, IP configuration, firewalls."),
            C("sysadmin-scripting", "Scripting & Automation", "Automation", 1.5, "coding", ("bash", "python", "ansible"), "Automating admin tasks."),
            C("backup-storage", "Backup & Storage", "Storage", 1, None, (), "RAID, backups, restores."),
            C("sysadmin-troubleshooting", "Troubleshooting & Monitoring", "Troubleshooting", 2, "scenario", ("linux",), "Diagnosing outages and performance issues."),
            C("sysadmin-security", "System Security & Patching", "Security", 1, None, ("linux",), "Hardening, patching, access control."),
        ),
        ("scenario", "coding"), ("sysadmin", "systems administrator", "it administrator", "windows administrator"),
        ("PYTHON",),
    ),
    InterviewRole(
        "linux-administrator", "Linux Administrator", "Infrastructure",
        "Administers Linux servers.",
        (
            C("linux-core", "Linux Fundamentals", "Linux Fundamentals", 2.5, None, ("linux", "bash"), "Filesystem, processes, permissions, systemd."),
            C("linux-scripting", "Shell Scripting", "Scripting", 2, "coding", ("bash", "linux", "python"), "Bash scripting, text processing."),
            C("linux-networking", "Linux Networking", "Networking", 1.5, None, ("linux", "subnet", "dhcp"), "ip, ss, iptables/nftables, DNS."),
            C("linux-troubleshooting", "Troubleshooting & Performance", "Troubleshooting", 2, "scenario", ("linux",), "CPU, memory, disk, logs."),
            C("linux-security", "Security & Hardening", "Security", 1, None, ("linux",), "SSH, SELinux/AppArmor, patching."),
        ),
        ("scenario", "coding"), ("linux admin", "linux system administrator", "linux engineer", "unix administrator"),
        ("PYTHON",),
    ),
    InterviewRole(
        "cloud-engineer", "Cloud Engineer", "Cloud",
        "Builds and operates cloud infrastructure.",
        _CLOUD_CORE + (
            C("iac", "Infrastructure as Code", "Infrastructure as Code", 1.5, "scenario", ("terraform", "ansible"), "Terraform concepts, state, modules."),
            C("containers", "Containers", "Containers", 1, None, ("docker", "kubernetes"), "Containers on cloud platforms."),
        ),
        ("scenario",), ("cloud infrastructure engineer", "cloud operations engineer"), (), "cloud-engineer",
    ),
    InterviewRole(
        "aws-cloud-engineer", "AWS Cloud Engineer", "Cloud",
        "Builds and operates infrastructure on AWS.",
        _replace(_CLOUD_CORE, cloud_compute=2.5) + (
            C("iac", "Infrastructure as Code", "Infrastructure as Code", 1.5, "scenario", ("terraform", "aws"), "CloudFormation/Terraform."),
        ),
        ("scenario",), ("aws engineer", "aws cloud architect", "aws devops engineer", "aws solutions engineer"), (), "cloud-engineer",
    ),
    InterviewRole(
        "azure-cloud-engineer", "Azure Cloud Engineer", "Cloud",
        "Builds and operates infrastructure on Microsoft Azure.",
        _replace(_CLOUD_CORE, cloud_compute=2.5) + (
            C("iac", "Infrastructure as Code", "Infrastructure as Code", 1.5, "scenario", ("terraform", "azure"), "ARM/Bicep/Terraform."),
        ),
        ("scenario",), ("azure engineer", "azure cloud architect", "azure devops engineer", "azure administrator"), (), "cloud-engineer",
    ),
    InterviewRole(
        "devops-engineer", "DevOps Engineer", "DevOps",
        "Automates delivery and operates infrastructure.",
        _DEVOPS_CORE + (
            C("devops-git", "Git & Version Control", "CI/CD", 0.5, None, (), "Branching strategies, merges, tags."),
            C("devops-cloud", "Cloud Services", "Cloud", 1, None, ("aws", "azure", "gcp"), "Cloud building blocks for delivery."),
        ),
        ("coding", "scenario"), ("devops", "devops specialist", "build and release engineer", "platform engineer", "release engineer"),
        ("PYTHON",), "devops-engineer",
    ),
    InterviewRole(
        "site-reliability-engineer", "Site Reliability Engineer", "DevOps",
        "Keeps production services reliable through engineering.",
        _replace(_DEVOPS_CORE, monitoring=2.5, iac=1, ci_cd=1) + (
            C("slo", "SLIs, SLOs & Error Budgets", "Reliability", 2, "scenario", ("prometheus", "grafana"), "Defining and using reliability targets."),
            C("incident-management", "Incident Management", "Reliability", 1.5, "scenario", (), "On-call, incident command, postmortems."),
        ),
        ("scenario", "coding"), ("sre", "reliability engineer", "production engineer"),
        ("PYTHON",), "devops-engineer",
    ),

    # --- Security ------------------------------------------------------------------
    InterviewRole(
        "cybersecurity-analyst", "Cybersecurity Analyst", "Security",
        "Monitors, detects and responds to security threats.",
        _SECURITY_CORE + (
            C("threat-analysis", "Threat Analysis", "Threat Intelligence", 1.5, "scenario", (), "MITRE ATT&CK, indicators of compromise, threat hunting."),
        ),
        ("scenario",), ("security analyst", "soc analyst", "cyber security analyst", "information security analyst", "infosec analyst"),
    ),
    InterviewRole(
        "security-engineer", "Security Engineer", "Security",
        "Designs and builds security controls into systems.",
        _replace(_SECURITY_CORE, access_control=2, network_security=1.5) + (
            C("secure-architecture", "Secure Architecture", "Architecture", 1.5, None, ("aws", "azure", "kubernetes"), "Threat modelling, zero trust, secrets."),
            C("secure-coding", "Secure Coding", "Application Security", 1, "coding", ("owasp", "python", "java", "javascript"), "Input validation, safe APIs."),
        ),
        ("scenario", "coding"), ("information security engineer", "cyber security engineer", "infosec engineer"),
        ("PYTHON", "JAVA", "JAVASCRIPT"),
    ),
    InterviewRole(
        "application-security-engineer", "Application Security Engineer", "Security",
        "Secures applications through design review, testing and secure coding.",
        (
            C("owasp", "OWASP Top 10", "Web Vulnerabilities", 2.5, "scenario", ("owasp", "xss", "sql injection", "csrf"), "Common web vulnerabilities and fixes."),
            C("secure-coding", "Secure Coding", "Secure Coding", 2, "coding", ("owasp", "python", "java", "javascript"), "Writing and fixing code securely."),
            C("appsec-auth", "Authentication & Session Security", "Identity", 1.5, None, ("oauth", "jwt"), "OAuth/OIDC, session handling."),
            C("threat-modeling", "Threat Modelling", "Design Review", 1.5, "scenario", (), "STRIDE, attack surfaces."),
            C("appsec-testing", "Security Testing (SAST/DAST)", "Security Testing", 1, None, ("burp suite",), "Tooling, triage, false positives."),
        ),
        ("scenario", "coding"), ("appsec engineer", "product security engineer", "application security analyst"),
        ("PYTHON", "JAVA", "JAVASCRIPT"),
    ),
    InterviewRole(
        "network-security-engineer", "Network Security Engineer", "Security",
        "Protects networks with firewalls, segmentation, VPNs and monitoring.",
        (
            C("firewalls", "Firewalls & ACLs", "Perimeter Security", 2.5, "scenario", ("cisco", "nat"), "Rule design, stateful inspection, NAT."),
            C("ip-subnetting", "IP Addressing & Segmentation", "Segmentation", 1.5, "calculation", ("subnet", "subnets", "subnetting", "cidr", "vlan", "vlans"),
              "Subnetting and segmentation."),
            C("vpn", "VPNs & Secure Connectivity", "Connectivity", 1.5, None, (), "IPsec, TLS VPNs, remote access."),
            C("ids-ips", "IDS/IPS & Monitoring", "Monitoring", 1.5, "scenario", ("siem", "wireshark", "splunk"), "Detection and traffic analysis."),
            C("network-models", "Networking Fundamentals", "Networking Fundamentals", 1, None, ("osi", "tcp/ip"), "Protocols relevant to security."),
        ),
        ("scenario", "calculation"), ("firewall engineer", "network security analyst"),
    ),
    InterviewRole(
        "penetration-tester", "Penetration Tester", "Security",
        "Finds and demonstrates vulnerabilities through authorized testing.",
        (
            C("recon", "Reconnaissance & Enumeration", "Methodology", 1.5, "scenario", ("nmap",), "Scoping, discovery, enumeration."),
            C("web-exploitation", "Web Application Testing", "Web Testing", 2.5, "scenario", ("owasp", "burp suite", "xss", "sql injection", "csrf"),
              "Finding and validating web vulnerabilities."),
            C("network-pentest", "Network & Infrastructure Testing", "Infrastructure Testing", 1.5, None, ("nmap", "metasploit", "linux"), "Services, misconfigurations."),
            C("privilege-escalation", "Privilege Escalation", "Post-Exploitation", 1, None, ("linux",), "Common escalation paths."),
            C("reporting", "Reporting & Remediation", "Reporting", 1, "scenario", (), "Risk rating and actionable remediation."),
        ),
        ("scenario",), ("pentester", "pen tester", "ethical hacker", "offensive security engineer", "red team engineer"),
    ),

    # --- Data & AI -----------------------------------------------------------------
    InterviewRole(
        "data-analyst", "Data Analyst", "Data",
        "Turns data into insight using SQL, spreadsheets, statistics and visualization.",
        (
            C("sql-queries", "SQL for Analysis", "SQL", 3, "sql", ("sql", "postgresql", "mysql"), "Aggregations, joins, window functions."),
            C("statistics", "Statistics", "Statistics", 2, None, (), "Descriptive statistics, distributions, hypothesis tests."),
            C("data-cleaning", "Data Cleaning & Preparation", "Data Preparation", 1.5, "scenario", ("pandas", "python"), "Missing values, outliers, joins."),
            C("visualization", "Data Visualization & Storytelling", "Visualization", 1.5, "scenario", ("tableau", "power bi"), "Choosing charts, dashboards, communicating findings."),
            C("business-metrics", "Business Metrics & KPIs", "Business Analysis", 1, None, (), "Defining and interpreting metrics, A/B tests."),
        ),
        ("sql", "scenario"), ("business intelligence analyst", "bi analyst", "reporting analyst", "data analytics specialist"),
        ("PYTHON",), "data-analyst",
    ),
    InterviewRole(
        "data-scientist", "Data Scientist", "Data",
        "Builds statistical and machine-learning models to answer business questions.",
        _ML_CORE + (
            C("statistics", "Statistics & Probability", "Statistics & Probability", 2.5, "scenario", (), "Probability, inference, experimental design."),
            C("sql-for-ds", "SQL for Data Science", "SQL", 1, None, ("sql",), "Extracting and shaping data with SQL."),
        ),
        ("coding", "scenario"), ("ds", "applied scientist", "data science engineer"),
        ("PYTHON",), "data-scientist",
    ),
    InterviewRole(
        "machine-learning-engineer", "Machine Learning Engineer", "AI & ML",
        "Builds, deploys and maintains machine-learning systems.",
        _replace(_ML_CORE, ml_fundamentals=2, python_data=2.5) + (
            C("deep-learning", "Deep Learning", "Deep Learning", 1.5, None, ("tensorflow", "pytorch"), "Neural networks, training dynamics."),
            C("mlops", "MLOps & Deployment", "MLOps", 1.5, "scenario", ("docker", "kubernetes", "airflow"), "Serving, monitoring, drift, retraining."),
        ),
        ("coding", "scenario"), ("ml engineer", "mle", "machine learning developer"),
        ("PYTHON",), "machine-learning-engineer",
    ),
    InterviewRole(
        "ai-engineer", "AI Engineer", "AI & ML",
        "Builds applications on top of ML models and LLMs.",
        (
            C("llm-apps", "LLM Application Development", "LLM Applications", 2.5, "scenario", ("llm", "llms", "transformers", "python"),
              "Prompting, retrieval-augmented generation, tool use, evaluation."),
            C("ml-fundamentals", "Machine Learning Fundamentals", "Machine Learning", 1.5, None, ("scikit-learn", "pytorch", "tensorflow"), "Core ML concepts."),
            C("python-ai", "Python Programming", "Programming", 2, "coding", ("python",), "Data handling and services in Python."),
            C("ai-deployment", "Model Serving & MLOps", "Deployment", 1.5, None, ("docker", "kubernetes", "fastapi"), "Serving, latency, cost, monitoring."),
            C("ai-evaluation", "Evaluation & Safety", "Evaluation", 1, "scenario", ("llm", "llms"), "Measuring quality, guardrails."),
        ),
        ("scenario", "coding"), ("artificial intelligence engineer", "genai engineer", "generative ai engineer", "llm engineer"),
        ("PYTHON",), "machine-learning-engineer",
    ),
    InterviewRole(
        "nlp-engineer", "NLP Engineer", "AI & ML",
        "Builds natural-language processing systems.",
        (
            C("nlp-fundamentals", "NLP Fundamentals", "NLP Fundamentals", 2.5, None, ("transformers", "bert"), "Tokenization, embeddings, sequence models."),
            C("transformers", "Transformers & LLMs", "Transformers", 2, "scenario", ("transformers", "bert", "llm", "llms", "pytorch"), "Architectures, fine-tuning."),
            C("python-nlp", "Python for NLP", "Programming", 2, "coding", ("python",), "Text processing in Python."),
            C("nlp-evaluation", "Evaluation & Metrics", "Evaluation", 1, None, (), "BLEU, ROUGE, F1, human evaluation."),
            C("model-evaluation", "Model Evaluation", "Evaluation", 1, None, ("scikit-learn",), "Validation, error analysis."),
        ),
        ("coding", "scenario"), ("natural language processing engineer", "nlp scientist", "computational linguist"),
        ("PYTHON",), "machine-learning-engineer",
    ),

    # --- Testing & quality ---------------------------------------------------------
    InterviewRole(
        "software-tester", "Software Tester", "Quality",
        "Verifies software quality through manual and exploratory testing.",
        _replace(_TESTING_CORE, test_design=3, bug_reporting=1.5),
        ("scenario",), ("manual tester", "qa tester", "test engineer", "software test engineer"),
    ),
    InterviewRole(
        "qa-engineer", "QA Engineer", "Quality",
        "Owns product quality through test strategy, automation and process.",
        _TESTING_CORE + (
            C("test-automation", "Test Automation", "Automation", 1.5, "coding", ("selenium", "cypress", "playwright", "pytest", "python", "javascript", "java"),
              "Automating checks, frameworks, flaky tests."),
            C("test-strategy", "Test Strategy & Planning", "Strategy", 1, None, (), "Risk-based testing, entry/exit criteria."),
        ),
        ("scenario", "coding"), ("quality assurance engineer", "qa analyst", "sdet", "quality engineer"),
        ("PYTHON", "JAVA", "JAVASCRIPT"),
    ),
    InterviewRole(
        "automation-test-engineer", "Automation Test Engineer", "Quality",
        "Builds automated test suites and frameworks.",
        (
            C("automation-frameworks", "Automation Frameworks", "Frameworks", 2.5, "scenario", ("selenium", "cypress", "playwright", "junit", "pytest"),
              "Page objects, fixtures, reporting."),
            C("automation-programming", "Programming for Automation", "Programming", 2, "coding", ("python", "java", "javascript"), "Writing maintainable test code."),
            C("api-testing", "API Test Automation", "API Testing", 1.5, None, ("postman",), "Automated API checks."),
            C("ci-testing", "Tests in CI/CD", "CI/CD", 1, None, ("ci/cd", "jenkins", "github actions"), "Running and gating on tests."),
            C("test-design", "Test Design", "Test Design", 1, None, (), "Choosing what to automate."),
        ),
        ("coding", "scenario"), ("test automation engineer", "automation tester", "automation engineer qa"),
        ("PYTHON", "JAVA", "JAVASCRIPT"),
    ),
    InterviewRole(
        "performance-test-engineer", "Performance Test Engineer", "Quality",
        "Measures and improves system performance under load.",
        (
            C("perf-fundamentals", "Performance Testing Fundamentals", "Fundamentals", 2, None, (), "Load, stress, soak, spike testing; workload models."),
            C("perf-tools", "Load Testing Tools", "Tools", 1.5, "scenario", ("jmeter", "gatling"), "Scripting and running load tests."),
            C("perf-analysis", "Results Analysis & Bottlenecks", "Analysis", 2.5, "scenario", ("prometheus", "grafana"), "Percentiles, throughput, finding bottlenecks."),
            C("perf-monitoring", "Monitoring & Profiling", "Monitoring", 1, None, ("prometheus", "grafana", "linux"), "System metrics and profiling."),
        ),
        ("scenario",), ("performance tester", "load test engineer", "performance engineer"),
    ),
)

ROLE_BY_SLUG: dict[str, InterviewRole] = {role.slug: role for role in ROLES}
