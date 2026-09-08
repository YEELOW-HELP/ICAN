"""MNP web sessions -- bearer auth for private user routes

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-09-01

Additive. `POST /v1/mnp/session` mints a random bearer token; only its
SHA-256 hash is stored here. Person KB private routes authenticate with
`Authorization: Bearer <token>` instead of trusting a client-supplied
`X-Mnp-User-Id`. Nothing existing is changed.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mnp_web_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_mnp_web_sessions_user_id"), "mnp_web_sessions", ["user_id"], unique=False)
    op.create_index(op.f("ix_mnp_web_sessions_token_hash"), "mnp_web_sessions", ["token_hash"], unique=False)


def downgrade() -> None:
    op.drop_table("mnp_web_sessions")
