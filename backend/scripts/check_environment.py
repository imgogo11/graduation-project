from __future__ import annotations

import argparse
from importlib import metadata
import shutil
import subprocess
import sys


NPM_BIN = "npm.cmd" if sys.platform.startswith("win") else "npm"

COMMANDS = [
    ("git", ["git", "--version"], None),
    ("node", ["node", "-v"], "20"),
    ("npm", [NPM_BIN, "-v"], None),
    ("python", [sys.executable, "--version"], "3.11"),
    ("docker", ["docker", "--version"], None),
    ("docker compose", ["docker", "compose", "version"], None),
    ("cmake", ["cmake", "--version"], None),
]

CORE_PACKAGES = ["fastapi", "akshare", "pybind11", "beautifulsoup4", "pandas", "requests"]
OPTIONAL_PACKAGES = ["tushare", "scrapy"]


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the MVP environment baseline.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 when a core package or command is missing.",
    )
    args = parser.parse_args()

    failures = 0

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

    print()
    print("== Optional Python packages ==")
    for package in OPTIONAL_PACKAGES:
        ok, version = _package_version(package)
        print(f"[{_status(ok)}] {package:<16} {version}")

    print()
    print("Notes:")
    print("- version-description.txt stores the local machine/version checklist.")
    print("- Use .env.template as the runtime template, and copy it to .env when needed.")
    print("- If Python 3.13 causes compatibility issues, add a Python 3.11 virtual environment.")

    if args.strict and failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
