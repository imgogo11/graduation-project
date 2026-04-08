# 作用:
# - 这是数据库基础设施模块，用来创建 SQLAlchemy Engine、SessionFactory 和请求级会话依赖。
# - 当前同时提供建表、连接检测和测试场景下的数据库状态重置能力。
# 关联文件:
# - 被 backend/app/api/routes/*.py 通过 `get_db_session` 作为依赖注入使用。
# - 被 backend/scripts/import_data.py、backend/tests/test_database_pipeline.py 直接调用。
# - 与 backend/app/models/__init__.py 配合完成元数据建表与 ORM 会话管理。
#
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import clear_settings_cache, get_settings


_ENGINE: Engine | None = None
_SESSION_FACTORY: sessionmaker[Session] | None = None
_ENGINE_URL: str | None = None


def _create_engine(database_url: str) -> Engine:
    kwargs: dict[str, Any] = {"future": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_pre_ping"] = True
    return create_engine(database_url, **kwargs)


def get_engine(database_url: str | None = None) -> Engine:
    global _ENGINE, _SESSION_FACTORY, _ENGINE_URL

    target_url = database_url or get_settings().database_url
    if _ENGINE is None or _SESSION_FACTORY is None or _ENGINE_URL != target_url:
        if _ENGINE is not None:
            _ENGINE.dispose()
        _ENGINE = _create_engine(target_url)
        _SESSION_FACTORY = sessionmaker(bind=_ENGINE, autoflush=False, autocommit=False, expire_on_commit=False)
        _ENGINE_URL = target_url
    return _ENGINE


def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    get_engine(database_url)
    assert _SESSION_FACTORY is not None
    return _SESSION_FACTORY


def get_db_session() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def reset_database_state() -> None:
    global _ENGINE, _SESSION_FACTORY, _ENGINE_URL
    if _ENGINE is not None:
        _ENGINE.dispose()
    _ENGINE = None
    _SESSION_FACTORY = None
    _ENGINE_URL = None
    clear_settings_cache()


def create_all_tables(database_url: str | None = None) -> None:
    from app.models import Base

    engine = get_engine(database_url)
    Base.metadata.create_all(bind=engine)


def check_database_connection() -> tuple[bool, str]:
    try:
        with get_engine().connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar_one()
        return result == 1, "ok"
    except Exception as exc:
        return False, str(exc)
