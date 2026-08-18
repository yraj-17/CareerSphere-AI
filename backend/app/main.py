from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine, Base
from app.db.models import User  # Ensures models are registered
from app.api.auth import router as auth_router
from app.schemas.auth import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables on startup
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables initialized successfully.")
    except Exception as e:
        print(f"Warning: Could not auto-create tables on startup: {e}")
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="CareerSphere AI Backend API - Authentication and Career Intelligence Engine",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
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
    """
    Health check endpoint to verify backend server status and database connectivity.
    """
    db_status = "connected"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"database check failed: {str(e)}"

    return HealthResponse(
        status="healthy",
        message=f"CareerSphere AI API is operational ({db_status})",
        service="CareerSphere AI Backend"
    )


# Mount Authentication Router under /api/auth
app.include_router(auth_router, prefix=settings.API_V1_STR)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
