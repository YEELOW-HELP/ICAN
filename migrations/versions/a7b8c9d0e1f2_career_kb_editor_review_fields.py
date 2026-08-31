"""MNP Career KB Editor V1 -- review_status / sort_order / note fields

Revision ID: a7b8c9d0e1f2
Revises: f2c3d4e5a6b7
Create Date: 2026-08-31

Additive only. The Career KB Editor lets an admin curate every block; a
free-text `review_status` per row supports a lightweight review workflow,
`sort_order` makes responsibilities / requirements reorderable in the UI,
and `note` lets an editor annotate an external mapping. No existing column
is changed and no data is migrated. Enum-backed columns stay plain
`String` (same convention as `f2c3d4e5a6b7`).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f2c3d4e5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_EDITORIAL = sa.text("'editorial'")


def upgrade() -> None:
    op.add_column("mnp_career_tasks", sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("mnp_career_tasks", sa.Column("review_status", sa.String(length=24), nullable=False, server_default=_EDITORIAL))

    op.add_column("mnp_career_skill_requirements", sa.Column("review_status", sa.String(length=24), nullable=False, server_default=_EDITORIAL))

    op.add_column("mnp_career_knowledge_requirements", sa.Column("source_version", sa.String(length=32), nullable=True))
    op.add_column("mnp_career_knowledge_requirements", sa.Column("review_status", sa.String(length=24), nullable=False, server_default=_EDITORIAL))

    op.add_column("mnp_career_requirements", sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("mnp_career_requirements", sa.Column("review_status", sa.String(length=24), nullable=False, server_default=_EDITORIAL))

    op.add_column("mnp_career_relations", sa.Column("source_version", sa.String(length=32), nullable=True))
    op.add_column("mnp_career_relations", sa.Column("review_status", sa.String(length=24), nullable=False, server_default=_EDITORIAL))

    op.add_column("mnp_external_mappings", sa.Column("review_status", sa.String(length=24), nullable=False, server_default=sa.text("'candidate'")))
    op.add_column("mnp_external_mappings", sa.Column("note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("mnp_external_mappings", "note")
    op.drop_column("mnp_external_mappings", "review_status")
    op.drop_column("mnp_career_relations", "review_status")
    op.drop_column("mnp_career_relations", "source_version")
    op.drop_column("mnp_career_requirements", "review_status")
    op.drop_column("mnp_career_requirements", "sort_order")
    op.drop_column("mnp_career_knowledge_requirements", "review_status")
    op.drop_column("mnp_career_knowledge_requirements", "source_version")
    op.drop_column("mnp_career_skill_requirements", "review_status")
    op.drop_column("mnp_career_tasks", "review_status")
    op.drop_column("mnp_career_tasks", "sort_order")
