"""One-click local launcher for ICAN.

Open this file in VS Code and press Run.  It starts the FastAPI backend and
the React/Vite frontend, then opens the application in the default browser.
Both child processes are stopped when this launcher exits.
"""

from __future__ import annotations

import os
import importlib.util
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
BACKEND_PORT = 8099
FRONTEND_PORT = 5173
APP_URL = f"http://127.0.0.1:{FRONTEND_PORT}/mnp/"


def _project_python() -> Path:
    if os.name == "nt":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def _ensure_project_python() -> None:
    """Make the VS Code Run button independent of its selected interpreter."""
    project_python = _project_python()
    if not project_python.exists():
        print("[setup] Створюю локальне Python-середовище .venv…", flush=True)
        candidates = [[sys.executable, "-m", "venv", str(ROOT / ".venv")]]
        if os.name == "nt" and shutil.which("py"):
            candidates = [
                ["py", "-3.12", "-m", "venv", str(ROOT / ".venv")],
                ["py", "-3.11", "-m", "venv", str(ROOT / ".venv")],
                *candidates,
            ]
        for command in candidates:
            if subprocess.run(command, cwd=ROOT, check=False).returncode == 0:
                break
        if not project_python.exists():
            raise SystemExit("Не вдалося створити .venv. Встановіть Python 3.12 або 3.11.")

    if Path(sys.executable).resolve() != project_python.resolve():
        os.execv(str(project_python), [str(project_python), str(Path(__file__).resolve()), *sys.argv[1:]])

    required_modules = ("fastapi", "sqlalchemy", "openpyxl")
    if any(importlib.util.find_spec(module) is None for module in required_modules):
        print("[setup] Встановлюю backend-залежності (потрібно лише один раз)…", flush=True)
        subprocess.run(
            [str(project_python), "-m", "pip", "install", "-r", str(BACKEND / "requirements.txt")],
            cwd=ROOT,
            check=True,
        )


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0


def _require_free_ports() -> None:
    occupied = [str(port) for port in (BACKEND_PORT, FRONTEND_PORT) if not _port_is_free(port)]
    if occupied:
        raise SystemExit(
            "Порт уже зайнятий: " + ", ".join(occupied)
            + ". Зупиніть старий backend/frontend у попередньому терміналі й запустіть ще раз."
        )


def _npm_command() -> str:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise SystemExit("Node.js/npm не знайдено. Встановіть Node.js LTS і повторіть запуск.")
    return npm


def _prepare_frontend(npm: str) -> None:
    if (FRONTEND / "node_modules").is_dir():
        return
    print("\n[setup] Встановлюю frontend-залежності (потрібно лише один раз)…", flush=True)
    subprocess.run([npm, "install"], cwd=FRONTEND, check=True)


def _prepare_backend() -> None:
    marker = BACKEND / "data" / "dev" / ".seed-complete"
    if marker.exists():
        return
    print("\n[setup] Створюю та наповнюю локальну базу (потрібно лише один раз)…", flush=True)
    subprocess.run([sys.executable, "-m", "scripts.dev_seed"], cwd=BACKEND, check=True)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("ready\n", encoding="utf-8")


def _backend_args() -> list[str]:
    return [sys.executable, "-m", "scripts.dev_seed", "--serve", "--skip-seed"]


def _spawn(args: list[str], cwd: Path) -> subprocess.Popen:
    options: dict = {"cwd": cwd}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    return subprocess.Popen(args, **options)


def _wait_for(url: str, processes: list[subprocess.Popen], timeout: int = 150) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        for process in processes:
            if process.poll() is not None:
                return False
        try:
            with urllib.request.urlopen(url, timeout=1):
                return True
        except Exception:
            time.sleep(0.5)
    return False


def _stop(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except Exception:
        process.kill()


def main() -> None:
    os.chdir(ROOT)
    _ensure_project_python()
    _require_free_ports()
    npm = _npm_command()
    _prepare_frontend(npm)
    _prepare_backend()
    print("[setup] Перевіряю обліковий запис власника…", flush=True)
    subprocess.run([sys.executable, "-m", "scripts.console_setup", "--ensure"], cwd=BACKEND, check=True)

    print("\n[start] FastAPI:     http://127.0.0.1:8099", flush=True)
    backend = _spawn(_backend_args(), BACKEND)
    print("[start] React/Vite: http://127.0.0.1:5173/mnp/", flush=True)
    frontend = _spawn([npm, "run", "dev", "--", "--host", "127.0.0.1"], FRONTEND)
    processes = [backend, frontend]

    try:
        if _wait_for(f"http://127.0.0.1:{BACKEND_PORT}/health", processes):
            if _wait_for(APP_URL, processes, timeout=30):
                print("\n[ready] ICAN запущено. Натисніть Ctrl+C, щоб зупинити все.\n", flush=True)
                if os.environ.get("ICAN_NO_BROWSER") != "1":
                    webbrowser.open(APP_URL)
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
        failed = [process.returncode for process in processes if process.poll() is not None]
        if failed and any(code not in (0, None) for code in failed):
            raise SystemExit("Один із процесів завершився з помилкою. Перегляньте повідомлення вище.")
    except KeyboardInterrupt:
        print("\n[stop] Зупиняю frontend і backend…", flush=True)
    finally:
        for process in reversed(processes):
            _stop(process)


if __name__ == "__main__":
    main()
