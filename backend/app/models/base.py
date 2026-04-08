# 作用:
# - 这是 ORM 基础模型模块，用来定义 SQLAlchemy Declarative Base 和统一的 UTC 时间工厂。
# 关联文件:
# - 被 backend/app/models/entities.py 中的所有 ORM 实体继承。
# - 被 backend/app/models/__init__.py 重新导出。
# - 被 backend/app/repositories/imports.py 用于统一设置导入记录完成时间。
#
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base declarative model class."""
