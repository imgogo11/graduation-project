from __future__ import annotations

import argparse
from importlib import metadata
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

from dotenv import dotenv_values


REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_VENV_DIR = REPO_ROOT / ".venv"
PROJECT_VENV_PYTHON = (
    PROJECT_VENV_DIR / "Scripts" / "python.exe"
    if sys.platform.startswith("win")
    else PROJECT_VENV_DIR / "bin" / "python"
)
NPM_BIN = "npm.cmd" if sys.platform.startswith("win") else "npm"

COMMANDS = [
    ("git", ["git", "--version"], None),
    ("node", ["node", "-v"], "20"),
    ("npm", [NPM_BIN, "-v"], None),
    ("python", [sys.executable, "--version"], "3.13"),
    ("uv", ["uv", "--version"], None),
    ("docker", ["docker", "--version"], None),
    ("docker compose", ["docker", "compose", "version"], None),
    ("cmake", ["cmake", "--version"], None),
]

CORE_PACKAGES = [
    "fastapi",
    "sqlalchemy",
    "pydantic",
    "pandas",
    "python-multipart",
    "openpyxl",
    "pybind11",
    "python-dotenv",
    "alembic",
    "psycopg",
    "uvicorn",
    "httpx",
]

BACKEND_ENV_FILE = REPO_ROOT / ".env"
BACKEND_ENV_TEMPLATE = REPO_ROOT / ".env.template"
FRONTEND_ENV_FILE = REPO_ROOT / "frontend" / ".env"
FRONTEND_ENV_TEMPLATE = REPO_ROOT / "frontend" / ".env.template"


def _run_command(command: list[str]) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        output = (completed.stdout or completed.stderr).strip().splitlines()
        return True, output[0] if output else ""
    except Exception as exc:
        return False, str(exc)


def _package_version(name: str) -> tuple[bool, str]:
    try:
        return True, metadata.version(name)
    except metadata.PackageNotFoundError:
        return False, "missing"


def _status(ok: bool) -> str:
    return "OK" if ok else "WARN"


def _uses_project_venv() -> bool:
    try:
        return PROJECT_VENV_PYTHON.exists() and Path(sys.executable).resolve() == PROJECT_VENV_PYTHON.resolve()
    except OSError:
        return False


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {key: value for key, value in dotenv_values(path).items() if value is not None}


def _pick_env_value(*sources: dict[str, str], key: str, default: str) -> str:
    for source in sources:
        value = source.get(key)
        if value:
            return value
    return default


def _check_tcp(address: str, port: int) -> tuple[bool, str]:
    try:
        with socket.create_connection((address, port), timeout=1.5):
            return True, f"{address}:{port} reachable"
    except OSError as exc:
        return False, f"{address}:{port} unreachable ({exc})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the local environment for the unified trading system.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 when a core package or command is missing.",
    )
    args = parser.parse_args()

    failures = 0

    print("== Python context ==")
    print(f"Current interpreter : {sys.executable}")
    print(f"Project venv path   : {PROJECT_VENV_PYTHON}")
    print(f"Using project .venv : {'yes' if _uses_project_venv() else 'no'}")
    if PROJECT_VENV_PYTHON.exists() and not _uses_project_venv():
        print("WARN: A project .venv exists, but this script is not running inside it.")
        print("      Recommended command: uv run python backend/scripts/check_environment.py")

    print()
    print("== Command checks ==")
    for label, command, recommended_prefix in COMMANDS:
        binary = command[0]
        binary_available = binary == sys.executable or shutil.which(binary) is not None
        if not binary_available:
            print(f"[WARN] {label:<16} not found in PATH")
            failures += 1
            continue

        ok, output = _run_command(command)
        print(f"[{_status(ok)}] {label:<16} {output}")
        if not ok:
            failures += 1
            continue

        if recommended_prefix and recommended_prefix not in output:
            print(f"       recommended baseline: {recommended_prefix}.x")

    print()
    print("== Core Python packages ==")
    for package in CORE_PACKAGES:
        ok, version = _package_version(package)
        print(f"[{_status(ok)}] {package:<16} {version}")
        if not ok:
            failures += 1

    backend_env = _load_env_file(BACKEND_ENV_FILE)
    backend_template_env = _load_env_file(BACKEND_ENV_TEMPLATE)
    frontend_env = _load_env_file(FRONTEND_ENV_FILE)
    frontend_template_env = _load_env_file(FRONTEND_ENV_TEMPLATE)

    postgres_host = _pick_env_value(os.environ, backend_env, backend_template_env, key="POSTGRES_HOST", default="127.0.0.1")
    postgres_port_text = _pick_env_value(os.environ, backend_env, backend_template_env, key="POSTGRES_PORT", default="15432")
    database_url = _pick_env_value(os.environ, backend_env, backend_template_env, key="DATABASE_URL", default="")
    frontend_host = _pick_env_value(os.environ, frontend_env, frontend_template_env, key="VITE_DEV_HOST", default="127.0.0.1")
    frontend_port = _pick_env_value(os.environ, frontend_env, frontend_template_env, key="VITE_DEV_PORT", default="4173")

    print()
    print("== Runtime defaults ==")
    print(f"Backend env file   : {BACKEND_ENV_FILE if BACKEND_ENV_FILE.exists() else '(missing, template fallback)'}")
    print(f"Frontend env file  : {FRONTEND_ENV_FILE if FRONTEND_ENV_FILE.exists() else '(missing, template fallback)'}")
    print(f"PostgreSQL host    : {postgres_host}")
    print(f"PostgreSQL port    : {postgres_port_text}")
    print(f"Database URL       : {database_url or '(derived from POSTGRES_* variables)'}")
    print(f"Frontend dev host  : {frontend_host}")
    print(f"Frontend dev port  : {frontend_port}")

    try:
        postgres_port = int(postgres_port_text)
    except ValueError:
        postgres_port = -1
        print("[WARN] PostgreSQL port is not a valid integer")
        failures += 1

    if postgres_port > 0:
        ok, output = _check_tcp(postgres_host, postgres_port)
        print(f"[{_status(ok)}] PostgreSQL socket {output}")
        if not ok:
            failures += 1

    print()
    print("Notes:")
    print("- version-description.txt stores the local machine/version checklist.")
    print("- Use .env.template and frontend/.env.template as runtime templates.")
    print("- Python 3.13 is the default project interpreter for the .venv workflow.")
    print("- The project now keeps only the user-upload trading workflow.")
    print("- Default local ports are PostgreSQL 15432 and frontend dev server 4173.")

    if args.strict and failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
