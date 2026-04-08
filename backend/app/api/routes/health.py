# 作用:
# - 这是健康检查路由模块，用来暴露最小可用的服务与数据库连通性检查接口。
# 关联文件:
# - 被 backend/app/api/router.py 统一挂载到 `/api/health`。
# - 依赖 backend/app/core/database.py 的连接检测能力和 backend/app/core/config.py 的环境配置。
# - 返回模型定义在 backend/app/schemas/api.py。
#
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.database import check_database_connection
from app.schemas.api import HealthResponse


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    database_ok, detail = check_database_connection()
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        environment=get_settings().app_env,
        database_ok=database_ok,
        detail=detail,
    )
