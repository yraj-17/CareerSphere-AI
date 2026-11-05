import json
from typing import List, Optional, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """Ensure SQLAlchemy uses the psycopg (v3) driver for PostgreSQL URLs."""
    if not url:
        return url
    # Guard against accidental "DATABASE_URL=DATABASE_URL=..." duplication in .env
    while url.startswith("DATABASE_URL="):
        url = url[len("DATABASE_URL=") :]
    if url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("sqlite"):
        raise ValueError(
            "SQLite is no longer supported. Set DATABASE_URL to a PostgreSQL URL "
            "(postgresql+psycopg://user:pass@host:5432/dbname)."
        )
    return url


class Settings(BaseSettings):
    PROJECT_NAME: str = "CareerSphere AI"
    API_V1_STR: str = "/api"

    # PostgreSQL (primary relational database)
    DATABASE_URL: str

    # Redis (cache / OTP / temporary state) — must run via Docker
    REDIS_URL: str = "redis://localhost:6379/0"

    # Qdrant (vector database)
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION_PROFILES: str = "user_profiles"
    QDRANT_COLLECTION_CONTENT: str = "career_content"
    QDRANT_COLLECTION_OPPORTUNITIES: str = "career_opportunities"
    EMBEDDING_PROVIDER: str = "ollama"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    EMBEDDING_DIMENSION: Optional[int] = None

    # MinIO (object storage)
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "careersphere"
    MINIO_SECURE: bool = False
    MINIO_PUBLIC_URL: str = ""  # optional override for browser-facing URLs

    # Ollama (local LLM — optional until AI features are wired)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3.5:9b"
    AI_SYSTEM_PROMPT: str = (
        "You are CareerSphere AI, a personalized AI career assistant. "
        "Help users with career development, resumes, interviews, skills, "
        "professional profiles, projects, professional networking, job preparation and career planning. "
        "The authenticated user's CareerSphere profile may be provided as context. "
        "Use profile context when it is relevant to the user's question. "
        "Do not invent skills, experience, education, projects, certifications, employers, or achievements. "
        "If profile information is missing, say what is missing and give practical next steps. "
        "Do not make hiring probability claims. "
        "Be practical, concise and helpful. "
        "Use the conversation history to maintain context. "
        "Do not claim to know personal information that has not been provided."
    )
    AI_MAX_PROMPT_CHARS: int = 8000
    AI_CONTEXT_MESSAGES: int = 20
    AI_CONTEXT_CHARS: int = 16000
    OLLAMA_TIMEOUT_SECONDS: float = 240.0
    OLLAMA_SKILL_GAP_TIMEOUT_SECONDS: float = 360.0
    # AI Interviewer — per-call model budget; each call is retried at most once.
    # The hosted model serves one request at a time and this budget includes time queued
    # behind other features' requests, so it matches the Career Assistant's budget
    # (OLLAMA_TIMEOUT_SECONDS) instead of being the shortest one (was 120 s).
    OLLAMA_INTERVIEW_TIMEOUT_SECONDS: float = 240.0
    INTERVIEW_AI_MAX_CONCURRENCY: int = 2
    # Follow-up questions after practical assessments: extra to the planned question count,
    # inside the existing interview time (the timer is never extended). 0 disables them.
    INTERVIEW_MAX_FOLLOW_UPS: int = 2
    INTERVIEW_FOLLOW_UP_MIN_REMAINING_SECONDS: int = 180
    # Answers that reach the backend within this window after the deadline are
    # still accepted (covers request latency); later submissions are rejected.
    INTERVIEW_SUBMISSION_GRACE_SECONDS: int = 15
    # Optional local Faster-Whisper transcription for voice interviews.
    # Empty model name disables transcription (voice mode is then unavailable).
    # Requires `pip install faster-whisper`; e.g. INTERVIEW_WHISPER_MODEL=base.en
    INTERVIEW_WHISPER_MODEL: str = ""
    INTERVIEW_WHISPER_DEVICE: str = "cpu"
    INTERVIEW_WHISPER_COMPUTE_TYPE: str = "int8"
    INTERVIEW_TRANSCRIPTION_TIMEOUT_SECONDS: float = 90.0
    INTERVIEW_MAX_AUDIO_BYTES: int = 8 * 1024 * 1024
    INTERVIEW_MAX_AUDIO_SECONDS: int = 180

    # Judge0 code execution (isolated CPU VM; never the app host or the Qwen server).
    # Backend-only: the token is never sent to the frontend or written to logs.
    # Empty URL/token means coding execution is unavailable (endpoints return 503).
    JUDGE0_API_URL: str = ""
    JUDGE0_AUTH_TOKEN: str = ""
    JUDGE0_CONNECT_TIMEOUT_SECONDS: float = 5.0
    JUDGE0_READ_TIMEOUT_SECONDS: float = 20.0
    JUDGE0_MAX_RETRIES: int = 2  # transient transport errors / 502-504 only
    JUDGE0_POLL_INTERVAL_SECONDS: float = 0.6
    # How long a request waits for results before returning "running" (the client
    # then polls the submission endpoint, which resumes from the stored Judge0 tokens).
    JUDGE0_INLINE_WAIT_SECONDS: float = 25.0
    JUDGE0_BATCH_SIZE: int = 20  # must not exceed MAX_SUBMISSION_BATCH_SIZE on the Judge0 host
    JUDGE0_LANGUAGES_CACHE_SECONDS: int = 600

    # Coding assessment limits (enforced by the backend; never taken from the client)
    CODING_MAX_SOURCE_BYTES: int = 64 * 1024
    CODING_MAX_CUSTOM_INPUT_BYTES: int = 16 * 1024
    CODING_RUN_RATE_LIMIT_PER_MINUTE: int = 10
    CODING_SUBMIT_RATE_LIMIT_PER_MINUTE: int = 4
    CODING_MAX_SUBMISSIONS_PER_QUESTION: int = 20
    CODING_INFLIGHT_LOCK_SECONDS: int = 120
    # Gemini (semantic reranking only; deterministic scores remain authoritative)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"
    GEMINI_RERANK_TIMEOUT_SECONDS: float = 20.0
    CAREER_MATCHING_CACHE_TTL_SECONDS: int = 900

    # ── Real job listings (Career Matching) ─────────────────────────────────
    # Backend-only. Credentials are never returned by any endpoint.
    # Company boards are "slug=Display Name" pairs separated by commas; every slug
    # must be a real, publicly published board (verify before adding one).
    JOB_GREENHOUSE_BOARDS: str = ""
    JOB_LEVER_BOARDS: str = ""
    JOB_ASHBY_BOARDS: str = ""
    # Only listings whose location mentions one of these keywords (case-insensitive)
    # are imported from company boards; empty = import every listing. Remote
    # listings open to India/APAC/worldwide are kept by the same keyword test.
    JOB_SYNC_LOCATION_KEYWORDS: str = (
        "india,bengaluru,bangalore,mumbai,pune,hyderabad,chennai,delhi,new delhi,"
        "gurgaon,gurugram,noida,kolkata,ahmedabad,jaipur,kochi,coimbatore,indore,chandigarh"
    )
    # Remote listings without a country restriction ("Remote", "Worldwide",
    # "Anywhere") are also imported when this is true.
    JOB_SYNC_INCLUDE_GLOBAL_REMOTE: bool = True
    # Automatic synchronisation runs inside the API process (asyncio task) and
    # uses a Redis lock so only one instance syncs at a time.
    JOB_SYNC_ENABLED: bool = True
    JOB_SYNC_INTERVAL_MINUTES: int = 360
    JOB_SYNC_ON_STARTUP: bool = True
    JOB_SYNC_HTTP_TIMEOUT_SECONDS: float = 30.0
    JOB_SYNC_MAX_LISTINGS_PER_SOURCE: int = 1500
    # Aggregator listings (Adzuna/Remotive) without an explicit expiry are
    # treated as inactive after this many days since posting.
    JOB_LISTING_MAX_AGE_DAYS: int = 45
    # Adzuna (requires a free developer account + a licence for commercial use).
    ADZUNA_APP_ID: str = ""
    ADZUNA_APP_KEY: str = ""
    ADZUNA_COUNTRY: str = "in"
    ADZUNA_QUERIES: str = "software developer,python developer,data analyst,devops engineer,frontend developer"
    ADZUNA_MAX_PAGES: int = 2
    # Remotive's public API terms forbid showing its listings to collect sign-ups,
    # and Career Matching is behind login, so it stays off until the operator has
    # Remotive's written permission (or its paid API).
    REMOTIVE_ENABLED: bool = False
    REMOTIVE_CATEGORIES: str = "software-dev,data,devops"
    # Comma-separated e-mail addresses allowed to use admin endpoints
    # (manual job sync, provider status).
    ADMIN_EMAILS: str = ""


    # LanguageTool (grammar / writing assistant — not the AI model)
    LANGUAGETOOL_URL: str = "http://localhost:8010"
    LANGUAGETOOL_LANGUAGE: str = "en-US"
    LANGUAGETOOL_TIMEOUT_SECONDS: float = 15.0

    # JWT Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # CORS
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000"]

    # Email / SMTP (Gmail)
    EMAIL_HOST: str = "smtp.gmail.com"
    EMAIL_PORT: int = 587
    EMAIL_HOST_USER: str = ""
    EMAIL_HOST_PASSWORD: str = ""

    # OTP settings
    OTP_EXPIRE_MINUTES: int = 10

    # Availability-check cache TTL (seconds)
    AVAILABILITY_CACHE_TTL: int = 60

    # WebSocket presence session TTL (seconds).
    # A session that has not been refreshed within this window will be
    # automatically expired by Redis.  The WS layer calls refresh_session()
    # on the interval below to keep active sessions alive.
    # Default: 90 s — gives a comfortable window for 30 s refresh intervals.
    REDIS_PRESENCE_TTL_SECONDS: int = 90

    # How often (seconds) the WebSocket layer refreshes an active presence
    # session.  Must be significantly less than REDIS_PRESENCE_TTL_SECONDS so
    # that a single missed refresh does not expire a live session.
    # Default: 30 s  (i.e. TTL/3 — three missed refreshes before expiry).
    REDIS_PRESENCE_REFRESH_INTERVAL_SECONDS: int = 30

    # Unique identifier for this FastAPI process/instance.
    # Used in Pub/Sub event metadata so consumers can distinguish the originating
    # instance.  Defaults to a stable random UUID generated at import time if
    # not provided via the environment.  Do NOT set this to a user ID or JWT.
    INSTANCE_ID: str = ""

    @model_validator(mode="after")
    def normalize_urls(self) -> "Settings":
        self.DATABASE_URL = normalize_database_url(self.DATABASE_URL)
        return self

    @field_validator("EMBEDDING_DIMENSION", mode="before")
    @classmethod
    def clean_embedding_dimension(cls, value):
        if value in ("", None):
            return None
        return value

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    return [i.strip() for i in v.strip("[]").split(",") if i.strip()]
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )


settings = Settings()
