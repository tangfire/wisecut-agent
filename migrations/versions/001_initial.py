"""Initial migration: create all core tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # conversation
    op.create_table(
        "conversation",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("profile_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="created"),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_conversation_user_id", "conversation", ["user_id"])
    op.create_index("ix_conversation_project_id", "conversation", ["project_id"])
    op.create_index("ix_conversation_status", "conversation", ["status"])

    # run
    op.create_table(
        "run",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(64), sa.ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("phase", sa.String(64), nullable=True),
        sa.Column("graph_thread_id", sa.String(64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_run_conversation_id", "run", ["conversation_id"])
    op.create_index("ix_run_status", "run", ["status"])
    op.create_unique_constraint("uq_run_conversation_id", "run", ["conversation_id", "id"])

    # message
    op.create_table(
        "message",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(64), sa.ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("run.id", ondelete="SET NULL"), nullable=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("type", sa.String(32), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_message_conversation_id", "message", ["conversation_id"])
    op.create_index("ix_message_run_id", "message", ["run_id"])
    op.create_index("ix_message_request_id", "message", ["request_id"])
    op.create_unique_constraint("uq_message_conversation_request_id", "message", ["conversation_id", "request_id"])

    # event
    op.create_table(
        "event",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(64), sa.ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload_json", JSONB, nullable=False),
        sa.Column("visible", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("source", sa.String(32), nullable=False, server_default="maa"),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_event_conversation_id", "event", ["conversation_id"])
    op.create_index("ix_event_run_id", "event", ["run_id"])
    op.create_index("ix_event_event_type", "event", ["event_type"])
    op.create_unique_constraint("uq_event_conversation_run_seq", "event", ["conversation_id", "run_id", "seq"])
    op.create_unique_constraint("uq_event_idempotency_key", "event", ["conversation_id", "run_id", "idempotency_key"])

    # interaction
    op.create_table(
        "interaction",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(64), sa.ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("intent", sa.String(64), nullable=False),
        sa.Column("payload_json", JSONB, nullable=False),
        sa.Column("answer_json", JSONB, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_interaction_conversation_id", "interaction", ["conversation_id"])
    op.create_index("ix_interaction_run_id", "interaction", ["run_id"])

    # approval
    op.create_table(
        "approval",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(64), sa.ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("arguments_json", JSONB, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("decision_json", JSONB, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_approval_conversation_id", "approval", ["conversation_id"])
    op.create_index("ix_approval_run_id", "approval", ["run_id"])

    # artifact
    op.create_table(
        "artifact",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(64), sa.ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_type", sa.String(64), nullable=False),
        sa.Column("uri", sa.Text, nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("payload_json", JSONB, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_artifact_conversation_id", "artifact", ["conversation_id"])
    op.create_index("ix_artifact_run_id", "artifact", ["run_id"])

    # tool_execution
    op.create_table(
        "tool_execution",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(64), nullable=False),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("input_json", JSONB, nullable=False),
        sa.Column("output_json", JSONB, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="1"),
        sa.Column("error_json", JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tool_execution_conversation_id", "tool_execution", ["conversation_id"])
    op.create_index("ix_tool_execution_run_id", "tool_execution", ["run_id"])

    # checkpoint
    op.create_table(
        "checkpoint",
        sa.Column("thread_id", sa.String(64), primary_key=True),
        sa.Column("checkpoint_id", sa.String(64), primary_key=True),
        sa.Column("parent_checkpoint_id", sa.String(64), nullable=True),
        sa.Column("state_json", JSONB, nullable=False),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # outbox_event
    op.create_table(
        "outbox_event",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("aggregate_type", sa.String(32), nullable=False),
        sa.Column("aggregate_id", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload_json", JSONB, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_outbox_event_aggregate_id", "outbox_event", ["aggregate_id"])
    op.create_index("ix_outbox_event_published_at", "outbox_event", ["published_at"])

    # audit_log
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(64), nullable=False),
        sa.Column("payload_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_log_actor", "audit_log", ["actor_type", "actor_id"])
    op.create_index("ix_audit_log_resource", "audit_log", ["resource_type", "resource_id"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("outbox_event")
    op.drop_table("checkpoint")
    op.drop_table("tool_execution")
    op.drop_table("artifact")
    op.drop_table("approval")
    op.drop_table("interaction")
    op.drop_table("event")
    op.drop_table("message")
    op.drop_table("run")
    op.drop_table("conversation")
