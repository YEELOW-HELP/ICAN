"""Matching V1 M1: versioned BASIC structured assessment data model

Revision ID: 8e2c4a71d9f3
Revises: 4f1d7c92e6ab
Create Date: 2026-08-28

Purely additive. 7 new tables, no existing table altered/dropped:

  assessment_scales           scale-level MNP<->O*NET compatibility metadata
                               (mapping_status/matching_usage/source, per
                               MNP_SCALE_TO_ONET_MAPPING_V0.1.md)
  assessment_definitions      one versioned question bank (e.g. the
                               "Matching V1 Alpha Long Form"); at most one
                               is_active=True per mode
  assessment_sections         UI/authoring grouping of items within a
                               definition
  assessment_items            one structured question, with full
                               provenance + profile/matching-usage metadata
  assessment_item_options     options for SINGLE_CHOICE/MULTI_CHOICE items
  basic_assessment_attempts   one BASIC_STRUCTURED attempt per user; at
                               most one NOT_STARTED/IN_PROGRESS at a time
                               (mirrors interview_sessions' one-unfinished-
                               session-per-user pattern, but is a wholly
                               separate table -- BASIC and PRO Hybrid
                               attempts never interact)
  basic_assessment_answers    immutable structured answers, "latest per
                               item_id wins" read convention, same shape
                               as the existing `answers` table's
                               idempotency-key pattern

No Stage 1/2/3 table (identity_users, interview_sessions, answers,
interview_messages, cv_uploads, question_selections) is touched. This
migration only adds two new FKs pointing INTO identity_users
(basic_assessment_attempts.user_id) -- nothing points the other way.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8e2c4a71d9f3"
down_revision: Union[str, None] = "4f1d7c92e6ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assessment_scales",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scale_family", sa.String(length=32), nullable=False),
        sa.Column("scale_key", sa.String(length=64), nullable=False),
        sa.Column("label_uk", sa.String(length=255), nullable=False),
        sa.Column("mapping_status", sa.String(length=16), nullable=False),
        sa.Column("matching_usage", sa.String(length=16), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=True),
        sa.Column("source_element_id", sa.String(length=64), nullable=True),
        sa.Column("source_element_name", sa.String(length=255), nullable=True),
        sa.Column("source_version", sa.String(length=32), nullable=True),
        sa.Column("transformation_version", sa.String(length=32), nullable=True),
        sa.Column("provisional", sa.Boolean(), nullable=False),
        sa.Column("methodology_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scale_family", "scale_key", name="uq_assessment_scale_family_key"),
    )
    op.create_index("ix_assessment_scales_scale_family", "assessment_scales", ["scale_family"])

    op.create_table(
        "assessment_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_version", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("methodology_version", sa.String(length=32), nullable=False),
        sa.Column("title_uk", sa.String(length=255), nullable=False),
        sa.Column("description_uk", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_version", name="uq_assessment_definition_version"),
    )
    op.create_index("ix_assessment_definitions_mode", "assessment_definitions", ["mode"])
    op.create_index(
        "uq_one_active_definition_per_mode",
        "assessment_definitions",
        ["mode"],
        unique=True,
        postgresql_where=sa.text("is_active"),
        sqlite_where=sa.text("is_active"),
    )

    op.create_table(
        "assessment_sections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("definition_id", sa.Uuid(), nullable=False),
        sa.Column("section_key", sa.String(length=64), nullable=False),
        sa.Column("title_uk", sa.String(length=255), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["definition_id"], ["assessment_definitions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("definition_id", "section_key", name="uq_assessment_section_key"),
    )
    op.create_index("ix_assessment_sections_definition_id", "assessment_sections", ["definition_id"])

    op.create_table(
        "assessment_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("definition_id", sa.Uuid(), nullable=False),
        sa.Column("section_id", sa.Uuid(), nullable=False),
        sa.Column("scale_id", sa.Uuid(), nullable=False),
        sa.Column("item_key", sa.String(length=64), nullable=False),
        sa.Column("scale_family", sa.String(length=32), nullable=False),
        sa.Column("scale_key", sa.String(length=64), nullable=False),
        sa.Column("subscale_key", sa.String(length=64), nullable=True),
        sa.Column("question_uk", sa.Text(), nullable=False),
        sa.Column("response_type", sa.String(length=16), nullable=False),
        sa.Column("reverse_scored", sa.Boolean(), nullable=False),
        sa.Column("reverse_exempt", sa.Boolean(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("profile_usage", sa.Boolean(), nullable=False),
        sa.Column("matching_usage", sa.String(length=16), nullable=False),
        sa.Column("source_reference", sa.String(length=255), nullable=False),
        sa.Column("methodology_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["definition_id"], ["assessment_definitions.id"]),
        sa.ForeignKeyConstraint(["section_id"], ["assessment_sections.id"]),
        sa.ForeignKeyConstraint(["scale_id"], ["assessment_scales.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("definition_id", "item_key", name="uq_assessment_item_key"),
    )
    op.create_index("ix_assessment_items_definition_id", "assessment_items", ["definition_id"])
    op.create_index("ix_assessment_items_section_id", "assessment_items", ["section_id"])
    op.create_index("ix_assessment_items_scale_id", "assessment_items", ["scale_id"])
    op.create_index("ix_assessment_items_scale_family", "assessment_items", ["scale_family"])

    op.create_table(
        "assessment_item_options",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("option_key", sa.String(length=64), nullable=False),
        sa.Column("label_uk", sa.String(length=255), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["assessment_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_id", "option_key", name="uq_assessment_item_option_key"),
    )
    op.create_index("ix_assessment_item_options_item_id", "assessment_item_options", ["item_id"])

    op.create_table(
        "basic_assessment_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("definition_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"]),
        sa.ForeignKeyConstraint(["definition_id"], ["assessment_definitions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_basic_assessment_attempts_user_id", "basic_assessment_attempts", ["user_id"])
    op.create_index("ix_basic_assessment_attempts_definition_id", "basic_assessment_attempts", ["definition_id"])
    op.create_index("ix_basic_assessment_attempts_status", "basic_assessment_attempts", ["status"])
    op.create_index(
        "uq_one_open_basic_attempt_per_user",
        "basic_assessment_attempts",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('not_started', 'in_progress')"),
        sqlite_where=sa.text("status IN ('not_started', 'in_progress')"),
    )

    op.create_table(
        "basic_assessment_answers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("response_type", sa.String(length=16), nullable=False),
        sa.Column("numeric_value", sa.Integer(), nullable=True),
        sa.Column("boolean_value", sa.Boolean(), nullable=True),
        sa.Column("selected_option_keys", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["basic_assessment_attempts.id"]),
        sa.ForeignKeyConstraint(["item_id"], ["assessment_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", "idempotency_key", name="uq_basic_answer_attempt_idempotency"),
    )
    op.create_index("ix_basic_assessment_answers_attempt_id", "basic_assessment_answers", ["attempt_id"])
    op.create_index("ix_basic_assessment_answers_item_id", "basic_assessment_answers", ["item_id"])
    op.create_index("ix_basic_assessment_answers_created_at", "basic_assessment_answers", ["created_at"])


def downgrade() -> None:
    op.drop_table("basic_assessment_answers")
    op.drop_index("uq_one_open_basic_attempt_per_user", table_name="basic_assessment_attempts")
    op.drop_table("basic_assessment_attempts")
    op.drop_table("assessment_item_options")
    op.drop_table("assessment_items")
    op.drop_table("assessment_sections")
    op.drop_index("uq_one_active_definition_per_mode", table_name="assessment_definitions")
    op.drop_table("assessment_definitions")
    op.drop_table("assessment_scales")
