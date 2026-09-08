"""Apply the additive grant migration to existing author audit records."""
import importlib
import uuid
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


def test_migration_preserves_authors_and_ignores_unattributed_profiles(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    people = sa.Table("mnp_persons", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    staff = sa.Table("admin_users", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    audit = sa.Table("audit_logs", metadata, sa.Column("entity_type", sa.String()),
                     sa.Column("entity_id", sa.String()), sa.Column("action", sa.String()),
                     sa.Column("actor_admin_id", sa.Integer()))
    metadata.create_all(engine)
    person_id, other_id = uuid.uuid4(), uuid.uuid4()
    migration = importlib.import_module("migrations.versions.e3f4a5b6c7d8_person_staff_access")
    with engine.begin() as conn:
        conn.execute(people.insert(), [{"id":person_id},{"id":other_id}])
        conn.execute(staff.insert(), [{"id":7}])
        event = {"entity_type":"mnp_person", "entity_id":str(person_id), "action":"person_created", "actor_admin_id":7}
        conn.execute(audit.insert(), [event, event, {**event,"entity_id":"invalid-id"},
                                     {**event,"entity_id":str(other_id),"action":"person_core_updated"}])
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(conn)))
        migration.upgrade()
        grants = sa.Table("mnp_person_access", sa.MetaData(), autoload_with=conn)
        rows = conn.execute(sa.select(grants)).mappings().all()
        assert len(rows) == 1
        assert str(rows[0]["person_id"]).replace("-", "") == person_id.hex
        assert rows[0]["admin_id"] == 7
        assert rows[0]["is_creator"] is True
    engine.dispose()
