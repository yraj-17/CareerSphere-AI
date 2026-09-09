from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine, Base
from app.db.models import User  # ensures models are registered with Base
from app.db.redis_client import ping_redis
from app.api.auth import router as auth_router
from app.schemas.auth import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    # Create all PostgreSQL tables if they don't exist yet
    Base.metadata.create_all(bind=engine)
    print("[Startup] PostgreSQL tables ready.")

    # Verify Redis is reachable
    if ping_redis():
        print("[Startup] Redis connection verified.")
    else:
        print("[Startup] WARNING: Redis is not reachable. OTP features will not work.")

    yield
    # --- Shutdown (nothing to clean up for now) ---


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
    """Health check — reports PostgreSQL and Redis connectivity."""
    # PostgreSQL
    pg_status = "connected"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        pg_status = f"error: {e}"

    # Redis
    redis_status = "connected" if ping_redis() else "unreachable"

    overall = "healthy" if pg_status == "connected" and redis_status == "connected" else "degraded"

    return HealthResponse(
        status=overall,
        message=f"PostgreSQL: {pg_status} | Redis: {redis_status}",
        service="CareerSphere AI Backend",
    )


app.include_router(auth_router, prefix=settings.API_V1_STR)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
