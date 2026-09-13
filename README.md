# 🚀 CareerSphere AI

> **Next-Generation AI Career Intelligence & Professional Guidance Platform**

CareerSphere AI is an end-to-end, AI-powered career growth platform. This repository currently ships a working FastAPI + Next.js authentication stack on the poster data architecture: **PostgreSQL**, **Redis**, **Qdrant**, and **MinIO**.

---

## Architecture

```
Frontend (Next.js :3000)
        │
        ▼
FastAPI Backend (:8000)
        │
        ├── PostgreSQL (:5432)   → users, media metadata, relational app data
        ├── Redis (:6379)        → OTP / verification tokens + availability cache
        ├── Qdrant (:6333)       → embeddings / semantic search collections
        └── MinIO (:9000/:9001)  → resumes, profile images, media objects

Optional: Ollama (:11434) via `docker compose --profile ai up -d ollama`

Optional: LanguageTool (:8010) via `docker compose --profile languagetool up -d languagetool`
```

**SQLite is not used.** All relational data goes to PostgreSQL.

### Embeddings and Qdrant foundation

Embeddings convert text into numeric vectors so related career content can be found by meaning instead of exact keywords. CareerSphere uses Qdrant as the vector database for those embeddings. PostgreSQL remains the source of truth for users, profiles, conversations, and media metadata; Redis stores temporary cache/session-style data; Qdrant stores vectors plus small payloads that reference source records; Ollama/Qwen generates natural-language responses; the embedding model only performs text-to-vector conversion.

Default embedding runtime:

| Setting | Value |
| :--- | :--- |
| Provider | `ollama` |
| Model | `nomic-embed-text` |
| Dimension | Detected from the model at runtime unless `EMBEDDING_DIMENSION` is explicitly set |

Install the local embedding model once:

```bash
docker compose --profile ai up -d ollama
docker exec careersphere-ollama ollama pull nomic-embed-text
```

Initialize Qdrant collections with the actual embedding dimension:

```bash
cd backend
python -c "from app.services.qdrant_service import ensure_default_collections; ensure_default_collections()"
```

Run the real semantic-search proof test when Qdrant and Ollama are running:

```bash
cd backend
RUN_QDRANT_INTEGRATION=1 pytest tests/test_vector_foundation.py -m integration
```

That test embeds a small career-content dataset, upserts vectors into a temporary Qdrant collection, searches for `backend development using Python`, and verifies that backend/Python content is prioritized. Normal unit tests mock external services and do not require Qdrant or Ollama.

---

## Technology Stack

### Frontend
* Next.js 14 (App Router), React 18, Tailwind CSS, Framer Motion, Axios

### Backend
* FastAPI, Uvicorn, SQLAlchemy 2, Alembic, Pydantic v2
* PostgreSQL (`psycopg` v3), Redis, Qdrant, MinIO
* JWT (PyJWT) + Bcrypt auth

---

## Prerequisites

* Docker Desktop (for PostgreSQL, Redis, Qdrant, MinIO)
* Python 3.10+
* Node.js 18+
* Git

---

## Quick start

### 1) Start infrastructure (Docker)

From the project root:

```bash
docker compose up -d postgres redis qdrant minio
```

Optional local LLM:

```bash
docker compose --profile ai up -d ollama
```

Optional grammar service:

```bash
docker compose --profile languagetool up -d languagetool
```

LanguageTool is used only for grammar/spelling suggestions. The AI Career Assistant still goes through FastAPI → Ollama → Qwen.

### 2) Configure environment

```bash
# from project root
cp .env.example .env
# OR
cp backend/.env.example backend/.env
```

Edit `.env` and set at least:

* `DATABASE_URL` (PostgreSQL)
* `REDIS_URL`
* `SECRET_KEY`
* `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` (Gmail app password for signup OTP)
* MinIO keys if you changed the compose defaults

### 3) Backend setup

```bash
cd backend
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

Apply schema (pick one path on a fresh database):

```bash
# Option A — Alembic migrations (recommended for versioned schema)
alembic upgrade head
python -c "from app.services.qdrant_service import ensure_default_collections; from app.services.storage_service import ensure_bucket; ensure_default_collections(); ensure_bucket()"

# Option B — Bootstrap helper (creates tables + Qdrant collections + MinIO bucket)
python init_db.py
# If you used Option B first, sync Alembic's version table:
alembic stamp head
```

> Do not run `alembic upgrade head` after `init_db.py` without stamping — both create the same tables.

Start API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

* API: http://localhost:8000  
* Docs: http://localhost:8000/docs  
* Health: http://localhost:8000/api/health  

### 4) Frontend setup

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

* App: http://localhost:3000  

---

## Environment variables

See `.env.example` / `backend/.env.example` for the full list.

| Variable | Purpose |
| :--- | :--- |
| `DATABASE_URL` | PostgreSQL URL (`postgresql+psycopg://...`) |
| `REDIS_URL` | Redis URL (`redis://localhost:6379/0` from host) |
| `QDRANT_URL` | Qdrant HTTP URL |
| `QDRANT_API_KEY` | Optional Qdrant API key; blank for local Docker |
| `QDRANT_COLLECTION_PROFILES` | Profile embedding collection |
| `QDRANT_COLLECTION_CONTENT` | Content embedding collection |
| `EMBEDDING_PROVIDER` | Embedding runtime provider, default `ollama` |
| `EMBEDDING_MODEL` | Text embedding model, default `nomic-embed-text` |
| `EMBEDDING_DIMENSION` | Optional vector-size override; blank detects the actual model dimension |
| `MINIO_ENDPOINT` | MinIO API host:port |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | MinIO credentials |
| `MINIO_BUCKET` | Default bucket (`careersphere`) |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | Optional local LLM |
| `LANGUAGETOOL_URL` | Optional LanguageTool base URL (`http://localhost:8010`) |
| `SECRET_KEY` | JWT signing secret |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | SMTP for OTP |

When the backend runs **inside** Docker on the same compose network, use service hostnames (`postgres`, `redis`, `qdrant`, `minio`) instead of `localhost`.

---

## Docker services & ports

| Service | Container | Ports | Volume |
| :--- | :--- | :--- | :--- |
| PostgreSQL | `careersphere-postgres` | `5432` | `postgres_data` |
| Redis | `careersphere-redis` | `6379` | `redis_data` |
| Qdrant | `careersphere-qdrant` | `6333`, `6334` | `qdrant_data` |
| MinIO | `careersphere-minio` | `9000` (API), `9001` (console) | `minio_data` |
| Ollama (optional) | `careersphere-ollama` | `11434` | `ollama_data` |
| LanguageTool (optional) | `careersphere-languagetool` | `8010` | — |

MinIO console: http://localhost:9001 (default `minioadmin` / `minioadmin`)

---

## Data responsibilities

| Store | Holds |
| :--- | :--- |
| **PostgreSQL** | `users`, `media_objects`, `conversations`, `chat_messages` |
| **Redis** | OTP + email verification tokens; short-lived username/email availability cache |
| **Qdrant** | `user_profiles`, `career_content` vector collections for embeddings and semantic search |
| **MinIO** | Binary files (resumes, profile images, documents) |

---

## API surface (current)

### Auth
| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | PostgreSQL / Redis / Qdrant / MinIO status |
| `POST` | `/api/auth/send-otp` | Email OTP |
| `POST` | `/api/auth/verify-otp` | Verify OTP → registration token |
| `GET` | `/api/auth/check-username` | Username availability |
| `GET` | `/api/auth/check-email` | Email availability |
| `POST` | `/api/auth/register` | Create account |
| `POST` | `/api/auth/login` | JWT login |
| `GET` | `/api/auth/me` | Current user |
| `POST` | `/api/auth/logout` | Client logout ack |

### Media (MinIO)
| Method | Path | Description |
| :--- | :--- | :--- |
| `POST` | `/api/media/upload` | Upload file (multipart) |
| `GET` | `/api/media` | List current user media |
| `GET` | `/api/media/{id}/url` | Presigned URL |
| `GET` | `/api/media/{id}/download` | Download bytes |
| `DELETE` | `/api/media/{id}` | Delete object + metadata |

### AI Career Assistant
| Method | Path | Description |
| :--- | :--- | :--- |
| `POST` | `/api/ai/chat` | One-shot prompt (authenticated, no conversation history) |
| `GET` | `/api/ai/conversations` | List current user's conversations |
| `POST` | `/api/ai/conversations` | Create a conversation on the first message |
| `GET` | `/api/ai/conversations/{id}` | Conversation + messages (owner only) |
| `POST` | `/api/ai/conversations/{id}/messages` | Send a follow-up message |
| `POST` | `/api/ai/conversations/{id}/retry` | Retry AI reply after a failed generation |
| `DELETE` | `/api/ai/conversations/{id}` | Delete a conversation |
| `POST` | `/api/ai/grammar-check` | LanguageTool grammar/spelling suggestions |

---

## Testing

Infrastructure must be running (`postgres` + `redis` at minimum):

```bash
cd backend
pytest
```

---

## Repository structure

```
CareerSphere AI/
├── backend/
│   ├── app/
│   │   ├── api/           # Auth + media routes
│   │   ├── core/          # Settings & security
│   │   ├── db/            # SQLAlchemy models, session, Redis client
│   │   ├── services/      # Qdrant, MinIO, Redis cache helpers
│   │   ├── schemas/
│   │   └── main.py
│   ├── alembic/           # PostgreSQL migrations
│   ├── tests/
│   ├── init_db.py         # Bootstrap PG tables + Qdrant + MinIO
│   ├── requirements.txt
│   └── .env.example
├── frontend/              # Next.js app
├── ollama/                # Optional LLM image
├── docker-compose.yml     # postgres, redis, qdrant, minio, ollama
├── .env.example
└── README.md
```


---

## Phase 1 — Career Knowledge Base

### Purpose

The career knowledge base is the semantic retrieval layer for CareerSphere AI.
It converts structured domain/role/skill data into vector embeddings stored in
Qdrant, enabling future features like Skill Analysis, Skill Gap Detection, and
Career Readiness scoring to answer questions like:

> *"Given a user's profile skills, how close are they to a Data Scientist role?"*

The architectural flow is:

```
Structured career dataset  (backend/app/data/career_knowledge.py)
          ↓  build documents
Career indexing service    (backend/app/services/career_indexing_service.py)
          ↓  embed_texts (nomic-embed-text via Ollama)
Embedding service          (backend/app/services/embedding_service.py)
          ↓  upsert_vectors
Qdrant service             (backend/app/services/qdrant_service.py)
          ↓
Qdrant collection: career_content  (768-dim, cosine)
          ↓
Semantic retrieval  →  Phase 2: Skill Analysis + Skill Gap Detection
```

PostgreSQL remains the source of truth for **user** data.
Qdrant is the **semantic retrieval** layer for career knowledge.

---

### Supported Career Domains

| # | Domain |
|---|--------|
| 1 | Software Engineering & Technology |
| 2 | Cloud & DevOps |
| 3 | AI, Machine Learning & Data |
| 4 | Product & Business |
| 5 | Design & Creative |
| 6 | Marketing & Communications |
| 7 | Finance & Accounting |
| 8 | Human Resources |
| 9 | Sales & Business Development |
| 10 | Operations & Supply Chain |
| 11 | Education & Learning |
| 12 | Engineering |
| 13 | Healthcare & Health Administration |
| 14 | Legal, Compliance & Risk |

---

### Initial Roles (30)

| Domain | Roles |
|--------|-------|
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

---

### Skill Dataset Structure

Each skill in the catalog (`SKILLS` dict in `career_knowledge.py`) has:

```python
SkillEntry(
    id="postgresql",           # stable slug — used as Qdrant source_id
    name="PostgreSQL",         # display name
    category="database",       # broad grouping
    description="...",         # 1–3 sentence description (embedded as text)
    aliases=["Postgres"],      # obvious equivalents
)
```

Each role has:

```python
RoleEntry(
    id="backend-engineer",     # stable slug
    name="Backend Engineer",
    domain="Software Engineering & Technology",
    description="...",         # rich description (embedded as text)
    required_skills=["python", "rest_apis", "postgresql", ...],
    recommended_skills=["fastapi", "docker", "redis", ...],
)
```

---

### Qdrant Indexing Architecture

| Property | Value |
|----------|-------|
| Collection | `career_content` (`QDRANT_COLLECTION_CONTENT`) |
| Vector size | 768 (nomic-embed-text) |
| Distance | Cosine |
| Point ID scheme | Deterministic UUID5 keyed on `"{source_type}:{source_id}"` |
| Idempotency | Upsert overwrites same point IDs — safe to re-run |
| Coexistence | Does not delete or modify existing unrelated points |

**Role payload example:**
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

**Skill payload example:**
```json
{
  "source_type": "skill",
  "source_id": "python",
  "text": "Python: general-purpose programming language ...",
  "metadata": {
    "name": "Python",
    "category": "programming",
    "aliases": ["Python 3"]
  }
}
```

---

### Initialisation Command

Run once (or to re-index after dataset changes):

```bash
cd backend
python -m scripts.index_career_knowledge
```

Or from the project root:

```bash
python -m backend.scripts.index_career_knowledge
```

This will print a full summary report including collection, vector count,
embedding model, embedding dimension, and elapsed time.

**Prerequisites:**
- Qdrant container running: `docker compose up -d qdrant`
- Ollama running with nomic-embed-text: `docker compose --profile ai up -d ollama`
- Model pulled: `docker exec careersphere-ollama ollama pull nomic-embed-text`

---

### Re-indexing

The indexing process is fully idempotent.
Running the command multiple times is safe — it simply overwrites the same
deterministic point IDs in Qdrant with the same content.

It **never** deletes existing unrelated points (e.g. future user profile embeddings).

---

### Testing

Unit tests (no external services required):

```bash
cd backend
pytest tests/test_career_knowledge.py -v
```

Full regression suite:

```bash
cd backend
pytest tests/ -v
```

Real integration test (requires live Qdrant + Ollama + nomic-embed-text):

```bash
cd backend
$env:RUN_QDRANT_INTEGRATION="1"
pytest tests/test_career_knowledge.py -v -m integration
```

The integration test uses a temporary isolated collection (cleaned up after).
It verifies: embed → upsert → semantic search → correct role/skill payload →
idempotency on second run.

---

## License

Distributed under the MIT License.

---

<p align="center">
  Made with ❤️ by the <b>CareerSphere AI</b> Team
</p>
