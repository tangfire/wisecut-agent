"""Synchronous application services for the API process.

These services use synchronous SQLAlchemy sessions (psycopg2/sqlite3) to
avoid the asyncpg event loop conflict under uvicorn/anyio in Docker.

The Worker process uses the async services in app/application/services.py
with asyncpg in its own dedicated event loop.

Architecture (plan.md section 10.1):
  API process  → sync DB access via app/persistence/sync_engine.py
  Worker process → async DB access via app/persistence/engine.py (asyncpg)
"""

from __future__ import annotations

import json
import logging
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.persistence.models import (
    Artifact,
    Asset,
    Conversation,
    Event,
    Message,
    Project,
    ProjectStatus,
    ProviderSetting,
    RefreshToken,
    Run,
    RunStatus,
    UserAccount,
    UserAccountStatus,
    Workspace,
)
from app.persistence.sync_engine import get_sync_session_factory
from app.protocol.sse import encode_sse_event, is_terminal_event

logger = logging.getLogger(__name__)


@contextmanager
def _sync_session() -> Generator[Any, None, None]:
    """Context manager for a synchronous DB session."""
    factory = get_sync_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Conversation Service (sync)
# ---------------------------------------------------------------------------

class APIConversationService:
    """Synchronous conversation service for the API process."""

    def create(
        self,
        title: str,
        user_id: str,
        project_id: str,
        profile_id: str = "one-click-quick",
        mode: str = "quick",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new conversation."""

        conversation_id = f"conv-{uuid4().hex[:12]}"
        meta = metadata or {}
        meta.update({
            "user_id": user_id,
            "project_id": project_id,
            "mode": mode,
            "agent_profile_id": profile_id,
        })

        with _sync_session() as session:
            conv = Conversation(
                id=conversation_id,
                user_id=user_id,
                project_id=project_id,
                profile_id=profile_id,
                title=title,
                status="created",
                metadata_json=meta,
            )
            session.add(conv)
            session.commit()
            session.refresh(conv)

        logger.info(
            "Conversation created (sync)",
            extra={"conversation_id": conversation_id},
        )
        return {
            "conversation_id": conv.id,
            "langgraph_thread_id": conv.id,
            "status": conv.status,
        }

    def get_by_id(self, conversation_id: str) -> Any | None:
        """Get conversation by ID."""
        with _sync_session() as session:
            return session.get(Conversation, conversation_id)

    def get_detail(self, conversation_id: str) -> dict[str, Any] | None:
        """Get conversation detail snapshot."""

        with _sync_session() as session:
            conv = session.get(Conversation, conversation_id)
            if conv is None:
                return None

            active_run = session.query(Run).filter(
                Run.conversation_id == conversation_id,
                Run.status.notin_(["completed", "failed", "cancelled"]),
            ).first()

            messages = session.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at.desc()).limit(50).all()

            return {
                "conversation": {
                    "id": conv.id,
                    "status": conv.status,
                    "metadata": conv.metadata_json or {},
                },
                "active_run": _serialize_run(active_run),
                "messages": [_serialize_message(m) for m in messages],
                "interactions": [],
                "recent_events": [],
            }


def _serialize_message(msg: Any) -> dict[str, Any]:
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "run_id": msg.run_id,
        "role": msg.role,
        "type": msg.type,
        "content": msg.content,
        "metadata": msg.metadata_json or {},
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


def _serialize_run(run: Any) -> dict[str, Any] | None:
    if run is None:
        return None
    return {
        "id": run.id,
        "conversation_id": run.conversation_id,
        "status": run.status,
        "phase": run.phase,
        "error": run.error_message or "",
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "ended_at": run.finished_at.isoformat() if run.finished_at else None,
    }


# ---------------------------------------------------------------------------
# Message Service (sync) — publishes to RabbitMQ
# ---------------------------------------------------------------------------

class APIMessageService:
    """API message service: publishes Run commands to RabbitMQ.

    The Worker process handles all database writes for messages.
    """

    def post_message(
        self,
        conversation_id: str,
        message_type: str,
        content: str | dict[str, Any],
        role: str = "user",
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Post a message: create Run and Message in DB, then publish to RabbitMQ."""
        from app.infra.messaging import publish_run_command
        from app.settings import settings

        run_id = f"run-{uuid4().hex[:12]}"
        message_id = f"msg-{uuid4().hex[:12]}"

        # Serialize dict content to JSON string for DB storage
        if isinstance(content, dict):
            content_str = json.dumps(content, ensure_ascii=False)
        else:
            content_str = content

        # Create Run and Message in database first (Worker needs Run to exist)
        with _sync_session() as session:
            from app.persistence.models import Message, Run
            run = Run(
                id=run_id,
                conversation_id=conversation_id,
                status="running",
                phase="starting",
                graph_thread_id=conversation_id,
            )
            session.add(run)
            msg = Message(
                id=message_id,
                conversation_id=conversation_id,
                run_id=run_id,
                role=role,
                type=message_type,
                content=content_str,
                metadata_json=metadata or {},
            )
            session.add(msg)
            session.commit()

        # Publish Run command to RabbitMQ
        import pika
        params = pika.URLParameters(settings.rabbitmq_url)
        with pika.BlockingConnection(params) as conn:
            ch = conn.channel()
            publish_run_command(
                ch,
                run_id=run_id,
                conversation_id=conversation_id,
                command_type=message_type,
                payload={
                    "content": content,
                    "message_id": message_id,
                    "message_type": message_type,
                    "role": role,
                    "request_id": request_id,
                    "metadata": metadata or {},
                },
            )

        logger.info(
            "Run command published (API->RabbitMQ)",
            extra={"run_id": run_id, "conversation_id": conversation_id},
        )
        return {
            "conversation_id": conversation_id,
            "run_id": run_id,
            "accepted_as_inbox": True,
            "events_url": f"/runs/{run_id}/events",
        }

    def post_interaction_response(
        self,
        conversation_id: str,
        run_id: str,
        interaction_id: str,
        action: str,
        content: Any,
        client_action_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Post interaction response: resolve interaction and publish to RabbitMQ."""
        from app.infra.messaging import publish_run_command
        from app.settings import settings

        # Resolve the interaction and find the original run_id
        with _sync_session() as session:
            from app.persistence.models import Interaction
            interaction = session.get(Interaction, interaction_id)
            if interaction is None:
                raise ValueError(f"Interaction not found: {interaction_id}")
            original_run_id = interaction.run_id
            interaction.status = "resolved"
            interaction.answer_json = {"action": action, "content": content}
            interaction.resolved_at = datetime.now(UTC)

            # Create message record
            message_id = f"msg-{uuid4().hex[:12]}"
            from app.persistence.models import Message
            msg = Message(
                id=message_id,
                conversation_id=conversation_id,
                run_id=original_run_id,
                role="user",
                type="interaction_response",
                content=content if isinstance(content, str) else json.dumps(content, ensure_ascii=False),
                metadata_json=metadata or {},
            )
            session.add(msg)
            session.commit()

        if isinstance(content, str):
            try:
                content_obj = json.loads(content)
            except json.JSONDecodeError:
                content_obj = {"value": content}
        else:
            content_obj = content

        request_id = f"interaction:{interaction_id}:{client_action_id}"
        payload = {
            "run_id": original_run_id,
            "conversation_id": conversation_id,
            "command_type": "interaction_response",
            "payload": {
                "interaction_id": interaction_id,
                "action": action,
                "content": content_obj,
                "client_action_id": client_action_id,
                "request_id": request_id,
                "metadata": {
                    "interaction_id": interaction_id,
                    "action": action,
                    "client_action_id": client_action_id,
                    **(metadata or {}),
                },
            },
        }

        import pika
        params = pika.URLParameters(settings.rabbitmq_url)
        with pika.BlockingConnection(params) as conn:
            ch = conn.channel()
            publish_run_command(
                ch,
                run_id=original_run_id,
                conversation_id=conversation_id,
                command_type="interaction_response",
                payload=payload,
            )

        logger.info(
            "Interaction response published",
            extra={"interaction_id": interaction_id, "run_id": original_run_id, "action": action},
        )

        return {
            "conversation_id": conversation_id,
            "run_id": original_run_id,
            "interaction_id": interaction_id,
            "accepted_as_inbox": True,
            "events_url": f"/runs/{original_run_id}/events",
        }


# ---------------------------------------------------------------------------
# Event Service (sync reads for SSE)
# ---------------------------------------------------------------------------

class APIEventService:
    """API event service: reads events from DB for SSE (sync)."""

    def get_events_for_sse(self, run_id: str, after_seq: int = 0) -> Generator[str, None, None]:
        """Generate SSE event stream for a run (sync)."""

        with _sync_session() as session:
            events = session.query(Event).filter(
                Event.run_id == run_id,
                Event.seq > after_seq,
            ).order_by(Event.seq.asc()).all()

            for event in events:
                sse = encode_sse_event(
                    event_id=event.id,
                    event_type=event.event_type,
                    data={
                        **event.payload_json,
                        "seq": event.seq,
                        "conversation_id": event.conversation_id,
                        "maa_run_id": run_id,
                    },
                )
                yield sse

                if is_terminal_event(event.event_type):
                    return

    def emit_event(
        self,
        conversation_id: str,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> int:
        """Emit a new event and persist it (sync)."""

        with _sync_session() as session:
            max_seq = session.query(Event.seq).filter(
                Event.run_id == run_id
            ).order_by(Event.seq.desc()).first()
            seq = (max_seq[0] + 1) if max_seq else 0

            event_id = f"evt-{uuid4().hex[:12]}"
            event = Event(
                id=event_id,
                conversation_id=conversation_id,
                run_id=run_id,
                seq=seq,
                event_type=event_type,
                payload_json=payload,
                visible=True,
            )
            session.add(event)
            session.commit()
            return seq


# ---------------------------------------------------------------------------
# WP-12: Product API Services (sync, psycopg2)
# ---------------------------------------------------------------------------


class APIUserService:
    """Synchronous user service for Product API authentication."""

    def register(self, email: str, password: str, display_name: str) -> dict[str, Any]:
        """Register a new user."""
        from app.security.auth import hash_password

        with _sync_session() as session:
            existing = session.query(UserAccount).filter(UserAccount.email == email.lower().strip()).first()
            if existing:
                raise ValueError("email already registered")

            user = UserAccount(
                id=f"usr-{__import__('uuid').uuid4().hex[:12]}",
                email=email.lower().strip(),
                password_hash=hash_password(password),
                display_name=display_name,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return {
                "id": user.id,
                "email": user.email,
                "display_name": user.display_name,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }

    def authenticate(self, email: str, password: str) -> dict[str, Any] | None:
        """Authenticate user with email/password. Returns user dict or None."""
        from app.security.auth import verify_password

        with _sync_session() as session:
            user = session.query(UserAccount).filter(UserAccount.email == email.lower().strip()).first()
            if user is None or user.status != UserAccountStatus.ACTIVE:
                return None
            if not verify_password(password, user.password_hash):
                return None
            self._update_last_login(session, user.id)
            return {
                "id": user.id,
                "email": user.email,
                "display_name": user.display_name,
            }

    def _update_last_login(self, session: Any, user_id: str) -> None:
        user = session.get(UserAccount, user_id)
        if user:
            user.last_login_at = datetime.now(UTC)
            session.commit()

    def store_refresh_token(self, user_id: str, token_hash: str, refresh_token: str) -> None:
        """Store a refresh token in DB."""
        from datetime import timedelta


        expires_at = datetime.now(UTC) + timedelta(days=30)
        with _sync_session() as session:
            rt = RefreshToken(
                id=f"rt-{__import__('uuid').uuid4().hex[:12]}",
                user_id=user_id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
            session.add(rt)
            session.commit()

    def get_refresh_token(self, token_hash: str) -> dict[str, Any] | None:
        """Get refresh token by hash."""

        with _sync_session() as session:
            rt = session.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
            if rt is None:
                return None
            return {
                "id": rt.id,
                "user_id": rt.user_id,
                "token_hash": rt.token_hash,
                "revoked": rt.revoked,
                "expires_at": rt.expires_at.isoformat() if rt.expires_at else None,
            }

    def revoke_refresh_token(self, token_hash: str) -> None:
        """Revoke a refresh token."""

        with _sync_session() as session:
            rt = session.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
            if rt:
                rt.revoked = True
                session.commit()


class APIProjectService:
    """Synchronous project service for Product API."""

    def get_default_workspace(self, user_id: str) -> str:
        """Get or create a default workspace for a user."""

        with _sync_session() as session:
            ws = session.query(Workspace).filter(Workspace.owner_user_id == user_id).first()
            if ws is None:
                ws = Workspace(
                    id=f"ws-{__import__('uuid').uuid4().hex[:12]}",
                    name="Default Workspace",
                    owner_user_id=user_id,
                )
                session.add(ws)
                session.commit()
                session.refresh(ws)
            return ws.id

    def create_project(self, workspace_id: str, name: str, description: str | None, created_by: str) -> Any:
        """Create a new project."""
        from app.persistence.models import Project

        with _sync_session() as session:
            project = Project(
                id=f"proj-{__import__('uuid').uuid4().hex[:12]}",
                workspace_id=workspace_id,
                name=name,
                description=description,
                created_by=created_by,
            )
            session.add(project)
            session.commit()
            session.refresh(project)
            return project

    def get_project(self, project_id: str) -> Any | None:
        """Get project by ID."""
        from app.persistence.models import Project

        with _sync_session() as session:
            return session.get(Project, project_id)

    def get_workspace(self, workspace_id: str) -> Any | None:
        """Get workspace by ID."""

        with _sync_session() as session:
            return session.get(Workspace, workspace_id)

    def list_projects(self, workspace_id: str, offset: int = 0, limit: int = 20) -> tuple[list[Any], int]:
        """List projects in a workspace with pagination."""
        from app.persistence.models import Project

        with _sync_session() as session:
            query = session.query(Project).filter(Project.workspace_id == workspace_id)
            total = query.count()
            projects = query.order_by(Project.updated_at.desc()).offset(offset).limit(limit).all()
            return projects, total

    def update_project(self, project_id: str, **kwargs: Any) -> Any | None:
        """Update project fields."""
        from app.persistence.models import Project

        with _sync_session() as session:
            project = session.get(Project, project_id)
            if project is None:
                return None
            for key, value in kwargs.items():
                if value is not None and hasattr(project, key):
                    setattr(project, key, value)
            session.commit()
            session.refresh(project)
            return project

    def delete_project(self, project_id: str) -> None:
        """Soft-delete a project."""
        with _sync_session() as session:
            project = session.get(Project, project_id)
            if project:
                project.status = ProjectStatus.DELETED
                session.commit()


class APIAssetService:
    """Synchronous asset service for Product API."""

    def verify_project_access(self, project_id: str, user_id: str) -> bool:
        """Verify user has access to the project's workspace."""
        from app.persistence.models import Project

        with _sync_session() as session:
            project = session.get(Project, project_id)
            if project is None:
                return False
            workspace = session.get(Workspace, project.workspace_id)
            return workspace is not None and workspace.owner_user_id == user_id

    def create_asset(
        self,
        project_id: str,
        name: str,
        asset_type: str,
        size_bytes: int,
        s3_key: str | None,
        s3_url: str | None,
        content_type: str | None = None,
    ) -> Any:
        """Create an asset record."""

        with _sync_session() as session:
            asset = Asset(
                id=f"ast-{__import__('uuid').uuid4().hex[:12]}",
                project_id=project_id,
                name=name,
                asset_type=asset_type,
                size_bytes=size_bytes,
                s3_key=s3_key,
                s3_url=s3_url,
                content_type=content_type,
            )
            session.add(asset)
            session.commit()
            session.refresh(asset)
            return asset

    def list_assets(
        self, project_id: str, asset_type: str | None = None, offset: int = 0, limit: int = 50
    ) -> tuple[list[Any], int]:
        """List assets in a project."""

        with _sync_session() as session:
            query = session.query(Asset).filter(Asset.project_id == project_id)
            if asset_type:
                query = query.filter(Asset.asset_type == asset_type)
            total = query.count()
            assets = query.order_by(Asset.created_at.desc()).offset(offset).limit(limit).all()
            return assets, total

    def get_bucket(self) -> str:
        """Get the S3 bucket name from settings."""
        from app.settings import settings
        return settings.s3_bucket


class APIRunService:
    """Synchronous run service for Product API."""

    def create_run(
        self,
        user_id: str,
        user_request: str,
        conversation_id: str | None = None,
        profile_id: str = "one-click-quick",
        product_link: str | None = None,
        input_files: list[str] | None = None,
    ) -> Any:
        """Create a new Agent Film run."""

        with _sync_session() as session:
            # Get or create conversation
            if conversation_id:
                conv = session.get(Conversation, conversation_id)
                if conv is None:
                    raise ValueError(f"conversation not found: {conversation_id}")
            else:
                conversation_id = f"conv-{__import__('uuid').uuid4().hex[:12]}"
                conv = Conversation(
                    id=conversation_id,
                    user_id=user_id,
                    project_id=self._get_default_project_id(session, user_id),
                    profile_id=profile_id,
                    title=user_request[:100],
                )
                session.add(conv)

            # Create run
            run = Run(
                id=f"run-{__import__('uuid').uuid4().hex[:12]}",
                conversation_id=conversation_id,
                status=RunStatus.QUEUED,
                graph_thread_id=conversation_id,
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return run

    def _get_default_project_id(self, session: Any, user_id: str) -> str:
        """Get or create a default project for a user."""
        from app.persistence.models import Project

        ws = session.query(Workspace).filter(Workspace.owner_user_id == user_id).first()
        if ws is None:
            ws = Workspace(
                id=f"ws-{__import__('uuid').uuid4().hex[:12]}",
                name="Default Workspace",
                owner_user_id=user_id,
            )
            session.add(ws)
            session.flush()

        proj = session.query(Project).filter(Project.workspace_id == ws.id).first()
        if proj is None:
            proj = Project(
                id=f"proj-{__import__('uuid').uuid4().hex[:12]}",
                workspace_id=ws.id,
                name="Default Project",
                created_by=user_id,
            )
            session.add(proj)
            session.flush()
        return proj.id

    def get_run(self, run_id: str) -> Any | None:
        """Get run by ID."""

        with _sync_session() as session:
            return session.get(Run, run_id)

    def verify_run_access(self, run_id: str, user_id: str) -> bool:
        """Verify user has access to the run's conversation."""

        with _sync_session() as session:
            run = session.get(Run, run_id)
            if run is None:
                return False
            conv = session.get(Conversation, run.conversation_id)
            return conv is not None and conv.user_id == user_id

    def verify_interaction_access(self, interaction_id: str, user_id: str) -> bool:
        """Verify user has access to the interaction's conversation."""
        from app.persistence.models import Interaction

        with _sync_session() as session:
            interaction = session.get(Interaction, interaction_id)
            if interaction is None:
                return False
            conv = session.get(Conversation, interaction.conversation_id)
            return conv is not None and conv.user_id == user_id

    def get_events_for_sse(self, run_id: str, after_seq: int = 0) -> Any:
        """Generate SSE events for a run."""

        with _sync_session() as session:
            events = session.query(Event).filter(
                Event.run_id == run_id,
                Event.seq > after_seq,
            ).order_by(Event.seq.asc()).all()

            for event in events:
                sse = encode_sse_event(
                    event_id=event.id,
                    event_type=event.event_type,
                    data={
                        **event.payload_json,
                        "seq": event.seq,
                        "conversation_id": event.conversation_id,
                        "maa_run_id": run_id,
                    },
                )
                yield sse

                if event.event_type in ("run.completed", "run.failed", "run.cancelled"):
                    return

    def request_cancel(self, run_id: str) -> None:
        """Request cancellation of a run."""

        with _sync_session() as session:
            run = session.get(Run, run_id)
            if run is None:
                raise ValueError("run not found")
            if run.status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED):
                raise ValueError(f"run is already in terminal state: {run.status}")
            run.status = RunStatus.CANCELLED
            run.finished_at = datetime.now(UTC)
            session.commit()

    def respond_to_interaction(self, interaction_id: str, response: dict[str, Any]) -> dict[str, Any]:
        """Submit a response to an interaction."""
        from app.persistence.models import Interaction

        with _sync_session() as session:
            interaction = session.get(Interaction, interaction_id)
            if interaction is None:
                raise ValueError(f"Interaction not found: {interaction_id}")
            interaction.status = "resolved"
            interaction.answer_json = response
            interaction.resolved_at = datetime.now(UTC)
            session.commit()

        return {
            "interaction_id": interaction_id,
            "status": "resolved",
        }


class APIArtifactService:
    """Synchronous artifact service for Product API."""

    def list_by_project(self, project_id: str, user_id: str) -> list[Any]:
        """List artifacts for a project."""
        with _sync_session() as session:
            # Artifact -> Run -> Conversation -> project_id
            artifacts = (
                session.query(Artifact)
                .join(Run, Artifact.run_id == Run.id)
                .join(Conversation, Run.conversation_id == Conversation.id)
                .filter(
                    Conversation.project_id == project_id,
                    Conversation.user_id == user_id,
                )
                .all()
            )
            return artifacts

    def get_artifact(self, artifact_id: str) -> Any | None:
        """Get artifact by ID."""

        with _sync_session() as session:
            return session.get(Artifact, artifact_id)

    def verify_artifact_access(self, artifact_id: str, user_id: str) -> bool:
        """Verify user has access to the artifact's conversation."""
        with _sync_session() as session:
            artifact = session.get(Artifact, artifact_id)
            if artifact is None:
                return False
            if artifact.project_id:
                # Check project ownership
                project = session.get(Project, artifact.project_id)
                if project:
                    workspace = session.get(Workspace, project.workspace_id)
                    return workspace is not None and workspace.owner_user_id == user_id
            return False

    def verify_project_access(self, project_id: str, user_id: str) -> bool:
        """Verify user has access to the project."""
        with _sync_session() as session:
            project = session.get(Project, project_id)
            if project is None:
                return False
            workspace = session.get(Workspace, project.workspace_id)
            return workspace is not None and workspace.owner_user_id == user_id

    def get_download_url(self, artifact_id: str) -> str | None:
        """Get presigned download URL for an artifact."""
        from app.infrastructure.storage import get_storage_client
        from app.settings import settings

        with _sync_session() as session:
            artifact = session.get(Artifact, artifact_id)
            if artifact is None or not artifact.s3_key:
                return None
            storage = get_storage_client()
            return storage.get_presigned_url(bucket=settings.s3_bucket, key=artifact.s3_key)


class APIProviderService:
    """Synchronous provider service for Product API."""

    def list_capabilities(self) -> list[dict[str, Any]]:
        """List available provider capabilities."""
        return [
            {"provider_type": "llm", "capabilities": ["chat", "structured_output", "streaming"]},
            {"provider_type": "video", "capabilities": ["render", "webhook", "cancel"]},
            {"provider_type": "material", "capabilities": ["search", "download"]},
            {"provider_type": "digital_human", "capabilities": ["match", "preview"]},
            {"provider_type": "tts", "capabilities": ["synthesize"]},
            {"provider_type": "research", "capabilities": ["product_lookup"]},
        ]

    def list_user_settings(self, user_id: str) -> list[Any]:
        """List provider settings for a user."""

        with _sync_session() as session:
            return session.query(ProviderSetting).filter(ProviderSetting.user_id == user_id).all()

    def set_config(self, user_id: str, provider_type: str, config: dict[str, Any], is_active: bool) -> Any:
        """Create or update a provider setting."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert


        with _sync_session() as session:
            stmt = (
                pg_insert(ProviderSetting)
                .values(
                    user_id=user_id,
                    provider_type=provider_type,
                    config_json=config,
                    is_active=is_active,
                )
                .on_conflict_do_update(
                    constraint="uq_provider_setting_user_type",
                    set_={"config_json": config, "is_active": is_active, "updated_at": datetime.now(UTC)},
                )
                .returning(ProviderSetting)
            )
            result = session.execute(stmt)
            setting = result.scalar_one()
            session.commit()
            return setting
