from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median

from app.core.database import get_session_factory
from app.models import TradingRecord
from app.repositories.audit_logs import AuditLogQuery, AuditLogRepository
from app.repositories.imports import ImportRunRepository
from app.repositories.users import UserRepository
from app.schemas.admin_dashboard import (
    AdminAssetDailyGrowthPointRead,
    AdminAssetGrowthPointRead,
    AdminAssetOverviewRead,
    AdminAssetOwnerRowRead,
    AdminAssetSizeBucketRead,
    AdminAssetSummaryRead,
    AdminAssetTopDatasetRead,
    AdminOverviewMetricRead,
    AdminOverviewRead,
    AdminRunMonitorRead,
    AdminRunMonitorRowRead,
)
from app.services.audit_logs import audit_log_service
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError


ALGO_INDEX_METADATA_KEY = "algo_index"
COMPLETED_RUN_STATUSES = ("completed",)
ASSET_SIZE_BUCKETS = (
    ("< 1万", 0, 10_000),
    ("1万 - 5万", 10_000, 50_000),
    ("5万 - 20万", 50_000, 200_000),
    ("20万+", 200_000, None),
)


class AdminDashboardService:
    def build_overview(self) -> AdminOverviewRead:
        now = datetime.now(timezone.utc)
        start_of_today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        day_ago = now - timedelta(days=1)

        session = get_session_factory()()
        try:
            users = UserRepository.list_users(session, role="user")
            runs = ImportRunRepository.list_all_visible_runs(session)
            total_records = int(sum(item.record_count or 0 for item in runs))
            try:
                recent_logs = AuditLogRepository.list(session, limit=8, offset=0)
                today_events = AuditLogRepository.count(session, query=AuditLogQuery(start_at=start_of_today))
                failed_events_24h = AuditLogRepository.count(
                    session,
                    query=AuditLogQuery(success=False, start_at=day_ago),
                )
            except SQLAlchemyError:
                session.rollback()
                recent_logs = []
                today_events = 0
                failed_events_24h = 0

            run_rows = self._serialize_run_rows(session=session, runs=runs[:8], all_runs=runs)
        finally:
            session.close()

        metrics = AdminOverviewMetricRead(
            total_users=len(users),
            active_users=sum(1 for item in users if item.is_active),
            total_runs=len(runs),
            total_records=total_records,
            today_events=today_events,
            failed_events_24h=failed_events_24h,
        )
        return AdminOverviewRead(
            metrics=metrics,
            recent_audit_logs=[audit_log_service._serialize_row(item) for item in recent_logs],
            recent_runs=run_rows,
        )

    def build_runs_monitor(self, *, limit: int = 30) -> AdminRunMonitorRead:
        normalized_limit = min(max(limit, 1), 200)
        session = get_session_factory()()
        try:
            runs = ImportRunRepository.list_all_visible_runs(session)
            all_rows = self._serialize_run_rows(session=session, runs=runs, all_runs=runs)
        finally:
            session.close()

        rows = all_rows[:normalized_limit]
        ready_indexes = sum(1 for item in all_rows if item.algo_index_status == "ready")
        failed_indexes = sum(1 for item in all_rows if item.algo_index_status == "failed")
        pending_indexes = max(len(all_rows) - ready_indexes - failed_indexes, 0)
        return AdminRunMonitorRead(
            total_runs=len(all_rows),
            ready_indexes=ready_indexes,
            pending_indexes=pending_indexes,
            failed_indexes=failed_indexes,
            rows=rows,
        )

    def build_asset_overview(self) -> AdminAssetOverviewRead:
        session = get_session_factory()()
        try:
            runs = ImportRunRepository.list_all_visible_runs(session, statuses=COMPLETED_RUN_STATUSES)
            if not runs:
                return AdminAssetOverviewRead(
                    summary=AdminAssetSummaryRead(
                        owner_count=0,
                        unique_stock_count=0,
                        largest_dataset_records=0,
                        median_dataset_records=0.0,
                        first_trade_date=None,
                        last_trade_date=None,
                        latest_imported_at=None,
                    ),
                    growth=[],
                    growth_daily=[],
                    size_buckets=[],
                    owner_rows=[],
                    top_datasets=[],
                )

            username_map = self._load_username_map(session, runs)
            display_id_map = self._build_display_id_map(runs)
            run_ids = [int(item.id) for item in runs]
            unique_stock_count, first_trade_date, last_trade_date = self._load_asset_range_summary(session, run_ids)
            total_records = int(sum(int(item.record_count or 0) for item in runs))
            record_counts = [int(item.record_count or 0) for item in runs]
            latest_imported_at = max((item.completed_at or item.started_at for item in runs), default=None)

            return AdminAssetOverviewRead(
                summary=AdminAssetSummaryRead(
                    owner_count=len({int(item.owner_user_id) for item in runs if item.owner_user_id is not None}),
                    unique_stock_count=unique_stock_count,
                    largest_dataset_records=max(record_counts, default=0),
                    median_dataset_records=float(median(record_counts)) if record_counts else 0.0,
                    first_trade_date=first_trade_date,
                    last_trade_date=last_trade_date,
                    latest_imported_at=latest_imported_at,
                ),
                growth=self._build_asset_growth(runs),
                growth_daily=self._build_asset_daily_growth(runs),
                size_buckets=self._build_asset_size_buckets(runs),
                owner_rows=self._build_asset_owner_rows(runs, username_map=username_map, total_records=total_records),
                top_datasets=self._build_top_datasets(runs, username_map=username_map, display_id_map=display_id_map),
            )
        finally:
            session.close()

    def _serialize_run_rows(self, *, session, runs, all_runs) -> list[AdminRunMonitorRowRead]:
        username_map = self._load_username_map(session, all_runs)
        display_id_map = self._build_display_id_map(all_runs)
        rows: list[AdminRunMonitorRowRead] = []
        for run in runs:
            metadata = run.metadata_json or {}
            algo_metadata = metadata.get(ALGO_INDEX_METADATA_KEY, {})
            status = str(algo_metadata.get("status") or "pending")
            rows.append(
                AdminRunMonitorRowRead(
                    import_run_id=int(run.id),
                    display_id=int(display_id_map.get(int(run.id), 0)),
                    dataset_name=run.dataset_name,
                    owner_user_id=run.owner_user_id,
                    owner_username=username_map.get(int(run.owner_user_id)) if run.owner_user_id is not None else None,
                    run_status=run.status,
                    started_at=run.started_at,
                    completed_at=run.completed_at,
                    record_count=run.record_count,
                    algo_index_status=status,
                    algo_index_ready=status == "ready",
                    algo_build_duration_ms=self._parse_int(algo_metadata.get("build_duration_ms")),
                    algo_last_error=self._parse_text(algo_metadata.get("last_error")),
                )
            )
        return rows

    def _build_asset_growth(self, runs) -> list[AdminAssetGrowthPointRead]:
        monthly_rows: dict[str, dict[str, int]] = defaultdict(lambda: {"datasets": 0, "records": 0})
        for run in runs:
            anchor = run.completed_at or run.started_at
            month_key = anchor.strftime("%Y-%m")
            monthly_rows[month_key]["datasets"] += 1
            monthly_rows[month_key]["records"] += int(run.record_count or 0)

        cumulative_datasets = 0
        cumulative_records = 0
        output: list[AdminAssetGrowthPointRead] = []
        for month_key in sorted(monthly_rows):
            cumulative_datasets += monthly_rows[month_key]["datasets"]
            cumulative_records += monthly_rows[month_key]["records"]
            output.append(
                AdminAssetGrowthPointRead(
                    month=month_key,
                    cumulative_datasets=cumulative_datasets,
                    cumulative_records=cumulative_records,
                )
            )
        return output

    def _build_asset_daily_growth(self, runs) -> list[AdminAssetDailyGrowthPointRead]:
        daily_rows: dict[date, dict[str, int]] = defaultdict(lambda: {"datasets": 0, "records": 0})
        for run in runs:
            anchor = (run.completed_at or run.started_at).date()
            daily_rows[anchor]["datasets"] += 1
            daily_rows[anchor]["records"] += int(run.record_count or 0)

        cumulative_datasets = 0
        cumulative_records = 0
        output: list[AdminAssetDailyGrowthPointRead] = []
        for day_key in sorted(daily_rows):
            cumulative_datasets += daily_rows[day_key]["datasets"]
            cumulative_records += daily_rows[day_key]["records"]
            output.append(
                AdminAssetDailyGrowthPointRead(
                    day=day_key,
                    cumulative_datasets=cumulative_datasets,
                    cumulative_records=cumulative_records,
                )
            )
        return output

    def _build_asset_size_buckets(self, runs) -> list[AdminAssetSizeBucketRead]:
        bucket_rows: dict[str, dict[str, int]] = defaultdict(lambda: {"dataset_count": 0, "record_count": 0})
        for run in runs:
            record_count = int(run.record_count or 0)
            bucket_label = self._resolve_size_bucket_label(record_count)
            bucket_rows[bucket_label]["dataset_count"] += 1
            bucket_rows[bucket_label]["record_count"] += record_count

        output: list[AdminAssetSizeBucketRead] = []
        for bucket_label, _, _ in ASSET_SIZE_BUCKETS:
            payload = bucket_rows.get(bucket_label)
            if not payload:
                continue
            output.append(
                AdminAssetSizeBucketRead(
                    bucket_label=bucket_label,
                    dataset_count=payload["dataset_count"],
                    record_count=payload["record_count"],
                )
            )
        return output

    def _build_asset_owner_rows(self, runs, *, username_map: dict[int, str], total_records: int) -> list[AdminAssetOwnerRowRead]:
        owner_rows: dict[int, dict[str, object]] = defaultdict(
            lambda: {"dataset_count": 0, "record_count": 0, "latest_completed_at": None}
        )
        for run in runs:
            if run.owner_user_id is None:
                continue
            owner_id = int(run.owner_user_id)
            payload = owner_rows[owner_id]
            payload["dataset_count"] = int(payload["dataset_count"]) + 1
            payload["record_count"] = int(payload["record_count"]) + int(run.record_count or 0)
            latest_completed_at = payload["latest_completed_at"]
            anchor = run.completed_at or run.started_at
            if latest_completed_at is None or anchor > latest_completed_at:
                payload["latest_completed_at"] = anchor

        rows = [
            AdminAssetOwnerRowRead(
                owner_user_id=owner_id,
                owner_username=username_map.get(owner_id),
                dataset_count=int(payload["dataset_count"]),
                record_count=int(payload["record_count"]),
                record_share_ratio=(int(payload["record_count"]) / total_records) if total_records else 0.0,
                avg_records_per_dataset=(
                    int(payload["record_count"]) / int(payload["dataset_count"])
                    if int(payload["dataset_count"])
                    else 0.0
                ),
                latest_completed_at=payload["latest_completed_at"],
            )
            for owner_id, payload in owner_rows.items()
        ]
        return sorted(
            rows,
            key=lambda item: (-item.record_count, -item.dataset_count, item.owner_username or ""),
        )

    def _build_top_datasets(self, runs, *, username_map: dict[int, str], display_id_map: dict[int, int]) -> list[AdminAssetTopDatasetRead]:
        sorted_runs = sorted(
            runs,
            key=lambda item: (
                -(int(item.record_count or 0)),
                -(item.completed_at or item.started_at).timestamp(),
                int(item.id),
            ),
        )
        return [
            AdminAssetTopDatasetRead(
                run_id=int(run.id),
                display_id=int(display_id_map.get(int(run.id), 0)),
                dataset_name=run.dataset_name,
                owner_username=username_map.get(int(run.owner_user_id)) if run.owner_user_id is not None else None,
                record_count=int(run.record_count or 0),
                completed_at=run.completed_at,
            )
            for run in sorted_runs[:10]
        ]

    def _load_username_map(self, session, runs) -> dict[int, str]:
        user_ids = sorted({int(item.owner_user_id) for item in runs if item.owner_user_id is not None})
        username_map: dict[int, str] = {}
        for user_id in user_ids:
            user = UserRepository.get_by_id(session, user_id)
            if user is not None:
                username_map[user_id] = user.username
        return username_map

    def _load_asset_range_summary(self, session, run_ids: list[int]) -> tuple[int, date | None, date | None]:
        if not run_ids:
            return 0, None, None

        stmt = (
            select(
                func.count(func.distinct(TradingRecord.stock_code)),
                func.min(TradingRecord.trade_date),
                func.max(TradingRecord.trade_date),
            )
            .where(TradingRecord.import_run_id.in_(run_ids))
        )
        unique_stock_count, first_trade_date, last_trade_date = session.execute(stmt).one()
        return int(unique_stock_count or 0), first_trade_date, last_trade_date

    def _resolve_size_bucket_label(self, record_count: int) -> str:
        for bucket_label, minimum, maximum in ASSET_SIZE_BUCKETS:
            if maximum is None and record_count >= minimum:
                return bucket_label
            if maximum is not None and minimum <= record_count < maximum:
                return bucket_label
        return ASSET_SIZE_BUCKETS[-1][0]

    def _build_display_id_map(self, runs) -> dict[int, int]:
        ordered_runs = sorted(runs, key=lambda item: (item.started_at, item.id))
        return {int(run.id): index for index, run in enumerate(ordered_runs, start=1)}

    def _parse_int(self, value) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _parse_text(self, value) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


admin_dashboard_service = AdminDashboardService()
