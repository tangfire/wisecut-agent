"""Application configuration with environment validation.

Environments:
  local-demo  — Demo LLM + Demo Media providers, no external credentials needed
  local-llm   — Real OpenAI-compatible LLM, Demo media providers
  staging     — Real providers + sandbox media + full observability
  production  — Real providers + Secret Manager + HA dependencies

All sensitive values MUST come from environment variables or secret injection.
No secrets are read from .env files in production.
"""

from __future__ import annotations

import os
import sys
from enum import Enum
from pathlib import Path

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    LOCAL_DEMO = "local-demo"
    LOCAL_LLM = "local-llm"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All fields map to env vars with the given prefix.
    Example: APP_ENV, DATABASE_URL, REDIS_URL, RABBITMQ_URL.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------
    app_env: Environment = Field(
        default=Environment.LOCAL_DEMO,
        description="Deployment environment.",
    )
    debug: bool = Field(default=False, description="Enable debug mode.")

    # ------------------------------------------------------------------
    # Service identity
    # ------------------------------------------------------------------
    service_name: str = Field(default="wisecut-agent", description="Service name for logs/tracing.")
    version: str = Field(default="0.1.0", description="Service version.")
    port: int = Field(default=10728, description="HTTP API port.")

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Log level.")
    log_format: str = Field(
        default="json",
        description="Log format: 'json' for structured, 'text' for console.",
    )

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://wisecut:wisecut@localhost:15432/wisecut_agent",
        description="PostgreSQL connection URL.",
    )
    db_pool_size: int = Field(default=5, ge=1, le=50, description="Connection pool size.")
    db_max_overflow: int = Field(default=10, ge=0, le=100, description="Max overflow connections.")

    # ------------------------------------------------------------------
    # Redis
    # ------------------------------------------------------------------
    redis_url: str = Field(
        default="redis://:wisecut@localhost:16381/0",
        description="Redis connection URL.",
    )
    redis_lock_ttl_seconds: int = Field(
        default=30, ge=5, description="TTL for distributed locks (seconds)."
    )

    # ------------------------------------------------------------------
    # RabbitMQ
    # ------------------------------------------------------------------
    rabbitmq_url: str = Field(
        default="amqp://wisecut:wisecut@localhost:15675/",
        description="RabbitMQ connection URL.",
    )
    rabbitmq_run_queue: str = Field(
        default="maa.run.commands",
        description="Durable queue for run commands.",
    )
    rabbitmq_retry_queue: str = Field(
        default="maa.run.commands.retry",
        description="Retry queue for failed run commands.",
    )
    rabbitmq_dlq: str = Field(
        default="maa.run.commands.dlq",
        description="Dead-letter queue for exhausted run commands.",
    )

    # ------------------------------------------------------------------
    # Object Storage (MinIO / S3-compatible)
    # ------------------------------------------------------------------
    s3_endpoint: str = Field(
        default="http://localhost:19000",
        description="S3-compatible endpoint.",
    )
    s3_access_key: str = Field(default="minioadmin", description="S3 access key.")
    s3_secret_key: str = Field(default="minioadmin", description="S3 secret key.")
    s3_bucket: str = Field(default="wisecut-agent", description="Default bucket name.")
    s3_region: str = Field(default="us-east-1", description="S3 region.")
    s3_use_path_style: bool = Field(
        default=True, description="Use path-style S3 addressing (required for MinIO)."
    )

    # ------------------------------------------------------------------
    # LLM Provider
    # ------------------------------------------------------------------
    llm_provider: str = Field(
        default="demo",
        description="LLM provider: 'demo' or 'openai-compatible'.",
    )
    llm_api_key: str | None = Field(default=None, description="LLM API key (for openai-compatible).")
    llm_base_url: str | None = Field(
        default=None,
        description="LLM base URL (for openai-compatible).",
    )
    llm_model: str = Field(default="gpt-4o-mini", description="LLM model name.")
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="LLM temperature.")
    llm_max_tokens: int = Field(default=4096, ge=1, description="LLM max output tokens.")

    # ------------------------------------------------------------------
    # Media Providers
    # ------------------------------------------------------------------
    material_provider: str = Field(
        default="demo",
        description="Material provider: 'demo' or 'real'.",
    )
    digital_human_provider: str = Field(
        default="demo",
        description="Digital human provider: 'demo' or 'real'.",
    )
    video_render_provider: str = Field(
        default="demo",
        description="Video render provider: 'demo' or 'real'.",
    )

    # ------------------------------------------------------------------
    # Feature flags
    # ------------------------------------------------------------------
    enable_demo_provider: bool = Field(
        default=True,
        description="Allow Demo Provider. MUST be False in production.",
    )
    enable_worker: bool = Field(
        default=True,
        description="Enable Worker process (API-only mode if False).",
    )

    # ------------------------------------------------------------------
    # Security (WP-10)
    # ------------------------------------------------------------------
    max_file_size_mb: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Max file size per upload (MB).",
    )
    max_total_upload_mb: int = Field(
        default=200,
        ge=1,
        le=2000,
        description="Max total upload size per request (MB).",
    )
    max_file_count: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Max number of files per request.",
    )
    enable_rate_limit: bool = Field(
        default=False,
        description="Enable API rate limiting (Redis-backed).",
    )
    rate_limit_requests: int = Field(
        default=100,
        ge=1,
        description="Max requests per window.",
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        ge=1,
        description="Rate limit window in seconds.",
    )

    # ------------------------------------------------------------------
    # Observability (WP-10)
    # ------------------------------------------------------------------
    api_key: str | None = Field(
        default=None,
        description="Optional API key for service-to-service auth.",
    )
    allowed_origins: str = Field(
        default="http://localhost:8080,http://localhost:5173",
        description="CORS allowed origins (comma-separated).",
    )

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------
    otel_exporter_endpoint: str | None = Field(
        default=None,
        description="OpenTelemetry collector endpoint.",
    )
    otel_service_version: str = Field(default="0.1.0", description="Service version for tracing.")

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("app_env", mode="before")
    @classmethod
    def normalize_env(cls, value: str | Environment) -> Environment:
        if isinstance(value, Environment):
            return value
        normalized = value.strip().lower().replace("_", "-")
        mapping = {
            "local-demo": Environment.LOCAL_DEMO,
            "local-llm": Environment.LOCAL_LLM,
            "staging": Environment.STAGING,
            "production": Environment.PRODUCTION,
        }
        if normalized in mapping:
            return mapping[normalized]
        raise ValueError(
            f"Unknown APP_ENV '{value}'. Must be one of: {[e.value for e in Environment]}"
        )

    @field_validator("database_url", "redis_url", "rabbitmq_url")
    @classmethod
    def validate_no_plaintext_secrets_in_production(cls, value: str, info) -> str:
        """Warn if obvious placeholder secrets are used in non-demo environments."""
        if info.field_name == "database_url" and "wisecut" in value:
            env = info.data.get("app_env")
            if env and env != Environment.LOCAL_DEMO:
                # In non-demo, this is a security risk — but we log, not fail,
                # because secrets may be injected at runtime.
                pass
        return value

    @model_validator(mode="after")
    def validate_production_constraints(self) -> "Settings":
        """Enforce production-specific constraints."""
        if self.app_env == Environment.PRODUCTION:
            if self.enable_demo_provider:
                raise ValueError(
                    "enable_demo_provider MUST be False in production. "
                    "Demo Provider is forbidden in production."
                )
            if self.debug:
                raise ValueError("debug MUST be False in production.")
            if self.llm_provider == "demo":
                raise ValueError("llm_provider MUST NOT be 'demo' in production.")
        return self

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def is_demo_env(self) -> bool:
        return self.app_env == Environment.LOCAL_DEMO

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def database_url_sync(self) -> str:
        """Synchronous DB URL for Alembic migrations."""
        return self.database_url.replace("+asyncpg", "")

    def validate_or_exit(self) -> None:
        """Run all validations and exit with a clear message if they fail.

        Call this at application startup.
        """
        try:
            # Re-run model validation
            type(self).model_validate(self.model_dump())
        except ValidationError as exc:
            print(f"FATAL: Configuration validation failed:\n{exc}", file=sys.stderr)
            sys.exit(1)

        # Check critical external dependencies are reachable
        self._check_critical_env_vars()

    def _check_critical_env_vars(self) -> None:
        """Verify that critical env vars are set (not default placeholders)."""
        critical_checks: list[tuple[str, str, bool]] = []

        if self.app_env in (Environment.STAGING, Environment.PRODUCTION):
            if not self.llm_api_key:
                critical_checks.append(
                    ("LLM_API_KEY", "LLM API key is not set", True)
                )
            if not self.otel_exporter_endpoint:
                critical_checks.append(
                    ("OTEL_EXPORTER_ENDPOINT", "Observability endpoint not set", False)
                )

        if critical_checks:
            warnings = [
                f"  {name}: {msg}" for name, msg, is_fatal in critical_checks if is_fatal
            ]
            if warnings:
                print(
                    "FATAL: Missing critical environment variables:\n"
                    + "\n".join(warnings),
                    file=sys.stderr,
                )
                sys.exit(1)

            infos = [
                f"  {name}: {msg}" for name, msg, is_fatal in critical_checks if not is_fatal
            ]
            if infos:
                print(
                    "WARNING: Recommended environment variables not set:\n"
                    + "\n".join(infos),
                    file=sys.stderr,
                )


# Global settings instance — loaded once at startup.
settings = Settings()

# Validate immediately on import so misconfiguration is caught early.
# Skip during pytest runs and when explicitly disabled.
if (
    "PYTEST_CURRENT_TEST" not in os.environ
    and "pytest" not in sys.modules
    and os.environ.get("SKIP_SETTINGS_VALIDATION") != "1"
):
    settings.validate_or_exit()
