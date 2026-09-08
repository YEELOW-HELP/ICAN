"""MNP V1 Career KB — Pros/Cons + Career Path Steps + Career entry fields

Revision ID: f2c3d4e5a6b7
Revises: e1a2f3c4d5b6
Create Date: 2026-08-30

Additive. Founder Decisions §5 (structured Pros/Cons — not a generic
CareerAttribute) and §6 (ordered Career Path Steps — distinct from
CareerRelation), plus three entry-characteristic columns on `mnp_careers`
(moat doc §5 "Entry"). No existing table is dropped and no data migrated.
`entry_without_experience` back-fills existing rows to 'unknown' (Founder
Decision #27: UNKNOWN is first-class, never silently 'no').

Enum-backed columns are plain `String` (same convention as
`e1a2f3c4d5b6`).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2c3d4e5a6b7"
down_revision: Union[str, None] = "e1a2f3c4d5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("mnp_careers", sa.Column("difficulty_level", sa.String(length=16), nullable=True))
    op.add_column(
        "mnp_careers",
        sa.Column(
            "entry_without_experience", sa.String(length=16),
            nullable=False, server_default=sa.text("'unknown'"),
        ),
    )
    op.add_column("mnp_careers", sa.Column("typical_entry_route_uk", sa.Text(), nullable=True))

    op.create_table(
        "mnp_career_pros_cons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("text_uk", sa.Text(), nullable=False),
        sa.Column("text_en", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("review_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["mnp_careers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("career_id", "type", "sort_order", name="uq_career_procon_order"),
    )
    op.create_index(op.f("ix_mnp_career_pros_cons_career_id"), "mnp_career_pros_cons", ["career_id"], unique=False)
    op.create_index(op.f("ix_mnp_career_pros_cons_type"), "mnp_career_pros_cons", ["type"], unique=False)

    op.create_table(
        "mnp_career_path_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_id", sa.Uuid(), nullable=False),
        sa.Column("path_code", sa.String(length=64), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_name_uk", sa.String(length=255), nullable=False),
        sa.Column("step_name_en", sa.String(length=255), nullable=True),
        sa.Column("step_type", sa.String(length=16), nullable=False),
        sa.Column("description_uk", sa.Text(), nullable=True),
        sa.Column("description_en", sa.Text(), nullable=True),
        sa.Column("typical_experience_text_uk", sa.String(length=128), nullable=True),
        sa.Column("is_current_career_step", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=True),
        sa.Column("review_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["mnp_careers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("career_id", "path_code", "step_order", name="uq_career_path_step_order"),
    )
    op.create_index(op.f("ix_mnp_career_path_steps_career_id"), "mnp_career_path_steps", ["career_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_mnp_career_path_steps_career_id"), table_name="mnp_career_path_steps")
    op.drop_table("mnp_career_path_steps")
    op.drop_index(op.f("ix_mnp_career_pros_cons_type"), table_name="mnp_career_pros_cons")
    op.drop_index(op.f("ix_mnp_career_pros_cons_career_id"), table_name="mnp_career_pros_cons")
    op.drop_table("mnp_career_pros_cons")
    op.drop_column("mnp_careers", "typical_entry_route_uk")
    op.drop_column("mnp_careers", "entry_without_experience")
    op.drop_column("mnp_careers", "difficulty_level")
