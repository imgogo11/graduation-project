# 作用:
# - 这是后端配置模块，用来集中读取 `.env` / 环境变量并构造运行期 Settings 对象。
# - 当前负责数据目录、数据库连接、Redis 预留配置以及默认 manifest 路径的统一解析。
# 关联文件:
# - 被 backend/app/main.py 用于挂载 API 前缀和环境信息。
# - 被 backend/app/core/database.py 用于创建数据库引擎。
# - 被 backend/app/api/routes/imports.py 和 backend/scripts/import_data.py 用于定位默认数据清单文件。
#
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
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "graduation_project")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str
    api_prefix: str
    project_root: Path
    data_root: Path
    raw_data_dir: Path
    processed_data_dir: Path
    database_url: str
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_host: str
    postgres_port: int
    redis_url: str
    default_stock_manifest: Path
    default_olist_manifest: Path
    default_synthetic_manifest: Path


def build_settings() -> Settings:
    project_root = PROJECT_ROOT
    data_root = _resolve_path(os.getenv("DATA_ROOT", "./data"), root=project_root)
    raw_data_dir = _resolve_path(os.getenv("RAW_DATA_DIR", "./data/raw"), root=project_root)
    processed_data_dir = _resolve_path(os.getenv("PROCESSED_DATA_DIR", "./data/processed"), root=project_root)

    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        api_prefix=os.getenv("API_PREFIX", "/api"),
        project_root=project_root,
        data_root=data_root,
        raw_data_dir=raw_data_dir,
        processed_data_dir=processed_data_dir,
        database_url=os.getenv("DATABASE_URL", _default_database_url()),
        postgres_db=os.getenv("POSTGRES_DB", "graduation_project"),
        postgres_user=os.getenv("POSTGRES_USER", "graduation"),
        postgres_password=os.getenv("POSTGRES_PASSWORD", "graduation"),
        postgres_host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
        redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
        default_stock_manifest=raw_data_dir / "stocks" / "akshare" / "akshare_daily_manifest.json",
        default_olist_manifest=raw_data_dir / "ecommerce" / "olist" / "olist_dataset_manifest.json",
        default_synthetic_manifest=processed_data_dir / "ecommerce" / "synthetic" / "synthetic_ecommerce_manifest.json",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return build_settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
