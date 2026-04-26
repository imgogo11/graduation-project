from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import AuditLog


@dataclass(slots=True)
class AuditLogQuery:
    actor_user_id: int | None = None
    actor_username: str | None = None
    category: str | None = None
    success: bool | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None


class AuditLogRepository:
    @staticmethod
    def create(
        session: Session,
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
    ) -> AuditLog:
        record = AuditLog(
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
            detail_json=detail_json or {},
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record

    @staticmethod
    def list(
        session: Session,
        *,
        query: AuditLogQuery | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[AuditLog]:
        stmt = AuditLogRepository._apply_query(select(AuditLog), query=query)
        stmt = stmt.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit)
        return list(session.scalars(stmt))

    @staticmethod
    def count(
        session: Session,
        *,
        query: AuditLogQuery | None = None,
    ) -> int:
        stmt = AuditLogRepository._apply_query(select(func.count(AuditLog.id)), query=query)
        return int(session.scalar(stmt) or 0)

    @staticmethod
    def count_distinct_actors(
        session: Session,
        *,
        query: AuditLogQuery | None = None,
    ) -> int:
        stmt = AuditLogRepository._apply_query(select(func.count(func.distinct(AuditLog.actor_user_id))), query=query)
        stmt = stmt.where(AuditLog.actor_user_id.is_not(None))
        return int(session.scalar(stmt) or 0)

    @staticmethod
    def category_breakdown(
        session: Session,
        *,
        query: AuditLogQuery | None = None,
        limit: int = 10,
    ) -> list[tuple[str, int]]:
        stmt = AuditLogRepository._apply_query(
            select(AuditLog.category, func.count(AuditLog.id).label("total")),
            query=query,
        )
        stmt = stmt.group_by(AuditLog.category).order_by(func.count(AuditLog.id).desc(), AuditLog.category.asc()).limit(limit)
        rows = session.execute(stmt).all()
        return [(str(category), int(total)) for category, total in rows]

    @staticmethod
    def _apply_query(
        stmt: Select,
        *,
        query: AuditLogQuery | None,
    ) -> Select:
        if query is None:
            return stmt
        if query.actor_user_id is not None:
            stmt = stmt.where(AuditLog.actor_user_id == query.actor_user_id)
        if query.actor_username:
            stmt = stmt.where(AuditLog.actor_username_snapshot.ilike(f"%{query.actor_username}%"))
        if query.category:
            stmt = stmt.where(AuditLog.category == query.category)
        if query.success is not None:
            stmt = stmt.where(AuditLog.success == query.success)
        if query.start_at is not None:
            stmt = stmt.where(AuditLog.occurred_at >= query.start_at)
        if query.end_at is not None:
            stmt = stmt.where(AuditLog.occurred_at <= query.end_at)
        return stmt
