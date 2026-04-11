# 作用:
# - 这是 API 总路由模块，用来把健康检查、导入、股票查询和电商查询路由统一挂载到一个 APIRouter。
# 关联文件:
# - 被 backend/app/main.py 直接导入并注册。
# - 依赖 backend/app/api/routes/ 下的 commerce.py、health.py、imports.py、stocks.py。
#
from __future__ import annotations

from fastapi import APIRouter

from .routes.algo import indexes as algo_indexes
from .routes.algo import risk_radar as algo_risk_radar
from .routes.algo import trading as algo_trading
from .routes import auth, health, imports, trading, trading_analysis


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(imports.router, prefix="/imports", tags=["imports"])
api_router.include_router(trading.router, prefix="/trading", tags=["trading"])
api_router.include_router(trading_analysis.router, prefix="/trading/analysis", tags=["trading-analysis"])
api_router.include_router(algo_trading.router, prefix="/algo/trading", tags=["algo-trading"])
api_router.include_router(algo_indexes.router, prefix="/algo/indexes", tags=["algo-indexes"])
api_router.include_router(algo_risk_radar.router, prefix="/algo/risk-radar", tags=["algo-risk-radar"])
