"""Stage 3B (Slice 3): Critic + consultant review + narrative

Revision ID: 7b3e9a1c5d84
Revises: 5c2e8f14a9b7
Create Date: 2026-08-27

Purely additive: 3 new tables + 1 new nullable column.

  direction_critic_findings   deterministic Critic findings (BLOCKER/
                               WARNING/INFO) against a completed DirectionRun
  direction_reviews           consultant-review workflow state, one per
                               DirectionRun (PENDING_REVIEW -> APPROVED |
                               CHANGES_REQUESTED | REJECTED)
  consultant_corrections      append-only correction/flag log, closed
                               13-code reason set (Founder Methodology
                               Contract v0.1 decision K)

  directions.narrative_structured  new nullable JSON column: the
                               {summary, why_fit, why_now, transition,
                               risks, what_to_verify} LLM narrative.
                               narrative_text/narrative_locale/
                               narrative_trace_id (Slice 1) and
                               direction_runs.narrative_prompt_version/model
                               (Slice 1) are reused unchanged.

No existing column is altered, dropped, or has data migrated. No `ai_traces`
table (unchanged Founder decision, see the Slice 1 hardening commit).

Migration ordering follows FK dependency order exactly; downgrade
reverses it. Rollback note: safe before any real consultant review data
exists.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7b3e9a1c5d84"
down_revision: Union[str, None] = "5c2e8f14a9b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("directions", sa.Column("narrative_structured", sa.JSON(), nullable=True))

    op.create_table(
        "direction_critic_findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("direction_id", sa.Uuid(), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("related_claim_ids", sa.JSON(), nullable=True),
        sa.Column("related_evidence_ids", sa.JSON(), nullable=True),
        sa.Column("related_career_ids", sa.JSON(), nullable=True),
        sa.Column("related_requirement_ids", sa.JSON(), nullable=True),
        sa.Column("engine_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["direction_runs.id"]),
        sa.ForeignKeyConstraint(["direction_id"], ["directions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_direction_critic_findings_run_id", "direction_critic_findings", ["run_id"])
    op.create_index("ix_direction_critic_findings_direction_id", "direction_critic_findings", ["direction_id"])
    op.create_index("ix_direction_critic_findings_severity", "direction_critic_findings", ["severity"])
    op.create_index("ix_direction_critic_findings_code", "direction_critic_findings", ["code"])

    op.create_table(
        "direction_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["direction_runs.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["admin_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_direction_review_run"),
    )
    op.create_index("ix_direction_reviews_run_id", "direction_reviews", ["run_id"])
    op.create_index("ix_direction_reviews_status", "direction_reviews", ["status"])

    op.create_table(
        "consultant_corrections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("direction_id", sa.Uuid(), nullable=True),
        sa.Column("artifact_type", sa.String(length=32), nullable=False),
        sa.Column("original_value", sa.JSON(), nullable=True),
        sa.Column("corrected_value", sa.JSON(), nullable=True),
        sa.Column("reason_code", sa.String(length=32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("related_claim_ids", sa.JSON(), nullable=True),
        sa.Column("related_evidence_ids", sa.JSON(), nullable=True),
        sa.Column("methodology_version", sa.String(length=64), nullable=False),
        sa.Column("knowledge_base_version_id", sa.Uuid(), nullable=False),
        sa.Column("scoring_config_version", sa.Integer(), nullable=False),
        sa.Column("ranking_policy_version", sa.Integer(), nullable=False),
        sa.Column("direction_engine_version", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["direction_reviews.id"]),
        sa.ForeignKeyConstraint(["direction_id"], ["directions.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["knowledge_base_version_id"], ["knowledge_base_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consultant_corrections_review_id", "consultant_corrections", ["review_id"])
    op.create_index("ix_consultant_corrections_direction_id", "consultant_corrections", ["direction_id"])
    op.create_index("ix_consultant_corrections_reason_code", "consultant_corrections", ["reason_code"])


def downgrade() -> None:
    op.drop_table("consultant_corrections")
    op.drop_table("direction_reviews")
    op.drop_table("direction_critic_findings")
    op.drop_column("directions", "narrative_structured")
