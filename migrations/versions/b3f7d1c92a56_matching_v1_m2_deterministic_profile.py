"""Matching V1 M2: deterministic BASIC profile persistence

Revision ID: b3f7d1c92a56
Revises: 8e2c4a71d9f3
Create Date: 2026-08-28

Purely additive. 4 new tables, no existing table altered/dropped:

  deterministic_profiles       one versioned deterministic-calculation
                                attempt over one BasicAssessmentAttempt;
                                at most one is_current=True per user
                                (mirrors potential_profiles' own
                                is_current idiom, but is a wholly separate
                                table -- BASIC and PRO Hybrid profiles
                                never share a row or a provenance model)
  profile_scale_results        one row per scored Likert scale
                                (RIASEC/Work Style/Work Values/Work
                                Environment), including PROFILE_ONLY
                                scales -- matching_usage is provenance,
                                never a reason to omit a result
  profile_vector_differentiation  one row per vector family's
                                minimum-dispersion (Founder-approved
                                stdev >= 0.10) differentiation check
  profile_structured_context   Goals/Constraints/Experience answers,
                                snapshotted as structured facts -- never
                                converted into an invented Likert score

No Stage 1/2/3/4 table (identity_users, interview_sessions,
potential_profiles, profile_claims, evidence, career KB tables) is
touched. Two new FKs point INTO identity_users / basic_assessment_attempts
/ assessment_definitions / assessment_scales / assessment_items -- nothing
points the other way, and none of those M1 tables is altered.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3f7d1c92a56"
down_revision: Union[str, None] = "8e2c4a71d9f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deterministic_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("definition_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_code", sa.String(length=64), nullable=False),
        sa.Column("assessment_version", sa.String(length=64), nullable=False),
        sa.Column("methodology_version", sa.String(length=32), nullable=False),
        sa.Column("profile_engine_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("coverage", sa.Float(), nullable=False),
        sa.Column("coverage_band", sa.String(length=16), nullable=False),
        sa.Column("context_completeness", sa.Float(), nullable=False),
        sa.Column("differentiation_state", sa.String(length=24), nullable=False),
        sa.Column("interest_ordering", sa.JSON(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"]),
        sa.ForeignKeyConstraint(["attempt_id"], ["basic_assessment_attempts.id"]),
        sa.ForeignKeyConstraint(["definition_id"], ["assessment_definitions.id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["deterministic_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "attempt_id", "profile_engine_version", name="uq_deterministic_profile_attempt_engine_version"
        ),
    )
    op.create_index("ix_deterministic_profiles_user_id", "deterministic_profiles", ["user_id"])
    op.create_index("ix_deterministic_profiles_attempt_id", "deterministic_profiles", ["attempt_id"])
    op.create_index("ix_deterministic_profiles_definition_id", "deterministic_profiles", ["definition_id"])
    op.create_index(
        "uq_one_current_basic_profile_per_user",
        "deterministic_profiles",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
        sqlite_where=sa.text("is_current"),
    )

    op.create_table(
        "profile_scale_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("scale_id", sa.Uuid(), nullable=False),
        sa.Column("scale_family", sa.String(length=32), nullable=False),
        sa.Column("scale_key", sa.String(length=64), nullable=False),
        sa.Column("raw_mean", sa.Float(), nullable=True),
        sa.Column("normalized_value", sa.Float(), nullable=True),
        sa.Column("items_answered", sa.Integer(), nullable=False),
        sa.Column("items_total", sa.Integer(), nullable=False),
        sa.Column("sufficiently_answered", sa.Boolean(), nullable=False),
        sa.Column("mapping_status", sa.String(length=16), nullable=False),
        sa.Column("matching_usage", sa.String(length=16), nullable=False),
        sa.Column("provisional", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["deterministic_profiles.id"]),
        sa.ForeignKeyConstraint(["scale_id"], ["assessment_scales.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "scale_id", name="uq_profile_scale_result_scale"),
    )
    op.create_index("ix_profile_scale_results_profile_id", "profile_scale_results", ["profile_id"])
    op.create_index("ix_profile_scale_results_scale_id", "profile_scale_results", ["scale_id"])
    op.create_index("ix_profile_scale_results_scale_family", "profile_scale_results", ["scale_family"])

    op.create_table(
        "profile_vector_differentiation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("scale_family", sa.String(length=32), nullable=False),
        sa.Column("stdev", sa.Float(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["deterministic_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "scale_family", name="uq_profile_vector_diff_family"),
    )
    op.create_index("ix_profile_vector_differentiation_profile_id", "profile_vector_differentiation", ["profile_id"])

    op.create_table(
        "profile_structured_context",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("scale_family", sa.String(length=32), nullable=False),
        sa.Column("scale_key", sa.String(length=64), nullable=False),
        sa.Column("response_type", sa.String(length=16), nullable=False),
        sa.Column("numeric_value", sa.Integer(), nullable=True),
        sa.Column("boolean_value", sa.Boolean(), nullable=True),
        sa.Column("selected_option_keys", sa.JSON(), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["deterministic_profiles.id"]),
        sa.ForeignKeyConstraint(["item_id"], ["assessment_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "item_id", name="uq_profile_structured_context_item"),
    )
    op.create_index("ix_profile_structured_context_profile_id", "profile_structured_context", ["profile_id"])
    op.create_index("ix_profile_structured_context_item_id", "profile_structured_context", ["item_id"])
    op.create_index("ix_profile_structured_context_scale_family", "profile_structured_context", ["scale_family"])


def downgrade() -> None:
    op.drop_table("profile_structured_context")
    op.drop_table("profile_vector_differentiation")
    op.drop_table("profile_scale_results")
    op.drop_index("uq_one_current_basic_profile_per_user", table_name="deterministic_profiles")
    op.drop_table("deterministic_profiles")
