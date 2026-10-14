"""Structured logging configuration.

All logs are JSON in non-debug mode. Sensitive fields are redacted.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC
from typing import Any

from app.settings import Environment, Settings

# Sensitive field names that must never appear in logs.
SENSITIVE_FIELDS: frozenset[str] = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "password",
        "secret",
        "token",
        "x-api-key",
        "x-auth-token",
        "llm_api_key",
        "s3_secret_key",
        "rabbitmq_password",
        "redis_password",
    }
)


class RedactingFormatter(logging.Formatter):
    """JSON log formatter that redacts sensitive fields."""

    def __init__(self, environment: str) -> None:
        super().__init__()
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": self._format_time(record.created),
            "level": record.levelname.lower(),
            "service": "wisecut-agent",
            "env": self.environment,
            "message": record.getMessage(),
        }

        # Add standard fields if present
        for field in ("trace_id", "request_id", "conversation_id", "run_id"):
            value = getattr(record, field, None)
            if value:
                log_entry[field] = value

        # Add extra fields, redacting sensitive ones
        extra = {
            k: v
            for k, v in record.__dict__.items()
            if k
            not in (
                "name",
                "msg",
                "args",
                "created",
                "relativeCreated",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "filename",
                "module",
                "pathname",
                "thread",
                "threadName",
                "process",
                "processName",
                "msecs",
                "levelname",
                "levelno",
                "taskName",
                "trace_id",
                "request_id",
                "conversation_id",
                "run_id",
            )
        }
        if extra:
            log_entry["data"] = self._redact(extra)

        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False, default=str)

    @staticmethod
    def _format_time(created: float) -> str:
        from datetime import datetime
        return datetime.fromtimestamp(created, tz=UTC).isoformat()

    @staticmethod
    def _redact(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                k: "***REDACTED***" if k.lower() in SENSITIVE_FIELDS else RedactingFormatter._redact(v)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [RedactingFormatter._redact(item) for item in obj]
        return obj


def setup_logging(settings: Settings) -> None:
    """Configure root logger based on settings."""
    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format == "json" or settings.app_env != Environment.LOCAL_DEMO:
        handler.setFormatter(RedactingFormatter(settings.app_env.value))
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root = logging.getLogger()
    root.setLevel(settings.log_level.value.upper())
    root.addHandler(handler)

    # Reduce noise from libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.WARNING if not settings.debug else logging.INFO
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class RequestContext:
    """Thread-local request context for trace_id and request_id."""

    _local: dict[str, Any] = {}

    @classmethod
    def set(cls, **kwargs: Any) -> None:
        cls._local.update(kwargs)

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        return cls._local.get(key, default)

    @classmethod
    def clear(cls) -> None:
        cls._local.clear()
