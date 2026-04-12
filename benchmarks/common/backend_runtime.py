from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import delete, insert

from .bootstrap import ensure_project_paths


ensure_project_paths()

from app.core.config import get_settings
from app.core.database import create_all_tables, get_engine, get_session_factory
from app.models import ImportRun, TradingRecord, utc_now
from app.repositories.imports import CURRENT_IMPORT_SOURCE_NAME, CURRENT_IMPORT_SOURCE_TYPE


@dataclass(frozen=True, slots=True)
class BackendRuntime:
    settings: Any
    engine: Any
    session_factory: Any


def create_runtime() -> BackendRuntime:
    create_all_tables()
    return BackendRuntime(
        settings=get_settings(),
        engine=get_engine(),
        session_factory=get_session_factory(),
    )


def dispose_runtime(runtime: BackendRuntime) -> None:
    runtime.engine.dispose()


def create_benchmark_run(
    session: Any,
    *,
    benchmark_name: str,
    instruments: int,
    days: int,
    row_count: int,
) -> ImportRun:
    timestamp = utc_now()
    run = ImportRun(
        owner_user_id=None,
        dataset_name=f"{benchmark_name}_{instruments}x{days}_{int(timestamp.timestamp())}",
        source_type=CURRENT_IMPORT_SOURCE_TYPE,
        source_name=CURRENT_IMPORT_SOURCE_NAME,
        source_uri=f"benchmark://{benchmark_name}/{instruments}x{days}",
        original_file_name=None,
        file_format="synthetic",
        status="completed",
        started_at=timestamp,
        completed_at=timestamp,
        record_count=row_count,
        metadata_json={"benchmark": benchmark_name},
    )
    session.add(run)
    session.flush()
    return run


def insert_benchmark_rows(session: Any, *, import_run_id: int, rows: list[dict[str, object]]) -> None:
    session.execute(insert(TradingRecord), [{"import_run_id": import_run_id, **row} for row in rows])


def cleanup_benchmark_run(session: Any, *, import_run_id: int) -> None:
    session.execute(delete(TradingRecord).where(TradingRecord.import_run_id == import_run_id))
    session.execute(delete(ImportRun).where(ImportRun.id == import_run_id))


def is_postgresql_database(database_url: str) -> bool:
    return database_url.startswith("postgresql")
