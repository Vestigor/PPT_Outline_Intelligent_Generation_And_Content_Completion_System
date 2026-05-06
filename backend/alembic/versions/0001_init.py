"""init: create all tables and super_admin account

Revision ID: 0001
Revises:
Create Date: 2026-05-04
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# super_admin 初始账户（用户名: admin，密码: PPTAdmin@2026）
# 首次部署后请立即修改密码
_SUPER_ADMIN_USERNAME = "admin"
_SUPER_ADMIN_HASH = "$2a$12$jmjZhSXEs5BCAOkvQoIG5.wW4xoihwOVutbd.sDE7nCm4TRjtJ3zG"


def upgrade() -> None:
    # ── pgvector 扩展 ──────────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("email", sa.String(256), nullable=True),
        sa.Column("is_email_verified", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "role",
            sa.Enum("super_admin", "admin", "user", name="userrole"),
            nullable=False,
            server_default="user",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 插入 super_admin 初始账号（密码：PPTAdmin@2024，首次登录后请修改）
    op.execute(
        f"INSERT INTO users (username, email, is_email_verified, password_hash, is_active, role) "
        f"VALUES ('{_SUPER_ADMIN_USERNAME}', NULL, false, '{_SUPER_ADMIN_HASH}', true, 'super_admin')"
    )

    # ── email_verification_codes ───────────────────────────────────────────────
    op.create_table(
        "email_verification_codes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(256), nullable=False),
        sa.Column(
            "purpose",
            sa.Enum("register", "reset_password", name="emailcodepurpose"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_email_verification_codes_email", "email_verification_codes", ["email"])

    # ── llm_providers ──────────────────────────────────────────────────────────
    op.create_table(
        "llm_providers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("base_url", sa.String(512), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── llm_provider_models ────────────────────────────────────────────────────
    op.create_table(
        "llm_provider_models",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("provider_id", sa.Integer, sa.ForeignKey("llm_providers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_llm_provider_models_provider_id", "llm_provider_models", ["provider_id"])
    op.create_unique_constraint("uq_llm_provider_model", "llm_provider_models", ["provider_id", "model_name"])

    # ── user_llm_configs ───────────────────────────────────────────────────────
    op.create_table(
        "user_llm_configs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_model_id", sa.Integer, sa.ForeignKey("llm_provider_models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("api_key", sa.String(512), nullable=False),
        sa.Column("provider_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("model_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("base_url", sa.String(512), nullable=False, server_default=""),
        sa.Column("alias", sa.String(64), nullable=True),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_llm_configs_user_id", "user_llm_configs", ["user_id"])
    op.create_index("ix_user_llm_configs_provider_model_id", "user_llm_configs", ["provider_model_id"])
    op.create_unique_constraint("uq_user_llm_config", "user_llm_configs", ["user_id", "provider_model_id"])

    # ── user_rag_configs ───────────────────────────────────────────────────────
    op.create_table(
        "user_rag_configs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("api_key", sa.String(512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_rag_configs_user_id", "user_rag_configs", ["user_id"])

    # ── user_search_configs ────────────────────────────────────────────────────
    op.create_table(
        "user_search_configs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("api_key", sa.String(512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_search_configs_user_id", "user_search_configs", ["user_id"])

    # ── sessions ───────────────────────────────────────────────────────────────
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(256), nullable=False, server_default="未命名 PPT"),
        sa.Column(
            "session_type",
            sa.Enum("report_driven", "guided", name="sessiontype"),
            nullable=False,
            server_default="guided",
        ),
        sa.Column(
            "stage",
            sa.Enum(
                "requirement_collection",
                "outline_generation",
                "outline_confirming",
                "content_generation",
                "content_confirming",
                "completed",
                name="sessionstage",
            ),
            nullable=False,
            server_default="requirement_collection",
        ),
        sa.Column("requirements", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("requirements_complete", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("message_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "current_user_llm_config_id",
            sa.Integer,
            sa.ForeignKey("user_llm_configs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rag_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("deep_search_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_current_user_llm_config_id", "sessions", ["current_user_llm_config_id"])

    # ── messages ───────────────────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "role",
            sa.Enum("user", "assistant", "system", name="messagerole"),
            nullable=False,
        ),
        sa.Column("seq_no", sa.Integer, nullable=False, server_default="0"),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("outline_json", sa.JSON, nullable=True),
        sa.Column("slide_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])

    # ── tasks ──────────────────────────────────────────────────────────────────
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "requirement_collection",
                "outline_generation",
                "outline_modification",
                "slide_batch",
                "slide_modification",
                name="tasktype",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "streaming", "completed", "failed", "cancelled", name="taskstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("trigger_message_id", sa.Integer, nullable=True),
        sa.Column("result", sa.JSON, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("snapshot_llm_config_id", sa.Integer, nullable=True),
        sa.Column("snapshot_rag_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("snapshot_deep_search_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tasks_session_id", "tasks", ["session_id"])

    # ── session_reports ────────────────────────────────────────────────────────
    op.create_table(
        "session_reports",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(512), nullable=False),
        sa.Column("file_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("oss_key", sa.String(1024), nullable=False),
        sa.Column("clean_text", sa.Text, nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_session_reports_session_id", "session_reports", ["session_id"])
    op.create_index("ix_session_reports_content_hash", "session_reports", ["content_hash"])
    op.create_unique_constraint("uq_session_reports_session_id", "session_reports", ["session_id"])

    # ── outlines ───────────────────────────────────────────────────────────────
    op.create_table(
        "outlines",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("outline_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_outlines_session_id", "outlines", ["session_id"])

    # ── slides ─────────────────────────────────────────────────────────────────
    op.create_table(
        "slides",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("content", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_slides_session_id", "slides", ["session_id"])

    # ── knowledge_files ────────────────────────────────────────────────────────
    op.create_table(
        "knowledge_files",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(512), nullable=False),
        sa.Column("file_name", sa.String(512), nullable=False),
        sa.Column("file_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("oss_key", sa.String(1024), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "ready", "failed", name="documentstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_knowledge_files_user_id", "knowledge_files", ["user_id"])
    op.create_index("ix_knowledge_files_content_hash", "knowledge_files", ["content_hash"])

    # ── document_chunks ────────────────────────────────────────────────────────
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("knowledge_files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("total_chunk", sa.Integer, nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("chunk_metadata", sa.JSON, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])

    # ── session_knowledge_refs ─────────────────────────────────────────────────
    op.create_table(
        "session_knowledge_refs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_file_id", sa.Integer, sa.ForeignKey("knowledge_files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_session_knowledge_refs_session_id", "session_knowledge_refs", ["session_id"])
    op.create_unique_constraint(
        "uq_session_knowledge_refs", "session_knowledge_refs", ["session_id", "knowledge_file_id"]
    )


def downgrade() -> None:
    op.drop_table("session_knowledge_refs")
    op.drop_table("document_chunks")
    op.drop_table("knowledge_files")
    op.drop_table("slides")
    op.drop_table("outlines")
    op.drop_table("session_reports")
    op.drop_table("tasks")
    op.drop_table("messages")
    op.drop_table("sessions")
    op.drop_table("user_search_configs")
    op.drop_table("user_rag_configs")
    op.drop_table("user_llm_configs")
    op.drop_table("llm_provider_models")
    op.drop_table("llm_providers")
    op.drop_table("email_verification_codes")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS emailcodepurpose")
    op.execute("DROP TYPE IF EXISTS sessiontype")
    op.execute("DROP TYPE IF EXISTS sessionstage")
    op.execute("DROP TYPE IF EXISTS messagerole")
    op.execute("DROP TYPE IF EXISTS tasktype")
    op.execute("DROP TYPE IF EXISTS taskstatus")
    op.execute("DROP TYPE IF EXISTS documentstatus")
    op.execute("DROP EXTENSION IF EXISTS vector")
