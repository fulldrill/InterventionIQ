"""
Student Proficiency Insight Platform - FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from core.config import settings
from core.database import engine, Base
from routers import auth, assessments, analytics, ai, admin, health

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("SPIP API starting up...")
    # NOTE: Do NOT auto-create tables here in production. Use Alembic migrations.
    # await create_tables()
    yield
    logger.info("SPIP API shutting down...")


app = FastAPI(
    title="Student Proficiency Insight Platform API",
    description="Automated student math and literacy proficiency analysis with AI instructional insights.",
    version="1.0.0",
    lifespan=lifespan,
    # Disable OpenAPI in production
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
)

# CORS - restrict to frontend origin in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url] if settings.app_env == "production" else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Register routers
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(assessments.router, prefix="/assessments", tags=["Assessments"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(ai.router, prefix="/ai", tags=["AI Assistant"])
app.include_router(admin.router, prefix="/admin", tags=["Administration"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global error handler - never expose stack traces in production."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    if settings.app_env == "production":
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal error occurred. Please contact support."}
        )
    # Development: expose the error
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )
