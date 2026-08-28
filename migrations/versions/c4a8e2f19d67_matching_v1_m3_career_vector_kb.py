"""Matching V1 M3: Career Vector Knowledge Base

Revision ID: c4a8e2f19d67
Revises: b3f7d1c92a56
Create Date: 2026-08-28

Purely additive. 3 new tables, no existing table altered/dropped:

  career_external_mappings   many-to-many crosswalk from Career to an
                              external taxonomy code (O*NET-SOC today);
                              CONFIRMED/PROVISIONAL/UNMAPPED/REJECTED
  career_matching_profiles   one versioned career-vector generation per
                              Career; at most one is_current=True per
                              career (mirrors deterministic_profiles'
                              is_current idiom)
  career_matching_components one scale's career-side value, gated so it
                              can only ever be created for a MATCH_ENABLED
                              scale (enforced in
                              app/services/career_kb/vectors.py, not by a
                              DB CHECK -- consistent with this codebase's
                              existing service-layer-enforcement
                              convention for similar invariants)

No Stage 1/2/3/4 table (careers, career_requirements, career_work_contexts,
career_skills, career_facts, identity_users, assessment_scales, ...) is
altered. Two new FKs point INTO careers / career_matching_profiles /
assessment_scales-adjacent data is read at the application layer, not FK'd
directly (career_matching_components stores a denormalized
mapping_status/matching_usage snapshot, not a live FK to
assessment_scales, since a scale's own metadata could theoretically be
re-seeded under a new methodology_version later and a historical
component must stay reproducible against what it saw at creation time).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4a8e2f19d67"
down_revision: Union[str, None] = "b3f7d1c92a56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "career_external_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(length=16), nullable=False),
        sa.Column("external_code", sa.String(length=64), nullable=True),
        sa.Column("external_label", sa.String(length=255), nullable=True),
        sa.Column("external_url", sa.String(length=1000), nullable=True),
        sa.Column("mapping_status", sa.String(length=16), nullable=False),
        sa.Column("mapping_version", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("career_id", "source_system", "external_code", name="uq_career_external_mapping_code"),
    )
    op.create_index("ix_career_external_mappings_career_id", "career_external_mappings", ["career_id"])
    op.create_index("ix_career_external_mappings_source_system", "career_external_mappings", ["source_system"])
    op.create_index("ix_career_external_mappings_mapping_status", "career_external_mappings", ["mapping_status"])

    op.create_table(
        "career_matching_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_id", sa.Uuid(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("career_vector_version", sa.String(length=32), nullable=False),
        sa.Column("matching_methodology_version", sa.String(length=32), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.Column("mapping_version", sa.String(length=32), nullable=False),
        sa.Column("localization_version", sa.String(length=32), nullable=False),
        sa.Column("provisional", sa.Boolean(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["career_matching_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "career_id", "career_vector_version", "mapping_version", "source_version",
            name="uq_career_matching_profile_versions",
        ),
    )
    op.create_index("ix_career_matching_profiles_career_id", "career_matching_profiles", ["career_id"])
    op.create_index(
        "uq_one_current_career_matching_profile",
        "career_matching_profiles",
        ["career_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
        sqlite_where=sa.text("is_current"),
    )

    op.create_table(
        "career_matching_components",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("scale_family", sa.String(length=32), nullable=False),
        sa.Column("scale_key", sa.String(length=64), nullable=False),
        sa.Column("normalized_value", sa.Float(), nullable=True),
        sa.Column("mapping_status", sa.String(length=16), nullable=False),
        sa.Column("matching_usage", sa.String(length=16), nullable=False),
        sa.Column("provisional", sa.Boolean(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=True),
        sa.Column("source_element_id", sa.String(length=64), nullable=True),
        sa.Column("source_element_name", sa.String(length=255), nullable=True),
        sa.Column("source_raw_value", sa.String(length=64), nullable=True),
        sa.Column("transformation_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["career_matching_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "scale_family", "scale_key", name="uq_career_matching_component_scale"),
    )
    op.create_index("ix_career_matching_components_profile_id", "career_matching_components", ["profile_id"])
    op.create_index("ix_career_matching_components_scale_family", "career_matching_components", ["scale_family"])


def downgrade() -> None:
    op.drop_table("career_matching_components")
    op.drop_index("uq_one_current_career_matching_profile", table_name="career_matching_profiles")
    op.drop_table("career_matching_profiles")
    op.drop_table("career_external_mappings")
