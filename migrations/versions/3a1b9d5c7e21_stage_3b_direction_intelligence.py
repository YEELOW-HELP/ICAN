"""Stage 3B (Slice 1): Direction Intelligence foundation -- four-output model

Revision ID: 3a1b9d5c7e21
Revises: 7d3720363f8e
Create Date: 2026-08-27

Purely additive. 8 new tables:

  scoring_configs             versioned EXPERIMENTAL per-output weights + thresholds
  ranking_policies            SEPARATE versioned decision layer (Founder decisions O + G)
  profile_constraints         structured, matchable projection of constraint-dimension claims
  direction_runs              one versioned Direction Intelligence generation attempt (per user)
  directions                  one candidate career -- FOUR separate output blocks (Founder decision N)
  direction_score_components  one score component result per (direction, output_family, component_key)
  direction_constraint_checks Hard Constraint Gate results
  clarification_requests      emitted when a run / fit output could not be completed

No existing table is altered, dropped, or has data migrated.

Direction Intelligence is the arrow that connects the two bounded
domains, so (unlike Stage 3A) this revision DOES have FKs into
identity_users / potential_profiles / profile_claims and into careers /
knowledge_base_versions -- by design. It still stores no raw answer/CV
text.

Slice 1 exercises `scoring_configs`, `ranking_policies`, and
`profile_constraints`. The `direction_*` + `clarification_requests`
tables are created now (shapes follow the Founder-approved four-output
model) so the Slice 2 orchestrator needs no further migration. The
consultant-review / critic-finding tables are deliberately NOT here.

Migration ordering follows FK dependency order exactly; downgrade
reverses it. Rollback note: safe before real DirectionRun data exists.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "3a1b9d5c7e21"
down_revision: Union[str, None] = "7d3720363f8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scoring_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_experimental", sa.Boolean(), nullable=False),
        sa.Column("methodology_version", sa.String(length=64), nullable=False),
        sa.Column("component_weights", sa.JSON(), nullable=False),
        sa.Column("thresholds", sa.JSON(), nullable=False),
        sa.Column("enabled_components", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version", name="uq_scoring_config_version"),
    )
    op.create_index("ix_scoring_configs_status", "scoring_configs", ["status"])
    op.create_index(
        "uq_one_active_scoring_config",
        "scoring_configs",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "ranking_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_experimental", sa.Boolean(), nullable=False),
        sa.Column("methodology_version", sa.String(length=64), nullable=False),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version", name="uq_ranking_policy_version"),
    )
    op.create_index("ix_ranking_policies_status", "ranking_policies", ["status"])
    op.create_index(
        "uq_one_active_ranking_policy",
        "ranking_policies",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "profile_constraints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("source_claim_id", sa.Uuid(), nullable=False),
        sa.Column("constraint_subtype", sa.String(length=32), nullable=False),
        sa.Column("constraint_taxonomy_version", sa.String(length=64), nullable=False),
        sa.Column("normalized_value", sa.Text(), nullable=False),
        sa.Column("is_hard", sa.Boolean(), nullable=False),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["potential_profiles.id"]),
        sa.ForeignKeyConstraint(["source_claim_id"], ["profile_claims.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id", "source_claim_id", "constraint_subtype", name="uq_profile_constraint_identity"
        ),
    )
    op.create_index("ix_profile_constraints_profile_id", "profile_constraints", ["profile_id"])
    op.create_index("ix_profile_constraints_source_claim_id", "profile_constraints", ["source_claim_id"])
    op.create_index("ix_profile_constraints_constraint_subtype", "profile_constraints", ["constraint_subtype"])

    op.create_table(
        "direction_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_version_id", sa.Uuid(), nullable=False),
        sa.Column("scoring_config_id", sa.Uuid(), nullable=False),
        sa.Column("ranking_policy_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("methodology_version", sa.String(length=64), nullable=False),
        sa.Column("direction_engine_version", sa.String(length=64), nullable=False),
        sa.Column("direction_evaluation_model_version", sa.String(length=64), nullable=False),
        sa.Column("ranking_policy_version", sa.String(length=64), nullable=False),
        sa.Column("dimension_mapping_version", sa.String(length=64), nullable=False),
        sa.Column("subdimension_taxonomy_version", sa.String(length=64), nullable=False),
        sa.Column("constraint_taxonomy_version", sa.String(length=64), nullable=False),
        sa.Column("evidence_standard_version", sa.String(length=64), nullable=False),
        sa.Column("candidate_prompt_version", sa.String(length=64), nullable=True),
        sa.Column("narrative_prompt_version", sa.String(length=64), nullable=True),
        sa.Column("critic_prompt_version", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("trace_ids", sa.JSON(), nullable=True),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"]),
        sa.ForeignKeyConstraint(["profile_id"], ["potential_profiles.id"]),
        sa.ForeignKeyConstraint(["knowledge_base_version_id"], ["knowledge_base_versions.id"]),
        sa.ForeignKeyConstraint(["scoring_config_id"], ["scoring_configs.id"]),
        sa.ForeignKeyConstraint(["ranking_policy_id"], ["ranking_policies.id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["direction_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "version", name="uq_direction_run_user_version"),
    )
    op.create_index("ix_direction_runs_user_id", "direction_runs", ["user_id"])
    op.create_index("ix_direction_runs_profile_id", "direction_runs", ["profile_id"])
    op.create_index("ix_direction_runs_knowledge_base_version_id", "direction_runs", ["knowledge_base_version_id"])
    op.create_index("ix_direction_runs_scoring_config_id", "direction_runs", ["scoring_config_id"])
    op.create_index("ix_direction_runs_ranking_policy_id", "direction_runs", ["ranking_policy_id"])
    op.create_index("ix_direction_runs_status", "direction_runs", ["status"])
    op.create_index(
        "uq_one_current_direction_run_per_user",
        "direction_runs",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
        sqlite_where=sa.text("is_current = 1"),
    )

    op.create_table(
        "directions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("career_id", sa.Uuid(), nullable=False),
        sa.Column("career_code", sa.String(length=128), nullable=False),
        sa.Column("domain", sa.String(length=32), nullable=False),
        sa.Column("placement", sa.String(length=24), nullable=False),
        sa.Column("rank_within_placement", sa.Integer(), nullable=True),
        sa.Column("trade_off_notes", sa.Text(), nullable=True),
        sa.Column("potential_fit_raw_experimental", sa.Float(), nullable=True),
        sa.Column("potential_fit_band", sa.String(length=16), nullable=True),
        sa.Column("potential_fit_coverage_ratio", sa.Float(), nullable=True),
        sa.Column("potential_fit_scored_component_count", sa.Integer(), nullable=False),
        sa.Column("goal_alignment_raw_experimental", sa.Float(), nullable=True),
        sa.Column("goal_alignment_band", sa.String(length=16), nullable=True),
        sa.Column("goal_alignment_coverage_ratio", sa.Float(), nullable=True),
        sa.Column("goal_alignment_scored_component_count", sa.Integer(), nullable=False),
        sa.Column("transition_feasibility_raw_experimental", sa.Float(), nullable=True),
        sa.Column("transition_feasibility_band", sa.String(length=16), nullable=True),
        sa.Column("transition_feasibility_coverage_ratio", sa.Float(), nullable=True),
        sa.Column("transition_feasibility_scored_component_count", sa.Integer(), nullable=False),
        sa.Column("evidence_confidence_raw_experimental", sa.Float(), nullable=True),
        sa.Column("evidence_confidence_band", sa.String(length=16), nullable=True),
        sa.Column("evidence_confidence_coverage_note", sa.Text(), nullable=True),
        sa.Column("skills_to_verify", sa.JSON(), nullable=True),
        sa.Column("narrative_text", sa.Text(), nullable=True),
        sa.Column("narrative_locale", sa.String(length=8), nullable=True),
        sa.Column("narrative_trace_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["direction_runs.id"]),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "career_code", name="uq_direction_run_career"),
    )
    op.create_index("ix_directions_run_id", "directions", ["run_id"])
    op.create_index("ix_directions_career_id", "directions", ["career_id"])
    op.create_index("ix_directions_placement", "directions", ["placement"])

    op.create_table(
        "direction_score_components",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("direction_id", sa.Uuid(), nullable=False),
        sa.Column("output_family", sa.String(length=32), nullable=False),
        sa.Column("component_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("raw_score", sa.Float(), nullable=True),
        sa.Column("weight_applied", sa.Float(), nullable=False),
        sa.Column("scoring_config_id", sa.Uuid(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("contributing_claim_ids", sa.JSON(), nullable=True),
        sa.Column("contributing_career_attributes", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["direction_id"], ["directions.id"]),
        sa.ForeignKeyConstraint(["scoring_config_id"], ["scoring_configs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("direction_id", "output_family", "component_key", name="uq_direction_score_component"),
    )
    op.create_index("ix_direction_score_components_direction_id", "direction_score_components", ["direction_id"])
    op.create_index("ix_direction_score_components_output_family", "direction_score_components", ["output_family"])

    op.create_table(
        "direction_constraint_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("direction_id", sa.Uuid(), nullable=False),
        sa.Column("profile_constraint_id", sa.Uuid(), nullable=True),
        sa.Column("constraint_subtype", sa.String(length=32), nullable=False),
        sa.Column("career_attribute_ref", sa.String(length=128), nullable=True),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("is_hard", sa.Boolean(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["direction_id"], ["directions.id"]),
        sa.ForeignKeyConstraint(["profile_constraint_id"], ["profile_constraints.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_direction_constraint_checks_direction_id", "direction_constraint_checks", ["direction_id"])
    op.create_index("ix_direction_constraint_checks_result", "direction_constraint_checks", ["result"])

    op.create_table(
        "clarification_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("canonical_dimension", sa.String(length=48), nullable=True),
        sa.Column("related_claim_ids", sa.JSON(), nullable=True),
        sa.Column("suggested_question_topic", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["direction_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clarification_requests_run_id", "clarification_requests", ["run_id"])


def downgrade() -> None:
    op.drop_table("clarification_requests")
    op.drop_table("direction_constraint_checks")
    op.drop_table("direction_score_components")
    op.drop_index("uq_one_current_direction_run_per_user", table_name="direction_runs")
    op.drop_table("directions")
    op.drop_table("direction_runs")
    op.drop_table("profile_constraints")
    op.drop_index("uq_one_active_ranking_policy", table_name="ranking_policies")
    op.drop_table("ranking_policies")
    op.drop_index("uq_one_active_scoring_config", table_name="scoring_configs")
    op.drop_table("scoring_configs")
