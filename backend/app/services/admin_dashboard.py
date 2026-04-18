from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.database import get_session_factory
from app.repositories.audit_logs import AuditLogQuery, AuditLogRepository
from app.repositories.imports import ImportRunRepository
from app.repositories.users import UserRepository
from app.schemas.admin_dashboard import (
    AdminOverviewMetricRead,
    AdminOverviewRead,
    AdminRunMonitorRead,
    AdminRunMonitorRowRead,
)
from app.services.audit_logs import audit_log_service
from sqlalchemy.exc import SQLAlchemyError


ALGO_INDEX_METADATA_KEY = "algo_index"


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

            run_rows = self._serialize_run_rows(runs=runs[:8], all_runs=runs)
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
            all_rows = self._serialize_run_rows(runs=runs, all_runs=runs)
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

    def _serialize_run_rows(self, *, runs, all_runs) -> list[AdminRunMonitorRowRead]:
        user_ids = sorted({item.owner_user_id for item in all_runs if item.owner_user_id is not None})
        username_map: dict[int, str] = {}
        session = get_session_factory()()
        try:
            for user_id in user_ids:
                user = UserRepository.get_by_id(session, int(user_id))
                if user is not None:
                    username_map[int(user.id)] = user.username
        finally:
            session.close()

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
