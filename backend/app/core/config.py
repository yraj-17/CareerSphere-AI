import json
from typing import List, Union
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
    EMBEDDING_DIMENSION: int = 768

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
        "You are CareerSphere AI, an AI career assistant. "
        "Help users with career development, resumes, interviews, skills, "
        "professional networking, job preparation and career planning. "
        "Be practical, concise and helpful. "
        "Use the conversation history to maintain context. "
        "Do not claim to know personal information that has not been provided."
    )
    AI_MAX_PROMPT_CHARS: int = 8000
    AI_CONTEXT_MESSAGES: int = 20
    AI_CONTEXT_CHARS: int = 16000

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

    @model_validator(mode="after")
    def normalize_urls(self) -> "Settings":
        self.DATABASE_URL = normalize_database_url(self.DATABASE_URL)
        return self

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
