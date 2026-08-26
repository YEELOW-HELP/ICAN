"""Stage 2: Evidence, Potential Profile, Profile Claims, Taxonomy

Revision ID: 0c9abc704162
Revises: fa4da9c6032d
Create Date: 2026-08-26

Purely additive: 7 new tables (Issue #2 -- docs/architecture/02_ERD.md's
TAXONOMY/TAXONOMY_VERSION/TAXONOMY_TERM/EVIDENCE/POTENTIAL_PROFILE/
PROFILE_CLAIM, plus the PROFILE_CLAIM<->EVIDENCE join table). No existing
Stage 1 table is altered, dropped, or has data migrated. No taxonomy
content is seeded here -- see app/services/profile/taxonomy.py's
docstring for why seed data is an idempotent application-level concern,
not a migration concern, for methodology content that is expected to
evolve.

Migration ordering follows FK dependency order exactly; downgrade
reverses it. Rollback note: safe before real Stage 2 traffic exists --
once potential_profiles/profile_claims/evidence hold real generated
profiles, dropping these tables is destructive and requires an explicit,
separately reviewed decision, not a routine `alembic downgrade`.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0c9abc704162"
down_revision: Union[str, None] = "fa4da9c6032d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "taxonomies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_taxonomies_key", "taxonomies", ["key"])

    op.create_table(
        "taxonomy_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("taxonomy_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["taxonomy_id"], ["taxonomies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("taxonomy_id", "version", name="uq_taxonomy_version_number"),
    )
    op.create_index("ix_taxonomy_versions_taxonomy_id", "taxonomy_versions", ["taxonomy_id"])

    op.create_table(
        "taxonomy_terms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("taxonomy_version_id", sa.Uuid(), nullable=False),
        sa.Column("parent_term_id", sa.Uuid(), nullable=True),
        sa.Column("term_key", sa.String(length=128), nullable=False),
        sa.Column("label_uk", sa.String(length=255), nullable=False),
        sa.Column("label_en", sa.String(length=255), nullable=True),
        sa.Column("dimension", sa.String(length=32), nullable=True),
        sa.Column("term_metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["taxonomy_version_id"], ["taxonomy_versions.id"]),
        sa.ForeignKeyConstraint(["parent_term_id"], ["taxonomy_terms.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("taxonomy_version_id", "term_key", name="uq_taxonomy_term_key_per_version"),
    )
    op.create_index("ix_taxonomy_terms_taxonomy_version_id", "taxonomy_terms", ["taxonomy_version_id"])

    op.create_table(
        "potential_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("methodology_version", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("summary_locale", sa.String(length=8), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["potential_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "version", name="uq_potential_profile_user_version"),
    )
    op.create_index("ix_potential_profiles_user_id", "potential_profiles", ["user_id"])
    op.create_index("ix_potential_profiles_session_id", "potential_profiles", ["session_id"])
    op.create_index("ix_potential_profiles_status", "potential_profiles", ["status"])
    # Founder decision (Stage 2 brief §10): at most one *current* profile
    # per user. Partial unique index -- same idiom as Stage 1's
    # uq_one_unfinished_session_per_user -- so full version history stays
    # unbounded while "current" stays a hard invariant, not a convention.
    op.create_index(
        "uq_one_current_profile_per_user",
        "potential_profiles",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
        sqlite_where=sa.text("is_current = 1"),
    )

    op.create_table(
        "profile_claims",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("dimension", sa.String(length=32), nullable=False),
        sa.Column("taxonomy_version_id", sa.Uuid(), nullable=True),
        sa.Column("term_key", sa.String(length=128), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("normalized_value", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("generated_by", sa.String(length=64), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("superseded_by_claim_id", sa.Uuid(), nullable=True),
        sa.Column("correction_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["potential_profiles.id"]),
        sa.ForeignKeyConstraint(["taxonomy_version_id"], ["taxonomy_versions.id"]),
        sa.ForeignKeyConstraint(["superseded_by_claim_id"], ["profile_claims.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_profile_claims_profile_id", "profile_claims", ["profile_id"])
    op.create_index("ix_profile_claims_dimension", "profile_claims", ["dimension"])
    op.create_index("ix_profile_claims_status", "profile_claims", ["status"])

    op.create_table(
        "evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("taxonomy_version_id", sa.Uuid(), nullable=True),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("extraction_method", sa.String(length=32), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"]),
        sa.ForeignKeyConstraint(["taxonomy_version_id"], ["taxonomy_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id", "source_type", "source_id", "evidence_type", name="uq_evidence_source_per_type"
        ),
    )
    op.create_index("ix_evidence_user_id", "evidence", ["user_id"])
    op.create_index("ix_evidence_session_id", "evidence", ["session_id"])
    op.create_index("ix_evidence_source_id", "evidence", ["source_id"])

    op.create_table(
        "profile_claim_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["profile_claims.id"]),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_id", "evidence_id", name="uq_claim_evidence_pair"),
    )
    op.create_index("ix_profile_claim_evidence_claim_id", "profile_claim_evidence", ["claim_id"])
    op.create_index("ix_profile_claim_evidence_evidence_id", "profile_claim_evidence", ["evidence_id"])


def downgrade() -> None:
    op.drop_table("profile_claim_evidence")
    op.drop_table("evidence")
    op.drop_table("profile_claims")
    op.drop_index("uq_one_current_profile_per_user", table_name="potential_profiles")
    op.drop_table("potential_profiles")
    op.drop_table("taxonomy_terms")
    op.drop_table("taxonomy_versions")
    op.drop_table("taxonomies")
