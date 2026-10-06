# """FastAPI application entrypoint: app factory, lifespan, telemetry, routing."""

# from __future__ import annotations

# import logging
# from contextlib import asynccontextmanager

# from fastapi import FastAPI

# from app.api.v1.router import api_router
# from app.core.config import settings
# from app.core.database import dispose_engine
# from app.core.telemetry import setup_telemetry

# logging.basicConfig(
#     level=settings.log_level.upper(),
#     format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
# )
# logger = logging.getLogger(__name__)


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """Startup/shutdown hooks."""
#     logger.info("Starting %s (env=%s)", settings.app_name, settings.environment)
#     yield
#     logger.info("Shutting down; disposing database engine.")
#     await dispose_engine()


# def create_app() -> FastAPI:
#     app = FastAPI(
#         title=settings.app_name,
#         version="0.1.0",
#         description=(
#             "Account Servicing Entity for Interledger/Rafiki — double-entry ledger, "
#             "wallet provisioning, and HMAC-secured webhook processing."
#         ),
#         docs_url="/docs",
#         redoc_url="/redoc",
#         openapi_url="/openapi.json",
#         lifespan=lifespan,
#     )

#     app.include_router(api_router, prefix=settings.api_v1_prefix)

#     # Instrument last so routes are registered before FastAPI instrumentation.
#     setup_telemetry(app)

#     return app


# app = create_app()


"""FastAPI application entrypoint"""

