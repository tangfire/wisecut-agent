"""S3-compatible object storage client.

Wraps boto3 S3 client for MinIO/S3-compatible object storage.
"""
from __future__ import annotations

import logging
from typing import Any

from app.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy client
# ---------------------------------------------------------------------------

_client: Any = None


def get_storage_client() -> Any:
    """Get or create the S3-compatible storage client."""
    global _client
    if _client is None:
        import boto3
        from botocore.config import Config

        _client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(
                s3={"addressing_style": "path" if settings.s3_use_path_style else "virtual"},
            ),
        )
        logger.info("S3 storage client initialized", extra={"endpoint": settings.s3_endpoint})
    return _client


def reset_storage_client() -> None:
    """Reset the storage client (for testing)."""
    global _client
    _client = None


# ---------------------------------------------------------------------------
# High-level operations
# ---------------------------------------------------------------------------


def upload_bytes(bucket: str, key: str, data: bytes, content_type: str | None = None) -> str:
    """Upload bytes to S3 and return the public URL."""
    client = get_storage_client()
    extra: dict[str, Any] = {}
    if content_type:
        extra["ContentType"] = content_type
    client.put_object(Bucket=bucket, Key=key, Body=data, **extra)
    return f"{settings.s3_endpoint}/{bucket}/{key}"


def get_presigned_url(bucket: str, key: str, expires_in: int = 3600) -> str:
    """Generate a presigned URL for downloading an object."""
    client = get_storage_client()
    url: str = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )
    return url


def delete_object(bucket: str, key: str) -> None:
    """Delete an object from S3."""
    client = get_storage_client()
    client.delete_object(Bucket=bucket, Key=key)
