"""Health check endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from core.database import get_db
import os

router = APIRouter()

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    System health check. Verifies DB connectivity, pgvector extension, and disk space.
    Used by Docker healthcheck and monitoring.
    """
    checks = {}

    # Database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"

    # pgvector extension
    try:
        result = await db.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        )
        checks["pgvector"] = "ok" if result.scalar() else "not_installed"
    except Exception:
        checks["pgvector"] = "error"

    # Disk space check
    try:
        stat = os.statvfs("/app/uploads")
        free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
        checks["disk_free_gb"] = round(free_gb, 2)
        checks["disk"] = "ok" if free_gb > 0.5 else "low"
    except Exception:
        checks["disk"] = "unknown"

    overall = "ok" if all(v == "ok" for k, v in checks.items() if k != "disk_free_gb") else "degraded"

    return {"status": overall, "checks": checks}
