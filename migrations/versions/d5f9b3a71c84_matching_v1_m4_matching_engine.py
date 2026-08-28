"""Matching V1 M4: deterministic user x career matching results

Revision ID: d5f9b3a71c84
Revises: c4a8e2f19d67
Create Date: 2026-08-28

Purely additive. 3 new tables, no existing table altered/dropped:

  matching_results            one pairwise (DeterministicProfile x
                               CareerMatchingProfile) result, immutable,
                               full version-pin chain
  match_family_results        one Interest/Work Style/Values Fit result
                               per matching_results row -- status/score/
                               band/counts/comparable-scale-key trace,
                               never the raw vectors themselves
  match_feasibility_results   one Transition Feasibility result per
                               matching_results row -- status/score/band
                               + barrier/gap/skill-check lists

Deliberately NOT built on Stage 3B's direction_runs/directions/
direction_score_components (models_direction.py) -- that family's
OutputFamily enum is hardcoded to the old four-output model. No Stage
1/2/3/4 table is altered. Two new FKs point INTO deterministic_profiles /
careers / career_matching_profiles -- nothing points the other way.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5f9b3a71c84"
down_revision: Union[str, None] = "c4a8e2f19d67"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "matching_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("career_id", sa.Uuid(), nullable=False),
        sa.Column("career_matching_profile_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_version", sa.String(length=64), nullable=False),
        sa.Column("profile_engine_version", sa.String(length=32), nullable=False),
        sa.Column("matching_methodology_version", sa.String(length=32), nullable=False),
        sa.Column("career_vector_version", sa.String(length=32), nullable=False),
        sa.Column("career_source_version", sa.String(length=32), nullable=False),
        sa.Column("matching_engine_version", sa.String(length=32), nullable=False),
        sa.Column("metric_version", sa.String(length=32), nullable=False),
        sa.Column("config_version", sa.String(length=32), nullable=False),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["deterministic_profiles.id"]),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"]),
        sa.ForeignKeyConstraint(["career_matching_profile_id"], ["career_matching_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id", "career_matching_profile_id", "matching_engine_version", "config_version",
            name="uq_matching_result_pair_engine_config",
        ),
    )
    op.create_index("ix_matching_results_profile_id", "matching_results", ["profile_id"])
    op.create_index("ix_matching_results_career_id", "matching_results", ["career_id"])
    op.create_index("ix_matching_results_career_matching_profile_id", "matching_results", ["career_matching_profile_id"])

    op.create_table(
        "match_family_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("matching_result_id", sa.Uuid(), nullable=False),
        sa.Column("scale_family", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("raw_score", sa.Float(), nullable=True),
        sa.Column("band", sa.String(length=16), nullable=True),
        sa.Column("user_component_count", sa.Integer(), nullable=False),
        sa.Column("career_component_count", sa.Integer(), nullable=False),
        sa.Column("comparable_component_count", sa.Integer(), nullable=False),
        sa.Column("comparable_scale_keys", sa.JSON(), nullable=False),
        sa.Column("coverage_ratio", sa.Float(), nullable=False),
        sa.Column("provisional", sa.Boolean(), nullable=False),
        sa.Column("user_stdev", sa.Float(), nullable=True),
        sa.Column("career_stdev", sa.Float(), nullable=True),
        sa.Column("differentiation_threshold", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["matching_result_id"], ["matching_results.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("matching_result_id", "scale_family", name="uq_match_family_result_family"),
    )
    op.create_index("ix_match_family_results_matching_result_id", "match_family_results", ["matching_result_id"])
    op.create_index("ix_match_family_results_scale_family", "match_family_results", ["scale_family"])

    op.create_table(
        "match_feasibility_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("matching_result_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("raw_score", sa.Float(), nullable=True),
        sa.Column("band", sa.String(length=16), nullable=True),
        sa.Column("hard_barriers", sa.JSON(), nullable=False),
        sa.Column("soft_barriers", sa.JSON(), nullable=False),
        sa.Column("information_gaps", sa.JSON(), nullable=False),
        sa.Column("skills_to_verify", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["matching_result_id"], ["matching_results.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("matching_result_id", name="uq_match_feasibility_result_pair"),
    )
    op.create_index("ix_match_feasibility_results_matching_result_id", "match_feasibility_results", ["matching_result_id"])


def downgrade() -> None:
    op.drop_table("match_feasibility_results")
    op.drop_table("match_family_results")
    op.drop_table("matching_results")
