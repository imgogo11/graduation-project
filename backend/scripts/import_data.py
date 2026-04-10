from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_backend_on_path

ensure_backend_on_path()

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.repositories.users import UserRepository
from app.services.imports import ImportService


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Import a local trading CSV/XLSX file into the configured database.")
    parser.add_argument("--file-path", required=True, help="Path to the local trading CSV/XLSX file")
    parser.add_argument("--dataset-name", required=True, help="Display name for the imported dataset")
    parser.add_argument(
        "--asset-class",
        choices=["stock", "commodity"],
        required=True,
        help="Logical asset class for the uploaded file",
    )
    parser.add_argument(
        "--username",
        default=settings.admin_username,
        help="Existing username that should own the imported run",
    )
    args = parser.parse_args()

    file_path = Path(args.file_path).expanduser().resolve()
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
            dataset_name=args.dataset_name,
            asset_class=args.asset_class,
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
