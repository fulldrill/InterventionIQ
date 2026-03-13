"""
Student Proficiency Insight Platform - FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import importlib

from core.config import settings
from routers import health

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

# Register required health router first so container health checks can pass
app.include_router(health.router, tags=["Health"])

# Optional routers can fail to import in partially provisioned environments.
OPTIONAL_ROUTERS = [
    ("routers.auth", "/auth", ["Authentication"]),
    ("routers.assessments", "/assessments", ["Assessments"]),
    ("routers.analytics", "/analytics", ["Analytics"]),
    ("routers.ai", "/ai", ["AI Assistant"]),
    ("routers.admin", "/admin", ["Administration"]),
]

for module_name, prefix, tags in OPTIONAL_ROUTERS:
    try:
        module = importlib.import_module(module_name)
        app.include_router(module.router, prefix=prefix, tags=tags)
    except Exception as exc:
        logger.warning("Skipping optional router %s: %s", module_name, exc)


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
