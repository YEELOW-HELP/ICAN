"""Stage 3A: Curated Career Knowledge Base + source provenance

Revision ID: 7d3720363f8e
Revises: 0c9abc704162
Create Date: 2026-08-26

Purely additive: 8 new tables (Issue #4 -- knowledge_base_versions,
knowledge_sources, careers, career_aliases, career_skills,
career_requirements, career_work_contexts, career_relations,
career_facts). No existing table is altered, dropped, or has data
migrated. No FK into identity_users/interview_sessions/evidence/
profile_claims exists anywhere in this revision -- Career Knowledge and
User Evidence/Profile are separate bounded domains (brief §21).

career_skills.skill_term_id references the existing taxonomy_terms table
(Stage 2) -- skills are seeded Taxonomy content, not a new Skill table
(see app/db/models_knowledge.py's module docstring for the reuse
rationale).

Migration ordering follows FK dependency order exactly; downgrade
reverses it. Rollback note: safe before real Stage 3A curated content
exists -- once careers/career_facts hold real curated data, dropping
these tables is destructive and requires an explicit, separately
reviewed decision, not a routine `alembic downgrade`.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7d3720363f8e"
down_revision: Union[str, None] = "0c9abc704162"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_base_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version"),
    )
    op.create_index("ix_knowledge_base_versions_status", "knowledge_base_versions", ["status"])
    op.create_index(
        "uq_one_current_knowledge_base_version",
        "knowledge_base_versions",
        ["is_current"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
        sqlite_where=sa.text("is_current = 1"),
    )

    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("publisher", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("country_region", sa.String(length=64), nullable=True),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trust_level", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "careers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_version_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("title_uk", sa.String(length=255), nullable=False),
        sa.Column("title_en", sa.String(length=255), nullable=True),
        sa.Column("domain", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("short_description", sa.Text(), nullable=False),
        sa.Column("typical_activities", sa.Text(), nullable=True),
        sa.Column("works_with_people", sa.Float(), nullable=True),
        sa.Column("works_with_data", sa.Float(), nullable=True),
        sa.Column("works_with_technology", sa.Float(), nullable=True),
        sa.Column("creative_component", sa.Float(), nullable=True),
        sa.Column("analytical_component", sa.Float(), nullable=True),
        sa.Column("autonomy_level", sa.Float(), nullable=True),
        sa.Column("structure_routine_level", sa.Float(), nullable=True),
        sa.Column("external_esco_id", sa.String(length=64), nullable=True),
        sa.Column("external_onet_id", sa.String(length=64), nullable=True),
        sa.Column("external_isco_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["knowledge_base_version_id"], ["knowledge_base_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("knowledge_base_version_id", "code", name="uq_career_code_per_kb_version"),
    )
    op.create_index("ix_careers_knowledge_base_version_id", "careers", ["knowledge_base_version_id"])
    op.create_index("ix_careers_code", "careers", ["code"])
    op.create_index("ix_careers_domain", "careers", ["domain"])

    op.create_table(
        "career_aliases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_id", sa.Uuid(), nullable=False),
        sa.Column("alias_text", sa.String(length=255), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=False),
        sa.Column("normalized_text", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("career_id", "locale", "normalized_text", name="uq_career_alias_per_locale"),
    )
    op.create_index("ix_career_aliases_career_id", "career_aliases", ["career_id"])
    op.create_index("ix_career_aliases_normalized_text", "career_aliases", ["normalized_text"])

    op.create_table(
        "career_skills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_id", sa.Uuid(), nullable=False),
        sa.Column("skill_term_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_type", sa.String(length=32), nullable=False),
        sa.Column("expected_level", sa.String(length=32), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"]),
        sa.ForeignKeyConstraint(["skill_term_id"], ["taxonomy_terms.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("career_id", "skill_term_id", name="uq_career_skill_pair"),
    )
    op.create_index("ix_career_skills_career_id", "career_skills", ["career_id"])
    op.create_index("ix_career_skills_skill_term_id", "career_skills", ["skill_term_id"])

    op.create_table(
        "career_requirements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("certainty", sa.String(length=32), nullable=False),
        sa.Column("jurisdiction", sa.String(length=64), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_career_requirements_career_id", "career_requirements", ["career_id"])
    op.create_index("ix_career_requirements_category", "career_requirements", ["category"])
    op.create_index("ix_career_requirements_certainty", "career_requirements", ["certainty"])

    op.create_table(
        "career_work_contexts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_id", sa.Uuid(), nullable=False),
        sa.Column("setting", sa.String(length=32), nullable=True),
        sa.Column("indoor_outdoor", sa.String(length=32), nullable=True),
        sa.Column("travel_required", sa.String(length=32), nullable=True),
        sa.Column("shift_work", sa.Boolean(), nullable=True),
        sa.Column("physical_intensity", sa.Float(), nullable=True),
        sa.Column("teamwork_level", sa.Float(), nullable=True),
        sa.Column("customer_interaction_level", sa.Float(), nullable=True),
        sa.Column("client_facing", sa.Boolean(), nullable=True),
        sa.Column("repetitive_vs_varied", sa.Float(), nullable=True),
        sa.Column("schedule_predictability", sa.Float(), nullable=True),
        sa.Column("responsibility_level", sa.Float(), nullable=True),
        sa.Column("stress_level", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("career_id"),
    )
    op.create_index("ix_career_work_contexts_career_id", "career_work_contexts", ["career_id"])

    op.create_table(
        "career_relations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("from_career_id", sa.Uuid(), nullable=False),
        sa.Column("to_career_id", sa.Uuid(), nullable=False),
        sa.Column("relation_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["from_career_id"], ["careers.id"]),
        sa.ForeignKeyConstraint(["to_career_id"], ["careers.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_career_id", "to_career_id", "relation_type", name="uq_career_relation_triple"),
    )
    op.create_index("ix_career_relations_from_career_id", "career_relations", ["from_career_id"])
    op.create_index("ix_career_relations_to_career_id", "career_relations", ["to_career_id"])

    op.create_table(
        "career_facts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_version_id", sa.Uuid(), nullable=False),
        sa.Column("fact_type", sa.String(length=128), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=False),
        sa.Column("value_metadata", sa.JSON(), nullable=True),
        sa.Column("geography", sa.String(length=64), nullable=True),
        sa.Column("is_market_sensitive", sa.Boolean(), nullable=False),
        sa.Column("verification_state", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("as_of_date", sa.Date(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["careers.id"]),
        sa.ForeignKeyConstraint(["knowledge_base_version_id"], ["knowledge_base_versions.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "career_id", "fact_type", "geography", "knowledge_base_version_id", name="uq_career_fact_identity"
        ),
    )
    op.create_index("ix_career_facts_career_id", "career_facts", ["career_id"])
    op.create_index("ix_career_facts_knowledge_base_version_id", "career_facts", ["knowledge_base_version_id"])
    op.create_index("ix_career_facts_is_market_sensitive", "career_facts", ["is_market_sensitive"])


def downgrade() -> None:
    op.drop_table("career_facts")
    op.drop_table("career_relations")
    op.drop_table("career_work_contexts")
    op.drop_table("career_requirements")
    op.drop_table("career_skills")
    op.drop_table("career_aliases")
    op.drop_table("careers")
    op.drop_table("knowledge_sources")
    op.drop_index("uq_one_current_knowledge_base_version", table_name="knowledge_base_versions")
    op.drop_table("knowledge_base_versions")
