# 作用:
# - 这是数据库初始迁移文件，用来创建数据库优先阶段所需的导入元数据表和股票、电商业务真值表。
# 关联文件:
# - 由 backend/alembic/env.py 在 `upgrade head` 时加载执行。
# - 依赖 backend/app/models/__init__.py 暴露的完整 ORM 元数据。
# - 与 deploy/docker-compose.yml 中启动的 PostgreSQL 容器配合完成首轮建库。
#
from __future__ import annotations

from pathlib import Path
import sys

from alembic import op


BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models import Base


revision = "20260407_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
