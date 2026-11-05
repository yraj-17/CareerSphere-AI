"""
Normalisation vocabulary for real job listings and user profiles.

* ``TECH_SKILLS`` — canonical skill id → (display name, text patterns). Patterns
  are matched case-insensitively on word boundaries against a listing's title +
  description, so only skills a listing actually mentions are recorded.
  Ambiguous short aliases (e.g. "Go", "R", "Next") use stricter patterns.
* ``ROLE_FAMILIES`` — canonical role → title patterns. Equivalent titles
  ("Software Engineer - Backend", "SDE II (Python)", "Server-side Developer")
  collapse to one family so matching does not depend on exact wording.
* Seniority helpers parse level words and "N+ years" phrases.

Everything here is deterministic and explainable; nothing is guessed when a
listing does not state it.
"""

from __future__ import annotations

import re
from typing import Optional

from app.data.career_knowledge import ROLES, SKILLS

# Bump when extraction/classification rules change; stored listings are then
# re-derived on the next sync (it is part of each listing's content hash).
TAXONOMY_VERSION = "3"

# ─────────────────────────────────────────────────────────────────────────────
# Skills
# ─────────────────────────────────────────────────────────────────────────────

# id: (display name, [regex patterns]) — ids reuse career_knowledge ids where they exist.
TECH_SKILLS: dict[str, tuple[str, list[str]]] = {
    "python": ("Python", [r"python"]),
    "java": ("Java", [r"java(?!\s*script)"]),
    "javascript": ("JavaScript", [r"javascript", r"ecmascript", r"es6"]),
    "typescript": ("TypeScript", [r"typescript"]),
    "go": ("Go", [r"golang", r"go\s+(?:language|lang|developer|engineer|programming)", r"\(go\)"]),
    "rust": ("Rust", [r"rust"]),
    "c_cpp": ("C/C++", [r"c\+\+", r"cpp", r"c/c\+\+"]),
    "csharp": ("C#", [r"c#", r"\.net", r"dotnet", r"asp\.net"]),
    "kotlin": ("Kotlin", [r"kotlin"]),
    "swift": ("Swift", [r"swift(?:ui)?"]),
    "scala": ("Scala", [r"scala"]),
    "ruby": ("Ruby", [r"ruby", r"ruby\s+on\s+rails"]),
    "php": ("PHP", [r"php", r"laravel"]),
    "r_lang": ("R", [r"\br\s+(?:programming|language)", r"\(r\)", r"python\s*(?:/|or|and|,)\s*r\b", r"\br\s*(?:/|or|and|,)\s*python"]),
    "sql": ("SQL", [r"sql(?!ite)"]),
    "postgresql": ("PostgreSQL", [r"postgres(?:ql)?"]),
    "mysql": ("MySQL", [r"mysql"]),
    "mongodb": ("MongoDB", [r"mongo(?:db)?"]),
    "redis": ("Redis", [r"redis"]),
    "elasticsearch": ("Elasticsearch", [r"elastic\s*search", r"opensearch"]),
    "cassandra": ("Cassandra", [r"cassandra"]),
    "dynamodb": ("DynamoDB", [r"dynamo\s*db"]),
    "kafka": ("Kafka", [r"kafka"]),
    "rabbitmq": ("RabbitMQ", [r"rabbitmq"]),
    "spark": ("Spark", [r"spark", r"pyspark"]),
    "hadoop": ("Hadoop", [r"hadoop"]),
    "airflow": ("Airflow", [r"airflow"]),
    "dbt": ("dbt", [r"dbt"]),
    "snowflake": ("Snowflake", [r"snowflake"]),
    "databricks": ("Databricks", [r"databricks"]),
    "fastapi": ("FastAPI", [r"fastapi"]),
    "django": ("Django", [r"django"]),
    "flask": ("Flask", [r"flask"]),
    "spring": ("Spring Boot", [r"spring\s*boot", r"spring\s+framework"]),
    "nodejs": ("Node.js", [r"node\.?js", r"node\s+js", r"nodejs"]),
    "express": ("Express", [r"express\.?js"]),
    # Plain "react" is also an English verb, so it only counts next to list
    # punctuation or a framework word ("React, Node", "React/Redux", "React hooks").
    "react": ("React", [r"react\.?js",
                        r"react(?!\s*native)(?=\s*(?:[,/)]|and\b|or\b|hooks|redux|developer|engineer|framework|ecosystem|query|router))",
                        r"(?<=[,/(]\s)react(?!\s*native)", r"(?<=[,/(])react(?!\s*native)"]),
    "react_native": ("React Native", [r"react\s*native"]),
    "nextjs": ("Next.js", [r"next\.?js"]),
    "angular": ("Angular", [r"angular"]),
    "vue": ("Vue.js", [r"vue(?:\.?js)?"]),
    "html_css": ("HTML/CSS", [r"html5?", r"css3?", r"tailwind"]),
    "graphql": ("GraphQL", [r"graphql"]),
    "rest_apis": ("REST APIs", [r"rest(?:ful)?\s+apis?", r"rest\s+services"]),
    "grpc": ("gRPC", [r"grpc"]),
    "microservices": ("Microservices", [r"micro-?services"]),
    "system_design": ("System Design", [r"system\s+design", r"distributed\s+systems"]),
    "docker": ("Docker", [r"docker", r"containeri[sz]ation"]),
    "kubernetes": ("Kubernetes", [r"kubernetes", r"k8s", r"\beks\b", r"\bgke\b", r"\baks\b"]),
    "aws": ("AWS", [r"aws", r"amazon\s+web\s+services"]),
    "gcp": ("GCP", [r"gcp", r"google\s+cloud"]),
    "azure": ("Azure", [r"azure"]),
    "terraform": ("Terraform", [r"terraform"]),
    "ansible": ("Ansible", [r"ansible"]),
    "ci_cd": ("CI/CD", [r"ci\s*/\s*cd", r"jenkins", r"github\s+actions", r"gitlab\s+ci", r"continuous\s+(?:integration|delivery|deployment)"]),
    "linux": ("Linux", [r"linux", r"unix"]),
    "git": ("Git", [r"git"]),
    "monitoring": ("Monitoring & Observability", [r"observability", r"prometheus", r"grafana", r"datadog", r"new\s+relic"]),
    "networking": ("Networking", [r"tcp/ip", r"computer\s+networking", r"network\s+protocols", r"networking\s+fundamentals",
                                  r"\bdns\b", r"\bdhcp\b", r"routing\s+(?:and|&)\s+switching", r"osi\s+model", r"\bccna\b"]),
    "security": ("Security", [r"application\s+security", r"cyber\s*security", r"owasp", r"infosec", r"information\s+security"]),
    # Security-operations vocabulary (SOC / analyst roles). "SOC" alone is not used:
    # descriptions often mean "SOC 2" compliance reports.
    "network_security": ("Network Security", [r"network\s+security", r"firewalls?", r"ids\s*/\s*ips",
                                              r"intrusion\s+(?:detection|prevention)", r"\bvpns?\b"]),
    "cryptography": ("Cryptography", [r"cryptograph(?:y|ic)", r"encryption", r"\bpki\b"]),
    "wireshark": ("Wireshark", [r"wireshark", r"tcpdump", r"packet\s+(?:analysis|capture)"]),
    "nmap": ("Nmap", [r"nmap", r"port\s+scann(?:ing|er)"]),
    "siem": ("SIEM", [r"siem", r"splunk", r"qradar", r"microsoft\s+sentinel", r"arcsight"]),
    "vulnerability_management": ("Vulnerability Assessment", [r"vulnerability\s+(?:assessment|management|scanning)", r"\bvapt\b",
                                                              r"nessus", r"qualys", r"burp\s+suite", r"penetration\s+testing",
                                                              r"pen[\s-]?test(?:ing)?"]),
    "incident_response": ("Incident Response", [r"incident\s+response", r"threat\s+(?:detection|hunting|intelligence)",
                                                r"security\s+monitoring", r"soc\s+(?:analyst|operations|team|monitoring)",
                                                r"security\s+operations\s+cent(?:er|re)"]),
    "iam": ("Identity & Access Management", [r"identity\s+(?:and|&)\s+access\s+management", r"\biam\b", r"\bsso\b", r"saml", r"oauth"]),
    "machine_learning": ("Machine Learning", [r"machine\s+learning", r"\bml\b"]),
    "deep_learning": ("Deep Learning", [r"deep\s+learning", r"neural\s+networks?"]),
    "nlp": ("Natural Language Processing", [r"nlp", r"natural\s+language\s+processing"]),
    "llm": ("LLMs / GenAI", [r"llms?", r"large\s+language\s+models?", r"generative\s+ai", r"gen\s*ai", r"rag\b"]),
    "computer_vision": ("Computer Vision", [r"computer\s+vision"]),
    "pytorch": ("PyTorch", [r"pytorch"]),
    "tensorflow": ("TensorFlow", [r"tensorflow", r"keras"]),
    "scikit_learn": ("scikit-learn", [r"scikit-?learn", r"sklearn"]),
    "pandas": ("Pandas", [r"pandas", r"numpy"]),
    "mlops": ("MLOps", [r"mlops", r"mlflow", r"kubeflow"]),
    "statistics": ("Statistics", [r"statistic(?:s|al)"]),
    "data_analysis": ("Data Analysis", [r"data\s+analysis", r"data\s+analytics"]),
    "data_visualization": ("Data Visualization", [r"data\s+visuali[sz]ation", r"tableau", r"power\s*bi", r"looker"]),
    "excel": ("Excel", [r"ms\s*excel", r"microsoft\s+excel", r"advanced\s+excel",
                        r"excel\s+(?:skills|formulas|modell?ing|spreadsheets)", r"spreadsheets?"]),
    "data_engineering": ("Data Engineering", [r"data\s+pipelines?", r"etl", r"elt", r"data\s+warehous(?:e|ing)"]),
    "android": ("Android", [r"android"]),
    "ios": ("iOS", [r"\bios\b"]),
    "flutter": ("Flutter", [r"flutter"]),
    "testing": ("Testing / QA", [r"unit\s+test(?:s|ing)", r"test\s+automation", r"selenium", r"cypress", r"playwright", r"pytest", r"junit"]),
    "agile": ("Agile", [r"agile", r"scrum"]),
    "figma": ("Figma", [r"figma"]),
    "ui_design": ("UI Design", [r"ui\s+design", r"user\s+interface\s+design", r"visual\s+design"]),
    "ux_research": ("UX Research", [r"ux\s+research", r"user\s+research", r"usability\s+testing"]),
    "product_strategy": ("Product Strategy", [r"product\s+strategy", r"product\s+roadmap"]),
    "stakeholder_management": ("Stakeholder Management", [r"stakeholder\s+management"]),
    "project_management": ("Project Management", [r"project\s+management", r"pmp"]),
    "seo": ("SEO", [r"seo", r"search\s+engine\s+optimi[sz]ation"]),
    "crm": ("CRM", [r"crm", r"salesforce", r"hubspot"]),
    "financial_analysis": ("Financial Analysis", [r"financial\s+analysis", r"financial\s+modell?ing"]),
    "accounting": ("Accounting", [r"accounting", r"gaap", r"ind\s*as", r"ifrs"]),
}

_COMPILED_SKILLS: dict[str, re.Pattern] = {
    skill_id: re.compile(r"(?<![a-z0-9+#])(?:" + "|".join(patterns) + r")(?![a-z0-9+#])", re.IGNORECASE)
    for skill_id, (_name, patterns) in TECH_SKILLS.items()
}


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9+#]+", "", (value or "").strip().lower())


# Free-text profile skill → canonical id. Built from display names, the career
# knowledge base aliases, and explicit synonyms users commonly type.
_ALIAS_TO_ID: dict[str, str] = {}
for _sid, (_name, _patterns) in TECH_SKILLS.items():
    _ALIAS_TO_ID[_key(_sid)] = _sid
    _ALIAS_TO_ID[_key(_name)] = _sid
for _sid, _entry in SKILLS.items():
    for _value in [_sid, _entry.name, *_entry.aliases]:
        _ALIAS_TO_ID.setdefault(_key(_value), _sid)

_EXTRA_ALIASES = {
    "golang": "go", "go": "go", "node": "nodejs", "nodejs": "nodejs", "expressjs": "express",
    "reactjs": "react", "react.js": "react", "nextjs": "nextjs", "vuejs": "vue", "angularjs": "angular",
    "html": "html_css", "css": "html_css", "html5": "html_css", "css3": "html_css", "tailwind": "html_css",
    "tailwindcss": "html_css", "c++": "c_cpp", "cpp": "c_cpp", "c": "c_cpp", "c#": "csharp", ".net": "csharp",
    "dotnet": "csharp", "springboot": "spring", "spring": "spring", "postgres": "postgresql", "mongo": "mongodb",
    "k8s": "kubernetes", "postgre": "postgresql", "psql": "postgresql", "amazonwebservices": "aws", "googlecloud": "gcp", "gcloud": "gcp", "msazure": "azure",
    "cicd": "ci_cd", "jenkins": "ci_cd", "githubactions": "ci_cd", "github": "git", "gitlab": "git",
    "prometheus": "monitoring", "grafana": "monitoring", "ml": "machine_learning", "ai": "machine_learning",
    "artificialintelligence": "machine_learning", "dl": "deep_learning", "genai": "llm", "llm": "llm", "llms": "llm",
    "generativeai": "llm", "langchain": "llm", "sklearn": "scikit_learn", "numpy": "pandas", "keras": "tensorflow",
    "powerbi": "data_visualization", "tableau": "data_visualization", "msexcel": "excel", "pyspark": "spark",
    "restapi": "rest_apis", "restapis": "rest_apis", "restful": "rest_apis", "api": "rest_apis", "apis": "rest_apis",
    "selenium": "testing", "pytest": "testing", "jest": "testing", "scrum": "agile", "r": "r_lang",
    "etl": "data_engineering", "unix": "linux", "bash": "linux", "shellscripting": "linux",
    "cybersecurity": "security", "cybersecurityfundamentals": "security", "informationsecurity": "security",
    "securityfundamentals": "security", "computernetworking": "networking", "networkingfundamentals": "networking",
    "networking": "networking", "tcpip": "networking", "dns": "networking", "networksecurity": "network_security",
    "firewall": "network_security", "encryption": "cryptography", "splunk": "siem", "vapt": "vulnerability_management",
    "penetrationtesting": "vulnerability_management", "ethicalhacking": "vulnerability_management",
    "incidentresponse": "incident_response", "soc": "incident_response", "threatdetection": "incident_response",
}
_ALIAS_TO_ID.update({_key(alias): sid for alias, sid in _EXTRA_ALIASES.items()})


def canonical_skill_id(value: str) -> str:
    """Map any user/listing skill spelling to a stable canonical id."""
    key = _key(value)
    return _ALIAS_TO_ID.get(key, key)


def skill_display_name(skill_id: str) -> str:
    if skill_id in TECH_SKILLS:
        return TECH_SKILLS[skill_id][0]
    if skill_id in SKILLS:
        return SKILLS[skill_id].name
    return skill_id


def extract_skills(text: str) -> list[str]:
    """Return canonical ids of skills explicitly mentioned in ``text`` (stable order)."""
    if not text:
        return []
    return [skill_id for skill_id, pattern in _COMPILED_SKILLS.items() if pattern.search(text)]


# ─────────────────────────────────────────────────────────────────────────────
# Roles
# ─────────────────────────────────────────────────────────────────────────────

ROLE_FAMILIES: dict[str, list[str]] = {
    "Backend Engineer": [r"back[\s-]?end", r"server[\s-]side", r"api\s+(?:developer|engineer)", r"platform\s+engineer",
                         r"(?:python|java|golang|go|node(?:\.?js)?|ruby|php|\.net|c#|scala|kotlin)\s+(?:developer|engineer|sde)"],
    "Full Stack Developer": [r"full[\s-]?stack", r"mern", r"mean\s+stack"],
    "Frontend Developer": [r"front[\s-]?end", r"ui\s+(?:developer|engineer)", r"web\s+developer",
                           r"(?:react|angular|vue|javascript|typescript)\s+(?:developer|engineer)"],
    "Mobile Developer": [r"android", r"\bios\b", r"mobile\s+(?:developer|engineer|app)", r"flutter", r"react\s+native"],
    "DevOps Engineer": [r"devops", r"dev\s*ops", r"site\s+reliability", r"\bsre\b", r"release\s+engineer", r"build\s+engineer",
                        r"infrastructure\s+engineer"],
    "Cloud Engineer": [r"cloud\s+(?:engineer|architect|developer|infrastructure)", r"aws\s+engineer", r"azure\s+engineer"],
    # Analyst / security-operations work (SOC, detection, response, GRC) is a
    # different family from security *engineering*; generic software or
    # infrastructure roles are not close neighbours of it.
    "Security Analyst": [r"(?:cyber\s*security|information\s+security|infosec|security|soc|threat|cyber|grc)\s+(?:analyst|specialist)",
                         r"soc\s+(?:analyst|engineer|lead)", r"security\s+operations", r"incident\s+(?:response|responder|commander)",
                         r"threat\s+(?:detection|intelligence|research|hunt(?:er|ing)?)", r"detection\s+(?:&|and)\s+response",
                         r"vulnerability\s+(?:analyst|management|assessment)", r"penetration\s+tester", r"\bvapt\b",
                         r"ethical\s+hacker", r"(?:analyst|specialist),?\s+(?:cyber\s*|information\s+)security",
                         r"(?:digital|cyber|computer)\s+forensics?", r"\bdfir\b"],
    "Security Engineer": [r"security\s+(?:engineer|architect)", r"appsec", r"product\s+security", r"devsecops",
                          r"cyber\s*security", r"cyber\s+resilience"],
    "Network Engineer": [r"network\s+(?:engineer|administrator|admin|analyst|specialist|operations)", r"\bnoc\b",
                         r"system\s+administrator", r"sysadmin"],
    "QA Engineer": [r"\bqa\b", r"quality\s+(?:assurance|engineer)", r"\bsdet\b", r"test\s+(?:engineer|automation)", r"automation\s+tester"],
    "Data Engineer": [r"data\s+engineer", r"analytics\s+engineer", r"etl\s+developer", r"big\s+data", r"data\s+platform"],
    "Machine Learning Engineer": [r"machine\s+learning", r"\bml\b", r"\bai\s+(?:engineer|developer|researcher)", r"deep\s+learning",
                                  r"applied\s+scientist", r"research\s+(?:engineer|scientist)", r"\bnlp\b", r"computer\s+vision",
                                  r"\bllm\b", r"gen\s*ai"],
    "Data Scientist": [r"data\s+scien(?:ce|tists?)", r"decision\s+scientist"],
    "Data Analyst": [r"data\s+analyst", r"business\s+intelligence", r"\bbi\s+(?:analyst|developer|engineer)", r"analytics\s+analyst",
                     r"reporting\s+analyst", r"product\s+analyst", r"insights\s+analyst"],
    "Software Engineer": [r"software\s+(?:engineer|developer|development\s+engineer)", r"\bsde\b", r"\bswe\b",
                          r"programmer", r"application\s+developer", r"member\s+of\s+technical\s+staff", r"\bmts\b"],
    "Engineering Manager": [r"engineering\s+manager", r"head\s+of\s+engineering", r"director.*engineering", r"vp.*engineering"],
    "Product Manager": [r"product\s+manager", r"product\s+owner", r"\bapm\b", r"product\s+lead"],
    "UI/UX Designer": [r"ux", r"ui\s*/\s*ux", r"product\s+designer", r"interaction\s+designer", r"visual\s+designer", r"ui\s+designer"],
    "Business Analyst": [r"business\s+analyst", r"business\s+systems\s+analyst"],
    "Technical Support Engineer": [r"support\s+engineer", r"technical\s+support", r"solutions?\s+engineer", r"customer\s+engineer",
                                   r"implementation\s+engineer"],
}

_COMPILED_ROLES: list[tuple[str, re.Pattern]] = [
    (role, re.compile(r"(?<![a-z0-9])(?:" + "|".join(patterns) + r")(?![a-z0-9])", re.IGNORECASE))
    for role, patterns in ROLE_FAMILIES.items()
]

# Families that are close neighbours. Score multipliers are applied by the matcher.
RELATED_ROLES: dict[str, set[str]] = {
    "Backend Engineer": {"Full Stack Developer", "Software Engineer", "Cloud Engineer", "DevOps Engineer", "Data Engineer"},
    "Full Stack Developer": {"Backend Engineer", "Frontend Developer", "Software Engineer"},
    "Frontend Developer": {"Full Stack Developer", "Software Engineer", "Mobile Developer", "UI/UX Designer"},
    "Mobile Developer": {"Frontend Developer", "Software Engineer"},
    "DevOps Engineer": {"Cloud Engineer", "Backend Engineer", "Software Engineer", "Security Engineer"},
    "Cloud Engineer": {"DevOps Engineer", "Backend Engineer", "Software Engineer", "Security Engineer"},
    "Security Engineer": {"DevOps Engineer", "Cloud Engineer", "Software Engineer", "Security Analyst"},
    "Security Analyst": {"Security Engineer", "Network Engineer"},
    "Network Engineer": {"Security Analyst", "DevOps Engineer", "Cloud Engineer", "Technical Support Engineer"},
    "QA Engineer": {"Software Engineer", "Backend Engineer", "Frontend Developer"},
    "Data Engineer": {"Backend Engineer", "Data Scientist", "Data Analyst", "Software Engineer", "Machine Learning Engineer"},
    "Machine Learning Engineer": {"Data Scientist", "Data Engineer", "Software Engineer", "Backend Engineer"},
    "Data Scientist": {"Machine Learning Engineer", "Data Analyst", "Data Engineer"},
    "Data Analyst": {"Data Scientist", "Business Analyst", "Data Engineer"},
    "Software Engineer": {"Backend Engineer", "Full Stack Developer", "Frontend Developer", "Mobile Developer", "DevOps Engineer",
                          "Cloud Engineer", "QA Engineer", "Data Engineer", "Machine Learning Engineer", "Security Engineer"},
    "Engineering Manager": {"Software Engineer", "Product Manager"},
    "Product Manager": {"Business Analyst", "UI/UX Designer", "Engineering Manager"},
    "UI/UX Designer": {"Frontend Developer", "Product Manager"},
    "Business Analyst": {"Data Analyst", "Product Manager"},
    "Technical Support Engineer": {"Software Engineer", "QA Engineer", "DevOps Engineer"},
}

_KB_ROLE_BY_LOWER = {role.name.lower(): role.name for role in ROLES}


def classify_role(title: str) -> list[str]:
    """Return every role family whose patterns appear in ``title`` (most specific first)."""
    if not title:
        return []
    matches = [role for role, pattern in _COMPILED_ROLES if pattern.search(title)]
    # "Software Engineer" is the generic family: keep it last so specific families win.
    if "Software Engineer" in matches and len(matches) > 1:
        matches.remove("Software Engineer")
        matches.append("Software Engineer")
    return matches


def normalize_target_roles(value: Optional[str]) -> list[str]:
    """Parse a user's free-text target role(s) into canonical role families.

    "Backend and Devops" → ["Backend Engineer", "DevOps Engineer"]. Parts that do
    not match a known family are kept verbatim (title-cased) so they can still be
    compared by keyword overlap.
    """
    if not value or not value.strip():
        return []
    roles: list[str] = []
    parts = re.split(r"[,/;|&+]+|\band\b|\bor\b", value, flags=re.IGNORECASE)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        families = classify_role(part)
        if not families:
            # Bare family words without "engineer"/"developer" (e.g. "Backend", "Devops").
            families = classify_role(f"{part} engineer") or classify_role(f"{part} developer")
        if not families and part.lower() in _KB_ROLE_BY_LOWER:
            families = [_KB_ROLE_BY_LOWER[part.lower()]]
        candidates = families[:1] if families else [part.title()]
        for role in candidates:
            if role not in roles:
                roles.append(role)
    return roles


def title_keywords(value: str) -> set[str]:
    stop = {"and", "or", "the", "of", "for", "with", "in", "a", "an", "to", "i", "ii", "iii", "iv", "senior", "junior",
            "sr", "jr", "lead", "staff", "principal", "intern", "engineer", "developer", "analyst", "specialist",
            "associate", "manager", "architect", "consultant", "executive", "officer", "-", "remote", "india"}
    return {token for token in re.findall(r"[a-z0-9+#.]+", (value or "").lower()) if token not in stop and len(token) > 1}


# ─────────────────────────────────────────────────────────────────────────────
# Seniority / experience
# ─────────────────────────────────────────────────────────────────────────────

# Ordinal levels: 0 intern, 1 entry, 2 junior/mid-entry, 3 mid, 4 senior, 5 lead/staff+, 6 management
LEVEL_NAMES = {0: "Intern", 1: "Entry Level", 2: "Junior", 3: "Mid Level", 4: "Senior", 5: "Lead / Staff", 6: "Manager / Director"}

_LEVEL_PATTERNS: list[tuple[int, re.Pattern]] = [
    (0, re.compile(r"\b(?:intern|internship|apprentice|trainee)\b", re.I)),
    (6, re.compile(r"\b(?:director|vp|vice\s+president|head\s+of|chief)\b", re.I)),
    (5, re.compile(r"\b(?:principal|staff|lead|architect|distinguished)\b", re.I)),
    (6, re.compile(r"\bmanager\b", re.I)),
    (4, re.compile(r"\b(?:senior|sr\.?|sde\s*-?\s*(?:iii|3)|engineer\s+(?:iii|3)|level\s*(?:iii|3))\b", re.I)),
    (1, re.compile(r"\b(?:entry[\s-]level|graduate|new\s+grad|fresher|freshers|campus|university\s+grad)\b", re.I)),
    (2, re.compile(r"\b(?:junior|jr\.?|associate|sde\s*-?\s*(?:i|1)|engineer\s+(?:i|1)|level\s*(?:i|1))\b", re.I)),
    (3, re.compile(r"\b(?:mid[\s-]level|sde\s*-?\s*(?:ii|2)|engineer\s+(?:ii|2)|level\s*(?:ii|2))\b", re.I)),
]

_YEARS_RANGE = re.compile(r"(\d{1,2})\s*(?:\+\s*)?(?:-|–|to)\s*(\d{1,2})\s*\+?\s*(?:years|yrs)", re.I)
_YEARS_MIN = re.compile(r"(?:minimum|min\.?|at\s+least|over)?\s*(\d{1,2})\s*\+?\s*(?:years|yrs)(?:'|’)?\s*(?:of\s+)?(?:[\w/-]+\s+){0,4}?(?:experience|exp\b)", re.I)


def level_from_title(title: str) -> Optional[int]:
    if not title:
        return None
    for level, pattern in _LEVEL_PATTERNS:
        if pattern.search(title):
            return level
    return None


def parse_experience_years(text: str) -> tuple[Optional[int], Optional[int]]:
    """Return (min, max) years of experience explicitly stated in ``text``.

    Returns (None, None) when the listing does not state a requirement.
    Implausible values (>25 years — usually "25 years of company history") are ignored.
    """
    if not text:
        return None, None
    for match in _YEARS_RANGE.finditer(text):
        low, high = int(match.group(1)), int(match.group(2))
        if 0 <= low <= high <= 25:
            return low, high
    candidates = [int(m.group(1)) for m in _YEARS_MIN.finditer(text) if 0 <= int(m.group(1)) <= 25]
    if candidates:
        return min(candidates), None
    return None, None


def level_from_years(min_years: Optional[int]) -> Optional[int]:
    if min_years is None:
        return None
    if min_years <= 0:
        return 1
    if min_years <= 2:
        return 2
    if min_years <= 4:
        return 3
    if min_years <= 7:
        return 4
    return 5
