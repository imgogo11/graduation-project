# 作用:
# - 这是最小 FastAPI 后端应用入口，用来创建应用实例并挂载统一 API 路由。
# - 当前主要承载数据库优先阶段的健康检查、数据导入入口和只读查询接口。
# 关联文件:
# - 直接依赖 backend/app/api/router.py 提供的统一路由注册。
# - 直接依赖 backend/app/core/config.py 提供 API 前缀等运行配置。
# - 通常由 `uvicorn app.main:app --app-dir backend` 作为启动入口。
#
from __future__ import annotations

from fastapi import FastAPI, Request

from app.api.router import api_router
from app.core.config import get_settings
from app.services.audit_logs import audit_log_service


settings = get_settings()
app = FastAPI(
    title="Stock Trading Data Management and Analysis System Backend",
    version="0.1.0",
    description="FastAPI backend for the stock trading data management and analysis system.",
)
app.include_router(api_router, prefix=settings.api_prefix)

ANALYSIS_AUDIT_PREFIXES = (
    f"{settings.api_prefix}/trading/analysis",
    f"{settings.api_prefix}/algo/risk-radar",
    f"{settings.api_prefix}/algo/trading",
)

ANALYSIS_AUDIT_EVENT_TYPES = {
    f"{settings.api_prefix}/trading/analysis/summary": "analysis.summary.view",
    f"{settings.api_prefix}/trading/analysis/quality": "analysis.quality.view",
    f"{settings.api_prefix}/trading/analysis/indicators": "analysis.indicators.view",
    f"{settings.api_prefix}/trading/analysis/risk": "analysis.risk.view",
    f"{settings.api_prefix}/trading/analysis/anomalies": "analysis.anomalies.view",
    f"{settings.api_prefix}/trading/analysis/cross-section": "analysis.cross_section.view",
    f"{settings.api_prefix}/trading/analysis/correlation": "analysis.correlation.view",
    f"{settings.api_prefix}/trading/analysis/compare-scopes": "analysis.scope_compare.view",
    f"{settings.api_prefix}/algo/risk-radar/overview": "algo.radar.overview.view",
    f"{settings.api_prefix}/algo/risk-radar/events": "algo.radar.events.view",
    f"{settings.api_prefix}/algo/risk-radar/stocks": "algo.radar.stocks.view",
    f"{settings.api_prefix}/algo/risk-radar/calendar": "algo.radar.calendar.view",
    f"{settings.api_prefix}/algo/risk-radar/event-context": "algo.radar.event_context.view",
    f"{settings.api_prefix}/algo/trading/range-max-amount": "algo.trading.range_max_amount.query",
    f"{settings.api_prefix}/algo/trading/range-kth-volume": "algo.trading.range_kth_volume.query",
    f"{settings.api_prefix}/algo/trading/joint-anomaly-ranking": "algo.trading.joint_anomaly_ranking.query",
}


def _is_analysis_request(path: str, method: str) -> bool:
    if method.upper() != "GET":
        return False
    return any(path.startswith(prefix) for prefix in ANALYSIS_AUDIT_PREFIXES)


def _build_analysis_event_type(path: str) -> str:
    return ANALYSIS_AUDIT_EVENT_TYPES.get(path, "analysis.endpoint.view")


@app.middleware("http")
async def audit_analysis_access(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if _is_analysis_request(path, request.method):
        actor_user_id, actor_username, actor_role = audit_log_service.resolve_actor_from_authorization(
            request.headers.get("authorization")
        )
        audit_log_service.record_event(
            category="analysis_access",
            event_type=_build_analysis_event_type(path),
            success=response.status_code < 400,
            status_code=response.status_code,
            actor_user_id=actor_user_id,
            actor_username_snapshot=actor_username,
            actor_role=actor_role,
            request_path=path,
            http_method=request.method.upper(),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    return response
