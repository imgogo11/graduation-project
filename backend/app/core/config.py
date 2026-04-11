from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _resolve_path(value: str, *, root: Path) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return (root / candidate).resolve()


def _default_database_url() -> str:
    user = os.getenv("POSTGRES_USER", "graduation")
    password = os.getenv("POSTGRES_PASSWORD", "graduation")
    host = os.getenv("POSTGRES_HOST", "127.0.0.1")
    port = os.getenv("POSTGRES_PORT", "15432")
    database = os.getenv("POSTGRES_DB", "graduation_project")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str
    api_prefix: str
    project_root: Path
    upload_root: Path
    database_url: str
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_host: str
    postgres_port: int
    jwt_secret: str
    jwt_expire_minutes: int
    admin_username: str
    admin_password: str


def build_settings() -> Settings:
    project_root = PROJECT_ROOT
    upload_root = _resolve_path(os.getenv("UPLOAD_ROOT", "./data/uploads"), root=project_root)

    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        api_prefix=os.getenv("API_PREFIX", "/api"),
        project_root=project_root,
        upload_root=upload_root,
        database_url=os.getenv("DATABASE_URL", _default_database_url()),
        postgres_db=os.getenv("POSTGRES_DB", "graduation_project"),
        postgres_user=os.getenv("POSTGRES_USER", "graduation"),
        postgres_password=os.getenv("POSTGRES_PASSWORD", "graduation"),
        postgres_host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "15432")),
        jwt_secret=os.getenv("JWT_SECRET", "development-change-me"),
        jwt_expire_minutes=int(os.getenv("JWT_EXPIRE_MINUTES", "1440")),
        admin_username=os.getenv("ADMIN_USERNAME", "admin"),
        admin_password=os.getenv("ADMIN_PASSWORD", "admin123456"),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return build_settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
