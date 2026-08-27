"""Stage 3B (Slice 2): end-to-end Direction Generation orchestrator

Revision ID: 5c2e8f14a9b7
Revises: 3a1b9d5c7e21
Create Date: 2026-08-27

Purely additive: 4 new nullable columns on the existing `directions`
table, no other schema change.

  explanation_bundle       structured deterministic explanation/provenance
                            (WHY_FIT / WHY_NOW / TRANSITION / CONFIDENCE /
                            PROVENANCE) -- backend data for consultant
                            review, not client prose (plan section 8)
  duplicate_of_career_code set when placement == DEDUPED: the career_code
                            of the stronger recommendation this direction
                            was folded into (deterministic exact-collision
                            dedup only -- app/services/direction/dedup.py)
  dedup_reason              why this direction was deduped
  diversity_warning         optional non-blocking note when the candidate
                            pool has limited material differentiation,
                            even without an exact-duplicate collision

No existing column is altered, dropped, or has data migrated.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5c2e8f14a9b7"
down_revision: Union[str, None] = "3a1b9d5c7e21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("directions", sa.Column("explanation_bundle", sa.JSON(), nullable=True))
    op.add_column("directions", sa.Column("duplicate_of_career_code", sa.String(length=128), nullable=True))
    op.add_column("directions", sa.Column("dedup_reason", sa.Text(), nullable=True))
    op.add_column("directions", sa.Column("diversity_warning", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("directions", "diversity_warning")
    op.drop_column("directions", "dedup_reason")
    op.drop_column("directions", "duplicate_of_career_code")
    op.drop_column("directions", "explanation_bundle")
