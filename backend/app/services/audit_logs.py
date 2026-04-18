from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.database import get_session_factory
from app.core.security import TokenDecodeError, decode_access_token
from app.models import AuditLog
from app.repositories.audit_logs import AuditLogQuery, AuditLogRepository
from app.repositories.users import UserRepository
from app.schemas.admin_dashboard import (
    AuditLogCategoryStatRead,
    AuditLogListRead,
    AuditLogRead,
    AuditLogStatsRead,
)


def _normalize_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    candidate = value.strip()
    if not candidate:
        return None
    parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


class AuditLogService:
    def record_event(
        self,
        *,
        category: str,
        event_type: str,
        success: bool,
        status_code: int | None = None,
        actor_user_id: int | None = None,
        actor_username_snapshot: str | None = None,
        actor_role: str | None = None,
        target_type: str | None = None,
        target_label: str | None = None,
        import_run_id: int | None = None,
        request_path: str | None = None,
        http_method: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        detail_json: dict[str, Any] | None = None,
    ) -> None:
        session = get_session_factory()()
        try:
            AuditLogRepository.create(
                session,
                category=category,
                event_type=event_type,
                success=success,
                status_code=status_code,
                actor_user_id=actor_user_id,
                actor_username_snapshot=actor_username_snapshot,
                actor_role=actor_role,
                target_type=target_type,
                target_label=target_label,
                import_run_id=import_run_id,
                request_path=request_path,
                http_method=http_method,
                ip_address=ip_address,
                user_agent=user_agent,
                detail_json=detail_json,
            )
        except Exception:
            # Do not block business request flow when audit logging fails.
            session.rollback()
        finally:
            session.close()

    def list_logs(
        self,
        *,
        page: int,
        page_size: int,
        actor_user_id: int | None = None,
        category: str | None = None,
        success: bool | None = None,
        start_at: datetime | str | None = None,
        end_at: datetime | str | None = None,
    ) -> AuditLogListRead:
        normalized_page = max(page, 1)
        normalized_page_size = min(max(page_size, 1), 200)
        offset = (normalized_page - 1) * normalized_page_size
        query = AuditLogQuery(
            actor_user_id=actor_user_id,
            category=(category or "").strip() or None,
            success=success,
            start_at=_normalize_datetime(start_at),
            end_at=_normalize_datetime(end_at),
        )
        session = get_session_factory()()
        try:
            rows = AuditLogRepository.list(session, query=query, limit=normalized_page_size, offset=offset)
            total = AuditLogRepository.count(session, query=query)
        except Exception:
            session.rollback()
            rows = []
            total = 0
        finally:
            session.close()
        return AuditLogListRead(
            total=total,
            page=normalized_page,
            page_size=normalized_page_size,
            rows=[self._serialize_row(item) for item in rows],
        )

    def build_stats(
        self,
        *,
        actor_user_id: int | None = None,
        category: str | None = None,
        success: bool | None = None,
        start_at: datetime | str | None = None,
        end_at: datetime | str | None = None,
    ) -> AuditLogStatsRead:
        query = AuditLogQuery(
            actor_user_id=actor_user_id,
            category=(category or "").strip() or None,
            success=success,
            start_at=_normalize_datetime(start_at),
            end_at=_normalize_datetime(end_at),
        )
        now = datetime.now(timezone.utc)
        start_of_today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        session = get_session_factory()()
        try:
            total_events = AuditLogRepository.count(session, query=query)
            if query.success is True:
                success_events = total_events
                failed_events = 0
            elif query.success is False:
                success_events = 0
                failed_events = total_events
            else:
                success_events = AuditLogRepository.count(
                    session,
                    query=AuditLogQuery(
                        actor_user_id=query.actor_user_id,
                        category=query.category,
                        success=True,
                        start_at=query.start_at,
                        end_at=query.end_at,
                    ),
                )
                failed_events = AuditLogRepository.count(
                    session,
                    query=AuditLogQuery(
                        actor_user_id=query.actor_user_id,
                        category=query.category,
                        success=False,
                        start_at=query.start_at,
                        end_at=query.end_at,
                    ),
                )
            unique_actor_count = AuditLogRepository.count_distinct_actors(session, query=query)
            today_events = AuditLogRepository.count(
                session,
                query=AuditLogQuery(
                    actor_user_id=query.actor_user_id,
                    category=query.category,
                    success=query.success,
                    start_at=max(query.start_at, start_of_today) if query.start_at else start_of_today,
                    end_at=query.end_at,
                ),
            )
            breakdown_rows = AuditLogRepository.category_breakdown(session, query=query)
        except Exception:
            session.rollback()
            total_events = 0
            success_events = 0
            failed_events = 0
            unique_actor_count = 0
            today_events = 0
            breakdown_rows = []
        finally:
            session.close()
        return AuditLogStatsRead(
            total_events=total_events,
            success_events=success_events,
            failed_events=failed_events,
            unique_actor_count=unique_actor_count,
            today_events=today_events,
            category_breakdown=[
                AuditLogCategoryStatRead(category=category_name, total=total)
                for category_name, total in breakdown_rows
            ],
        )

    def resolve_actor_from_authorization(
        self,
        authorization: str | None,
    ) -> tuple[int | None, str | None, str | None]:
        if not authorization:
            return None, None, None
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None, None, None
        try:
            payload = decode_access_token(token)
            user_id = int(payload.get("sub"))
        except (TokenDecodeError, ValueError, TypeError):
            return None, None, None
        username = payload.get("username")
        role = payload.get("role")
        if username and role:
            return user_id, str(username), str(role)
        session = get_session_factory()()
        try:
            user = UserRepository.get_by_id(session, user_id)
            if user is None:
                return user_id, None, None
            return user_id, user.username, user.role
        finally:
            session.close()

    def _serialize_row(self, row: AuditLog) -> AuditLogRead:
        return AuditLogRead(
            id=row.id,
            occurred_at=row.occurred_at,
            category=row.category,
            event_type=row.event_type,
            success=row.success,
            status_code=row.status_code,
            actor_user_id=row.actor_user_id,
            actor_username_snapshot=row.actor_username_snapshot,
            actor_role=row.actor_role,
            target_type=row.target_type,
            target_label=row.target_label,
            import_run_id=row.import_run_id,
            request_path=row.request_path,
            http_method=row.http_method,
            ip_address=row.ip_address,
            user_agent=row.user_agent,
            detail_json=row.detail_json or {},
        )


audit_log_service = AuditLogService()
