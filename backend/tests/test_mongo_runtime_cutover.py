from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROOT = BACKEND_ROOT.parent


def test_procfile_starts_only_mongo_runtime():
    procfile = (ROOT / "Procfile").read_text(encoding="utf-8")
    assert "app.mongo_runtime.main:app" in procfile
    assert "alembic" not in procfile
    assert "asyncpg" not in procfile
    assert "app.api.main" not in procfile


def test_mongo_main_has_no_sql_runtime_imports():
    source = (BACKEND_ROOT / "app/mongo_runtime/main.py").read_text(encoding="utf-8")
    assert "sqlalchemy" not in source.lower()
    assert "asyncpg" not in source.lower()
    assert "get_session" not in source
