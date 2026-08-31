"""MNP V1 BLOCK A: core domain + Career Knowledge Base

Revision ID: e1a2f3c4d5b6
Revises: 7d3720363f8e
Create Date: 2026-08-29

Purely additive: 38 new `mnp_`-prefixed tables implementing
`MNP_DEVELOPMENT_PACKAGE_V1/02_DOMAIN/MNP_DATA_MODEL_V1.md` §3-23. No
existing table is altered, dropped, or has data migrated.

This is a deliberately separate, `mnp_`-prefixed schema from Stage 3A's
`careers`/`career_skills`/etc. (`7d3720363f8e`) and Stage 2's `evidence`
(`0c9abc704162`) -- those tables are shaped for a different, AI-driven
assessment methodology that MNP_METHODOLOGY_V1 supersedes for this
product line (RIASEC secondary not core; zero-LLM BASIC flow; per-career
DRAFT->ACTIVE->ARCHIVED lifecycle instead of whole-catalog version
snapshots). Stage 1-3A tables are untouched and remain available for
whatever else still depends on them. The only cross-reference out of this
new schema is `mnp_assessment_sessions.user_id` / `mnp_career_cards.
user_id` / `mnp_source_documents.user_id`, which FK to Stage 1's
`identity_users` (the one genuinely reusable piece: MNP_DATA_MODEL_V1
does not define a new User entity).

Enum-backed columns are plain `String` (matching every prior migration's
convention for `Enum(..., native_enum=False)` model columns -- see
`7d3720363f8e`), not a DB-level `ENUM`/CHECK constraint, so adding a new
enum value never requires a migration.

Generated from `Base.metadata` for exactly the new `mnp_` tables (via
Alembic's own autogenerate diff against an empty DB, run in isolation --
see Founder Report for this phase for the isolation-harness rationale:
this environment cannot run `alembic upgrade head` end-to-end against
either SQLite, because an earlier migration uses a Postgres-only `ALTER
COLUMN ... TYPE` statement, or a live Postgres instance) -- verified
in isolation against a fresh SQLite connection stubbed with just
`identity_users`, both upgrade() and downgrade().
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1a2f3c4d5b6"
down_revision: Union[str, None] = "7d3720363f8e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mnp_career_families",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name_uk", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "mnp_external_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("mnp_entity_id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("external_label", sa.String(length=255), nullable=True),
        sa.Column("mapping_type", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_version", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entity_type", "mnp_entity_id", "source_system", "external_id", name="uq_external_mapping"
        ),
    )
    op.create_index(
        op.f("ix_mnp_external_mappings_mnp_entity_id"), "mnp_external_mappings", ["mnp_entity_id"], unique=False
    )
    op.create_table(
        "mnp_knowledge",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("canonical_name_en", sa.String(length=255), nullable=False),
        sa.Column("canonical_name_uk", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "mnp_learning_opportunities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.Column("format", sa.String(length=32), nullable=True),
        sa.Column("cost", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("duration", sa.String(length=64), nullable=True),
        sa.Column("credential", sa.String(length=255), nullable=True),
        sa.Column("eligibility", sa.Text(), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "mnp_skills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("canonical_name_en", sa.String(length=255), nullable=False),
        sa.Column("canonical_name_uk", sa.String(length=255), nullable=False),
        sa.Column("skill_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("taxonomy_version", sa.String(length=32), nullable=False),
        sa.Column("parent_skill_id", sa.Uuid(), nullable=True),
        sa.Column("skill_family", sa.String(length=64), nullable=True),
        sa.Column("notes_internal", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["parent_skill_id"], ["mnp_skills.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mnp_skills_skill_family"), "mnp_skills", ["skill_family"], unique=False)
    op.create_index(op.f("ix_mnp_skills_skill_type"), "mnp_skills", ["skill_type"], unique=False)
    op.create_index(op.f("ix_mnp_skills_status"), "mnp_skills", ["status"], unique=False)
    op.create_table(
        "mnp_work_values",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=32), nullable=False),
        sa.Column("label_uk", sa.String(length=128), nullable=False),
        sa.Column("label_en", sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_table(
        "mnp_assessment_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entry_mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("methodology_version", sa.String(length=32), nullable=False),
        sa.Column("career_kb_version", sa.String(length=32), nullable=True),
        sa.Column("market_snapshot_version", sa.String(length=32), nullable=True),
        sa.Column("reset_from_session_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["reset_from_session_id"], ["mnp_assessment_sessions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_assessment_sessions_user_id"), "mnp_assessment_sessions", ["user_id"], unique=False
    )
    op.create_table(
        "mnp_careers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("canonical_name_uk", sa.String(length=255), nullable=False),
        sa.Column("canonical_name_en", sa.String(length=255), nullable=False),
        sa.Column("description_short_uk", sa.Text(), nullable=False),
        sa.Column("description_long_uk", sa.Text(), nullable=True),
        sa.Column("career_family_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("catalog_priority", sa.Integer(), nullable=False),
        sa.Column("career_profile_version", sa.Integer(), nullable=False),
        sa.Column("market_data_limited", sa.Boolean(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["career_family_id"], ["mnp_career_families.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_careers_career_family_id"), "mnp_careers", ["career_family_id"], unique=False
    )
    op.create_index(op.f("ix_mnp_careers_code"), "mnp_careers", ["code"], unique=True)
    op.create_index(op.f("ix_mnp_careers_status"), "mnp_careers", ["status"], unique=False)
    op.create_table(
        "mnp_learning_opportunity_skills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("learning_opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["learning_opportunity_id"], ["mnp_learning_opportunities.id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["mnp_skills.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_learning_opportunity_skills_learning_opportunity_id"),
        "mnp_learning_opportunity_skills",
        ["learning_opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mnp_learning_opportunity_skills_skill_id"),
        "mnp_learning_opportunity_skills",
        ["skill_id"],
        unique=False,
    )
    op.create_table(
        "mnp_skill_aliases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("alias_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["skill_id"], ["mnp_skills.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("skill_id", "language", "alias", name="uq_skill_alias"),
    )
    op.create_index(op.f("ix_mnp_skill_aliases_alias"), "mnp_skill_aliases", ["alias"], unique=False)
    op.create_index(op.f("ix_mnp_skill_aliases_skill_id"), "mnp_skill_aliases", ["skill_id"], unique=False)
    op.create_table(
        "mnp_career_aliases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_id", sa.Uuid(), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("alias_type", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["mnp_careers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("career_id", "language", "alias", name="uq_career_alias"),
    )
    op.create_index(op.f("ix_mnp_career_aliases_alias"), "mnp_career_aliases", ["alias"], unique=False)
    op.create_index(op.f("ix_mnp_career_aliases_career_id"), "mnp_career_aliases", ["career_id"], unique=False)
    op.create_table(
        "mnp_career_attributes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_id", sa.Uuid(), nullable=False),
        sa.Column("attribute_group", sa.String(length=32), nullable=False),
        sa.Column("attribute_key", sa.String(length=64), nullable=False),
        sa.Column("value_numeric", sa.Float(), nullable=True),
        sa.Column("value_text", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["career_id"], ["mnp_careers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("career_id", "attribute_group", "attribute_key", name="uq_career_attribute"),
    )
    op.create_index(
        op.f("ix_mnp_career_attributes_attribute_group"), "mnp_career_attributes", ["attribute_group"], unique=False
    )
    op.create_index(
        op.f("ix_mnp_career_attributes_career_id"), "mnp_career_attributes", ["career_id"], unique=False
    )
    op.create_table(
        "mnp_career_cards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_session_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_mode", sa.String(length=32), nullable=False),
        sa.Column("completeness_score_internal", sa.Float(), nullable=True),
        sa.Column("confidence_score_internal", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["assessment_session_id"], ["mnp_assessment_sessions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mnp_career_cards_user_id"), "mnp_career_cards", ["user_id"], unique=False)
    op.create_index("uq_one_career_card_per_user", "mnp_career_cards", ["user_id"], unique=True)
    op.create_table(
        "mnp_career_knowledge_requirements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_id", sa.Uuid(), nullable=False),
        sa.Column("importance", sa.String(length=32), nullable=False),
        sa.Column("required_level", sa.String(length=16), nullable=False),
        sa.Column("requirement_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["mnp_careers.id"]),
        sa.ForeignKeyConstraint(["knowledge_id"], ["mnp_knowledge.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("career_id", "knowledge_id", name="uq_career_knowledge_requirement"),
    )
    op.create_index(
        op.f("ix_mnp_career_knowledge_requirements_career_id"),
        "mnp_career_knowledge_requirements",
        ["career_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mnp_career_knowledge_requirements_knowledge_id"),
        "mnp_career_knowledge_requirements",
        ["knowledge_id"],
        unique=False,
    )
    op.create_table(
        "mnp_career_relations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("from_career_id", sa.Uuid(), nullable=False),
        sa.Column("to_career_id", sa.Uuid(), nullable=False),
        sa.Column("relation_type", sa.String(length=32), nullable=False),
        sa.Column("strength", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["from_career_id"], ["mnp_careers.id"]),
        sa.ForeignKeyConstraint(["to_career_id"], ["mnp_careers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_career_id", "to_career_id", "relation_type", name="uq_career_relation"),
    )
    op.create_index(
        op.f("ix_mnp_career_relations_from_career_id"), "mnp_career_relations", ["from_career_id"], unique=False
    )
    op.create_index(
        op.f("ix_mnp_career_relations_to_career_id"), "mnp_career_relations", ["to_career_id"], unique=False
    )
    op.create_table(
        "mnp_career_requirements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=True),
        sa.Column("hardness", sa.String(length=32), nullable=False),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("source_version", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["career_id"], ["mnp_careers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_career_requirements_career_id"), "mnp_career_requirements", ["career_id"], unique=False
    )
    op.create_index(
        op.f("ix_mnp_career_requirements_category"), "mnp_career_requirements", ["category"], unique=False
    )
    op.create_table(
        "mnp_career_skill_requirements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("importance", sa.String(length=32), nullable=False),
        sa.Column("required_level", sa.String(length=16), nullable=False),
        sa.Column("requirement_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("source_version", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["career_id"], ["mnp_careers.id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["mnp_skills.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("career_id", "skill_id", name="uq_career_skill_requirement"),
    )
    op.create_index(
        op.f("ix_mnp_career_skill_requirements_career_id"),
        "mnp_career_skill_requirements",
        ["career_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mnp_career_skill_requirements_skill_id"),
        "mnp_career_skill_requirements",
        ["skill_id"],
        unique=False,
    )
    op.create_table(
        "mnp_career_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_id", sa.Uuid(), nullable=False),
        sa.Column("task_code", sa.String(length=64), nullable=False),
        sa.Column("title_uk", sa.String(length=500), nullable=False),
        sa.Column("title_en", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("importance", sa.String(length=32), nullable=False),
        sa.Column("frequency", sa.String(length=32), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("source_version", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["career_id"], ["mnp_careers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mnp_career_tasks_career_id"), "mnp_career_tasks", ["career_id"], unique=False)
    op.create_table(
        "mnp_market_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_id", sa.Uuid(), nullable=False),
        sa.Column("country", sa.String(length=8), nullable=False),
        sa.Column("region", sa.String(length=128), nullable=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=True),
        sa.Column("data_quality", sa.String(length=32), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=True),
        sa.Column("vacancy_count", sa.Integer(), nullable=True),
        sa.Column("demand_trend", sa.String(length=16), nullable=True),
        sa.Column("remote_share", sa.Float(), nullable=True),
        sa.Column("entry_level_availability", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["mnp_careers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_market_snapshots_career_id"), "mnp_market_snapshots", ["career_id"], unique=False
    )
    op.create_table(
        "mnp_opportunities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_type", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("location", sa.String(length=128), nullable=True),
        sa.Column("is_remote", sa.Boolean(), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("starts_at", sa.Date(), nullable=True),
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["career_id"], ["mnp_careers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mnp_opportunities_career_id"), "mnp_opportunities", ["career_id"], unique=False)
    op.create_table(
        "mnp_source_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_session_id", sa.Uuid(), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("storage_ref", sa.String(length=500), nullable=False),
        sa.Column("text_extraction_status", sa.String(length=32), nullable=False),
        sa.Column("parser_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["assessment_session_id"], ["mnp_assessment_sessions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_source_documents_assessment_session_id"),
        "mnp_source_documents",
        ["assessment_session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mnp_source_documents_user_id"), "mnp_source_documents", ["user_id"], unique=False
    )
    op.create_table(
        "mnp_career_card_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_card_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["career_card_id"], ["mnp_career_cards.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("career_card_id", "version", name="uq_career_card_version"),
    )
    op.create_index(
        op.f("ix_mnp_career_card_versions_career_card_id"),
        "mnp_career_card_versions",
        ["career_card_id"],
        unique=False,
    )
    op.create_table(
        "mnp_career_goals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_card_id", sa.Uuid(), nullable=False),
        sa.Column("goal_type", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("time_horizon", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["career_card_id"], ["mnp_career_cards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_career_goals_career_card_id"), "mnp_career_goals", ["career_card_id"], unique=False
    )
    op.create_table(
        "mnp_constraints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_card_id", sa.Uuid(), nullable=False),
        sa.Column("constraint_type", sa.String(length=64), nullable=False),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["career_card_id"], ["mnp_career_cards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_constraints_career_card_id"), "mnp_constraints", ["career_card_id"], unique=False
    )
    op.create_table(
        "mnp_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_card_id", sa.Uuid(), nullable=False),
        sa.Column("credential_type", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("issuer", sa.String(length=255), nullable=True),
        sa.Column("issued_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["career_card_id"], ["mnp_career_cards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_credentials_career_card_id"), "mnp_credentials", ["career_card_id"], unique=False
    )
    op.create_table(
        "mnp_educations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_card_id", sa.Uuid(), nullable=False),
        sa.Column("level", sa.String(length=64), nullable=False),
        sa.Column("field", sa.String(length=255), nullable=True),
        sa.Column("institution", sa.String(length=255), nullable=True),
        sa.Column("qualification", sa.String(length=255), nullable=True),
        sa.Column("graduation_year", sa.Integer(), nullable=True),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.Column("recognition", sa.String(length=64), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["career_card_id"], ["mnp_career_cards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_educations_career_card_id"), "mnp_educations", ["career_card_id"], unique=False
    )
    op.create_table(
        "mnp_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_card_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_ref", sa.String(length=500), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("strength_internal", sa.Float(), nullable=False),
        sa.Column("parser_confidence", sa.Float(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["career_card_id"], ["mnp_career_cards.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["mnp_source_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mnp_evidence_career_card_id"), "mnp_evidence", ["career_card_id"], unique=False)
    op.create_index(op.f("ix_mnp_evidence_entity_id"), "mnp_evidence", ["entity_id"], unique=False)
    op.create_index(op.f("ix_mnp_evidence_entity_type"), "mnp_evidence", ["entity_type"], unique=False)
    op.create_table(
        "mnp_experiences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_card_id", sa.Uuid(), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("raw_job_title", sa.String(length=255), nullable=False),
        sa.Column("normalized_career_id", sa.Uuid(), nullable=True),
        sa.Column("industry_raw", sa.String(length=255), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("duration_months", sa.Integer(), nullable=True),
        sa.Column("seniority", sa.String(length=32), nullable=True),
        sa.Column("responsibilities_raw", sa.Text(), nullable=True),
        sa.Column("management_scope", sa.Boolean(), nullable=True),
        sa.Column("team_size", sa.Integer(), nullable=True),
        sa.Column("tools_raw", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["career_card_id"], ["mnp_career_cards.id"]),
        sa.ForeignKeyConstraint(["normalized_career_id"], ["mnp_careers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_experiences_career_card_id"), "mnp_experiences", ["career_card_id"], unique=False
    )
    op.create_table(
        "mnp_income_targets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_card_id", sa.Uuid(), nullable=False),
        sa.Column("current_income", sa.Float(), nullable=True),
        sa.Column("target_income", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["career_card_id"], ["mnp_career_cards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_income_targets_career_card_id"), "mnp_income_targets", ["career_card_id"], unique=True
    )
    op.create_table(
        "mnp_languages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_card_id", sa.Uuid(), nullable=False),
        sa.Column("language_code", sa.String(length=8), nullable=False),
        sa.Column("overall_level", sa.String(length=16), nullable=True),
        sa.Column("speaking_level", sa.String(length=16), nullable=True),
        sa.Column("reading_level", sa.String(length=16), nullable=True),
        sa.Column("writing_level", sa.String(length=16), nullable=True),
        sa.Column("certified_level", sa.String(length=32), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["career_card_id"], ["mnp_career_cards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_languages_career_card_id"), "mnp_languages", ["career_card_id"], unique=False
    )
    op.create_table(
        "mnp_learning_capacities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_card_id", sa.Uuid(), nullable=False),
        sa.Column("hours_per_week", sa.Float(), nullable=True),
        sa.Column("max_months", sa.Integer(), nullable=True),
        sa.Column("budget", sa.Float(), nullable=True),
        sa.Column("willing_new_credential", sa.Boolean(), nullable=True),
        sa.Column("willing_lower_entry_role", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["career_card_id"], ["mnp_career_cards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_learning_capacities_career_card_id"),
        "mnp_learning_capacities",
        ["career_card_id"],
        unique=True,
    )
    op.create_table(
        "mnp_match_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_card_id", sa.Uuid(), nullable=False),
        sa.Column("career_card_version", sa.Integer(), nullable=False),
        sa.Column("assessment_session_id", sa.Uuid(), nullable=False),
        sa.Column("methodology_version", sa.String(length=32), nullable=False),
        sa.Column("matching_engine_version", sa.String(length=32), nullable=False),
        sa.Column("career_kb_version", sa.String(length=32), nullable=False),
        sa.Column("market_data_version", sa.String(length=32), nullable=True),
        sa.Column("ranking_mode", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["assessment_session_id"], ["mnp_assessment_sessions.id"]),
        sa.ForeignKeyConstraint(["career_card_id"], ["mnp_career_cards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_match_runs_career_card_id"), "mnp_match_runs", ["career_card_id"], unique=False
    )
    op.create_table(
        "mnp_person_knowledge",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_card_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_id", sa.Uuid(), nullable=False),
        sa.Column("proficiency_level", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["career_card_id"], ["mnp_career_cards.id"]),
        sa.ForeignKeyConstraint(["knowledge_id"], ["mnp_knowledge.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("career_card_id", "knowledge_id", name="uq_person_knowledge"),
    )
    op.create_index(
        op.f("ix_mnp_person_knowledge_career_card_id"), "mnp_person_knowledge", ["career_card_id"], unique=False
    )
    op.create_index(
        op.f("ix_mnp_person_knowledge_knowledge_id"), "mnp_person_knowledge", ["knowledge_id"], unique=False
    )
    op.create_table(
        "mnp_person_skills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_card_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("proficiency_level", sa.String(length=32), nullable=False),
        sa.Column("evidence_strength", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("years_used", sa.Float(), nullable=True),
        sa.Column("last_used_at", sa.Date(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["career_card_id"], ["mnp_career_cards.id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["mnp_skills.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("career_card_id", "skill_id", name="uq_person_skill"),
    )
    op.create_index(
        op.f("ix_mnp_person_skills_career_card_id"), "mnp_person_skills", ["career_card_id"], unique=False
    )
    op.create_index(op.f("ix_mnp_person_skills_skill_id"), "mnp_person_skills", ["skill_id"], unique=False)
    op.create_table(
        "mnp_person_work_values",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_card_id", sa.Uuid(), nullable=False),
        sa.Column("work_value_id", sa.Uuid(), nullable=False),
        sa.Column("priority_rank", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["career_card_id"], ["mnp_career_cards.id"]),
        sa.ForeignKeyConstraint(["work_value_id"], ["mnp_work_values.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("career_card_id", "work_value_id", name="uq_person_work_value"),
    )
    op.create_index(
        op.f("ix_mnp_person_work_values_career_card_id"),
        "mnp_person_work_values",
        ["career_card_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mnp_person_work_values_work_value_id"),
        "mnp_person_work_values",
        ["work_value_id"],
        unique=False,
    )
    op.create_table(
        "mnp_preference_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_card_id", sa.Uuid(), nullable=False),
        sa.Column("preferred_work_object", sa.String(length=32), nullable=True),
        sa.Column("autonomy_preference", sa.Float(), nullable=True),
        sa.Column("teamwork_preference", sa.Float(), nullable=True),
        sa.Column("customer_interaction_preference", sa.Float(), nullable=True),
        sa.Column("routine_vs_novelty_preference", sa.Float(), nullable=True),
        sa.Column("leadership_preference", sa.Float(), nullable=True),
        sa.Column("physical_activity_preference", sa.Float(), nullable=True),
        sa.Column("work_format", sa.String(length=32), nullable=True),
        sa.Column("location_region", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(["career_card_id"], ["mnp_career_cards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_preference_profiles_career_card_id"),
        "mnp_preference_profiles",
        ["career_card_id"],
        unique=True,
    )
    op.create_table(
        "mnp_salary_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("market_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("percentile_25", sa.Float(), nullable=True),
        sa.Column("median", sa.Float(), nullable=True),
        sa.Column("percentile_75", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["market_snapshot_id"], ["mnp_market_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_salary_snapshots_market_snapshot_id"),
        "mnp_salary_snapshots",
        ["market_snapshot_id"],
        unique=False,
    )
    op.create_table(
        "mnp_unmapped_phrases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_card_id", sa.Uuid(), nullable=False),
        sa.Column("raw_phrase", sa.String(length=500), nullable=False),
        sa.Column("context", sa.String(length=64), nullable=True),
        sa.Column("resolved_skill_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["career_card_id"], ["mnp_career_cards.id"]),
        sa.ForeignKeyConstraint(["resolved_skill_id"], ["mnp_skills.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_unmapped_phrases_career_card_id"), "mnp_unmapped_phrases", ["career_card_id"], unique=False
    )
    op.create_table(
        "mnp_achievements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_card_id", sa.Uuid(), nullable=False),
        sa.Column("experience_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["career_card_id"], ["mnp_career_cards.id"]),
        sa.ForeignKeyConstraint(["experience_id"], ["mnp_experiences.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_achievements_career_card_id"), "mnp_achievements", ["career_card_id"], unique=False
    )
    op.create_table(
        "mnp_career_matches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("match_run_id", sa.Uuid(), nullable=False),
        sa.Column("career_id", sa.Uuid(), nullable=False),
        sa.Column("rank_overall", sa.Integer(), nullable=False),
        sa.Column("overall_score_internal", sa.Float(), nullable=False),
        sa.Column("display_band", sa.String(length=32), nullable=False),
        sa.Column("feasibility_status", sa.String(length=32), nullable=False),
        sa.Column("transition_distance", sa.String(length=32), nullable=False),
        sa.Column("confidence_internal", sa.String(length=32), nullable=False),
        sa.Column("is_featured", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["career_id"], ["mnp_careers.id"]),
        sa.ForeignKeyConstraint(["match_run_id"], ["mnp_match_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_career_matches_career_id"), "mnp_career_matches", ["career_id"], unique=False
    )
    op.create_index(
        op.f("ix_mnp_career_matches_match_run_id"), "mnp_career_matches", ["match_run_id"], unique=False
    )
    op.create_table(
        "mnp_career_routes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_match_id", sa.Uuid(), nullable=False),
        sa.Column("route_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("duration_estimate", sa.String(length=64), nullable=True),
        sa.Column("cost_estimate", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["career_match_id"], ["mnp_career_matches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_career_routes_career_match_id"), "mnp_career_routes", ["career_match_id"], unique=False
    )
    op.create_table(
        "mnp_feasibility_findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_match_id", sa.Uuid(), nullable=False),
        sa.Column("finding_type", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("requirement_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("explanation_code", sa.String(length=64), nullable=False),
        sa.Column("evidence_ref", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["career_match_id"], ["mnp_career_matches.id"]),
        sa.ForeignKeyConstraint(["requirement_id"], ["mnp_career_requirements.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_feasibility_findings_career_match_id"),
        "mnp_feasibility_findings",
        ["career_match_id"],
        unique=False,
    )
    op.create_table(
        "mnp_match_components",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_match_id", sa.Uuid(), nullable=False),
        sa.Column("component_type", sa.String(length=32), nullable=False),
        sa.Column("score_internal", sa.Float(), nullable=True),
        sa.Column("band", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("explanation_code", sa.String(length=64), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["career_match_id"], ["mnp_career_matches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_match_components_career_match_id"),
        "mnp_match_components",
        ["career_match_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mnp_match_components_component_type"),
        "mnp_match_components",
        ["component_type"],
        unique=False,
    )
    op.create_table(
        "mnp_personal_gaps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("career_match_id", sa.Uuid(), nullable=False),
        sa.Column("gap_type", sa.String(length=32), nullable=False),
        sa.Column("reference_id", sa.Uuid(), nullable=True),
        sa.Column("reference_label", sa.String(length=255), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("priority_internal", sa.Float(), nullable=False),
        sa.Column("estimated_time", sa.String(length=64), nullable=True),
        sa.Column("estimated_cost", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["career_match_id"], ["mnp_career_matches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mnp_personal_gaps_career_match_id"), "mnp_personal_gaps", ["career_match_id"], unique=False
    )
    op.create_table(
        "mnp_route_steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("route_id", sa.Uuid(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_skill_id", sa.Uuid(), nullable=True),
        sa.Column("opportunity_id", sa.Uuid(), nullable=True),
        sa.Column("duration_estimate", sa.String(length=64), nullable=True),
        sa.Column("completion_rule", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["opportunity_id"], ["mnp_opportunities.id"]),
        sa.ForeignKeyConstraint(["route_id"], ["mnp_career_routes.id"]),
        sa.ForeignKeyConstraint(["target_skill_id"], ["mnp_skills.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mnp_route_steps_route_id"), "mnp_route_steps", ["route_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_mnp_route_steps_route_id"), table_name="mnp_route_steps")
    op.drop_table("mnp_route_steps")
    op.drop_index(op.f("ix_mnp_personal_gaps_career_match_id"), table_name="mnp_personal_gaps")
    op.drop_table("mnp_personal_gaps")
    op.drop_index(op.f("ix_mnp_match_components_component_type"), table_name="mnp_match_components")
    op.drop_index(op.f("ix_mnp_match_components_career_match_id"), table_name="mnp_match_components")
    op.drop_table("mnp_match_components")
    op.drop_index(op.f("ix_mnp_feasibility_findings_career_match_id"), table_name="mnp_feasibility_findings")
    op.drop_table("mnp_feasibility_findings")
    op.drop_index(op.f("ix_mnp_career_routes_career_match_id"), table_name="mnp_career_routes")
    op.drop_table("mnp_career_routes")
    op.drop_index(op.f("ix_mnp_career_matches_match_run_id"), table_name="mnp_career_matches")
    op.drop_index(op.f("ix_mnp_career_matches_career_id"), table_name="mnp_career_matches")
    op.drop_table("mnp_career_matches")
    op.drop_index(op.f("ix_mnp_achievements_career_card_id"), table_name="mnp_achievements")
    op.drop_table("mnp_achievements")
    op.drop_index(op.f("ix_mnp_unmapped_phrases_career_card_id"), table_name="mnp_unmapped_phrases")
    op.drop_table("mnp_unmapped_phrases")
    op.drop_index(op.f("ix_mnp_salary_snapshots_market_snapshot_id"), table_name="mnp_salary_snapshots")
    op.drop_table("mnp_salary_snapshots")
    op.drop_index(op.f("ix_mnp_preference_profiles_career_card_id"), table_name="mnp_preference_profiles")
    op.drop_table("mnp_preference_profiles")
    op.drop_index(op.f("ix_mnp_person_work_values_work_value_id"), table_name="mnp_person_work_values")
    op.drop_index(op.f("ix_mnp_person_work_values_career_card_id"), table_name="mnp_person_work_values")
    op.drop_table("mnp_person_work_values")
    op.drop_index(op.f("ix_mnp_person_skills_skill_id"), table_name="mnp_person_skills")
    op.drop_index(op.f("ix_mnp_person_skills_career_card_id"), table_name="mnp_person_skills")
    op.drop_table("mnp_person_skills")
    op.drop_index(op.f("ix_mnp_person_knowledge_knowledge_id"), table_name="mnp_person_knowledge")
    op.drop_index(op.f("ix_mnp_person_knowledge_career_card_id"), table_name="mnp_person_knowledge")
    op.drop_table("mnp_person_knowledge")
    op.drop_index(op.f("ix_mnp_match_runs_career_card_id"), table_name="mnp_match_runs")
    op.drop_table("mnp_match_runs")
    op.drop_index(op.f("ix_mnp_learning_capacities_career_card_id"), table_name="mnp_learning_capacities")
    op.drop_table("mnp_learning_capacities")
    op.drop_index(op.f("ix_mnp_languages_career_card_id"), table_name="mnp_languages")
    op.drop_table("mnp_languages")
    op.drop_index(op.f("ix_mnp_income_targets_career_card_id"), table_name="mnp_income_targets")
    op.drop_table("mnp_income_targets")
    op.drop_index(op.f("ix_mnp_experiences_career_card_id"), table_name="mnp_experiences")
    op.drop_table("mnp_experiences")
    op.drop_index(op.f("ix_mnp_evidence_entity_type"), table_name="mnp_evidence")
    op.drop_index(op.f("ix_mnp_evidence_entity_id"), table_name="mnp_evidence")
    op.drop_index(op.f("ix_mnp_evidence_career_card_id"), table_name="mnp_evidence")
    op.drop_table("mnp_evidence")
    op.drop_index(op.f("ix_mnp_educations_career_card_id"), table_name="mnp_educations")
    op.drop_table("mnp_educations")
    op.drop_index(op.f("ix_mnp_credentials_career_card_id"), table_name="mnp_credentials")
    op.drop_table("mnp_credentials")
    op.drop_index(op.f("ix_mnp_constraints_career_card_id"), table_name="mnp_constraints")
    op.drop_table("mnp_constraints")
    op.drop_index(op.f("ix_mnp_career_goals_career_card_id"), table_name="mnp_career_goals")
    op.drop_table("mnp_career_goals")
    op.drop_index(op.f("ix_mnp_career_card_versions_career_card_id"), table_name="mnp_career_card_versions")
    op.drop_table("mnp_career_card_versions")
    op.drop_index(op.f("ix_mnp_source_documents_user_id"), table_name="mnp_source_documents")
    op.drop_index(op.f("ix_mnp_source_documents_assessment_session_id"), table_name="mnp_source_documents")
    op.drop_table("mnp_source_documents")
    op.drop_index(op.f("ix_mnp_opportunities_career_id"), table_name="mnp_opportunities")
    op.drop_table("mnp_opportunities")
    op.drop_index(op.f("ix_mnp_market_snapshots_career_id"), table_name="mnp_market_snapshots")
    op.drop_table("mnp_market_snapshots")
    op.drop_index(op.f("ix_mnp_career_tasks_career_id"), table_name="mnp_career_tasks")
    op.drop_table("mnp_career_tasks")
    op.drop_index(op.f("ix_mnp_career_skill_requirements_skill_id"), table_name="mnp_career_skill_requirements")
    op.drop_index(
        op.f("ix_mnp_career_skill_requirements_career_id"), table_name="mnp_career_skill_requirements"
    )
    op.drop_table("mnp_career_skill_requirements")
    op.drop_index(op.f("ix_mnp_career_requirements_category"), table_name="mnp_career_requirements")
    op.drop_index(op.f("ix_mnp_career_requirements_career_id"), table_name="mnp_career_requirements")
    op.drop_table("mnp_career_requirements")
    op.drop_index(op.f("ix_mnp_career_relations_to_career_id"), table_name="mnp_career_relations")
    op.drop_index(op.f("ix_mnp_career_relations_from_career_id"), table_name="mnp_career_relations")
    op.drop_table("mnp_career_relations")
    op.drop_index(
        op.f("ix_mnp_career_knowledge_requirements_knowledge_id"),
        table_name="mnp_career_knowledge_requirements",
    )
    op.drop_index(
        op.f("ix_mnp_career_knowledge_requirements_career_id"), table_name="mnp_career_knowledge_requirements"
    )
    op.drop_table("mnp_career_knowledge_requirements")
    op.drop_index("uq_one_career_card_per_user", table_name="mnp_career_cards")
    op.drop_index(op.f("ix_mnp_career_cards_user_id"), table_name="mnp_career_cards")
    op.drop_table("mnp_career_cards")
    op.drop_index(op.f("ix_mnp_career_attributes_career_id"), table_name="mnp_career_attributes")
    op.drop_index(op.f("ix_mnp_career_attributes_attribute_group"), table_name="mnp_career_attributes")
    op.drop_table("mnp_career_attributes")
    op.drop_index(op.f("ix_mnp_career_aliases_career_id"), table_name="mnp_career_aliases")
    op.drop_index(op.f("ix_mnp_career_aliases_alias"), table_name="mnp_career_aliases")
    op.drop_table("mnp_career_aliases")
    op.drop_index(op.f("ix_mnp_skill_aliases_skill_id"), table_name="mnp_skill_aliases")
    op.drop_index(op.f("ix_mnp_skill_aliases_alias"), table_name="mnp_skill_aliases")
    op.drop_table("mnp_skill_aliases")
    op.drop_index(
        op.f("ix_mnp_learning_opportunity_skills_skill_id"), table_name="mnp_learning_opportunity_skills"
    )
    op.drop_index(
        op.f("ix_mnp_learning_opportunity_skills_learning_opportunity_id"),
        table_name="mnp_learning_opportunity_skills",
    )
    op.drop_table("mnp_learning_opportunity_skills")
    op.drop_index(op.f("ix_mnp_careers_status"), table_name="mnp_careers")
    op.drop_index(op.f("ix_mnp_careers_code"), table_name="mnp_careers")
    op.drop_index(op.f("ix_mnp_careers_career_family_id"), table_name="mnp_careers")
    op.drop_table("mnp_careers")
    op.drop_index(op.f("ix_mnp_assessment_sessions_user_id"), table_name="mnp_assessment_sessions")
    op.drop_table("mnp_assessment_sessions")
    op.drop_table("mnp_work_values")
    op.drop_index(op.f("ix_mnp_skills_status"), table_name="mnp_skills")
    op.drop_index(op.f("ix_mnp_skills_skill_type"), table_name="mnp_skills")
    op.drop_index(op.f("ix_mnp_skills_skill_family"), table_name="mnp_skills")
    op.drop_table("mnp_skills")
    op.drop_table("mnp_learning_opportunities")
    op.drop_table("mnp_knowledge")
    op.drop_index(op.f("ix_mnp_external_mappings_mnp_entity_id"), table_name="mnp_external_mappings")
    op.drop_table("mnp_external_mappings")
    op.drop_table("mnp_career_families")
