# 作用:
# - 这是导入记录仓储模块，用来封装 import_runs、import_manifests、import_artifacts 的写入与查询操作。
# 关联文件:
# - 被 backend/app/services/imports.py 直接依赖，用于记录每次导入任务的状态和产物。
# - 相关 ORM 实体定义在 backend/app/models/entities.py。
#
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.models import (
    ImportArtifactRecord,
    ImportManifestRecord,
    ImportMappingTemplate,
    ImportPreviewSession,
    ImportRun,
    utc_now,
)


CURRENT_IMPORT_SOURCE_TYPE = "upload"
CURRENT_IMPORT_SOURCE_NAME = "user.upload"
ACTIVE_UPLOAD_STATUSES = ("running", "completed")


def _current_import_filter(stmt):
    return stmt.where(ImportRun.source_type == CURRENT_IMPORT_SOURCE_TYPE).where(
        ImportRun.source_name == CURRENT_IMPORT_SOURCE_NAME
    )


def _apply_visibility_filters(
    stmt,
    *,
    owner_user_id: int | None = None,
    include_deleted: bool = False,
    statuses: tuple[str, ...] | None = None,
):
    if owner_user_id is not None:
        stmt = stmt.where(ImportRun.owner_user_id == owner_user_id)
    if not include_deleted:
        stmt = stmt.where(ImportRun.deleted_at.is_(None))
    if statuses is not None:
        stmt = stmt.where(ImportRun.status.in_(statuses))
    return stmt


class ImportRunRepository:
    @staticmethod
    def create_run(
        session: Session,
        *,
        owner_user_id: int | None,
        dataset_name: str,
        source_type: str,
        source_name: str,
        source_uri: str | None,
        original_file_name: str | None,
        file_format: str | None,
        metadata_json: dict[str, Any] | None = None,
    ) -> ImportRun:
        run = ImportRun(
            owner_user_id=owner_user_id,
            dataset_name=dataset_name,
            source_type=source_type,
            source_name=source_name,
            source_uri=source_uri,
            original_file_name=original_file_name,
            file_format=file_format,
            status="running",
            metadata_json=metadata_json or {},
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        return run

    @staticmethod
    def add_manifest(
        session: Session,
        *,
        import_run_id: int,
        manifest_path: str,
        created_at: datetime,
        record_count: int,
        columns_json: list[str],
        metadata_json: dict[str, Any],
    ) -> ImportManifestRecord:
        record = ImportManifestRecord(
            import_run_id=import_run_id,
            manifest_path=manifest_path,
            created_at=created_at,
            record_count=record_count,
            columns_json=columns_json,
            metadata_json=metadata_json,
        )
        session.add(record)
        session.flush()
        return record

    @staticmethod
    def add_artifact(
        session: Session,
        *,
        import_run_id: int,
        manifest_id: int,
        name: str,
        path: str,
        row_count: int,
        columns_json: list[str],
    ) -> None:
        session.add(
            ImportArtifactRecord(
                import_run_id=import_run_id,
                manifest_id=manifest_id,
                name=name,
                path=path,
                row_count=row_count,
                columns_json=columns_json,
            )
        )

    @staticmethod
    def mark_completed(session: Session, run: ImportRun, *, record_count: int) -> None:
        run.status = "completed"
        run.completed_at = utc_now()
        run.record_count = record_count
        session.add(run)

    @staticmethod
    def mark_failed(session: Session, *, run_id: int, error_message: str) -> ImportRun:
        run = session.get(ImportRun, run_id)
        if run is None:
            raise ValueError(f"Import run {run_id} not found")
        run.status = "failed"
        run.completed_at = utc_now()
        run.error_message = error_message
        session.add(run)
        session.commit()
        session.refresh(run)
        return run

    @staticmethod
    def get_run(session: Session, run_id: int) -> ImportRun | None:
        return session.get(ImportRun, run_id)

    @staticmethod
    def get_visible_run(
        session: Session,
        *,
        run_id: int,
        owner_user_id: int | None = None,
        include_deleted: bool = False,
        statuses: tuple[str, ...] | None = None,
    ) -> ImportRun | None:
        stmt = _current_import_filter(select(ImportRun).where(ImportRun.id == run_id))
        stmt = _apply_visibility_filters(
            stmt,
            owner_user_id=owner_user_id,
            include_deleted=include_deleted,
            statuses=statuses,
        )
        return session.scalar(stmt)

    @staticmethod
    def get_active_upload_run_by_dataset_name(
        session: Session,
        *,
        owner_user_id: int | None,
        dataset_name: str,
    ) -> ImportRun | None:
        stmt = _current_import_filter(select(ImportRun).where(ImportRun.dataset_name == dataset_name))
        stmt = stmt.where(ImportRun.deleted_at.is_(None))
        stmt = stmt.where(ImportRun.status.in_(ACTIVE_UPLOAD_STATUSES))
        if owner_user_id is None:
            stmt = stmt.where(ImportRun.owner_user_id.is_(None))
        else:
            stmt = stmt.where(ImportRun.owner_user_id == owner_user_id)
        stmt = stmt.order_by(desc(ImportRun.id)).limit(1)
        return session.scalar(stmt)

    @staticmethod
    def list_runs(
        session: Session,
        *,
        owner_user_id: int | None = None,
        include_deleted: bool = False,
        statuses: tuple[str, ...] | None = None,
        limit: int = 20,
    ) -> list[ImportRun]:
        stmt = _current_import_filter(select(ImportRun))
        stmt = _apply_visibility_filters(
            stmt,
            owner_user_id=owner_user_id,
            include_deleted=include_deleted,
            statuses=statuses,
        )
        stmt = stmt.order_by(desc(ImportRun.id)).limit(limit)
        return list(session.scalars(stmt))

    @staticmethod
    def list_all_visible_runs(
        session: Session,
        *,
        owner_user_id: int | None = None,
        include_deleted: bool = False,
        statuses: tuple[str, ...] | None = None,
    ) -> list[ImportRun]:
        stmt = _current_import_filter(select(ImportRun))
        stmt = _apply_visibility_filters(
            stmt,
            owner_user_id=owner_user_id,
            include_deleted=include_deleted,
            statuses=statuses,
        )
        stmt = stmt.order_by(desc(ImportRun.started_at), desc(ImportRun.id))
        return list(session.scalars(stmt))

    @staticmethod
    def soft_delete(session: Session, run: ImportRun) -> ImportRun:
        run.deleted_at = utc_now()
        session.add(run)
        session.commit()
        session.refresh(run)
        return run


class ImportPreviewSessionRepository:
    @staticmethod
    def create(
        session: Session,
        *,
        preview_id: str,
        owner_user_id: int,
        dataset_name: str,
        original_file_name: str,
        file_format: str,
        staged_file_path: str,
        header_fingerprint: str,
        preview_payload_json: dict[str, Any],
        expires_at: datetime,
    ) -> ImportPreviewSession:
        row = ImportPreviewSession(
            id=preview_id,
            owner_user_id=owner_user_id,
            dataset_name=dataset_name,
            original_file_name=original_file_name,
            file_format=file_format,
            staged_file_path=staged_file_path,
            header_fingerprint=header_fingerprint,
            preview_payload_json=preview_payload_json,
            status="pending",
            expires_at=expires_at,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row

    @staticmethod
    def get_by_id(session: Session, preview_id: str) -> ImportPreviewSession | None:
        return session.get(ImportPreviewSession, preview_id)

    @staticmethod
    def list_expired_pending(session: Session, *, now: datetime, limit: int = 100) -> list[ImportPreviewSession]:
        stmt = (
            select(ImportPreviewSession)
            .where(ImportPreviewSession.status == "pending")
            .where(ImportPreviewSession.expires_at < now)
            .order_by(ImportPreviewSession.expires_at.asc())
            .limit(limit)
        )
        return list(session.scalars(stmt))

    @staticmethod
    def delete_many(session: Session, preview_ids: list[str]) -> None:
        if not preview_ids:
            return
        stmt = delete(ImportPreviewSession).where(ImportPreviewSession.id.in_(preview_ids))
        session.execute(stmt)
        session.commit()

    @staticmethod
    def mark_committed(session: Session, row: ImportPreviewSession, *, run_id: int) -> None:
        row.status = "committed"
        row.committed_run_id = run_id
        session.add(row)
        session.commit()
        session.refresh(row)


class ImportMappingTemplateRepository:
    @staticmethod
    def get_for_owner_and_fingerprint(
        session: Session,
        *,
        owner_user_id: int,
        header_fingerprint: str,
    ) -> ImportMappingTemplate | None:
        stmt = (
            select(ImportMappingTemplate)
            .where(ImportMappingTemplate.owner_user_id == owner_user_id)
            .where(ImportMappingTemplate.header_fingerprint == header_fingerprint)
            .limit(1)
        )
        return session.scalar(stmt)

    @staticmethod
    def upsert(
        session: Session,
        *,
        owner_user_id: int,
        header_fingerprint: str,
        mapping_json: dict[str, str],
    ) -> ImportMappingTemplate:
        now = utc_now()
        row = ImportMappingTemplateRepository.get_for_owner_and_fingerprint(
            session,
            owner_user_id=owner_user_id,
            header_fingerprint=header_fingerprint,
        )
        if row is None:
            row = ImportMappingTemplate(
                owner_user_id=owner_user_id,
                header_fingerprint=header_fingerprint,
                mapping_json=mapping_json,
                usage_count=1,
                created_at=now,
                updated_at=now,
                last_used_at=now,
            )
        else:
            row.mapping_json = mapping_json
            row.usage_count = (row.usage_count or 0) + 1
            row.updated_at = now
            row.last_used_at = now
        session.add(row)
        session.commit()
        session.refresh(row)
        return row
