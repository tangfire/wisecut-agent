"""Authentication endpoints for Product API.

Uses JWT access tokens (30min) and refresh tokens (30 days, revocable).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from app.application.sync_services import APIUserService
from app.persistence.models import UserAccount, UserAccountStatus
from app.security.auth import (
    create_access_token,
    create_refresh_token,
    generate_refresh_token_hash,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    display_name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800  # 30 minutes in seconds


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    created_at: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["Auth"])
def register(body: RegisterRequest):
    """Register a new user account."""
    service = APIUserService()
    try:
        user = service.register(
            email=body.email,
            password=body.password,
            display_name=body.display_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return UserResponse(
        id=user["id"],
        email=user["email"],
        display_name=user["display_name"],
        created_at=user.get("created_at"),
    )


@router.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(body: LoginRequest):
    """Login with email and password. Returns JWT access + refresh tokens."""
    service = APIUserService()
    user = service.authenticate(body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(user_id=user["id"], email=user["email"])
    token_hash = generate_refresh_token_hash()
    refresh_token = create_refresh_token(user_id=user["id"], token_hash=token_hash)

    service.store_refresh_token(
        user_id=user["id"],
        token_hash=token_hash,
        refresh_token=refresh_token,
    )

    logger.info("User logged in", extra={"user_id": user["id"], "email": user["email"]})
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/auth/refresh", response_model=TokenResponse, tags=["Auth"])
def refresh(body: RefreshRequest):
    """Refresh access token using a valid refresh token."""
    payload = __import__("app.security.auth", fromlist=["decode_token"]).decode_token(body.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid refresh token",
        )

    user_id = payload.get("sub")
    jti = payload.get("jti")
    if not user_id or not jti:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token payload")

    service = APIUserService()
    rt = service.get_refresh_token(jti)
    if rt is None or rt.get("revoked") or rt.get("expires_at", "") < datetime.now(UTC).isoformat():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="refresh token expired or revoked",
        )

    from app.persistence.sync_engine import get_sync_session_factory

    with get_sync_session_factory()() as session:
        user = session.get(UserAccount, user_id)
        if user is None or user.status != UserAccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found or inactive")

    access_token = create_access_token(user_id=user_id, email=user.email)
    return TokenResponse(access_token=access_token, refresh_token=body.refresh_token)


@router.get("/me", response_model=UserResponse, tags=["Auth"])
def get_me(request: Request):
    """Get current user info from access token."""
    from app.persistence.models import UserAccount
    from app.persistence.sync_engine import get_sync_session_factory
    from app.security.auth import get_current_user_id

    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    with get_sync_session_factory()() as session:
        user = session.get(UserAccount, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["Auth"])
def logout(request: Request, body: RefreshRequest | None = None):
    """Revoke refresh token (if provided) and logout."""
    from app.security.auth import decode_token, get_current_user_id

    user_id = get_current_user_id(request)
    if user_id and body and body.refresh_token:
        payload = decode_token(body.refresh_token)
        if payload and payload.get("type") == "refresh":
            jti = payload.get("jti", "")
            if jti:
                service = APIUserService()
                service.revoke_refresh_token(jti)
