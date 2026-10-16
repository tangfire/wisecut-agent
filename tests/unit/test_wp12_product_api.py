"""Unit tests for WP-12 Product API and domain models."""
from __future__ import annotations

import pytest

from app.graph.state import create_initial_state


# ---------------------------------------------------------------------------
# Model import tests
# ---------------------------------------------------------------------------


class TestWp12Models:
    def test_user_account_model_imports(self):
        from app.persistence.models import UserAccount, UserAccountStatus
        assert UserAccount is not None
        assert UserAccountStatus.ACTIVE == "active"

    def test_workspace_model_imports(self):
        from app.persistence.models import Workspace
        assert Workspace is not None

    def test_project_model_imports(self):
        from app.persistence.models import Project, ProjectStatus
        assert Project is not None
        assert ProjectStatus.ACTIVE == "active"

    def test_asset_model_imports(self):
        from app.persistence.models import Asset, AssetType
        assert Asset is not None
        assert AssetType.IMAGE == "image"

    def test_provider_setting_model_imports(self):
        from app.persistence.models import ProviderSetting, ProviderType
        assert ProviderSetting is not None
        assert ProviderType.LLM == "llm"

    def test_refresh_token_model_imports(self):
        from app.persistence.models import RefreshToken
        assert RefreshToken is not None


# ---------------------------------------------------------------------------
# Repository import tests
# ---------------------------------------------------------------------------


class TestWp12Repositories:
    def test_user_repository_imports(self):
        from app.persistence.repositories import UserAccountRepository
        assert UserAccountRepository is not None

    def test_workspace_repository_imports(self):
        from app.persistence.repositories import WorkspaceRepository
        assert WorkspaceRepository is not None

    def test_project_repository_imports(self):
        from app.persistence.repositories import ProjectRepository
        assert ProjectRepository is not None

    def test_asset_repository_imports(self):
        from app.persistence.repositories import AssetRepository
        assert AssetRepository is not None

    def test_provider_setting_repository_imports(self):
        from app.persistence.repositories import ProviderSettingRepository
        assert ProviderSettingRepository is not None

    def test_refresh_token_repository_imports(self):
        from app.persistence.repositories import RefreshTokenRepository
        assert RefreshTokenRepository is not None


# ---------------------------------------------------------------------------
# Auth module tests
# ---------------------------------------------------------------------------


class TestAuth:
    def test_hash_password(self):
        from app.security.auth import hash_password, verify_password
        hashed = hash_password("testpass123")
        assert hashed != "testpass123"
        assert verify_password("testpass123", hashed) is True
        assert verify_password("wrongpass", hashed) is False

    def test_create_and_decode_access_token(self):
        from app.security.auth import create_access_token, decode_token
        token = create_access_token(user_id="usr-123", email="test@example.com")
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "usr-123"
        assert payload["email"] == "test@example.com"
        assert payload["type"] == "access"

    def test_decode_invalid_token(self):
        from app.security.auth import decode_token
        payload = decode_token("invalid.token.here")
        assert payload is None

    def test_generate_refresh_token_hash(self):
        from app.security.auth import generate_refresh_token_hash
        h1 = generate_refresh_token_hash()
        h2 = generate_refresh_token_hash()
        assert h1 != h2
        assert len(h1) == 64  # SHA256 hex


# ---------------------------------------------------------------------------
# Product API router import tests
# ---------------------------------------------------------------------------


class TestProductAPI:
    def test_auth_router_imports(self):
        from app.api.product.auth import router
        assert router is not None

    def test_projects_router_imports(self):
        from app.api.product.projects import router
        assert router is not None

    def test_assets_router_imports(self):
        from app.api.product.assets import router
        assert router is not None

    def test_runs_router_imports(self):
        from app.api.product.runs import router
        assert router is not None

    def test_artifacts_router_imports(self):
        from app.api.product.artifacts import router
        assert router is not None

    def test_providers_router_imports(self):
        from app.api.product.providers import router
        assert router is not None
