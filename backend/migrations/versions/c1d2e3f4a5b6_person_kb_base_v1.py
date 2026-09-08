"""PERSON KB BASE V1 -- canonical Person KB

Revision ID: c1d2e3f4a5b6
Revises: a7b8c9d0e1f2
Create Date: 2026-09-01

Additive. ONE canonical Person KB root (`mnp_persons`) + fact tables
(education / credentials / experience / activities / skills / languages /
documents), fed by user-manual / CV-review / admin-manual flows. Reuses
the canonical `mnp_skills` taxonomy and FK to `mnp_careers` for an
optional experience -> Career mapping. Nothing in the existing person-side
schema (`mnp_career_cards` & children, Matching) is touched. Enum-backed
columns stay plain `String` (project convention). Boolean-free: every
yes/no fact is a tri-state string ('yes' | 'no' | 'unknown').
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOW = sa.text("CURRENT_TIMESTAMP")


def _fact_columns() -> list[sa.Column]:
    return [
        sa.Column("supporting_document_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_state", sa.String(length=24), nullable=False,
                  server_default=sa.text("'self_reported'")),
        sa.Column("source", sa.String(length=16), nullable=False, server_default=sa.text("'user_manual'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "mnp_persons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("identity_user_id", sa.Uuid(), nullable=True),
        sa.Column("first_name", sa.String(length=120), nullable=False),
        sa.Column("last_name", sa.String(length=120), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("telegram_username", sa.String(length=64), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("region", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("source", sa.String(length=16), nullable=False, server_default=sa.text("'admin_manual'")),
        sa.Column("profile_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("has_driver_license", sa.String(length=8), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("driver_license_categories", sa.String(length=64), nullable=True),
        sa.Column("has_car", sa.String(length=8), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("willing_to_relocate", sa.String(length=8), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("work_geography", sa.JSON(), nullable=True),
        sa.Column("work_format", sa.String(length=16), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["identity_user_id"], ["identity_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identity_user_id"),
    )
    op.create_index(op.f("ix_mnp_persons_identity_user_id"), "mnp_persons", ["identity_user_id"], unique=False)
    op.create_index(op.f("ix_mnp_persons_status"), "mnp_persons", ["status"], unique=False)

    op.create_table(
        "mnp_person_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False, server_default=sa.text("'other'")),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("storage_ref", sa.String(length=500), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["mnp_persons.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mnp_person_documents_person_id"), "mnp_person_documents", ["person_id"], unique=False)

    op.create_table(
        "mnp_person_educations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("education_level", sa.String(length=24), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("institution_name", sa.String(length=255), nullable=True),
        sa.Column("specialty_or_qualification", sa.String(length=255), nullable=True),
        sa.Column("start_year", sa.Integer(), nullable=True),
        sa.Column("end_year", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("description", sa.Text(), nullable=True),
        *_fact_columns(),
        sa.ForeignKeyConstraint(["person_id"], ["mnp_persons.id"]),
        sa.ForeignKeyConstraint(["supporting_document_id"], ["mnp_person_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mnp_person_educations_person_id"), "mnp_person_educations", ["person_id"], unique=False)

    op.create_table(
        "mnp_person_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("credential_type", sa.String(length=32), nullable=False, server_default=sa.text("'other'")),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=255), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("credential_number", sa.String(length=120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        *_fact_columns(),
        sa.ForeignKeyConstraint(["person_id"], ["mnp_persons.id"]),
        sa.ForeignKeyConstraint(["supporting_document_id"], ["mnp_person_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mnp_person_credentials_person_id"), "mnp_person_credentials", ["person_id"], unique=False)

    op.create_table(
        "mnp_person_experiences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("raw_job_title", sa.String(length=255), nullable=False),
        sa.Column("canonical_career_id", sa.Uuid(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.String(length=8), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("responsibilities_description", sa.Text(), nullable=True),
        sa.Column("achievements", sa.Text(), nullable=True),
        sa.Column("tools_used", sa.Text(), nullable=True),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("employment_type", sa.String(length=64), nullable=True),
        *_fact_columns(),
        sa.ForeignKeyConstraint(["person_id"], ["mnp_persons.id"]),
        sa.ForeignKeyConstraint(["canonical_career_id"], ["mnp_careers.id"]),
        sa.ForeignKeyConstraint(["supporting_document_id"], ["mnp_person_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mnp_person_experiences_person_id"), "mnp_person_experiences", ["person_id"], unique=False)

    op.create_table(
        "mnp_person_activities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("activity_type", sa.String(length=32), nullable=False, server_default=sa.text("'other'")),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("organization", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=255), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("result_or_achievement", sa.Text(), nullable=True),
        *_fact_columns(),
        sa.ForeignKeyConstraint(["person_id"], ["mnp_persons.id"]),
        sa.ForeignKeyConstraint(["supporting_document_id"], ["mnp_person_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mnp_person_activities_person_id"), "mnp_person_activities", ["person_id"], unique=False)

    op.create_table(
        "mnp_person_skills_v1",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_skill_id", sa.Uuid(), nullable=True),
        sa.Column("raw_input", sa.String(length=255), nullable=True),
        sa.Column("custom_status", sa.String(length=16), nullable=False, server_default=sa.text("'canonical'")),
        sa.Column("proficiency", sa.String(length=8), nullable=True),
        sa.Column("years_used", sa.Integer(), nullable=True),
        sa.Column("last_used_year", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_fact_columns(),
        sa.ForeignKeyConstraint(["person_id"], ["mnp_persons.id"]),
        sa.ForeignKeyConstraint(["canonical_skill_id"], ["mnp_skills.id"]),
        sa.ForeignKeyConstraint(["supporting_document_id"], ["mnp_person_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mnp_person_skills_v1_person_id"), "mnp_person_skills_v1", ["person_id"], unique=False)
    op.create_index(op.f("ix_mnp_person_skills_v1_canonical_skill_id"), "mnp_person_skills_v1",
                    ["canonical_skill_id"], unique=False)

    op.create_table(
        "mnp_person_languages_v1",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("language", sa.String(length=64), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("certificate", sa.String(length=255), nullable=True),
        *_fact_columns(),
        sa.ForeignKeyConstraint(["person_id"], ["mnp_persons.id"]),
        sa.ForeignKeyConstraint(["supporting_document_id"], ["mnp_person_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mnp_person_languages_v1_person_id"), "mnp_person_languages_v1", ["person_id"], unique=False)


def downgrade() -> None:
    op.drop_table("mnp_person_languages_v1")
    op.drop_table("mnp_person_skills_v1")
    op.drop_table("mnp_person_activities")
    op.drop_table("mnp_person_experiences")
    op.drop_table("mnp_person_credentials")
    op.drop_table("mnp_person_educations")
    op.drop_table("mnp_person_documents")
    op.drop_table("mnp_persons")
