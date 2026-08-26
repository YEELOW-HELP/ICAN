"""Stage 1: canonical identity, consent, product access, assessment engine

Revision ID: cd3d7f6f9e54
Revises: b1f3c9a02e11
Create Date: 2026-08-26

Founder Product Reconciliation Stage 1 (docs/product/15_MIY_NAPRYAM_V1_IMPLEMENTATION_ROADMAP.md).
Purely additive: 15 new tables, one widened enum on the existing
`admin_users.role` column (SUPER_ADMIN/REVIEWER added), and one new
nullable bridge column on the legacy `users` table
(`canonical_user_id`, unset for every existing row). No existing table
is dropped, renamed, or has a column removed. No data is backfilled or
migrated by this revision -- see app/db/models_identity.py's module
docstring for why.

Migration ordering follows FK dependency order exactly; downgrade
reverses it. Rollback note: downgrading this revision is safe only
before real Stage 1 traffic exists -- once interview_sessions/answers/
entitlements hold real user data, dropping these tables is destructive
and requires an explicit, separately reviewed decision, not a routine
`alembic downgrade`.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "cd3d7f6f9e54"
down_revision: Union[str, None] = "b1f3c9a02e11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- Product Access configuration (no FKs) ----
    op.create_table(
        "product_plans",
        sa.Column("plan_code", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("price_amount_minor", sa.Integer(), nullable=False),
        sa.Column("price_currency", sa.String(length=8), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("plan_code"),
    )
    # Price as configuration data, not hard-coded authorization logic
    # (docs/product/14_MIY_NAPRYAM_V1_PRODUCT_DEFINITION.md §5).
    op.execute(
        """
        INSERT INTO product_plans (plan_code, display_name, price_amount_minor, price_currency, is_active)
        VALUES
            ('BASIC', 'Basic', 50000, 'UAH', true),
            ('PREMIUM', 'Premium', 100000, 'UAH', true)
        """
    )

    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("contact_info", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ---- Canonical identity ----
    op.create_table(
        "identity_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("locale", sa.String(length=8), server_default="uk", nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "auth_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("provider_username", sa.String(length=255), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_auth_identity_provider_subject"),
    )
    op.create_index(op.f("ix_auth_identities_user_id"), "auth_identities", ["user_id"], unique=False)

    op.create_table(
        "consents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("granted_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "grantor_role",
            sa.Enum("SELF", "GUARDIAN", "AUTHORIZED_REPRESENTATIVE", name="grantorrole", native_enum=False),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["identity_users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_consents_user_id"), "consents", ["user_id"], unique=False)

    # ---- Product Access / Entitlement ----
    op.create_table(
        "package_allocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("plan_code", sa.String(length=32), nullable=False),
        sa.Column("total_quantity", sa.Integer(), nullable=False),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["plan_code"], ["product_plans.plan_code"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_package_allocations_organization_id"), "package_allocations", ["organization_id"], unique=False)

    op.create_table(
        "promo_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("allocation_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("max_redemptions", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["allocation_id"], ["package_allocations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_promo_codes_allocation_id"), "promo_codes", ["allocation_id"], unique=False)
    op.create_index(op.f("ix_promo_codes_code"), "promo_codes", ["code"], unique=True)

    op.create_table(
        "promo_redemptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("promo_code_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["promo_code_id"], ["promo_codes.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("promo_code_id", "user_id", name="uq_promo_redemption_code_user"),
    )
    op.create_index(op.f("ix_promo_redemptions_promo_code_id"), "promo_redemptions", ["promo_code_id"], unique=False)
    op.create_index(op.f("ix_promo_redemptions_user_id"), "promo_redemptions", ["user_id"], unique=False)

    op.create_table(
        "entitlements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_code", sa.String(length=32), nullable=False),
        sa.Column("source", sa.Enum("MANUAL", "PROMO", "PAYMENT", name="entitlementsource", native_enum=False), nullable=False),
        sa.Column("granted_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("redemption_id", sa.Uuid(), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["granted_by_admin_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["plan_code"], ["product_plans.plan_code"]),
        sa.ForeignKeyConstraint(["redemption_id"], ["promo_redemptions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("redemption_id"),
    )
    op.create_index(op.f("ix_entitlements_user_id"), "entitlements", ["user_id"], unique=False)

    # ---- Assessment Engine ----
    op.create_table(
        "interview_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("entitlement_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "ACTIVE", "PAUSED", "COMPLETE", "PROCESSING", "READY", "FAILED", name="assessmentstatus", native_enum=False),
            nullable=False,
        ),
        sa.Column("assessment_version", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("completeness", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["entitlement_id"], ["entitlements.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["identity_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_interview_sessions_user_id"), "interview_sessions", ["user_id"], unique=False)
    op.create_index(op.f("ix_interview_sessions_status"), "interview_sessions", ["status"], unique=False)

    op.create_table(
        "answers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.String(length=64), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("extracted_value", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("contradicts_previous", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "idempotency_key", name="uq_answer_session_idempotency"),
    )
    op.create_index(op.f("ix_answers_session_id"), "answers", ["session_id"], unique=False)
    op.create_index(op.f("ix_answers_question_id"), "answers", ["question_id"], unique=False)
    op.create_index(op.f("ix_answers_created_at"), "answers", ["created_at"], unique=False)

    op.create_table(
        "interview_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "sequence", name="uq_interview_message_session_sequence"),
    )
    op.create_index(op.f("ix_interview_messages_session_id"), "interview_messages", ["session_id"], unique=False)

    op.create_table(
        "question_selections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Enum("MISSING", "LOW_CONFIDENCE", "CONTRADICTION", name="selectionreason", native_enum=False), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answer_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["answer_id"], ["answers.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_question_selections_session_id"), "question_selections", ["session_id"], unique=False)

    op.create_table(
        "cv_uploads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column(
            "extraction_status",
            sa.Enum("PENDING", "SUCCESS", "FAILED", "UNSUPPORTED", "EMPTY", name="cvextractionstatus", native_enum=False),
            nullable=False,
        ),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cv_uploads_session_id"), "cv_uploads", ["session_id"], unique=False)

    # ---- Platform: audit ----
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_admin_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("before_snapshot", sa.JSON(), nullable=True),
        sa.Column("after_snapshot", sa.JSON(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["actor_admin_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["identity_users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_occurred_at"), "audit_logs", ["occurred_at"], unique=False)

    # ---- Widen admin_users.role for SUPER_ADMIN / REVIEWER (additive; no
    # DB-level CHECK constraint exists on this column today, so this only
    # keeps SQLAlchemy's own type metadata in sync with the Python enum). ----
    op.alter_column(
        "admin_users",
        "role",
        existing_type=sa.Enum("ADMIN", "MANAGER", "CAREER_CONSULTANT", name="adminrole", native_enum=False),
        type_=sa.Enum("SUPER_ADMIN", "ADMIN", "MANAGER", "CAREER_CONSULTANT", "REVIEWER", name="adminrole", native_enum=False),
        existing_nullable=False,
    )

    # ---- Legacy bridge column (nullable, unset for all existing rows) ----
    op.add_column("users", sa.Column("canonical_user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_users_canonical_user_id", "users", "identity_users", ["canonical_user_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_canonical_user_id", "users", type_="foreignkey")
    op.drop_column("users", "canonical_user_id")

    op.alter_column(
        "admin_users",
        "role",
        existing_type=sa.Enum("SUPER_ADMIN", "ADMIN", "MANAGER", "CAREER_CONSULTANT", "REVIEWER", name="adminrole", native_enum=False),
        type_=sa.Enum("ADMIN", "MANAGER", "CAREER_CONSULTANT", name="adminrole", native_enum=False),
        existing_nullable=False,
    )

    op.drop_index(op.f("ix_audit_logs_occurred_at"), table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index(op.f("ix_cv_uploads_session_id"), table_name="cv_uploads")
    op.drop_table("cv_uploads")

    op.drop_index(op.f("ix_question_selections_session_id"), table_name="question_selections")
    op.drop_table("question_selections")

    op.drop_index(op.f("ix_interview_messages_session_id"), table_name="interview_messages")
    op.drop_table("interview_messages")

    op.drop_index(op.f("ix_answers_created_at"), table_name="answers")
    op.drop_index(op.f("ix_answers_question_id"), table_name="answers")
    op.drop_index(op.f("ix_answers_session_id"), table_name="answers")
    op.drop_table("answers")

    op.drop_index(op.f("ix_interview_sessions_status"), table_name="interview_sessions")
    op.drop_index(op.f("ix_interview_sessions_user_id"), table_name="interview_sessions")
    op.drop_table("interview_sessions")

    op.drop_index(op.f("ix_entitlements_user_id"), table_name="entitlements")
    op.drop_table("entitlements")

    op.drop_index(op.f("ix_promo_redemptions_user_id"), table_name="promo_redemptions")
    op.drop_index(op.f("ix_promo_redemptions_promo_code_id"), table_name="promo_redemptions")
    op.drop_table("promo_redemptions")

    op.drop_index(op.f("ix_promo_codes_code"), table_name="promo_codes")
    op.drop_index(op.f("ix_promo_codes_allocation_id"), table_name="promo_codes")
    op.drop_table("promo_codes")

    op.drop_index(op.f("ix_package_allocations_organization_id"), table_name="package_allocations")
    op.drop_table("package_allocations")

    op.drop_index(op.f("ix_consents_user_id"), table_name="consents")
    op.drop_table("consents")

    op.drop_index(op.f("ix_auth_identities_user_id"), table_name="auth_identities")
    op.drop_table("auth_identities")

    op.drop_table("identity_users")
    op.drop_table("organizations")
    op.drop_table("product_plans")
