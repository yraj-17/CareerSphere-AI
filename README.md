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

## License

Distributed under the MIT License.

---

<p align="center">
  Made with ❤️ by the <b>CareerSphere AI</b> Team
</p>
