"""MAA service-to-service authentication (WP-10).

The MAA Compatibility API is consumed by the WiseCut Go backend.
All requests must carry a shared service token in the
`X-MAA-Service-Token` header.  The Go client already sets this
via its configuration; we validate it on every MAA route.

In `local-demo` environment the token check is relaxed so that
contract tests and local development work without configuring
a secret.  In staging/production the token MUST be set.
"""
from __future__ import annotations

import hmac

from fastapi import Request

from app.settings import Environment, settings


def _is_demo() -> bool:
    return settings.app_env == Environment.LOCAL_DEMO


def verify_maa_service_auth(request: Request) -> bool:
    """Return True when the request carries a valid service token."""
    if _is_demo():
        return True
    token = request.headers.get("X-MAA-Service-Token", "")
    expected = settings.maa_service_token
    if not expected:
        return False
    return hmac.compare_digest(token, expected)


def require_maa_auth(request: Request) -> None:
    """Raise 403 when service auth fails."""
    if not verify_maa_service_auth(request):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="invalid service token")


def get_verified_maa_user_id(request: Request) -> str:
    """Extract user_id from MAA headers.

    In demo mode returns the raw header value (may be empty for
    contract fixtures).  In staging/production the user_id MUST
    be present because service auth already passed.
    """
    user_id = getattr(request.state, "maa_user_id", "") or ""
    if _is_demo():
        return user_id
    if not user_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="X-User-ID header is required")
    return user_id


def get_verified_maa_project_id(request: Request) -> str:
    """Extract project_id from MAA headers."""
    project_id = getattr(request.state, "maa_project_id", "") or ""
    if _is_demo():
        return project_id
    if not project_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="X-Project-ID header is required")
    return project_id
