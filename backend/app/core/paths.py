"""Stable filesystem locations, independent of the process working directory."""
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
FRONTEND_ROOT = REPO_ROOT / "frontend"
DATA_ROOT = BACKEND_ROOT / "data"
DOCS_ROOT = REPO_ROOT / "docs"
