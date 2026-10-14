"""WiseCut MAA Agent — FastAPI application entry point.

Starts the API server on port 10728 with:
  GET  /health         — liveness probe
  GET  /ready          — readiness probe (checks dependencies)
  GET  /version        — service version
  POST /conversations  — create conversation
  ... (other MAA endpoints from WP-04+)
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.core.exceptions import MAAException
from app.settings import Settings
from app.core.logging import RequestContext, get_logger, setup_logging

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown hooks."""
    settings = app.state.settings
    logger.info(
        "Starting WiseCut MAA Agent",
        extra={
            "env": settings.app_env.value,
            "version": settings.version,
            "port": settings.port,
        },
    )
    yield
    logger.info("Shutting down WiseCut MAA Agent")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        from app.settings import settings as _settings
        settings = _settings

    setup_logging(settings)

    app = FastAPI(
        title="WiseCut MAA Agent API",
        description="MAA wire-compatible Agent Film service for WiseCut.",
        version=settings.version,
        lifespan=lifespan,
    )
    app.state.settings = settings

    # ---- Middleware ----
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        """Inject trace_id and request_id into request state and logs."""
        trace_id = request.headers.get("X-Trace-ID", str(__import__("uuid").uuid4()))
        request_id = request.headers.get("X-Request-ID", str(__import__("uuid").uuid4()))
        request.state.trace_id = trace_id
        request.state.request_id = request_id
        RequestContext.set(trace_id=trace_id, request_id=request_id)

        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                f"{request.method} {request.url.path} {response.status_code}",
                extra={
                    "trace_id": trace_id,
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Trace-ID"] = trace_id
            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                f"{request.method} {request.url.path} 500",
                extra={
                    "trace_id": trace_id,
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            raise
        finally:
            RequestContext.clear()

    # ---- Exception handlers ----
    @app.exception_handler(MAAException)
    async def maa_exception_handler(request: Request, exc: MAAException):
        error = exc.to_response()
        logger.warning(
            f"MAA error: {exc.detail}",
            extra={
                "trace_id": getattr(request.state, "trace_id", None),
                "request_id": getattr(request.state, "request_id", None),
                "error": error.model_dump(),
            },
        )
        return JSONResponse(status_code=exc.status_code, content=error.model_dump())

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Any):
        from app.core.exceptions import ErrorResponse
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                method=request.method,
                path=str(request.url.path),
                status_code=404,
                detail="not found",
            ).model_dump(),
        )

    # ---- Health endpoints ----
    @app.get("/health", tags=["Health"], summary="Liveness probe")
    async def health():
        """Liveness check — returns 200 if the process is running."""
        return {"status": "ok"}

    @app.get("/ready", tags=["Health"], summary="Readiness probe")
    async def ready(request: Request):
        """Readiness check — verifies critical dependencies are reachable."""
        checks: dict[str, Any] = {"status": "ready", "dependencies": {}}
        all_ready = True

        # Database check
        try:
            from sqlalchemy import text
            from app.persistence.engine import get_engine
            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["dependencies"]["database"] = {"status": "ok"}
        except Exception as exc:
            logger.warning(f"Readiness: database check failed: {exc}")
            checks["dependencies"]["database"] = {"status": "error", "detail": str(exc)}
            all_ready = False

        # Redis check
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.redis_url)
            await r.ping()
            await r.aclose()
            checks["dependencies"]["redis"] = {"status": "ok"}
        except Exception as exc:
            logger.warning(f"Readiness: redis check failed: {exc}")
            checks["dependencies"]["redis"] = {"status": "error", "detail": str(exc)}
            all_ready = False

        # RabbitMQ check
        try:
            import aio_pika
            connection = await aio_pika.connect_robust(settings.rabbitmq_url)
            await connection.close()
            checks["dependencies"]["rabbitmq"] = {"status": "ok"}
        except Exception as exc:
            logger.warning(f"Readiness: rabbitmq check failed: {exc}")
            checks["dependencies"]["rabbitmq"] = {"status": "error", "detail": str(exc)}
            all_ready = False

        checks["status"] = "ready" if all_ready else "degraded"
        status_code = 200 if all_ready else 503
        return JSONResponse(status_code=status_code, content=checks)

    @app.get("/version", tags=["Health"], summary="Service version")
    async def version(request: Request):
        """Return service version and environment."""
        return {
            "service": settings.service_name,
            "version": settings.version,
            "env": settings.app_env.value,
        }

    # ---- MAA API routers (stubs for WP-01 contract) ----
    from app.api import conversations, messages, runs, approvals, artifacts

    app.include_router(conversations.router, prefix="/conversations", tags=["Conversation"])
    app.include_router(messages.router, prefix="", tags=["Message"])
    app.include_router(runs.router, prefix="", tags=["Run"])
    app.include_router(approvals.router, prefix="", tags=["Approval"])
    app.include_router(artifacts.router, prefix="", tags=["Artifact"])

    logger.info(
        "MAA API routes registered",
        extra={
            "trace_id": None,
            "request_id": None,
            "routes": [r.path for r in app.routes],
        },
    )

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.value,
    )
