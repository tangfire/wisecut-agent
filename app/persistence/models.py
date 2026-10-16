"""Database models (SQLAlchemy ORM).

Core tables:
  conversation, run, message, event, interaction, approval,
  artifact, tool_execution, checkpoint, outbox_event, audit_log
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ConversationStatus(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    WAITING_INTERACTION = "waiting_interaction"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_INTERACTION = "waiting_interaction"
    WAITING_APPROVAL = "waiting_approval"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class ArtifactStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    EXPIRED = "expired"
    FAILED = "failed"


class EventSource(StrEnum):
    MAA = "maa"
    SYSTEM = "system"
    USER = "user"
    PROVIDER = "provider"


class Conversation(Base):
    __tablename__ = "conversation"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[ConversationStatus] = mapped_column(
        SAEnum(ConversationStatus), nullable=False, default=ConversationStatus.CREATED
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    runs: Mapped[list[Run]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    messages: Mapped[list[Message]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    events: Mapped[list[Event]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    interactions: Mapped[list[Interaction]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    approvals: Mapped[list[Approval]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    artifacts: Mapped[list[Artifact]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class Run(Base):
    __tablename__ = "run"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[RunStatus] = mapped_column(
        SAEnum(RunStatus), nullable=False, default=RunStatus.QUEUED
    )
    phase: Mapped[str | None] = mapped_column(String(64), nullable=True)
    graph_thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    conversation: Mapped[Conversation] = relationship(back_populates="runs")
    messages: Mapped[list[Message]] = relationship(back_populates="run", cascade="all, delete-orphan")
    events: Mapped[list[Event]] = relationship(back_populates="run", cascade="all, delete-orphan")
    interactions: Mapped[list[Interaction]] = relationship(back_populates="run", cascade="all, delete-orphan")
    approvals: Mapped[list[Approval]] = relationship(back_populates="run", cascade="all, delete-orphan")
    artifacts: Mapped[list[Artifact]] = relationship(back_populates="run", cascade="all, delete-orphan")
    tool_executions: Mapped[list[ToolExecution]] = relationship(back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("conversation_id", "id", name="uq_run_conversation_id"),
    )


class Message(Base):
    __tablename__ = "message"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("run.id", ondelete="SET NULL"), nullable=True, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant | system
    type: Mapped[str | None] = mapped_column(String(32), nullable=True)  # message | guidance | interaction_response
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    run: Mapped[Run | None] = relationship(back_populates="messages")

    __table_args__ = (
        UniqueConstraint("conversation_id", "request_id", name="uq_message_conversation_request_id"),
    )


class Event(Base):
    __tablename__ = "event"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default=EventSource.MAA)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    conversation: Mapped[Conversation] = relationship(back_populates="events")
    run: Mapped[Run] = relationship(back_populates="events")

    __table_args__ = (
        UniqueConstraint("conversation_id", "run_id", "seq", name="uq_event_conversation_run_seq"),
        UniqueConstraint("conversation_id", "run_id", "idempotency_key", name="uq_event_idempotency_key"),
    )


class Interaction(Base):
    __tablename__ = "interaction"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    intent: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    answer_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    conversation: Mapped[Conversation] = relationship(back_populates="interactions")
    run: Mapped[Run] = relationship(back_populates="interactions")


class Approval(Base):
    __tablename__ = "approval"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    arguments_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(
        SAEnum(ApprovalStatus), nullable=False, default=ApprovalStatus.PENDING
    )
    decision_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    conversation: Mapped[Conversation] = relationship(back_populates="approvals")
    run: Mapped[Run] = relationship(back_populates="approvals")


class Artifact(Base):
    __tablename__ = "artifact"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[ArtifactStatus] = mapped_column(
        SAEnum(ArtifactStatus), nullable=False, default=ArtifactStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    conversation: Mapped[Conversation] = relationship(back_populates="artifacts")
    run: Mapped[Run] = relationship(back_populates="artifacts")


class ToolExecution(Base):
    __tablename__ = "tool_execution"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    output_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    error_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    run: Mapped[Run] = relationship(back_populates="tool_executions")


class Checkpoint(Base):
    __tablename__ = "checkpoint"

    thread_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    checkpoint_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    parent_checkpoint_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    state_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OutboxEvent(Base):
    __tablename__ = "outbox_event"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    aggregate_type: Mapped[str] = mapped_column(String(32), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)  # user | system | agent
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# WP-12: Independent Product Domain Models
# ---------------------------------------------------------------------------

class UserAccountStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


class UserAccount(Base):
    __tablename__ = "user_account"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[UserAccountStatus] = mapped_column(
        SAEnum(UserAccountStatus), nullable=False, default=UserAccountStatus.ACTIVE
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    workspaces: Mapped[list[Workspace]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    provider_settings: Mapped[list[ProviderSetting]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Workspace(Base):
    __tablename__ = "workspace"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped[UserAccount] = relationship(back_populates="workspaces")
    projects: Mapped[list[Project]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class Project(Base):
    __tablename__ = "project"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus), nullable=False, default=ProjectStatus.ACTIVE
    )
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped[Workspace] = relationship(back_populates="projects")
    assets: Mapped[list[Asset]] = relationship(back_populates="project", cascade="all, delete-orphan")


class AssetType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    OTHER = "other"


class Asset(Base):
    __tablename__ = "asset"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(SAEnum(AssetType), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    s3_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    project: Mapped[Project] = relationship(back_populates="assets")


class ProviderType(StrEnum):
    LLM = "llm"
    VIDEO = "video"
    MATERIAL = "material"
    DIGITAL_HUMAN = "digital_human"
    TTS = "tts"
    RESEARCH = "research"


class ProviderSetting(Base):
    __tablename__ = "provider_setting"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_type: Mapped[ProviderType] = mapped_column(SAEnum(ProviderType), nullable=False)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[UserAccount] = relationship(back_populates="provider_settings")

    __table_args__ = (
        UniqueConstraint("user_id", "provider_type", name="uq_provider_setting_user_type"),
    )


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
