"""Verifies the Alembic migration chain actually applies to real
PostgreSQL end to end -- not just that the revision graph is
structurally sound (see tests/test_migrations.py, whose own docstring
documents why it stops short of this). This resolves technical debt
register Item 1.

Skipped unless POSTGRES_TEST_DATABASE_URL is set to a real, reachable
Postgres server -- wired up by the dedicated `postgres-migrations` job
in .github/workflows/ci.yml. A developer with a local Postgres can also
set this env var to run the same check locally.

There is deliberately no SQLite fallback anywhere in this file: if the
env var is unset, the test skips (never silently substitutes SQLite or
any other database); if it's set but malformed or unreachable, alembic's
own subprocess fails and the test fails loudly.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_DATABASE_URL,
    reason=(
        "POSTGRES_TEST_DATABASE_URL not set -- this test only runs against a "
        "real Postgres server (see the postgres-migrations CI job). Skipping "
        "here is expected and correct for the regular local/CI test run."
    ),
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_alembic(*args: str) -> subprocess.CompletedProcess:
    # Belt-and-suspenders: refuse to proceed against anything that isn't
    # actually Postgres, even if the env var is set to something else by
    # mistake -- this is the guarantee that this check can never silently
    # end up validating SQLite instead.
    assert POSTGRES_TEST_DATABASE_URL.startswith("postgresql"), (
        f"POSTGRES_TEST_DATABASE_URL must be a real Postgres URL, got: "
        f"{POSTGRES_TEST_DATABASE_URL!r} -- refusing to run migrations "
        "against anything else."
    )
    env = os.environ.copy()
    env["DATABASE_URL"] = POSTGRES_TEST_DATABASE_URL
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_alembic_upgrade_head_applies_cleanly_to_postgres():
    result = _run_alembic("upgrade", "head")
    assert result.returncode == 0, (
        f"alembic upgrade head failed against real Postgres:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


def test_alembic_current_reports_head_after_upgrade():
    """Runs after the upgrade above (pytest executes a module's tests in
    file order by default, no randomization plugin is configured) --
    confirms the applied revision is actually the chain's head, not just
    that some upgrade step somewhere didn't error."""
    result = _run_alembic("current")
    assert result.returncode == 0, (
        f"alembic current failed:\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert "(head)" in result.stdout, (
        f"expected the applied revision to be tagged (head), got:\n{result.stdout}"
    )
