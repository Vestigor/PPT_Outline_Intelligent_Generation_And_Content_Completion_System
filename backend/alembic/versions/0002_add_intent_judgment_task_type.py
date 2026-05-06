"""add intent_judgment to tasktype enum

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-06
"""
from __future__ import annotations

from alembic import op


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block in older
    # PostgreSQL versions; commit first to be safe across environments.
    op.execute("COMMIT")
    op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'intent_judgment'")


def downgrade() -> None:
    # PostgreSQL has no native ALTER TYPE ... DROP VALUE.
    # Rolling back this migration would require recreating the enum and
    # rewriting every column that uses it — intentionally left as a no-op.
    pass
