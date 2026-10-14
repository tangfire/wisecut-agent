"""OpenTelemetry tracing setup.

Provides:
  - Tracer provider initialization
  - FastAPI and SQLAlchemy instrumentation
  - Helper to create spans from code
  - Context propagation utilities
"""
from __future__ import annotations

import logging
from typing import Optional

from app.settings import settings

logger = logging.getLogger(__name__)

# Module-level flag
_tracer_provider_initialized: bool = False
_tracer = None


def setup_tracing(app: Optional[object] = None) -> None:
    """Initialize OpenTelemetry tracing.

    Called at application startup.  Instruments:
      - FastAPI (if app provided)
      - SQLAlchemy
      - HTTPX (outbound calls)
      - Redis (if available)
    """
    global _tracer_provider_initialized, _tracer

    if _tracer_provider_initialized:
        return

    endpoint = settings.otel_exporter_endpoint
    if not endpoint:
        logger.debug("OTEL exporter not configured, tracing disabled")
        _tracer_provider_initialized = True
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        resource = Resource.create({
            "service.name": settings.service_name,
            "service.version": settings.version,
            "deployment.environment": settings.app_env.value,
        })

        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        _tracer = trace.get_tracer(__name__)
        _tracer_provider_initialized = True

        # Instrument FastAPI if provided
        if app is not None:
            try:
                from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
                FastAPIInstrumentor().instrument_app(app)
            except ImportError:
                logger.warning("FastAPI OTel instrumentation not available")

        # Instrument SQLAlchemy
        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
            from app.persistence.engine import get_engine
            SQLAlchemyInstrumentor().instrument(engine=get_engine())
        except Exception as exc:
            logger.warning("SQLAlchemy OTel instrumentation failed", extra={"error": str(exc)})

        logger.info(
            "OpenTelemetry tracing initialized",
            extra={"endpoint": endpoint},
        )

    except ImportError:
        logger.warning("OpenTelemetry packages not installed, tracing disabled")
        _tracer_provider_initialized = True
    except Exception as exc:
        logger.warning("Failed to initialize tracing", extra={"error": str(exc)})
        _tracer_provider_initialized = True


def get_tracer():
    """Get the global tracer instance."""
    global _tracer
    if _tracer is None:
        try:
            from opentelemetry import trace
            _tracer = trace.get_tracer(__name__)
        except ImportError:
            _tracer = None
    return _tracer


def create_span(name: str, attributes: Optional[dict[str, str]] = None):
    """Create a span context manager.

    Usage:
        with create_span("tool.execute", {"tool": "search_materials"}) as span:
            # do work
            span.set_attribute("result_count", 3)
    """
    tracer = get_tracer()
    if tracer is None:
        return _NoOpSpan()

    return tracer.start_as_current_span(name, attributes=attributes or {})


class _NoOpSpan:
    """No-op span when tracing is not available."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def set_attribute(self, *args, **kwargs):
        pass

    def record_exception(self, *args, **kwargs):
        pass
