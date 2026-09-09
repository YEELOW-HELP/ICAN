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
import secrets

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
           for module in ("fastapi", "openpyxl", "pymongo", "uvicorn")):
        print("[setup] Встановлюю залежності бекенду…", flush=True)
        subprocess.run([str(python), "-m", "pip", "install", "-r",
                        str(BACKEND / "requirements.txt")], cwd=BACKEND, check=True)


def main():
    parser = argparse.ArgumentParser(description="Run the ICAN backend")
    parser.parse_args()
    os.chdir(BACKEND)
    ensure_python()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        if connection.connect_ex(("127.0.0.1", PORT)) == 0:
            raise SystemExit(f"Порт {PORT} зайнятий. Зупиніть попередній бекенд через Ctrl+C.")

    # A stable local key keeps staff sessions valid between restarts. Hosting
    # must set JWT_SECRET explicitly in environment variables.
    if not os.environ.get("JWT_SECRET"):
        key_file = BACKEND / "data" / "dev" / ".console-jwt-key"
        key_file.parent.mkdir(parents=True, exist_ok=True)
        if not key_file.exists():
            key_file.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        os.environ["JWT_SECRET"] = key_file.read_text(encoding="utf-8").strip()
    print(f"\nBackend: http://127.0.0.1:{PORT}", flush=True)
    print("Frontend запускайте окремо: npm run dev у папці frontend.", flush=True)
    print("Ctrl+C у цьому терміналі зупиняє лише backend.\n", flush=True)
    import uvicorn
    uvicorn.run("app.mongo_runtime.main:app", host="127.0.0.1", port=PORT)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBackend зупинено.")
