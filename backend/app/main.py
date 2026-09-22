from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine, Base
from app.db.models import User, MediaObject, Conversation, ChatMessage  # noqa: F401 — register models with Base
from app.db.redis_client import ping_redis
from app.api.auth import router as auth_router
from app.api.media import router as media_router
from app.api.ai import router as ai_router
from app.api.profile import router as profile_router
from app.api.skill_analysis import router as skill_analysis_router
from app.api.career_matching import router as career_matching_router
from app.api.networking import router as networking_router
from app.api.messaging import router as messaging_router
from app.schemas.auth import HealthResponse
from app.services.qdrant_service import ping_qdrant, ensure_default_collections
from app.services.storage_service import ping_minio, ensure_bucket


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    Base.metadata.create_all(bind=engine)
    print("[Startup] PostgreSQL tables ready.")

    if ping_redis():
        print("[Startup] Redis connection verified.")
    else:
        print("[Startup] WARNING: Redis is not reachable. OTP/cache features will not work.")

    if ping_qdrant():
        try:
            ensure_default_collections()
            print("[Startup] Qdrant connection verified.")
        except Exception as exc:
            print(f"[Startup] WARNING: Qdrant collections init failed: {exc}")
    else:
        print("[Startup] WARNING: Qdrant is not reachable. Vector search will not work.")

    if ping_minio():
        try:
            ensure_bucket()
            print("[Startup] MinIO connection verified.")
        except Exception as exc:
            print(f"[Startup] WARNING: MinIO bucket init failed: {exc}")
    else:
        print("[Startup] WARNING: MinIO is not reachable. File uploads will not work.")

    yield
    # --- Shutdown ---


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="CareerSphere AI Backend API – Authentication & Career Intelligence Engine",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
origins = settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    """Health check — reports PostgreSQL, Redis, Qdrant, and MinIO connectivity."""
    pg_status = "connected"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        pg_status = f"error: {e}"

    redis_status = "connected" if ping_redis() else "unreachable"
    qdrant_status = "connected" if ping_qdrant() else "unreachable"
    minio_status = "connected" if ping_minio() else "unreachable"

    core_ok = pg_status == "connected" and redis_status == "connected"
    all_ok = core_ok and qdrant_status == "connected" and minio_status == "connected"
    overall = "healthy" if all_ok else ("degraded" if core_ok else "unhealthy")

    return HealthResponse(
        status=overall,
        message=(
            f"PostgreSQL: {pg_status} | Redis: {redis_status} | "
            f"Qdrant: {qdrant_status} | MinIO: {minio_status}"
        ),
        service="CareerSphere AI Backend",
        postgres=pg_status,
        redis=redis_status,
        qdrant=qdrant_status,
        minio=minio_status,
    )


app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(media_router, prefix=settings.API_V1_STR)
app.include_router(ai_router, prefix=settings.API_V1_STR)
app.include_router(profile_router, prefix=settings.API_V1_STR)
app.include_router(skill_analysis_router, prefix=settings.API_V1_STR)
app.include_router(career_matching_router, prefix=settings.API_V1_STR)
app.include_router(networking_router, prefix=settings.API_V1_STR)
app.include_router(messaging_router, prefix=settings.API_V1_STR)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
