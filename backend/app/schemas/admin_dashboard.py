from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class AuditLogRead(BaseModel):
    id: int
    occurred_at: datetime
    category: str
    event_type: str
    success: bool
    status_code: int | None
    actor_user_id: int | None
    actor_username_snapshot: str | None
    actor_role: str | None
    target_type: str | None
    target_label: str | None
    import_run_id: int | None
    request_path: str | None
    http_method: str | None
    ip_address: str | None
    user_agent: str | None
    detail_json: dict[str, Any]


class AuditLogCategoryStatRead(BaseModel):
    category: str
    total: int


class AuditLogStatsRead(BaseModel):
    total_events: int
    success_events: int
    failed_events: int
    unique_actor_count: int
    today_events: int
    category_breakdown: list[AuditLogCategoryStatRead]


class AuditLogListRead(BaseModel):
    total: int
    page: int
    page_size: int
    rows: list[AuditLogRead]


class AdminOverviewMetricRead(BaseModel):
    total_users: int
    active_users: int
    total_runs: int
    total_records: int
    today_events: int
    failed_events_24h: int


class AdminOverviewRead(BaseModel):
    metrics: AdminOverviewMetricRead
    recent_audit_logs: list[AuditLogRead]
    recent_runs: list["AdminRunMonitorRowRead"]


class AdminRunMonitorRowRead(BaseModel):
    import_run_id: int
    display_id: int
    dataset_name: str
    owner_user_id: int | None
    owner_username: str | None
    run_status: str
    started_at: datetime
    completed_at: datetime | None
    record_count: int | None
    algo_index_status: str
    algo_index_ready: bool
    algo_build_duration_ms: int | None
    algo_last_error: str | None


class AdminRunMonitorRead(BaseModel):
    total_runs: int
    ready_indexes: int
    pending_indexes: int
    failed_indexes: int
    rows: list[AdminRunMonitorRowRead]


class AdminAssetSummaryRead(BaseModel):
    owner_count: int
    unique_stock_count: int
    largest_dataset_records: int
    median_dataset_records: float
    first_trade_date: date | None
    last_trade_date: date | None
    latest_imported_at: datetime | None


class AdminAssetGrowthPointRead(BaseModel):
    month: str
    cumulative_datasets: int
    cumulative_records: int


class AdminAssetDailyGrowthPointRead(BaseModel):
    day: date
    cumulative_datasets: int
    cumulative_records: int


class AdminAssetSizeBucketRead(BaseModel):
    bucket_label: str
    dataset_count: int
    record_count: int


class AdminAssetOwnerRowRead(BaseModel):
    owner_user_id: int
    owner_username: str | None
    dataset_count: int
    record_count: int
    record_share_ratio: float
    avg_records_per_dataset: float
    latest_completed_at: datetime | None


class AdminAssetTopDatasetRead(BaseModel):
    run_id: int
    display_id: int
    dataset_name: str
    owner_username: str | None
    record_count: int
    completed_at: datetime | None


class AdminAssetOverviewRead(BaseModel):
    summary: AdminAssetSummaryRead
    growth: list[AdminAssetGrowthPointRead]
    growth_daily: list[AdminAssetDailyGrowthPointRead]
    size_buckets: list[AdminAssetSizeBucketRead]
    owner_rows: list[AdminAssetOwnerRowRead]
    top_datasets: list[AdminAssetTopDatasetRead]


AdminOverviewRead.model_rebuild()
