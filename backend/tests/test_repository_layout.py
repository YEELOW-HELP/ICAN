"""Relocation contracts: no dependency on an accidental working directory."""
import importlib.util
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.config import Settings
from app.core.paths import BACKEND_ROOT, DATA_ROOT, DOCS_ROOT, FRONTEND_ROOT, REPO_ROOT
from app.services.career_kb_mnp.seed_catalog import REFERENCE_CSV
from data_explorer import config as explorer
from scripts.dev_seed import DEFAULT_DB_PATH


def test_paths_follow_frontend_backend_docs_layout():
    assert BACKEND_ROOT == REPO_ROOT / "backend"
    assert FRONTEND_ROOT == REPO_ROOT / "frontend"
    assert DOCS_ROOT == REPO_ROOT / "docs"
    assert DEFAULT_DB_PATH == DATA_ROOT / "dev" / "mnp_dev.sqlite"
    assert REFERENCE_CSV.is_file()
    assert REFERENCE_CSV.is_relative_to(BACKEND_ROOT)
    assert explorer.DOCS_DIR == DOCS_ROOT / "data_explorer"
    assert explorer.GOLDEN_OUT_DIR.is_relative_to(BACKEND_ROOT)
    assert (FRONTEND_ROOT / "legacy" / "admin" / "index.html").is_file()
    assert (FRONTEND_ROOT / "legacy" / "mnp" / "index.html").is_file()


def test_settings_and_migrations_are_independent_of_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert Path(Settings.model_config["env_file"]) == BACKEND_ROOT / ".env"
    settings = Settings(_env_file=None, anthropic_api_key="")
    assert Path(settings.mnp_resume_storage_dir) == DATA_ROOT / "mnp_resumes"
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    assert len(ScriptDirectory.from_config(config).get_heads()) == 1


def test_root_launcher_preserves_existing_database_marker(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("ican_dev_launcher", REPO_ROOT / "dev.py")
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    assert launcher.BACKEND == BACKEND_ROOT
    assert launcher.FRONTEND == FRONTEND_ROOT
    assert launcher._project_python().is_relative_to(REPO_ROOT / ".venv")
    marker = tmp_path / "data" / "dev" / ".seed-complete"
    marker.parent.mkdir(parents=True)
    marker.write_text("existing", encoding="utf-8")
    monkeypatch.setattr(launcher, "BACKEND", tmp_path)

    def unexpected_seed(*args, **kwargs):
        raise AssertionError("Existing relocated DB must not be seeded again")

    monkeypatch.setattr(launcher.subprocess, "run", unexpected_seed)
    launcher._prepare_backend()
    assert marker.read_text(encoding="utf-8") == "existing"
