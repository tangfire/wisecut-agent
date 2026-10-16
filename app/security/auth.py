"""Authentication and authorization for Product API.

Uses JWT access tokens (short-lived) and refresh tokens (long-lived, revocable).
Passwords are hashed with bcrypt.

Product API auth is separate from MAA Compatibility API auth:
- Product API uses email/password login with JWT
- MAA API uses service-to-service headers (X-User-ID etc.)
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Request
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain-text password."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a hash."""
    return pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30


def _get_jwt_secret() -> str:
    """Get JWT secret from settings or environment."""
    secret = os.environ.get("JWT_SECRET_KEY") or getattr(settings, "jwt_secret_key", "")
    if not secret:
        # Dev fallback — NOT for production
        secret = "dev-jwt-secret-change-in-production"
        logger.warning("Using dev JWT secret — set JWT_SECRET_KEY in production")
    return secret


def create_access_token(user_id: str, email: str, extra: dict[str, Any] | None = None) -> str:
    """Create a short-lived JWT access token."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str, token_hash: str) -> str:
    """Create a JWT refresh token. token_hash is stored in DB for revocation."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": "refresh",
        "jti": token_hash,
        "iat": now,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token. Returns None if invalid."""
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_refresh_token_hash() -> str:
    """Generate a random hash for storing refresh tokens in DB."""
    return hashlib.sha256(secrets.token_bytes(32)).hexdigest()


# ---------------------------------------------------------------------------
# Current user extraction
# ---------------------------------------------------------------------------


def get_current_user_id(request: Request) -> str | None:
    """Extract user_id from the Authorization header JWT."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        return None
    return payload.get("sub")
