"""FastAPI application entrypoint: app factory, lifespan, telemetry, routing."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.callbacks import router as callbacks_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import dispose_engine
from app.core.telemetry import setup_telemetry

logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hooks."""
    logger.info("Starting %s (env=%s)", settings.APP_NAME, settings.ENVIRONMENT)
    yield
    logger.info("Shutting down; disposing database engine.")
    await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        description=(
            "Account Servicing Entity for Interledger/Rafiki — double-entry ledger, "
            "wallet provisioning, and HMAC-secured webhook processing."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Allow the local frontend dev server (the frontend also ships a Vite proxy,
    # so this only matters when it calls the API origin directly).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    # Rafiki callbacks mount at the root — Rafiki is configured to call
    # /webhooks/rafiki and /rates directly, not under /api/v1.
    app.include_router(callbacks_router)

    # Instrument last so routes are registered before FastAPI instrumentation.
    setup_telemetry(app)

    return app


app = create_app()
