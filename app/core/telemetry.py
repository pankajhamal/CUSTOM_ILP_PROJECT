"""OpenTelemetry initialization.

Tracing is opt-in (``OTEL_ENABLED``). When disabled, :func:`setup_telemetry` is a
no-op and the OTel SDK imports are avoided so the service runs with zero overhead.
When enabled, it wires a tracer provider with an OTLP/gRPC exporter and installs
FastAPI + SQLAlchemy instrumentation.
"""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def setup_telemetry(app) -> None:  # noqa: ANN001 (FastAPI app, avoid import cycle)
    """Instrument the FastAPI app if ``OTEL_ENABLED`` is set; otherwise no-op."""
    if not settings.otel_enabled:
        logger.info("OpenTelemetry disabled (OTEL_ENABLED=false).")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:  # pragma: no cover - optional dependency
        logger.warning("OpenTelemetry packages missing; skipping instrumentation.")
        return

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
        )
    )
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    # Instrument the sync engine underlying our async engine.
    from app.core.database import engine

    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    logger.info(
        "OpenTelemetry enabled; exporting to %s", settings.otel_exporter_otlp_endpoint
    )
