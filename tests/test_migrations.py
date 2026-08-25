"""Regression baseline for the Alembic migration chain (Issue #12 checklist:
"Alembic migrations apply cleanly").

What this actually verifies: the revision graph itself is well-formed — a
single linear chain from base to head, no duplicate revision ids, no missing
or branching `down_revision` pointers. That is dialect-independent and does
not require a database at all, so it runs everywhere.

What this deliberately does NOT verify: that `alembic upgrade head` succeeds
against real Postgres. The migrations use Postgres-only DDL (e.g. `ALTER
COLUMN ... TYPE ...`, JSONB/ARRAY columns), so they cannot be executed against
the SQLite engine the rest of this suite uses — SQLite has no `ALTER COLUMN`
support at all. Running them against real Postgres would require a live
database (Neon prod is explicitly off-limits for tests, and no local/CI
Postgres is available in this environment yet). This is a known, currently
uncovered risk — see the Part 1 risk list.
"""

from alembic.config import Config
from alembic.script import ScriptDirectory


def _script_directory() -> ScriptDirectory:
    config = Config("alembic.ini")
    return ScriptDirectory.from_config(config)


def test_migration_chain_has_exactly_one_head():
    script = _script_directory()
    heads = script.get_heads()
    assert len(heads) == 1, f"expected a single linear head, found branches: {heads}"


def test_migration_chain_is_fully_linked_from_base_to_head():
    script = _script_directory()
    revisions = list(script.walk_revisions("base", "head"))
    assert len(revisions) > 0

    revision_ids = {r.revision for r in revisions}
    for r in revisions:
        if r.down_revision is not None:
            assert r.down_revision in revision_ids, (
                f"revision {r.revision} points to down_revision={r.down_revision!r}, "
                "which is not part of the chain reachable from head"
            )


def test_no_duplicate_revision_ids():
    script = _script_directory()
    all_ids = [r.revision for r in script.walk_revisions("base", "head")]
    assert len(all_ids) == len(set(all_ids)), "duplicate Alembic revision id detected"
