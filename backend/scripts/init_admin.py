from __future__ import annotations

from _bootstrap import ensure_backend_on_path

ensure_backend_on_path()

from app.core.config import get_settings
from app.core.database import create_all_tables, get_session_factory
from app.services.auth import AuthService


def main() -> int:
    settings = get_settings()
    create_all_tables()
    session = get_session_factory()()
    try:
        user = AuthService().ensure_admin_user(
            session,
            username=settings.admin_username,
            password=settings.admin_password,
        )
    finally:
        session.close()

    print(f"Admin user ready: username={user.username} role={user.role}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
