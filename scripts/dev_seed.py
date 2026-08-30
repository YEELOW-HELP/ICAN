"""Local dev environment bootstrap for the MNP frontend / API.

This machine has no Postgres, so the local dev DB is a SQLite file whose
schema is built straight from the SQLAlchemy models -- exactly what the
test suite does (`tests/conftest.py`). Two old migrations widen a column
with `ALTER COLUMN`, which SQLite cannot run, so `alembic upgrade head`
is Postgres-only; the models are the single source of truth for the
schema either way. After building the schema this stamps Alembic to
`head` so `alembic current` stays coherent.

Usage
-----
    # one-time (or after pulling schema changes): build + seed, then serve
    python -m scripts.dev_seed --serve

    # rebuild from scratch (drops the dev DB first)
    python -m scripts.dev_seed --reset --serve

    # just (re)seed, don't start the server
    python -m scripts.dev_seed

The dev DB lives at data/dev/mnp_dev.sqlite (data/ is gitignored). The
production Postgres in .env is never touched by this script.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "dev" / "mnp_dev.sqlite"
DEV_PORT = 8099


def _db_url(db_path: Path) -> str:
    return f"sqlite+aiosqlite:///{db_path.as_posix()}"


async def _build_and_seed(db_path: Path, *, reset: bool) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if reset and db_path.exists():
        db_path.unlink()
        print(f"  removed {db_path}")

    # settings.database_url is read at import time -> set it before importing.
    os.environ["DATABASE_URL"] = _db_url(db_path)

    from app.db.base import Base
    # import every model module so create_all() sees the full metadata
    from app.db import (  # noqa: F401
        models, models_access, models_assessment, models_career_card, models_career_kb_mnp,
        models_crm, models_identity, models_knowledge, models_matching_mnp, models_platform,
        models_profile,
    )
    from app.db.session import async_session_factory, engine
    from app.services.career_kb_mnp.seed_alpha import ALPHA_CAREER_CODES, seed_alpha_career_kb

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  schema created from models (Base.metadata.create_all)")

    async with async_session_factory() as session:
        await seed_alpha_career_kb(session)
    print(f"  seeded MNP Career KB: {len(ALPHA_CAREER_CODES)} ACTIVE careers")

    await engine.dispose()


def _stamp_alembic_head(db_path: Path) -> None:
    """Keep `alembic current` coherent with a model-built schema. Runs
    outside any event loop (this project's migrations/env.py is async)."""
    os.environ["DATABASE_URL"] = _db_url(db_path)
    try:
        from alembic import command
        from alembic.config import Config

        cfg = Config(str(REPO_ROOT / "alembic.ini"))
        command.stamp(cfg, "head")
        print("  alembic stamped to head")
    except Exception as exc:  # non-fatal -- the schema is already correct
        print(f"  (alembic stamp skipped: {exc})")


def _serve(db_path: Path) -> None:
    os.environ["DATABASE_URL"] = _db_url(db_path)
    import uvicorn

    print(f"\n  MNP frontend:  http://127.0.0.1:{DEV_PORT}/mnp/#/catalog")
    print(f"  API health:    http://127.0.0.1:{DEV_PORT}/health\n")
    uvicorn.run("app.api.main:app", host="127.0.0.1", port=DEV_PORT, log_level="info")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Bootstrap the local MNP dev environment (SQLite).")
    parser.add_argument("--reset", action="store_true", help="drop the dev DB and rebuild it")
    parser.add_argument("--serve", action="store_true", help="start uvicorn on :%d after seeding" % DEV_PORT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="dev SQLite path")
    parser.add_argument("--skip-seed", action="store_true", help="don't touch the DB, just --serve")
    args = parser.parse_args(argv)

    db_path: Path = args.db.resolve()

    if not args.skip_seed:
        print(f"Bootstrapping MNP dev DB at {db_path}")
        asyncio.run(_build_and_seed(db_path, reset=args.reset))
        _stamp_alembic_head(db_path)
    elif not db_path.exists():
        sys.exit(f"--skip-seed but {db_path} does not exist; run without --skip-seed first")

    if args.serve:
        _serve(db_path)
    else:
        print(f"\nDone. Start the server with:\n"
              f"  python -m scripts.dev_seed --serve --skip-seed\n"
              f"or in one step next time:\n"
              f"  python -m scripts.dev_seed --serve")


if __name__ == "__main__":
    main()
