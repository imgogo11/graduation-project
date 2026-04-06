from __future__ import annotations

from pathlib import Path
import tomllib


REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
MAIN_REQUIREMENTS_PATH = REPO_ROOT / "backend" / "requirements.txt"
OPTIONAL_REQUIREMENTS_PATH = REPO_ROOT / "backend" / "requirements-optional.txt"
OPTIONAL_EXTRA_NAME = "data-sources"


def _load_pyproject() -> dict:
    with PYPROJECT_PATH.open("rb") as file:
        return tomllib.load(file)


def _write_requirements(path: Path, dependencies: list[str], header: str) -> None:
    lines = [
        header,
        "# Generated from pyproject.toml by backend/scripts/export_requirements.py",
        "# Do not edit manually.",
        "",
        *dependencies,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    config = _load_pyproject()
    project = config["project"]
    optional = project.get("optional-dependencies", {})

    _write_requirements(
        MAIN_REQUIREMENTS_PATH,
        list(project.get("dependencies", [])),
        "# Core compatibility requirements",
    )
    _write_requirements(
        OPTIONAL_REQUIREMENTS_PATH,
        list(optional.get(OPTIONAL_EXTRA_NAME, [])),
        "# Optional compatibility requirements",
    )

    print(f"Wrote {MAIN_REQUIREMENTS_PATH}")
    print(f"Wrote {OPTIONAL_REQUIREMENTS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
