# 作用:
# - 这是导入记录仓储模块，用来封装 import_runs、import_manifests、import_artifacts 的写入与查询操作。
# 关联文件:
# - 被 backend/app/services/imports.py 直接依赖，用于记录每次导入任务的状态和产物。
# - 相关 ORM 实体定义在 backend/app/models/entities.py。
#
from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import ImportArtifactRecord, ImportManifestRecord, ImportRun, utc_now


class ImportRunRepository:
    @staticmethod
    def create_run(
        session: Session,
        *,
        dataset_name: str,
        source_type: str,
        source_name: str,
        source_uri: str | None,
        metadata_json: dict[str, Any],
    ) -> ImportRun:
        run = ImportRun(
            dataset_name=dataset_name,
            source_type=source_type,
            source_name=source_name,
            source_uri=source_uri,
            status="running",
            metadata_json=metadata_json,
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
    def list_runs(session: Session, *, limit: int = 20) -> list[ImportRun]:
        stmt = select(ImportRun).order_by(desc(ImportRun.id)).limit(limit)
        return list(session.scalars(stmt))
