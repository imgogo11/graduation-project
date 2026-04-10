# 作用:
# - 这是导入记录仓储模块，用来封装 import_runs、import_manifests、import_artifacts 的写入与查询操作。
# 关联文件:
# - 被 backend/app/services/imports.py 直接依赖，用于记录每次导入任务的状态和产物。
# - 相关 ORM 实体定义在 backend/app/models/entities.py。
#
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import ImportArtifactRecord, ImportManifestRecord, ImportRun, utc_now


CURRENT_IMPORT_SOURCE_TYPE = "upload"
CURRENT_IMPORT_SOURCE_NAME = "user.upload"


def _current_import_filter(stmt):
    return stmt.where(ImportRun.source_type == CURRENT_IMPORT_SOURCE_TYPE).where(
        ImportRun.source_name == CURRENT_IMPORT_SOURCE_NAME
    )


class ImportRunRepository:
    @staticmethod
    def create_run(
        session: Session,
        *,
        owner_user_id: int | None,
        dataset_name: str,
        asset_class: str | None,
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
            asset_class=asset_class,
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
    ) -> ImportRun | None:
        stmt = _current_import_filter(select(ImportRun).where(ImportRun.id == run_id))
        if owner_user_id is not None:
            stmt = stmt.where(ImportRun.owner_user_id == owner_user_id)
        if not include_deleted:
            stmt = stmt.where(ImportRun.deleted_at.is_(None))
        return session.scalar(stmt)

    @staticmethod
    def list_runs(
        session: Session,
        *,
        owner_user_id: int | None = None,
        include_deleted: bool = False,
        limit: int = 20,
    ) -> list[ImportRun]:
        stmt = _current_import_filter(select(ImportRun))
        if owner_user_id is not None:
            stmt = stmt.where(ImportRun.owner_user_id == owner_user_id)
        if not include_deleted:
            stmt = stmt.where(ImportRun.deleted_at.is_(None))
        stmt = stmt.order_by(desc(ImportRun.id)).limit(limit)
        return list(session.scalars(stmt))

    @staticmethod
    def list_all_visible_runs(
        session: Session,
        *,
        owner_user_id: int | None = None,
        include_deleted: bool = False,
    ) -> list[ImportRun]:
        stmt = _current_import_filter(select(ImportRun))
        if owner_user_id is not None:
            stmt = stmt.where(ImportRun.owner_user_id == owner_user_id)
        if not include_deleted:
            stmt = stmt.where(ImportRun.deleted_at.is_(None))
        stmt = stmt.order_by(desc(ImportRun.started_at), desc(ImportRun.id))
        return list(session.scalars(stmt))

    @staticmethod
    def soft_delete(session: Session, run: ImportRun) -> ImportRun:
        run.deleted_at = utc_now()
        session.add(run)
        session.commit()
        session.refresh(run)
        return run
