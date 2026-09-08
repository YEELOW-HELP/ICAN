"""Staff access grants for MnpPerson.

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
"""
from alembic import op
import sqlalchemy as sa

revision = "e3f4a5b6c7d8"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("mnp_person_access",
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("mnp_persons.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("admin_users.id"), primary_key=True),
        sa.Column("is_creator", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("granted_by", sa.Integer(), sa.ForeignKey("admin_users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    # Preserve access for people created before the workspace existed, using
    # the authoritative creation audit, never guessing ownership from names.
    bind = op.get_bind()
    audit = sa.table("audit_logs", sa.column("entity_type"), sa.column("entity_id"),
                     sa.column("action"), sa.column("actor_admin_id"))
    persons = sa.table("mnp_persons", sa.column("id", sa.Uuid()))
    staff = sa.table("admin_users", sa.column("id", sa.Integer()))
    grants = sa.table("mnp_person_access", sa.column("person_id", sa.Uuid()),
                      sa.column("admin_id", sa.Integer()), sa.column("is_creator", sa.Boolean()),
                      sa.column("granted_by", sa.Integer()))
    rows = sa.select(persons.c.id, audit.c.actor_admin_id, sa.true(), audit.c.actor_admin_id).select_from(
        audit.join(persons, sa.func.replace(sa.cast(persons.c.id, sa.String()), "-", "") ==
                   sa.func.replace(audit.c.entity_id, "-", ""))
        .join(staff, staff.c.id == audit.c.actor_admin_id)
    ).where(audit.c.entity_type == "mnp_person", audit.c.action == "person_created").distinct()
    op.execute(grants.insert().from_select(["person_id", "admin_id", "is_creator", "granted_by"], rows))


def downgrade():
    op.drop_table("mnp_person_access")
