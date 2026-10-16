"""Provider endpoints for Product API."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.application.sync_services import APIProviderService
from app.security.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter()


class ProviderSettingResponse(BaseModel):
    provider_type: str
    config: dict[str, Any]
    is_active: bool


class ProviderSettingRequest(BaseModel):
    provider_type: str = Field(pattern="^(llm|video|material|digital_human|tts|research)$")
    config: dict[str, Any]
    is_active: bool = True


class ProviderCapabilityResponse(BaseModel):
    provider_type: str
    capabilities: list[str]


def _serialize_setting(s: Any) -> ProviderSettingResponse:
    return ProviderSettingResponse(
        provider_type=s.provider_type.value if hasattr(s.provider_type, "value") else str(s.provider_type),
        config=s.config_json or {},
        is_active=s.is_active,
    )


@router.get("/providers", response_model=list[ProviderCapabilityResponse], tags=["Providers"])
def list_provider_capabilities():
    """List available provider types and their capabilities."""
    service = APIProviderService()
    return service.list_capabilities()


@router.get("/provider-settings", response_model=list[ProviderSettingResponse], tags=["Providers"])
def list_my_provider_settings(request: Request):
    """List current user's provider settings."""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    service = APIProviderService()
    settings_list = service.list_user_settings(user_id)
    return [_serialize_setting(s) for s in settings_list]


@router.put("/provider-settings", response_model=ProviderSettingResponse, tags=["Providers"])
def set_provider_setting(request: Request, body: ProviderSettingRequest):
    """Create or update a provider setting."""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    service = APIProviderService()
    setting = service.set_config(user_id, body.provider_type, body.config, body.is_active)
    return _serialize_setting(setting)
