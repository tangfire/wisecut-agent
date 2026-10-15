"""WiseCut MAA Agent — FastAPI application entry point.

Starts the API server on port 10728 with:
  GET  /health         — liveness probe
  GET  /ready          — readiness probe (checks dependencies)
  GET  /version        — service version
  POST /conversations  — create conversation
  ... (other MAA endpoints from WP-04+)
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.exceptions import MAAException
from app.core.logging import RequestContext, get_logger, setup_logging
from app.settings import Settings

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown hooks.

    The API process uses synchronous SQLAlchemy with psycopg2 for database
    access, avoiding the asyncpg event loop conflict under uvicorn/anyio.
    The Worker process owns the async engine and asyncpg pool in its own
    dedicated event loop (plan.md section 10.1).
    """
    settings = app.state.settings
    logger.info(
        "Starting WiseCut MAA Agent (API only, sync DB)",
        extra={
            "env": settings.app_env.value,
            "version": settings.version,
            "port": settings.port,
        },
    )

    # Initialize synchronous database engine for API process
    if not settings.database_url.startswith("sqlite"):
        try:
            from app.persistence.sync_engine import get_sync_engine
            _ = get_sync_engine()
            logger.info("Sync database engine initialized")
        except Exception as exc:
            logger.warning("Sync database engine init deferred", extra={"error": str(exc)})

    try:
        yield
    finally:
        # Dispose sync engine on shutdown
        try:
            from app.persistence.sync_engine import close_sync_db
            close_sync_db()
        except Exception:
            pass
        logger.info("Shutting down WiseCut MAA Agent (API)")


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
    async def metrics_middleware(request: Request, call_next: Any) -> Any:
        """Record HTTP request metrics (skip health probes)."""
        from app.observability.metrics import metrics as collector
        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000
            # Skip metrics for health/ready endpoints to avoid event loop issues
            if request.url.path not in ("/health", "/ready", "/version"):
                collector.record_http_request(
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                )
            return response
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            if request.url.path not in ("/health", "/ready", "/version"):
                collector.record_http_request(
                    method=request.method,
                    path=request.url.path,
                    status_code=500,
                    duration_ms=duration_ms,
                )
            raise

    if settings.enable_rate_limit:
        @app.middleware("http")
        async def rate_limit_middleware(request: Request, call_next: Any) -> Any:
            """Simple per-user rate limiting."""
            from app.security.rate_limit import get_rate_limiter
            limiter = get_rate_limiter()
            user_id = getattr(request.state, "maa_user_id", "") or "anon"
            key = f"user:{user_id}"
            allowed, info = await limiter.is_allowed(
                key=key,
                limit=settings.rate_limit_requests,
                window_seconds=settings.rate_limit_window_seconds,
            )
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limit_exceeded",
                        "detail": f"Rate limit exceeded: {info['limit']} requests per {settings.rate_limit_window_seconds}s",
                        "reset_seconds": info["reset_seconds"],
                    },
                )
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(info["limit"])
            response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
            response.headers["X-RateLimit-Reset"] = str(info["reset_seconds"])
            return response

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next: Any) -> Any:
        """Inject trace_id, request_id, and MAA headers into request state and logs."""
        trace_id = request.headers.get("X-Trace-ID", str(__import__("uuid").uuid4()))
        request_id = request.headers.get("X-Request-ID", str(__import__("uuid").uuid4()))
        request.state.trace_id = trace_id
        request.state.request_id = request_id
        # MAA protocol headers (set by Go Client via setAgentFilmHeaders)
        request.state.maa_user_id = request.headers.get("X-User-ID", "")
        request.state.maa_project_id = request.headers.get("X-Project-ID", "")
        request.state.maa_conversation_id = request.headers.get("X-Conversation-ID", "")
        request.state.maa_run_id = request.headers.get("X-Run-ID", "")
        RequestContext.set(
            trace_id=trace_id,
            request_id=request_id,
            user_id=request.state.maa_user_id,
            project_id=request.state.maa_project_id,
        )

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
                    "maa_user_id": request.state.maa_user_id,
                    "maa_project_id": request.state.maa_project_id,
                },
            )
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Trace-ID"] = trace_id
            return response
        except Exception:
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
    async def maa_exception_handler(request: Request, exc: MAAException) -> JSONResponse:
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
    async def not_found_handler(request: Request, exc: Any) -> JSONResponse:
        from app.core.exceptions import ErrorResponse
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                method=request.method,
                path=str(request.url.path),
                status_code=404,
                body="not found",
            ).model_dump(),
        )

    # ---- Health endpoints ----
    @app.get("/health", tags=["Health"], summary="Liveness probe")
    async def health() -> dict[str, str]:
        """Liveness check — returns 200 if the process is running."""
        return {"status": "ok"}

    @app.get("/ready", tags=["Health"], summary="Readiness probe")
    async def ready(request: Request) -> JSONResponse:
        """Readiness check — verifies critical dependencies are reachable."""
        checks: dict[str, Any] = {"status": "ready", "dependencies": {}}
        all_ready = True

        # Database check (sync engine for API process)
        try:
            from sqlalchemy import text

            from app.persistence.sync_engine import get_sync_engine

            engine = get_sync_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
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
            await r.close()
            checks["dependencies"]["redis"] = {"status": "ok"}
        except Exception as exc:
            logger.warning(f"Readiness: redis check failed: {exc}")
            checks["dependencies"]["redis"] = {"status": "error", "detail": str(exc)}
            all_ready = False

        # RabbitMQ check (uses pika sync client in thread pool)
        try:
            import pika

            def _check_rmq() -> bool:
                params = pika.URLParameters(settings.rabbitmq_url)
                conn = pika.BlockingConnection(params)
                conn.close()
                return True

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _check_rmq)
            checks["dependencies"]["rabbitmq"] = {"status": "ok"}
        except Exception as exc:
            logger.warning(f"Readiness: rabbitmq check failed: {exc}")
            checks["dependencies"]["rabbitmq"] = {"status": "error", "detail": str(exc)}
            all_ready = False

        checks["status"] = "ready" if all_ready else "degraded"
        status_code = 200 if all_ready else 503
        return JSONResponse(status_code=status_code, content=checks)

    @app.get("/version", tags=["Health"], summary="Service version")
    async def version(request: Request) -> dict[str, Any]:
        """Return service version and environment."""
        return {
            "service": settings.service_name,
            "version": settings.version,
            "env": settings.app_env.value,
        }

    @app.get("/metrics", tags=["Health"], summary="Application metrics")
    async def metrics_endpoint(request: Request) -> dict[str, Any]:
        """Return application metrics in JSON format."""
        from app.observability.metrics import metrics as collector
        return collector.to_dict()

    # ---- MAA API routers (stubs for WP-01 contract) ----
    from app.api import approvals, artifacts, conversations, messages, runs

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
            "routes": [str(getattr(r, "path", r)) for r in app.routes],
        },
    )

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

app = create_app()


if __name__ == "__main__":
    import uvicorn

    _app_settings = app.state.settings
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=_app_settings.port,
        reload=_app_settings.debug,
        log_level=_app_settings.log_level.value,
    )
