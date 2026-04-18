from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path

from _bootstrap import ensure_backend_on_path

ensure_backend_on_path()

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.repositories.users import UserRepository
from app.services.imports import ImportService


def _build_default_dataset_name(prefix: str) -> str:
    normalized_prefix = prefix.strip() or "demo_template"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{normalized_prefix}_{timestamp}"


def main() -> int:
    settings = get_settings()
    default_file_path = os.getenv("DEMO_IMPORT_FILE_PATH", "./web/public/trading_import_template.csv")
    default_dataset_prefix = os.getenv("DEMO_DATASET_PREFIX", "demo_template")
    default_username = os.getenv("DEMO_IMPORT_USERNAME", settings.admin_username)
    parser = argparse.ArgumentParser(description="Import a local trading CSV/XLSX file into the configured database.")
    parser.add_argument(
        "--file-path",
        default=default_file_path,
        help="Path to the local trading CSV/XLSX file. Defaults to DEMO_IMPORT_FILE_PATH.",
    )
    parser.add_argument(
        "--dataset-name",
        default="",
        help="Display name for the imported dataset. Defaults to DEMO_DATASET_PREFIX + timestamp.",
    )
    parser.add_argument(
        "--username",
        default=default_username,
        help="Existing username that should own the imported run",
    )
    args = parser.parse_args()

    file_path_text = (args.file_path or "").strip()
    if not file_path_text:
        parser.error("--file-path is required unless DEMO_IMPORT_FILE_PATH is configured.")

    dataset_name = (args.dataset_name or "").strip() or _build_default_dataset_name(default_dataset_prefix)
    file_path = Path(file_path_text).expanduser().resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"Trading file not found: {file_path}")

    session = get_session_factory()()
    service = ImportService()
    try:
        user = UserRepository.get_by_username(session, args.username.strip().lower())
        if user is None:
            raise ValueError(f"User not found: {args.username}")
        run = service.import_uploaded_file(
            session,
            owner=user,
            dataset_name=dataset_name,
            original_file_name=file_path.name,
            file_bytes=file_path.read_bytes(),
        )
    finally:
        session.close()

    print(
        f"Import run {run.id} finished with status={run.status} "
        f"dataset={run.dataset_name} owner_user_id={run.owner_user_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
