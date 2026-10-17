"""Asset endpoints for Product API."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from app.application.sync_services import APIAssetService
from app.security.auth import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter()


class AssetResponse(BaseModel):
    id: str
    project_id: str
    name: str
    asset_type: str
    size_bytes: int
    s3_url: str | None
    content_type: str | None
    created_at: str


class AssetListResponse(BaseModel):
    items: list[AssetResponse]
    total: int
    offset: int
    limit: int


def _serialize_asset(a: Any) -> AssetResponse:
    return AssetResponse(
        id=a.id,
        project_id=a.project_id,
        name=a.name,
        asset_type=a.asset_type.value if hasattr(a.asset_type, "value") else str(a.asset_type),
        size_bytes=a.size_bytes,
        s3_url=a.s3_url,
        content_type=a.content_type,
        created_at=a.created_at.isoformat() if a.created_at else "",
    )


@router.get("/projects/{project_id}/assets", response_model=AssetListResponse, tags=["Assets"])
def list_assets(request: Request, project_id: str, asset_type: str | None = None, offset: int = 0, limit: int = 50) -> AssetListResponse:
    """List assets in a project."""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    service = APIAssetService()
    if not service.verify_project_access(project_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    assets, total = service.list_assets(project_id, asset_type=asset_type, offset=offset, limit=limit)
    return AssetListResponse(
        items=[_serialize_asset(a) for a in assets],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post("/projects/{project_id}/assets", response_model=AssetResponse, status_code=status.HTTP_201_CREATED, tags=["Assets"])
async def upload_asset(request: Request, project_id: str, file: UploadFile = File(...)) -> AssetResponse:
    """Upload an asset to a project."""
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    service = APIAssetService()
    if not service.verify_project_access(project_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    # Read file content
    content = await file.read()
    size_bytes = len(content)

    # Validate size (max 100MB)
    if size_bytes > 100 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file too large (max 100MB)")

    # Determine asset type from content-type
    content_type = file.content_type or "application/octet-stream"
    asset_type = _guess_asset_type(content_type)

    # Upload to S3-compatible storage
    from app.infrastructure.storage import upload_bytes
    s3_key = f"projects/{project_id}/assets/{__import__('uuid').uuid4().hex[:12]}-{file.filename}"
    s3_url = upload_bytes(
        bucket=service.get_bucket(),
        key=s3_key,
        data=content,
        content_type=content_type,
    )

    asset = service.create_asset(
        project_id=project_id,
        name=file.filename or s3_key,
        asset_type=asset_type,
        size_bytes=size_bytes,
        s3_key=s3_key,
        s3_url=s3_url,
        content_type=content_type,
    )
    return _serialize_asset(asset)


def _guess_asset_type(content_type: str) -> str:
    if content_type.startswith("image/"):
        return "image"
    if content_type.startswith("video/"):
        return "video"
    if content_type.startswith("audio/"):
        return "audio"
    return "other"
