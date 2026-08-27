"""Stage 3B (Slice 3.5): Critic idempotency

Revision ID: 4f1d7c92e6ab
Revises: 7b3e9a1c5d84
Create Date: 2026-08-27

Purely additive: 1 new column + 1 new unique constraint on the existing
`direction_critic_findings` table. No other schema change.

  direction_critic_findings.identity_key   deterministic identity for one
                             finding -- (run_id, direction_id, severity,
                             code, engine_version, related-entity identity),
                             hashed. UNIQUE(run_id, identity_key) makes
                             re-running the Critic for the same
                             (run, engine_version) idempotent: the second
                             identical evaluation inserts zero new rows.
                             A later, different engine_version naturally
                             gets its own identity_keys, so historical
                             findings from a superseded engine version are
                             never touched or deleted by this constraint.

Assumes no real `direction_critic_findings` rows exist yet in any target
environment (Slice 3 shipped in the same pilot phase, immediately
superseded by this hardening before any real consultant review data was
produced) -- `identity_key` is added `nullable=False` directly rather than
via a backfill step. If that assumption is ever wrong for a specific
environment, backfill `identity_key` from existing rows' fields (using
`critic.py::_compute_identity_key`'s exact algorithm) before running this
revision there.

No existing column is altered or dropped. No Stage 1/2/3A table touched.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "4f1d7c92e6ab"
down_revision: Union[str, None] = "7b3e9a1c5d84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("direction_critic_findings", sa.Column("identity_key", sa.String(length=64), nullable=False))
    op.create_index("ix_direction_critic_findings_identity_key", "direction_critic_findings", ["identity_key"])
    op.create_unique_constraint(
        "uq_direction_critic_finding_identity", "direction_critic_findings", ["run_id", "identity_key"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_direction_critic_finding_identity", "direction_critic_findings", type_="unique")
    op.drop_index("ix_direction_critic_findings_identity_key", table_name="direction_critic_findings")
    op.drop_column("direction_critic_findings", "identity_key")
