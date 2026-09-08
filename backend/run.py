"""Run only FastAPI from VS Code or with `python run.py`.

Start the frontend independently with `npm run dev` in frontend/.
The API runs in this terminal, without a reloader or detached worker.
"""
from pathlib import Path
import argparse
import importlib.util
import os
import shutil
import socket
import subprocess
import sys

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parent
PORT = 8099


def ensure_python():
    """Reuse the repository environment even with another VS Code interpreter."""
    environment = ROOT / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        candidates = [[sys.executable, "-m", "venv", str(environment)]]
        if os.name == "nt" and shutil.which("py"):
            candidates = [["py", version, "-m", "venv", str(environment)]
                          for version in ("-3.12", "-3.11")] + candidates
        for command in candidates:
            if subprocess.run(command, cwd=ROOT, check=False).returncode == 0:
                break
        if not python.exists():
            raise SystemExit("Не вдалося створити .venv. Встановіть Python 3.12 або 3.11.")
    if Path(sys.executable).resolve() != python.resolve():
        os.execv(str(python), [str(python), str(Path(__file__).resolve()), *sys.argv[1:]])
    if any(importlib.util.find_spec(module) is None
           for module in ("fastapi", "sqlalchemy", "aiosqlite", "openpyxl", "pymongo")):
        print("[setup] Встановлюю залежності бекенду…", flush=True)
        subprocess.run([str(python), "-m", "pip", "install", "-r",
                        str(BACKEND / "requirements.txt")], cwd=BACKEND, check=True)


def main():
    parser = argparse.ArgumentParser(description="Run the ICAN backend")
    parser.add_argument(
        "--setup-admin",
        action="store_true",
        help="create or update the personal local superadmin before starting",
    )
    args = parser.parse_args()
    os.chdir(BACKEND)
    ensure_python()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        if connection.connect_ex(("127.0.0.1", PORT)) == 0:
            raise SystemExit(f"Порт {PORT} зайнятий. Зупиніть попередній бекенд через Ctrl+C.")

    # Preserve the existing development DB and personal owner setup.
    # This launcher does not change the chosen storage backend.
    from scripts.dev_seed import DEFAULT_DB_PATH, _serve
    marker = DEFAULT_DB_PATH.parent / ".seed-complete"
    if not marker.exists() or not DEFAULT_DB_PATH.exists():
        subprocess.run([sys.executable, "-m", "scripts.dev_seed"], cwd=BACKEND, check=True)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("ready\n", encoding="utf-8")
    if args.setup_admin:
        print("[setup] Налаштовую локального суперадміна…", flush=True)
        from scripts.console_setup import ensure_superadmin
        ensure_superadmin(DEFAULT_DB_PATH, only_if_missing=False)
    else:
        print(
            "[setup] Superadmin не перевіряється під час запуску. "
            "Для налаштування окремо виконайте: "
            "python -m scripts.console_setup --ensure",
            flush=True,
        )
    print(f"\nBackend: http://127.0.0.1:{PORT}", flush=True)
    print("Frontend запускайте окремо: npm run dev у папці frontend.", flush=True)
    print("Ctrl+C у цьому терміналі зупиняє лише backend.\n", flush=True)
    _serve(DEFAULT_DB_PATH)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBackend зупинено.")
