# 作用:
# - 这是 API 总路由模块，用来把健康检查、导入、股票查询和电商查询路由统一挂载到一个 APIRouter。
# 关联文件:
# - 被 backend/app/main.py 直接导入并注册。
# - 依赖 backend/app/api/routes/ 下的 commerce.py、health.py、imports.py、stocks.py。
#
from __future__ import annotations

from fastapi import APIRouter

from .routes import commerce, health, imports, stocks


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(imports.router, prefix="/imports", tags=["imports"])
api_router.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
api_router.include_router(commerce.router, prefix="/commerce", tags=["commerce"])
