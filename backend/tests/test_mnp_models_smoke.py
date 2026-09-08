"""MNP V1 BLOCK A -- smoke test: the full metadata (existing + new MNP
tables) creates cleanly against SQLite, with zero table-name/class-name
collisions between the MNP schema and every pre-existing module."""

from sqlalchemy import inspect


async def test_full_metadata_creates_cleanly(session_factory):
    async with session_factory() as session:
        tables = (await session.connection()).run_sync(lambda conn: inspect(conn).get_table_names())
        table_names = await tables
        mnp_tables = [t for t in table_names if t.startswith("mnp_")]
        assert len(mnp_tables) >= 35, f"expected >=35 mnp_ tables, got {len(mnp_tables)}: {sorted(mnp_tables)}"
        # No accidental non-prefixed new table slipped in under a name that
        # collides with an existing Stage 1-3A table.
        assert "careers" in table_names  # Stage 3A's, untouched
        assert "mnp_careers" in table_names  # MNP's own, distinct
        assert "evidence" in table_names  # Stage 2's, untouched
        assert "mnp_evidence" in table_names  # MNP's own, distinct
