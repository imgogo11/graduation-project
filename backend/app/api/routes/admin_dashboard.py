from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends

from app.api.deps import get_current_admin_user
from app.models import User
from app.schemas.admin_dashboard import (
    AdminAssetOverviewRead,
    AdminOverviewRead,
    AdminRunMonitorRead,
    AuditLogListRead,
    AuditLogStatsRead,
)
from app.services.admin_dashboard import admin_dashboard_service
from app.services.audit_logs import audit_log_service


router = APIRouter()


@router.get("/overview", response_model=AdminOverviewRead)
def get_admin_overview(
    _current_admin: User = Depends(get_current_admin_user),
) -> AdminOverviewRead:
    return admin_dashboard_service.build_overview()


@router.get("/audit-logs", response_model=AuditLogListRead)
def list_audit_logs(
    page: int = 1,
    page_size: int = 20,
    actor_user_id: int | None = None,
    actor_username: str | None = None,
    category: str | None = None,
    success: bool | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    _current_admin: User = Depends(get_current_admin_user),
) -> AuditLogListRead:
    return audit_log_service.list_logs(
        page=page,
        page_size=page_size,
        actor_user_id=actor_user_id,
        actor_username=actor_username,
        category=category,
        success=success,
        start_at=start_at,
        end_at=end_at,
    )


@router.get("/audit-logs/stats", response_model=AuditLogStatsRead)
def get_audit_log_stats(
    actor_user_id: int | None = None,
    actor_username: str | None = None,
    category: str | None = None,
    success: bool | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    _current_admin: User = Depends(get_current_admin_user),
) -> AuditLogStatsRead:
    return audit_log_service.build_stats(
        actor_user_id=actor_user_id,
        actor_username=actor_username,
        category=category,
        success=success,
        start_at=start_at,
        end_at=end_at,
    )


@router.get("/runs/monitor", response_model=AdminRunMonitorRead)
def get_admin_runs_monitor(
    limit: int = 30,
    _current_admin: User = Depends(get_current_admin_user),
) -> AdminRunMonitorRead:
    return admin_dashboard_service.build_runs_monitor(limit=limit)


@router.get("/assets/overview", response_model=AdminAssetOverviewRead)
def get_admin_assets_overview(
    _current_admin: User = Depends(get_current_admin_user),
) -> AdminAssetOverviewRead:
    return admin_dashboard_service.build_asset_overview()
