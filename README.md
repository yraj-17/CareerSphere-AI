# CareerSphere AI

**AI-powered career and professional networking platform.**

CareerSphere AI helps users build professional profiles, analyze their skills, prepare for interviews, discover suitable opportunities, and receive personalized AI guidance.

## Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Repository Structure](#repository-structure)
5. [Getting Started](#getting-started)
6. [Configuration](#configuration)
7. [Docker Services](#docker-services)
8. [API Reference](#api-reference)
9. [Career Matching](#career-matching)
10. [Career Knowledge Base](#career-knowledge-base)
11. [Embeddings and Qdrant](#embeddings-and-qdrant)
12. [AWS Ollama Deployment](#aws-ollama-deployment)
13. [Testing](#testing)
14. [License](#license)

---

## Features

- Professional profile creation and management
- Email OTP authentication with JWT-based sessions
- AI Career Assistant with persistent conversations (optionally profile-aware)
- AI Profile Optimization
- Skill Analysis with deterministic Skill Gap Detection
- Qwen-generated skill priorities and career roadmap insights
- Career Matching: semantic retrieval + deterministic scoring + Gemini reranking + Qwen explanations
- Redis caching for expensive Career Matching responses
- MinIO storage for profile, document, and media files
- Grammar and spelling assistance via LanguageTool

---

## Architecture

### Design Principle

| Component | Responsibility |
| :--- | :--- |
| **PostgreSQL** | Source of truth for structured data |
| **Qdrant** | Semantic / vector retrieval |
| **Backend (FastAPI)** | Deterministic comparison and scoring |
| **Gemini** | Second-stage semantic reranking |
| **Qwen (Ollama)** | Grounded explanations and AI insights |
| **Redis** | Cache and temporary state (OTP, tokens) |
| **MinIO** | Object storage (resumes, images, documents) |
| **Next.js** | Presentation layer |

> SQLite is not used. All relational data lives in PostgreSQL.

### System Overview

```text
Frontend (Next.js :3000)
        │
        ▼
FastAPI Backend (:8000)
        │
        ├── PostgreSQL (:5432)    users, media metadata, conversations, messages
        ├── Redis (:6379)         OTP / verification tokens, availability cache
        ├── Qdrant (:6333)        embeddings and semantic search collections
        └── MinIO (:9000/:9001)   resumes, profile images, media objects

Optional
        ├── Ollama (:11434)       local LLM and embeddings   (profile: ai)
        └── LanguageTool (:8010)  grammar and spelling       (profile: languagetool)
```

### Data Responsibilities

| Store | Holds |
| :--- | :--- |
| PostgreSQL | `users`, `media_objects`, `conversations`, `chat_messages`, opportunities |
| Redis | OTP and email verification tokens, short-lived username/email availability cache, Career Matching response cache |
| Qdrant | `user_profiles` and `career_content` vector collections |
| MinIO | Binary files (resumes, profile images, documents) |

### Career Matching Flow

```text
Qdrant retrieves → Backend compares → Weighted algorithm ranks → Gemini reranks → Qwen explains → Frontend presents
```

See [Career Matching](#career-matching) for details.

---

## Tech Stack

**Frontend**
- Next.js 14 (App Router), React 18, Tailwind CSS, Framer Motion, Axios

**Backend**
- FastAPI, Uvicorn, SQLAlchemy 2, Alembic, Pydantic v2
- PostgreSQL (`psycopg` v3), Redis, Qdrant, MinIO
- JWT (PyJWT) + Bcrypt authentication

**AI**
- Ollama with Qwen (explanations, insights, chat)
- `nomic-embed-text` (embeddings)
- Gemini (Career Matching reranking)
- LanguageTool (grammar and spelling)

---

## Repository Structure

```text
CareerSphere-AI/
├── backend/
│   ├── app/
│   │   ├── api/            # Route handlers (auth, media, AI, matching)
│   │   ├── core/           # Settings and security
│   │   ├── data/           # Career knowledge dataset (career_knowledge.py)
│   │   ├── db/             # SQLAlchemy models, session, Redis client
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Qdrant, MinIO, embedding, indexing, cache helpers
│   │   └── main.py
│   ├── alembic/            # PostgreSQL migrations
│   ├── scripts/            # Seeding and indexing scripts
│   ├── tests/
│   ├── init_db.py          # Bootstrap: PG tables + Qdrant collections + MinIO bucket
│   ├── requirements.txt
│   └── .env.example
├── frontend/               # Next.js application
├── ollama/                 # Optional LLM image
├── docker-compose.yml      # postgres, redis, qdrant, minio, ollama, languagetool
├── .env.example
└── README.md
```

---

## Getting Started

### Prerequisites

- Docker Desktop
- Python 3.10+
- Node.js 18+
- Git

### 1. Start infrastructure

From the project root:

```bash
docker compose up -d postgres redis qdrant minio
```

Optional services:

```bash
# Local LLM and embeddings
docker compose --profile ai up -d ollama

# Grammar service
docker compose --profile languagetool up -d languagetool
```

LanguageTool is used only for grammar and spelling suggestions. The AI Career Assistant still goes through FastAPI → Ollama → Qwen.

### 2. Configure environment

```bash
# from project root
cp .env.example .env
# or
cp backend/.env.example backend/.env
```

At minimum, set `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, and `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` (Gmail app password for signup OTP). Update MinIO keys if you changed the compose defaults.

### 3. Set up the backend

```bash
cd backend
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

Apply the schema (choose **one** path on a fresh database):

```bash
# Option A: Alembic migrations (recommended, versioned schema)
alembic upgrade head
python -c "from app.services.qdrant_service import ensure_default_collections; from app.services.storage_service import ensure_bucket; ensure_default_collections(); ensure_bucket()"

# Option B: Bootstrap helper (tables + Qdrant collections + MinIO bucket)
python init_db.py
alembic stamp head    # sync Alembic's version table after Option B
```

> Do not run `alembic upgrade head` after `init_db.py` without stamping. Both create the same tables.

Start the API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

| Endpoint | URL |
| :--- | :--- |
| API | http://localhost:8000 |
| Docs | http://localhost:8000/docs |
| Health | http://localhost:8000/api/health |

### 4. Set up the frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

App: http://localhost:3000

---

## Configuration

See `.env.example` and `backend/.env.example` for the full list.

| Variable | Purpose |
| :--- | :--- |
| `DATABASE_URL` | PostgreSQL URL (`postgresql+psycopg://...`) |
| `REDIS_URL` | Redis URL (`redis://localhost:6379/0` from host) |
| `QDRANT_URL` | Qdrant HTTP URL |
| `QDRANT_API_KEY` | Optional; blank for local Docker |
| `QDRANT_COLLECTION_PROFILES` | Profile embedding collection |
| `QDRANT_COLLECTION_CONTENT` | Content embedding collection |
| `EMBEDDING_PROVIDER` | Embedding provider (default `ollama`) |
| `EMBEDDING_MODEL` | Embedding model (default `nomic-embed-text`) |
| `EMBEDDING_DIMENSION` | Optional override; blank detects the model dimension |
| `MINIO_ENDPOINT` | MinIO API host |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | MinIO credentials |
| `MINIO_BUCKET` | Default bucket (`careersphere`) |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | Local or remote LLM |
| `LANGUAGETOOL_URL` | LanguageTool base URL (`http://localhost:8010`) |
| `SECRET_KEY` | JWT signing secret |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | SMTP credentials for OTP |

When the backend runs **inside** Docker on the same compose network, use service hostnames (`postgres`, `redis`, `qdrant`, `minio`) instead of `localhost`.

---

## Docker Services

| Service | Container | Ports | Volume |
| :--- | :--- | :--- | :--- |
| PostgreSQL | `careersphere-postgres` | 5432 | `postgres_data` |
| Redis | `careersphere-redis` | 6379 | `redis_data` |
| Qdrant | `careersphere-qdrant` | 6333, 6334 | `qdrant_data` |
| MinIO | `careersphere-minio` | 9000 (API), 9001 (console) | `minio_data` |
| Ollama (optional) | `careersphere-ollama` | 11434 | `ollama_data` |
| LanguageTool (optional) | `careersphere-languagetool` | 8010 | none |

MinIO console: http://localhost:9001 (default `minioadmin` / `minioadmin`; change for any non-local use).

---

## API Reference

### Auth

| Method | Path | Description |
| :--- | :--- | :--- |
| GET | `/api/health` | PostgreSQL / Redis / Qdrant / MinIO status |
| POST | `/api/auth/send-otp` | Send email OTP |
| POST | `/api/auth/verify-otp` | Verify OTP and receive registration token |
| GET | `/api/auth/check-username` | Username availability |
| GET | `/api/auth/check-email` | Email availability |
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | JWT login |
| GET | `/api/auth/me` | Current user |
| POST | `/api/auth/logout` | Client logout acknowledgement |

### Media (MinIO)

| Method | Path | Description |
| :--- | :--- | :--- |
| POST | `/api/media/upload` | Upload file (multipart) |
| GET | `/api/media` | List current user's media |
| GET | `/api/media/{id}/url` | Presigned URL |
| GET | `/api/media/{id}/download` | Download bytes |
| DELETE | `/api/media/{id}` | Delete object and metadata |

### AI Career Assistant

| Method | Path | Description |
| :--- | :--- | :--- |
| POST | `/api/ai/chat` | One-shot prompt (authenticated, no history) |
| GET | `/api/ai/conversations` | List conversations |
| POST | `/api/ai/conversations` | Create a conversation on the first message |
| GET | `/api/ai/conversations/{id}` | Conversation with messages (owner only) |
| POST | `/api/ai/conversations/{id}/messages` | Send a follow-up message |
| POST | `/api/ai/conversations/{id}/retry` | Retry after a failed generation |
| DELETE | `/api/ai/conversations/{id}` | Delete a conversation |
| POST | `/api/ai/grammar-check` | LanguageTool grammar/spelling suggestions |

### AI Analysis

| Method | Path | Description |
| :--- | :--- | :--- |
| POST | `/api/ai/profile/optimize` | Structured profile quality analysis for the authenticated user |
| GET | `/api/skill-analysis/me` | Deterministic skill gap |
| GET | `/api/skill-analysis/me?include_ai=true` | Skill gap plus Qwen explanations and priorities |
| GET | `/api/career-matching/me` | Career Matching results |
| GET | `/api/career-matching/me?include_ai=true` | Career Matching plus Qwen explanations |

The user is always identified from the JWT.

---

## Career Matching

Career Matching answers: **"Which specific opportunities are suitable for my current profile?"**

### Pipeline

| Stage | Component | Output |
| :--- | :--- | :--- |
| 1. Retrieve | Qdrant | Top 30 candidates |
| 2. Score | Deterministic engine | Top 10 |
| 3. Rerank | Gemini | Top 5 |
| 4. Explain | Qwen | Strengths and skill gaps |
| 5. Cache | Redis | Short-TTL final response |

### Deterministic Weights

| Factor | Weight |
| :--- | :--- |
| Required Skills | 35% |
| Preferred Skills | 15% |
| Target Role | 15% |
| Career Preferences | 15% |
| Experience | 12% |
| Location / Remote | 8% |
| **Total** | **100%** |

### AI Responsibilities and Fallbacks

- Qdrant similarity is used for retrieval only; it is **not** the final match score.
- The deterministic engine calculates the actual structured match.
- Gemini receives the deterministic Top 10 and may only rerank them. It cannot add opportunities or replace deterministic scores.
- Qwen explains the final opportunities.
- If Gemini is unavailable, the deterministic Top 5 is returned.
- If Qwen is unavailable, opportunities are returned without AI explanations.

### Opportunity Dataset

The repository uses a curated development/demo dataset (not a live job-board integration):

- 60 opportunities, 296 required-skill rows, 203 preferred-skill rows
- Backend, Full Stack, Frontend, DevOps, Cloud, ML, Data, Product, and UI/UX roles
- Jobs and internships, remote and non-remote
- Intern, Entry Level, Junior, and Mid Level bands

Seed and index:

```bash
cd backend
python -m scripts.seed_opportunities
python -m scripts.index_opportunities
```

Re-index after reseeding, since Qdrant payloads store the PostgreSQL `opportunity_id`. Integrity check:

```text
Qdrant opportunity_id → PostgreSQL Opportunity.id → record exists → deterministic matching
```

---

## Career Knowledge Base

The semantic retrieval layer for Skill Analysis, Skill Gap Detection, and Career Readiness scoring. It answers questions like: *"Given a user's skills, how close are they to a Data Scientist role?"*

### Indexing Flow

```text
Structured dataset        backend/app/data/career_knowledge.py
        ↓ build documents
Career indexing service   backend/app/services/career_indexing_service.py
        ↓ embed_texts (nomic-embed-text via Ollama)
Embedding service         backend/app/services/embedding_service.py
        ↓ upsert_vectors
Qdrant service            backend/app/services/qdrant_service.py
        ↓
Collection: career_content (768-dim, cosine)
```

PostgreSQL remains the source of truth for user data; Qdrant is the retrieval layer for career knowledge.

### Supported Domains (14)

Software Engineering & Technology, Cloud & DevOps, AI/ML & Data, Product & Business, Design & Creative, Marketing & Communications, Finance & Accounting, Human Resources, Sales & Business Development, Operations & Supply Chain, Education & Learning, Engineering, Healthcare & Health Administration, Legal/Compliance & Risk.

### Initial Roles (30)

| Domain | Roles |
| :--- | :--- |
| Software Engineering & Technology | Backend Engineer, Full Stack Developer, Frontend Developer |
| Cloud & DevOps | DevOps Engineer, Cloud Engineer |
| AI, ML & Data | Machine Learning Engineer, Data Scientist, Data Analyst |
| Product & Business | Product Manager, Business Analyst |
| Design & Creative | UI/UX Designer, Product Designer |
| Marketing & Communications | Digital Marketing Specialist, Content Strategist |
| Finance & Accounting | Financial Analyst, Accountant |
| Human Resources | HR Specialist, Talent Acquisition Specialist |
| Sales & Business Development | Sales Executive, Business Development Manager |
| Operations & Supply Chain | Operations Manager, Supply Chain Analyst |
| Education & Learning | Teacher / Educator, Instructional Designer |
| Engineering | Mechanical Engineer, Civil Engineer, Electrical Engineer |
| Healthcare & Health Administration | Healthcare Administrator |
| Legal, Compliance & Risk | Compliance Analyst, Risk Analyst |

### Dataset Structure

```python
SkillEntry(
    id="postgresql",        # stable slug, used as Qdrant source_id
    name="PostgreSQL",
    category="database",
    description="...",      # 1-3 sentences, embedded as text
    aliases=["Postgres"],
)

RoleEntry(
    id="backend-engineer",
    name="Backend Engineer",
    domain="Software Engineering & Technology",
    description="...",      # embedded as text
    required_skills=["python", "rest_apis", "postgresql"],
    recommended_skills=["fastapi", "docker", "redis"],
)
```

### Qdrant Indexing Properties

| Property | Value |
| :--- | :--- |
| Collection | `career_content` (`QDRANT_COLLECTION_CONTENT`) |
| Vector size | 768 (`nomic-embed-text`) |
| Distance | Cosine |
| Point ID | Deterministic UUID5 of `"{source_type}:{source_id}"` |
| Idempotency | Upsert overwrites the same point IDs; safe to re-run |
| Coexistence | Never deletes or modifies unrelated points |

Example role payload:

```json
{
  "source_type": "role",
  "source_id": "backend-engineer",
  "text": "Backend Engineer (Software Engineering & Technology): ...",
  "metadata": {
    "name": "Backend Engineer",
    "domain": "Software Engineering & Technology",
    "required_skills": ["Python", "REST APIs", "PostgreSQL"],
    "recommended_skills": ["FastAPI", "Docker", "Redis"]
  }
}
```

Example skill payload:

```json
{
  "source_type": "skill",
  "source_id": "python",
  "text": "Python: general-purpose programming language ...",
  "metadata": { "name": "Python", "category": "programming", "aliases": ["Python 3"] }
}
```

### Run the Indexer

Prerequisites: Qdrant running, Ollama running, and `nomic-embed-text` pulled.

```bash
cd backend
python -m scripts.index_career_knowledge
# or from project root: python -m backend.scripts.index_career_knowledge
```

The command is idempotent and prints a summary (collection, vector count, embedding model, dimension, elapsed time).

---

## Embeddings and Qdrant

Embeddings convert text into vectors so related career content can be found by meaning rather than exact keywords. Qdrant stores vectors plus small payloads referencing source records. The embedding model only converts text to vectors; Ollama/Qwen generates natural-language responses.

| Setting | Value |
| :--- | :--- |
| Provider | `ollama` |
| Model | `nomic-embed-text` |
| Dimension | Detected at runtime unless `EMBEDDING_DIMENSION` is set |

Install the embedding model once:

```bash
docker compose --profile ai up -d ollama
docker exec careersphere-ollama ollama pull nomic-embed-text
```

Initialize Qdrant collections:

```bash
cd backend
python -c "from app.services.qdrant_service import ensure_default_collections; ensure_default_collections()"
```

---

## AWS Ollama Deployment

The LLM can run locally or be offloaded to an AWS GPU instance. Only the Ollama endpoint changes; the application architecture stays the same.

### Reference Setup

| Component | Value |
| :--- | :--- |
| Cloud / Service | AWS EC2 |
| Region | São Paulo (`sa-east-1`) |
| Instance | `g6.xlarge` |
| GPU | NVIDIA L4 (~24 GB VRAM) |
| OS | Ubuntu 24.04 |
| Runtime | Ollama |
| Model | `qwen3.8:27b` |

### Steps

**1. Launch the instance and verify the GPU**

```bash
ssh -i <your-key.pem> ubuntu@<EC2_PUBLIC_IP>
nvidia-smi
```

**2. Install Ollama and pull the model**

```bash
ollama --version
systemctl status ollama
ollama pull qwen3.8:27b
ollama list
```

**3. Configure Ollama for remote access** (systemd environment)

```text
OLLAMA_HOST=0.0.0.0:11434
OLLAMA_KEEP_ALIVE=-1
```

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
ss -lntp | grep 11434
```

**4. Test the remote API**

```bash
curl http://<EC2_PUBLIC_IP>:11434/api/generate \
  -d '{"model": "qwen3.8:27b", "prompt": "Explain what a Docker container is in one sentence.", "stream": false}'
```

**5. Point FastAPI at it**

```env
# Local
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3.8:27b

# AWS
OLLAMA_BASE_URL=http://<EC2_PUBLIC_IP>:11434
OLLAMA_MODEL=qwen3.8:27b
```

Restart FastAPI after changing the environment.

### Local vs AWS

```text
Local:  FastAPI → localhost:11434 → Ollama → Qwen
AWS:    FastAPI → EC2:11434 → Ollama → NVIDIA L4 → Qwen
```

Response time depends on model warm-up, prompt length, generated tokens, network latency, and GPU utilization.

### Security

Ollama has no built-in authentication. Do not expose port 11434 publicly in production.

- Restrict SSH access
- Restrict port 11434 to trusted sources
- Use a private network, VPN, firewall, or reverse proxy in production
- Never commit AWS keys, `.pem` files, Gemini keys, SMTP passwords, JWT secrets, or `.env` files
- Never place private API keys in frontend code

---

## Testing

Infrastructure must be running (`postgres` and `redis` at minimum). Unit tests mock external services and do not require Qdrant or Ollama.

```bash
cd backend

# Full suite
pytest

# Career knowledge unit tests
pytest tests/test_career_knowledge.py -v
```

Integration tests (require live Qdrant, Ollama, and `nomic-embed-text`; they use temporary isolated collections):

```bash
# macOS / Linux
RUN_QDRANT_INTEGRATION=1 pytest tests/test_vector_foundation.py -m integration
RUN_QDRANT_INTEGRATION=1 pytest tests/test_career_knowledge.py -v -m integration

# Windows PowerShell
$env:RUN_QDRANT_INTEGRATION="1"
pytest tests/test_vector_foundation.py -m integration
pytest tests/test_career_knowledge.py -v -m integration
```

The vector foundation test embeds a small career dataset, searches for `backend development using Python`, and verifies backend/Python content ranks first. The career knowledge test verifies embed → upsert → search → payload correctness → idempotency on a second run.

---

## License

Distributed under the MIT License.