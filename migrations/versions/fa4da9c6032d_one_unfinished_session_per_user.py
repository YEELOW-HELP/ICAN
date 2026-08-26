"""Stage 1: enforce at most one unfinished session per user

Revision ID: fa4da9c6032d
Revises: cd3d7f6f9e54
Create Date: 2026-08-26

Founder decision from the Issue #1 readiness review (item 3): a user may
have at most one unfinished (draft/active/paused) InterviewSession at a
time -- enforced at the database level, not only by application code, so
a process-restart or a concurrent double /start cannot create two. This
is a partial unique index, not a plain UNIQUE(user_id): completed/failed
sessions are unbounded per user (retakes, history), only the "currently
in progress" set is constrained to size <= 1.

Purely additive: adds one index, drops nothing, touches no data.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "fa4da9c6032d"
down_revision: Union[str, None] = "cd3d7f6f9e54"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_one_unfinished_session_per_user",
        "interview_sessions",
        ["user_id"],
        unique=True,
        postgresql_where="status IN ('draft', 'active', 'paused')",
        sqlite_where="status IN ('draft', 'active', 'paused')",
    )


def downgrade() -> None:
    op.drop_index("uq_one_unfinished_session_per_user", table_name="interview_sessions")
