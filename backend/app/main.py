# 作用:
# - 这是最小 FastAPI 后端应用入口，用来创建应用实例并挂载统一 API 路由。
# - 当前主要承载数据库优先阶段的健康检查、数据导入入口和只读查询接口。
# 关联文件:
# - 直接依赖 backend/app/api/router.py 提供的统一路由注册。
# - 直接依赖 backend/app/core/config.py 提供 API 前缀等运行配置。
# - 通常由 `uvicorn app.main:app --app-dir backend` 作为启动入口。
#
from __future__ import annotations

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings


settings = get_settings()
app = FastAPI(
    title="C++-Powered Trading Data Analytics System Backend",
    version="0.1.0",
    description="FastAPI backend for the C++-Powered Trading Data Analytics System.",
)
app.include_router(api_router, prefix=settings.api_prefix)
