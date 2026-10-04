"""Liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import text

from app.api.deps import DBSession
from app.core.config import settings

router = APIRouter()


@router.get("/health", summary="Liveness probe")
async def health() -> dict:
    """Return 200 if the process is up."""
    return {"status": "ok", "service": settings.otel_service_name, "environment": settings.environment}


@router.get("/health/ready", summary="Readiness probe")
async def ready(session: DBSession) -> dict:
    """Return 200 only if dependencies (the database) are reachable."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - surface any failure as not-ready
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database not ready: {exc}",
        ) from exc
    return {"status": "ready"}
