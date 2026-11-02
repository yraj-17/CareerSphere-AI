# CareerSphere AI

CareerSphere AI is an AI-assisted career development platform that combines profile intelligence, skill analysis, career matching, interview practice, professional networking, communities, resources, messaging, notifications, and a social feed in one workspace.

The repository contains a Next.js frontend and a FastAPI backend backed by PostgreSQL, Redis, Qdrant, and MinIO. Ollama/Qwen, Gemini reranking, and LanguageTool integrations are optional capabilities configured through environment variables.

## Project status

| Area | Status | Notes |
| --- | --- | --- |
| Authentication | Implemented | Email OTP registration, JWT login, password changes, and protected API routes |
| Profile workspace | Implemented | Skills, education, experience, projects, certifications, and career preferences |
| AI Career Assistant | Implemented | Persistent conversations, profile context, retry support, and optional grammar checking |
| Skill Analysis | Implemented | Deterministic skill-gap analysis with optional AI explanations |
| Career Matching | Implemented | Local opportunity index, deterministic scoring, optional Gemini reranking, and Qwen explanations |
| AI Interviewer | Implemented | Text interview sessions, role analysis, navigation, evaluation, reports, and history |
| Voice interview mode | Optional | Requires a separately installed Faster-Whisper model and runtime configuration |
| Networking | Implemented | Discovery, connection requests, accepted connections, and profile views |
| Communities | Implemented | Communities, memberships, posts, reactions, comments, and media |
| Messaging | Implemented | REST messaging, WebSocket delivery, Redis Pub/Sub fan-out, and presence |
| Resources and home feed | Implemented | Curated resources, saved resources, global posts, likes, comments, and sharing |
| Production deployment | Project-specific | Compose provides local infrastructure services; deployment orchestration is not included |

## Contents

- [Overview](#overview)
- [Key features](#key-features)
- [Visual documentation](#visual-documentation)
- [Architecture](#architecture)
- [Technology stack](#technology-stack)
- [Repository structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Getting started](#getting-started)
- [Docker infrastructure](#docker-infrastructure)
- [Configuration reference](#configuration-reference)
- [API reference](#api-reference)
- [AI and data flow](#ai-and-data-flow)
- [Database design](#database-design)
- [Development workflow](#development-workflow)
- [Testing](#testing)
- [Contributing](#contributing)
- [Roadmap](#roadmap)
- [Security](#security)
- [License](#license)
- [Acknowledgements](#acknowledgements)

## Overview

CareerSphere AI is organized around a user’s career context:

1. A user creates an account and builds a structured professional profile.
2. Profile data is used by skill analysis, career matching, interview preparation, and the AI assistant.
3. Networking and community features support discovery, conversations, and collaboration.
4. Resources and posts provide a shared knowledge layer around career growth.
5. PostgreSQL remains the system of record, while Redis, Qdrant, MinIO, and model services support specialized workloads.

The project intentionally keeps deterministic domain logic in the backend. AI services enhance explanations, prioritization, and conversations, but they do not replace the authoritative profile, scoring, persistence, or permission boundaries.

## Key features

### Career intelligence

- Profile-aware AI career assistant with persistent conversations.
- Structured profile optimization recommendations.
- Skill inventory and skill-gap analysis.
- Career opportunity matching using profile, preference, skill, experience, and location signals.
- Optional semantic reranking through Gemini.
- Optional Qwen-generated explanations for matches and skill priorities.

### Interview preparation

- Role and interview-type selection.
- Custom role analysis and interview blueprint preview.
- Text interview sessions with draft answers, navigation, retries, and completion.
- Answer evaluation and final interview reports.
- Interview history and report regeneration.
- Optional voice transcription through Faster-Whisper when configured.

### Professional networking

- People discovery and connection requests.
- Accepted connection management.
- Community creation, membership, posts, reactions, comments, and media.
- Direct conversations with REST and WebSocket delivery.
- Redis-backed cross-instance message fan-out and presence tracking.
- Notifications for relevant account and networking activity.

### Knowledge and social feed

- Resource library with type and category filters.
- Save and unsave resources.
- Global posts with likes, comments, pagination, and sharing.
- Media upload and presigned object URLs through MinIO.

## Visual documentation

This README intentionally contains no screenshots, banners, logos, decorative graphics, externally hosted image links, or image directories. The documentation is text-first and uses Mermaid only for technical diagrams. Run the application locally to inspect the current interface.

## Architecture

### System context

~~~mermaid
flowchart LR
    Browser["Browser<br/>Next.js + React"] --> API["FastAPI<br/>/api"]
    API --> Domain["Domain services<br/>auth, profile, matching, interviews, social"]
    Domain --> PostgreSQL[("PostgreSQL")]
    Domain --> Redis[("Redis")]
    Domain --> Qdrant[("Qdrant")]
    Domain --> MinIO[("MinIO")]
    Domain --> Ollama["Ollama<br/>Qwen + embeddings"]
    Domain -. optional .-> Gemini["Gemini reranking"]
    Domain -. optional .-> LanguageTool["LanguageTool"]
    Domain --> SMTP["SMTP provider<br/>email OTP"]
    API <-->|"WebSocket messaging"| Browser
    Redis <-->|"Pub/Sub and presence"| API
~~~

### Application layers

| Layer | Responsibility |
| --- | --- |
| Next.js client | Routes, forms, dashboards, feed, interview workspace, networking, resources, and messaging UI |
| FastAPI application | HTTP routing, WebSocket routing, authentication dependencies, validation, startup checks, and health reporting |
| Domain services | Profile context, matching, interviews, posts, communities, conversations, notifications, resources, and storage orchestration |
| PostgreSQL | Users, profiles, career data, opportunities, conversations, messages, posts, communities, resources, notifications, and interview records |
| Redis | Caching, matching responses, presence TTLs, Pub/Sub fan-out, and distributed messaging coordination |
| Qdrant | Profile, career knowledge, and opportunity vector collections used for semantic retrieval |
| MinIO | Binary media storage with metadata in PostgreSQL and presigned access URLs |
| Model integrations | Ollama/Qwen for assistant and interview workloads, Ollama embeddings for retrieval, and optional Gemini reranking |

### Request lifecycle

1. The browser sends requests to the FastAPI base URL configured by NEXT_PUBLIC_API_URL.
2. Axios attaches the JWT bearer token stored by the frontend authentication helper.
3. FastAPI validates the request and delegates to a domain service.
4. The service reads or writes PostgreSQL and calls specialized infrastructure only when required.
5. The API returns a validated response; messaging can also deliver updates through the WebSocket route.

## Technology stack

| Layer | Technologies |
| --- | --- |
| Frontend | Next.js 16, React 18, Axios, Tailwind CSS, Framer Motion, Lucide React |
| Frontend quality | ESLint, Jest 30, Testing Library, jsdom |
| Backend | Python, FastAPI, Uvicorn, Pydantic Settings |
| Persistence | PostgreSQL, SQLAlchemy 2, Alembic |
| Caching and realtime | Redis, Redis Pub/Sub, WebSockets |
| Retrieval | Qdrant, Ollama embeddings |
| AI | Ollama/Qwen, optional Gemini reranking |
| Object storage | MinIO |
| Optional language tooling | LanguageTool and Faster-Whisper |
| Local orchestration | Docker Compose |

The frontend package currently defines these scripts:

~~~text
npm run dev
npm run build
npm run start
npm run lint
npm test
npm run test:ci
~~~

## Repository structure

~~~text
.
├── backend/
│   ├── app/
│   │   ├── api/              FastAPI routers
│   │   ├── core/             Settings and security
│   │   ├── data/             Curated career and interview data
│   │   ├── db/               SQLAlchemy models and database session
│   │   ├── schemas/          Pydantic request and response models
│   │   └── services/         Domain and infrastructure services
│   ├── alembic/              Database migrations
│   ├── scripts/              Opportunity seeding and indexing tools
│   ├── tests/                Backend test suite
│   ├── init_db.py            Database and infrastructure bootstrap
│   ├── requirements.txt      Python dependencies
│   └── pytest.ini            Pytest configuration
├── frontend/
│   ├── app/                  Next.js App Router pages
│   ├── components/           Reusable UI and feature components
│   ├── hooks/                Client hooks, including messaging WebSocket support
│   ├── lib/                  Client helpers and authentication storage
│   ├── services/             Frontend API client
│   ├── __tests__/            Frontend tests
│   ├── public/               Runtime assets
│   └── package.json          Frontend scripts and dependencies
├── ollama/                   Optional local Ollama image and entrypoint
├── docker-compose.yml        Redis, Qdrant, MinIO, and optional AI services
├── .env.example              Root backend environment template
└── README.md
~~~

## Prerequisites

Install the following before starting:

- Git.
- Node.js and npm compatible with the installed Next.js toolchain.
- A supported Python 3 environment. The repository does not pin an exact Python minor version; Python 3.10+ is recommended.
- PostgreSQL. The repository requires an external PostgreSQL instance; the supplied Compose file does not define a PostgreSQL service.
- Docker Desktop or Docker Engine with Docker Compose for Redis, Qdrant, and MinIO.
- An SMTP account or provider if email OTP registration is enabled.
- Ollama if using local assistant, interview, or embedding models.

## Getting started

### 1. Clone the repository

~~~bash
git clone https://github.com/yraj-17/CareerSphere-AI.git
cd CareerSphere-AI
~~~

### 2. Configure environment variables

Copy the root template:

~~~powershell
Copy-Item .env.example .env
~~~

On macOS or Linux:

~~~bash
cp .env.example .env
~~~

Create the frontend-local environment file:

~~~powershell
Copy-Item frontend/.env.example frontend/.env.local
~~~

On macOS or Linux:

~~~bash
cp frontend/.env.example frontend/.env.local
~~~

Set at least:

- DATABASE_URL for a reachable PostgreSQL database.
- A long random SECRET_KEY.
- CORS_ORIGINS containing the frontend origin.
- SMTP credentials if email OTP is required.
- Model and infrastructure values appropriate for the local environment.

Do not commit .env or .env.local.

### 3. Create the PostgreSQL database

Create the database using your local PostgreSQL installation, a managed database, or another PostgreSQL container:

~~~bash
psql -U postgres -c "CREATE DATABASE careersphere_db;"
~~~

If the database already exists, continue with the next step. Update DATABASE_URL when your host, port, username, password, or database name differs.

### 4. Start local infrastructure

The default Compose services are Redis, Qdrant, and MinIO:

~~~bash
docker compose up -d redis qdrant minio
~~~

Optional services:

~~~bash
docker compose --profile ai up -d ollama
docker compose --profile languagetool up -d languagetool
~~~

Compose does not start the FastAPI or Next.js applications and does not create PostgreSQL.

### 5. Install backend dependencies

PowerShell:

~~~powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
~~~

macOS or Linux:

~~~bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
~~~

### 6. Initialize the database and storage collections

For a migration-based setup:

~~~bash
alembic upgrade head
~~~

For a local bootstrap that also creates Qdrant collections and the MinIO bucket:

~~~bash
python init_db.py
~~~

Use one initialization path. init_db.py creates the SQLAlchemy schema and stamps the Alembic head before ensuring the supporting collections and bucket.

The backend checks PostgreSQL during application import, so PostgreSQL must be available before starting Uvicorn.

### 7. Seed and index optional career data

The repository includes backend scripts for local opportunity data and retrieval indexes:

~~~bash
python -m scripts.seed_opportunities
python -m scripts.index_opportunities
python -m scripts.index_career_knowledge
~~~

The indexing commands require the configured embedding provider and Qdrant. If Ollama is running in Compose, pull the embedding model inside the container before indexing:

~~~bash
docker exec careersphere-ollama ollama pull nomic-embed-text
~~~

The exact container name may differ if Compose assigns a project-specific prefix. Use docker compose ps to identify it.

### 8. Start the backend

Run this from the backend directory with the virtual environment active:

~~~bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
~~~

Useful backend URLs:

- Health: http://localhost:8000/api/health
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 9. Install and start the frontend

Open a second terminal:

~~~bash
cd frontend
npm install
npm run dev
~~~

Open http://localhost:3000. The frontend defaults to http://localhost:8000 through NEXT_PUBLIC_API_URL; update frontend/.env.local when the backend is hosted elsewhere.

### 10. Verify the services

PowerShell:

~~~powershell
Invoke-RestMethod http://localhost:8000/api/health
~~~

macOS or Linux:

~~~bash
curl http://localhost:8000/api/health
~~~

The health response reports PostgreSQL, Redis, Qdrant, and MinIO independently. A fully healthy response requires all four core dependencies to be reachable.

## Docker infrastructure

The supplied docker-compose.yml defines infrastructure only:

| Service | Profile | Port | Purpose |
| --- | --- | ---: | --- |
| redis | default | 6379 | Cache, Pub/Sub, presence, and coordination |
| qdrant | default | 6333, 6334 | Vector search and collection storage |
| minio | default | 9000, 9001 | Object storage API and console |
| ollama | ai | 11434 | Local language and embedding models |
| languagetool | languagetool | 8010 | Optional grammar checking |

Common commands:

~~~bash
docker compose ps
docker compose logs -f redis qdrant minio
docker compose stop
docker compose start
docker compose down
~~~

docker compose down removes containers but preserves named volumes unless --volumes is supplied. Treat docker compose down --volumes as destructive because it removes local Redis, Qdrant, MinIO, and Ollama data.

Default local consoles:

- MinIO API: http://localhost:9000
- MinIO console: http://localhost:9001
- Qdrant HTTP API: http://localhost:6333
- Ollama API when enabled: http://localhost:11434
- LanguageTool when enabled: http://localhost:8010

## Configuration reference

The backend loads .env and also checks the parent directory when running from backend. The frontend reads frontend/.env.local.

### Core application and database

| Variable | Required | Purpose |
| --- | --- | --- |
| PROJECT_NAME | No | Application display name |
| DATABASE_URL | Yes | PostgreSQL connection URL; postgresql+psycopg is supported |
| SECRET_KEY | Yes | JWT signing secret; use a long random value |
| ALGORITHM | No | JWT algorithm, default HS256 |
| ACCESS_TOKEN_EXPIRE_MINUTES | No | Access-token lifetime |
| CORS_ORIGINS | No | Allowed frontend origins; defaults to localhost frontend |

SQLite is not supported by the backend configuration.

### Cache, retrieval, and storage

| Variable | Purpose |
| --- | --- |
| REDIS_URL | Redis connection URL |
| QDRANT_URL | Qdrant endpoint |
| QDRANT_API_KEY | Optional Qdrant API key |
| QDRANT_COLLECTION_PROFILES | Profile vector collection |
| QDRANT_COLLECTION_CONTENT | Career-content vector collection |
| QDRANT_COLLECTION_OPPORTUNITIES | Opportunity vector collection |
| EMBEDDING_PROVIDER | Embedding provider, default ollama |
| EMBEDDING_MODEL | Embedding model, default nomic-embed-text |
| EMBEDDING_DIMENSION | Optional explicit vector dimension |
| MINIO_ENDPOINT | MinIO host and port |
| MINIO_ACCESS_KEY / MINIO_SECRET_KEY | Object-storage credentials |
| MINIO_BUCKET | Object-storage bucket |
| MINIO_SECURE | Whether MinIO uses HTTPS |
| MINIO_PUBLIC_URL | Optional public media URL |

### AI and language services

| Variable | Purpose |
| --- | --- |
| OLLAMA_BASE_URL | Ollama endpoint |
| OLLAMA_MODEL | Qwen model used for assistant and interview workloads |
| AI_MAX_PROMPT_CHARS | Prompt size guard |
| AI_CONTEXT_MESSAGES / AI_CONTEXT_CHARS | Conversation context limits |
| GEMINI_API_KEY | Optional Gemini reranking credential |
| GEMINI_MODEL | Gemini reranking model |
| GEMINI_RERANK_TIMEOUT_SECONDS | Gemini request timeout |
| LANGUAGETOOL_URL | Optional grammar-check endpoint |
| LANGUAGETOOL_LANGUAGE | LanguageTool language code |
| LANGUAGETOOL_TIMEOUT_SECONDS | LanguageTool timeout |

### Interview and transcription controls

| Variable | Purpose |
| --- | --- |
| OLLAMA_INTERVIEW_TIMEOUT_SECONDS | Interview-generation timeout |
| INTERVIEW_AI_MAX_CONCURRENCY | Interview AI concurrency limit |
| INTERVIEW_SUBMISSION_GRACE_SECONDS | Submission grace period |
| INTERVIEW_WHISPER_MODEL | Optional Faster-Whisper model; blank disables voice transcription |
| INTERVIEW_WHISPER_DEVICE | Whisper device, commonly cpu |
| INTERVIEW_WHISPER_COMPUTE_TYPE | Whisper compute type |
| INTERVIEW_TRANSCRIPTION_TIMEOUT_SECONDS | Transcription timeout |
| INTERVIEW_MAX_AUDIO_BYTES | Maximum uploaded audio size |
| INTERVIEW_MAX_AUDIO_SECONDS | Maximum audio duration |

### Email and operational settings

| Variable | Purpose |
| --- | --- |
| EMAIL_HOST_USER | SMTP account used for OTP email |
| EMAIL_HOST_PASSWORD | SMTP password or provider app password |
| OTP_EXPIRE_MINUTES | OTP validity period |
| AVAILABILITY_CACHE_TTL | Username/email availability cache duration |
| REDIS_PRESENCE_TTL_SECONDS | Presence expiration |
| INSTANCE_ID | Optional instance identifier for distributed runtime |

Never commit real credentials, API keys, JWT secrets, SMTP passwords, or production endpoints. Values in .env.example are development placeholders only.

## API reference

The API base path is:

~~~text
http://localhost:8000/api
~~~

Interactive documentation is generated by FastAPI:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

Protected endpoints use:

~~~http
Authorization: Bearer <access-token>
~~~

### Route groups

| Group | Prefix | Responsibilities |
| --- | --- | --- |
| Health | /health | Dependency health status |
| Authentication | /auth | OTP registration, login, account details, password changes, logout |
| Media | /media | Uploads, metadata, presigned URLs, downloads, and deletion |
| AI assistant | /ai | Chat, conversations, retries, profile optimization, and grammar checks |
| Profile | /profile | Profile, skills, education, experience, projects, certifications, preferences |
| Skill analysis | /skill-analysis | Profile skill-gap analysis and optional AI insights |
| Career matching | /career-matching | Profile-based opportunity matching and optional explanations |
| Networking | /networking | Discovery, requests, connections, and network views |
| Communities | /communities | Communities, memberships, posts, reactions, comments, and media |
| Messaging | /messaging | Conversations, messages, stars, deletion, and message management |
| Notifications | /notifications | Notification list, unread count, read, and read-all actions |
| Resources | /resources | Resource discovery, detail, save, unsave, and management |
| Posts | /posts | Global feed posts, likes, comments, editing, deletion, and sharing |
| Interviews | /interviews | Options, roles, blueprint, sessions, questions, answers, evaluation, and reports |

Notable endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /health | Check PostgreSQL, Redis, Qdrant, and MinIO |
| GET | /auth/me | Read the current account |
| POST | /auth/login | Authenticate and issue a JWT |
| POST | /ai/chat | Send a message to the career assistant |
| GET | /skill-analysis/me | Analyze the current profile |
| GET | /career-matching/me | Retrieve current career matches |
| POST | /posts | Create a global feed post |
| POST | /interviews | Create an interview session |
| POST | /interviews/{interview_id}/submit-answer | Submit an interview answer |
| GET | /interviews/{interview_id}/report | Read an interview report |
| WebSocket | /messaging/ws/{conversation_id} | Receive and send live conversation events |

The OpenAPI document at /openapi.json is the source of truth for request and response schemas.

## AI and data flow

### Career matching flow

~~~mermaid
sequenceDiagram
    participant User as Browser
    participant API as FastAPI /api
    participant Match as Career matching service
    participant PG as PostgreSQL
    participant Q as Qdrant
    participant Embed as Ollama embeddings
    participant Gemini as Optional Gemini
    participant Qwen as Ollama/Qwen
    participant Redis as Redis cache

    User->>API: GET /career-matching/me
    API->>Match: Load profile context
    Match->>PG: Read skills, experience, projects, preferences
    Match->>Embed: Create retrieval query embedding
    Embed-->>Match: Query vector
    Match->>Q: Retrieve opportunity candidates
    Q-->>Match: Candidate identifiers and scores
    Match->>PG: Load opportunity records
    Match->>Match: Apply deterministic match weights
    opt Gemini configured
        Match->>Gemini: Rerank deterministic candidates
        Gemini-->>Match: Semantic ordering signal
    end
    opt Explanations enabled
        Match->>Qwen: Explain matches and priorities
        Qwen-->>Match: Explanations
    end
    Match->>Redis: Cache response
    Match-->>API: Validated matching result
    API-->>User: JSON response
~~~

The deterministic matching service remains authoritative. Its current weighting includes required skills, preferred skills, target role, experience, location or remote preference, and career preferences. Gemini is an optional second-stage reranker and Qwen explanations are supplemental.

### AI boundaries and fallbacks

- The AI assistant uses profile context when available and stores conversation state in PostgreSQL.
- Skill analysis can return deterministic gaps without an AI provider.
- Career matching can return deterministic matches when Gemini or Qwen is unavailable.
- Text interviews do not require voice transcription.
- LanguageTool and Gemini are optional integrations.
- External model failures must not bypass authorization or persistence checks.

## Database design

PostgreSQL is the source of truth for product data. Qdrant stores searchable vectors, Redis stores ephemeral or cached state, and MinIO stores binary objects.

### Domain ownership

| Domain | Primary records |
| --- | --- |
| Identity | User, MediaObject, account and authentication state |
| Profile | Profile, ProfileSkill, ProfileEducation, ProfileExperience, ProfileProject, ProfileCertification, CareerPreference |
| Opportunities | Opportunity, required skills, preferred skills |
| Networking | Connection, Notification |
| Messaging | DirectConversation, participants, DirectMessage, stars, deletion records |
| Social | GlobalPost, media, likes, comments |
| Communities | Community, memberships, posts, reactions, comments, tags, media |
| Resources | Resource, SavedResource |
| Interviews | InterviewSession, questions, answers, reports, role profiles |

### Simplified entity relationship model

~~~mermaid
erDiagram
    USER ||--|| PROFILE : owns
    PROFILE ||--o{ PROFILE_SKILL : has
    PROFILE ||--o{ PROFILE_EDUCATION : records
    PROFILE ||--o{ PROFILE_EXPERIENCE : records
    PROFILE ||--o{ PROFILE_PROJECT : builds
    PROFILE ||--o{ PROFILE_CERTIFICATION : earns
    PROFILE ||--o| CAREER_PREFERENCE : sets
    USER ||--o{ CONNECTION : participates
    USER ||--o{ GLOBAL_POST : authors
    GLOBAL_POST ||--o{ GLOBAL_POST_COMMENT : receives
    GLOBAL_POST ||--o{ GLOBAL_POST_LIKE : receives
    USER ||--o{ DIRECT_CONVERSATION : starts
    DIRECT_CONVERSATION ||--o{ DIRECT_MESSAGE : contains
    USER ||--o{ COMMUNITY_MEMBERSHIP : joins
    COMMUNITY ||--o{ COMMUNITY_MEMBERSHIP : has
    COMMUNITY ||--o{ COMMUNITY_POST : contains
    USER ||--o{ RESOURCE : shares
    RESOURCE ||--o{ SAVED_RESOURCE : saved_by
    USER ||--o{ INTERVIEW_SESSION : completes
    INTERVIEW_SESSION ||--o{ INTERVIEW_QUESTION : contains
    INTERVIEW_QUESTION ||--o{ INTERVIEW_ANSWER : receives
    INTERVIEW_SESSION ||--o| INTERVIEW_REPORT : produces
~~~

The diagram is intentionally simplified. The complete schema is defined by SQLAlchemy models in backend/app/db/models.py and the Alembic migrations in backend/alembic/versions/.

## Development workflow

### Frontend

Run from frontend:

~~~bash
npm run dev
npm run lint
npm test
npm run test:ci
npm run build
npm run start
~~~

The Next.js App Router pages live under frontend/app. Feature components are grouped under frontend/components, while HTTP access is centralized in frontend/services/api.js.

### Backend

Run from backend with the virtual environment active:

~~~bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pytest
pytest -m integration
~~~

The backend uses Alembic migrations for schema evolution. Add a migration for persistent schema changes and keep Pydantic schemas, service logic, and route contracts aligned.

### Recommended change flow

1. Create a focused branch from the current development branch.
2. Make the smallest change that satisfies the feature or bug requirement.
3. Add or update the relevant frontend and backend tests.
4. Run lint, unit tests, build checks, and targeted integration tests.
5. Review the diff for secrets, unrelated changes, and API compatibility.
6. Open a pull request with behavior, test evidence, and migration notes.

## Testing

### Frontend checks

~~~bash
cd frontend
npm run lint
npm test
npm run test:ci
npm run build
~~~

Frontend tests use Jest, jsdom, and Testing Library. They cover major dashboard features including the home feed, communities, interview flows, messaging, networking, notifications, profile, resources, and settings.

### Backend checks

~~~bash
cd backend
pytest
~~~

The backend suite includes authentication, AI conversations, career matching, career knowledge, communities, messaging, presence, notifications, opportunities, posts, profile, resources, interviews, networking, vector foundations, and reliability coverage.

Integration tests that depend on PostgreSQL, Redis, Qdrant, MinIO, or model services require those services to be available and correctly configured. Use the project’s integration marker for targeted runs:

~~~bash
pytest -m integration
~~~

Do not treat a passing unit test run with mocked infrastructure as proof that every local service is configured correctly. Validate /api/health and exercise the relevant route when changing an integration boundary.

## Contributing

Contributions should preserve the project’s separation between deterministic domain logic and optional AI enhancements.

When opening a pull request:

- Describe the user-visible behavior and affected route or component.
- Include tests for new logic and regression coverage for fixes.
- Include an Alembic migration for schema changes.
- Document new environment variables in .env.example and this README.
- Avoid committing .env, credentials, model files, generated media, or local database data.
- Keep API behavior backward-compatible unless the change is explicitly versioned.
- Include manual verification steps for UI, WebSocket, model, or infrastructure changes.

## Roadmap

There is no separate committed roadmap file in the repository. The following items are reasonable next steps, not promises of a scheduled release:

- Add a documented production deployment profile with PostgreSQL included or explicitly provisioned.
- Add a first-class production observability and audit-log strategy.
- Formalize service contracts and generated API client typing.
- Expand integration-test orchestration for PostgreSQL, Redis, Qdrant, MinIO, and model providers.
- Add clearer model-provider health, timeout, and fallback diagnostics.
- Add repository-level CONTRIBUTING.md, SECURITY.md, and license files.
- Decide whether opportunity data should remain curated or gain a governed external ingestion path.

## Security

- Store secrets only in environment variables or a managed secret store.
- Generate a strong random SECRET_KEY for every deployed environment.
- Never commit .env, .env.local, API keys, SMTP passwords, JWT secrets, or production URLs.
- Use provider app passwords or scoped SMTP credentials instead of a personal mailbox password.
- Keep CORS_ORIGINS restricted to known application origins.
- Use HTTPS and secure cookie or token-delivery policies when deploying beyond local development.
- Review MinIO exposure before making MINIO_PUBLIC_URL public.
- Restrict Qdrant, Redis, MinIO, Ollama, and LanguageTool network access in deployed environments; local Compose defaults are intended for development.
- Preserve ownership checks on profile, post, resource, message, community, and interview operations.

No public security contact is defined in the repository yet. For a private report, contact the project maintainers through the repository’s private communication channel rather than posting sensitive details in a public issue.

## License

No LICENSE file was found in the repository at the time this README was written. Until the maintainers add a license, reuse and redistribution rights should be treated as unspecified. Add a license file and update this section before presenting the project as an open-source package.

## Acknowledgements

CareerSphere AI is built with open-source technologies including:

- [Next.js](https://nextjs.org/)
- [React](https://react.dev/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Alembic](https://alembic.sqlalchemy.org/)
- [PostgreSQL](https://www.postgresql.org/)
- [Redis](https://redis.io/)
- [Qdrant](https://qdrant.tech/)
- [MinIO](https://min.io/)
- [Ollama](https://ollama.com/)
- [Docker Compose](https://docs.docker.com/compose/)

See the dependency manifests for the complete list of direct and transitive packages used by the application.
