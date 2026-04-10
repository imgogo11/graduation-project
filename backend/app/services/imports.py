from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import re
from typing import Any

import pandas as pd
from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ImportRun, TradingRecord, User, utc_now
from app.repositories.imports import ImportRunRepository
from app.repositories.users import UserRepository
from app.schemas.trading import ImportOwnerSummaryRead, ImportRunRead, ImportStatsRead, ImportMonthlyStatRead


class ImportExecutionError(RuntimeError):
    def __init__(self, run_id: int, message: str):
        self.run_id = run_id
        super().__init__(message)


class ImportValidationError(ValueError):
    """Raised when an uploaded trading file cannot be parsed or validated."""


REQUIRED_COLUMNS = [
    "instrument_code",
    "instrument_name",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
]
NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume", "amount"]
ASSET_CLASSES = {"stock", "commodity"}
DECIMAL_QUANTUM = Decimal("0.0001")


@dataclass(slots=True)
class NormalizedTradingDataset:
    rows: list[dict[str, Any]]
    columns: list[str]
    row_count: int


class ImportService:
    def import_uploaded_file(
        self,
        session: Session,
        *,
        owner: User,
        dataset_name: str,
        asset_class: str,
        original_file_name: str,
        file_bytes: bytes,
    ) -> ImportRun:
        cleaned_dataset_name = dataset_name.strip()
        if not cleaned_dataset_name:
            raise ImportValidationError("Dataset name is required")

        normalized_asset_class = asset_class.strip().lower()
        if normalized_asset_class not in ASSET_CLASSES:
            raise ImportValidationError("asset_class must be one of: stock, commodity")

        safe_file_name = self._sanitize_file_name(original_file_name)
        file_format = self._resolve_file_format(safe_file_name)
        run = ImportRunRepository.create_run(
            session,
            owner_user_id=owner.id,
            dataset_name=cleaned_dataset_name,
            asset_class=normalized_asset_class,
            source_type="upload",
            source_name="user.upload",
            source_uri=None,
            original_file_name=safe_file_name,
            file_format=file_format,
            metadata_json={
                "required_columns": REQUIRED_COLUMNS,
                "template_version": "trading-v1",
            },
        )

        try:
            upload_path = self._build_upload_path(owner.id, run.id, safe_file_name)
            upload_path.parent.mkdir(parents=True, exist_ok=True)
            upload_path.write_bytes(file_bytes)

            dataset = self._load_and_normalize_dataset(upload_path, file_format)
            manifest_record = ImportRunRepository.add_manifest(
                session,
                import_run_id=run.id,
                manifest_path=str(upload_path),
                created_at=utc_now(),
                record_count=dataset.row_count,
                columns_json=dataset.columns,
                metadata_json={
                    "asset_class": normalized_asset_class,
                    "file_format": file_format,
                },
            )
            ImportRunRepository.add_artifact(
                session,
                import_run_id=run.id,
                manifest_id=manifest_record.id,
                name="original_upload",
                path=str(upload_path),
                row_count=dataset.row_count,
                columns_json=dataset.columns,
            )
            self._bulk_insert_records(session, run_id=run.id, rows=dataset.rows)
            ImportRunRepository.mark_completed(session, run, record_count=dataset.row_count)
            session.commit()
            session.refresh(run)
            return run
        except Exception as exc:
            session.rollback()
            ImportRunRepository.mark_failed(session, run_id=run.id, error_message=str(exc))
            raise ImportExecutionError(run.id, str(exc)) from exc

    def list_runs(
        self,
        session: Session,
        *,
        owner_user_id: int | None,
        limit: int,
    ) -> list[ImportRunRead]:
        runs = ImportRunRepository.list_runs(session, owner_user_id=owner_user_id, limit=limit)
        display_id_map = self._build_display_id_map(
            ImportRunRepository.list_all_visible_runs(session, owner_user_id=owner_user_id)
        )
        return self._serialize_runs(session, runs, display_id_map=display_id_map)

    def serialize_run(
        self,
        session: Session,
        run: ImportRun,
        *,
        owner_user_id: int | None,
    ) -> ImportRunRead:
        display_id_map = self._build_display_id_map(
            ImportRunRepository.list_all_visible_runs(session, owner_user_id=owner_user_id)
        )
        return self._serialize_runs(session, [run], display_id_map=display_id_map)[0]

    def build_stats(
        self,
        session: Session,
        *,
        owner_user_id: int | None,
    ) -> ImportStatsRead:
        runs = ImportRunRepository.list_all_visible_runs(session, owner_user_id=owner_user_id)
        username_map = self._load_username_map(session, runs)
        monthly_imports: dict[str, dict[str, int]] = defaultdict(lambda: {"runs": 0, "records": 0})
        owner_summaries: dict[int, dict[str, int]] = defaultdict(lambda: {"runs": 0, "records": 0})

        completed_runs = 0
        failed_runs = 0
        total_records = 0
        dataset_names: set[str] = set()

        for run in runs:
            dataset_names.add(run.dataset_name)
            month_key = run.started_at.strftime("%Y-%m")
            monthly_imports[month_key]["runs"] += 1
            monthly_imports[month_key]["records"] += run.record_count or 0

            if run.owner_user_id is not None:
                owner_summaries[run.owner_user_id]["runs"] += 1
                owner_summaries[run.owner_user_id]["records"] += run.record_count or 0

            total_records += run.record_count or 0
            if run.status == "completed":
                completed_runs += 1
            elif run.status == "failed":
                failed_runs += 1

        monthly_points = [
            ImportMonthlyStatRead(month=month, runs=payload["runs"], records=payload["records"])
            for month, payload in sorted(monthly_imports.items())
        ]
        owner_points = [
            ImportOwnerSummaryRead(
                owner_user_id=owner_id,
                owner_username=username_map.get(owner_id),
                runs=payload["runs"],
                records=payload["records"],
            )
            for owner_id, payload in sorted(owner_summaries.items(), key=lambda item: item[0])
        ]
        return ImportStatsRead(
            total_runs=len(runs),
            completed_runs=completed_runs,
            failed_runs=failed_runs,
            total_records=total_records,
            active_datasets=len(dataset_names),
            monthly_imports=monthly_points,
            owner_summaries=owner_points if owner_user_id is None else [],
        )

    def delete_run(self, session: Session, *, run: ImportRun) -> ImportRun:
        return ImportRunRepository.soft_delete(session, run)

    def _serialize_runs(
        self,
        session: Session,
        runs: list[ImportRun],
        *,
        display_id_map: dict[int, int] | None = None,
    ) -> list[ImportRunRead]:
        if display_id_map is None:
            display_id_map = self._build_display_id_map(runs)
        username_map = self._load_username_map(session, runs)
        return [
            ImportRunRead(
                id=run.id,
                display_id=self._resolve_display_id(display_id_map, run.id),
                owner_user_id=run.owner_user_id,
                owner_username=username_map.get(run.owner_user_id),
                dataset_name=run.dataset_name,
                asset_class=run.asset_class,
                source_type=run.source_type,
                source_name=run.source_name,
                original_file_name=run.original_file_name,
                file_format=run.file_format,
                status=run.status,
                started_at=run.started_at,
                completed_at=run.completed_at,
                record_count=run.record_count,
                error_message=run.error_message,
                deleted_at=run.deleted_at,
            )
            for run in runs
        ]

    def _build_display_id_map(self, runs: list[ImportRun]) -> dict[int, int]:
        ordered_runs = sorted(runs, key=lambda item: (item.started_at, item.id))
        return {run.id: index for index, run in enumerate(ordered_runs, start=1)}

    def _resolve_display_id(self, display_id_map: dict[int, int], run_id: int) -> int:
        display_id = display_id_map.get(run_id)
        if display_id is None:
            raise ValueError(f"display_id is not available for import run {run_id}")
        return display_id

    def _load_username_map(self, session: Session, runs: list[ImportRun]) -> dict[int, str]:
        owner_ids = sorted({run.owner_user_id for run in runs if run.owner_user_id is not None})
        result: dict[int, str] = {}
        for owner_id in owner_ids:
            user = UserRepository.get_by_id(session, owner_id)
            if user is not None:
                result[user.id] = user.username
        return result

    def _load_and_normalize_dataset(self, path: Path, file_format: str) -> NormalizedTradingDataset:
        if file_format == "csv":
            frame = pd.read_csv(path)
        else:
            frame = pd.read_excel(path, engine="openpyxl")

        if frame.empty:
            raise ImportValidationError("Uploaded file does not contain any rows")

        canonical_columns: dict[str, str] = {}
        rename_map: dict[str, str] = {}
        for column in frame.columns:
            normalized = str(column).strip().lower()
            if normalized in REQUIRED_COLUMNS and normalized not in canonical_columns:
                canonical_columns[normalized] = str(column)
                rename_map[str(column)] = normalized

        missing_columns = [column for column in REQUIRED_COLUMNS if column not in canonical_columns]
        if missing_columns:
            raise ImportValidationError(f"Missing required columns: {', '.join(missing_columns)}")

        normalized = frame.rename(columns=rename_map)[REQUIRED_COLUMNS].copy()
        normalized["instrument_code"] = normalized["instrument_code"].map(self._normalize_text)
        normalized["instrument_name"] = normalized["instrument_name"].map(self._normalize_nullable_text)

        if normalized["instrument_code"].isna().any():
            raise ImportValidationError("instrument_code contains empty values")

        parsed_dates = pd.to_datetime(normalized["trade_date"], errors="coerce")
        if parsed_dates.isna().any():
            raise ImportValidationError("trade_date contains invalid values")
        normalized["trade_date"] = parsed_dates.dt.date

        for column in NUMERIC_COLUMNS:
            parsed = pd.to_numeric(normalized[column], errors="coerce")
            if parsed.isna().any():
                raise ImportValidationError(f"{column} contains invalid numeric values")
            normalized[column] = parsed

        duplicate_mask = normalized.duplicated(subset=["instrument_code", "trade_date"], keep=False)
        if duplicate_mask.any():
            duplicates = normalized.loc[duplicate_mask, ["instrument_code", "trade_date"]].drop_duplicates()
            preview = ", ".join(
                f"{row.instrument_code}@{row.trade_date.isoformat()}" for row in duplicates.head(3).itertuples()
            )
            raise ImportValidationError(f"Duplicate instrument_code/trade_date rows found: {preview}")

        normalized = normalized.sort_values(["instrument_code", "trade_date"]).reset_index(drop=True)
        rows = [
            {
                "instrument_code": str(row["instrument_code"]),
                "instrument_name": row["instrument_name"],
                "trade_date": row["trade_date"],
                "open": self._to_decimal(row["open"]),
                "high": self._to_decimal(row["high"]),
                "low": self._to_decimal(row["low"]),
                "close": self._to_decimal(row["close"]),
                "volume": self._to_decimal(row["volume"]),
                "amount": self._to_decimal(row["amount"]),
            }
            for row in normalized.to_dict(orient="records")
        ]
        return NormalizedTradingDataset(rows=rows, columns=REQUIRED_COLUMNS, row_count=len(rows))

    def _bulk_insert_records(self, session: Session, *, run_id: int, rows: list[dict[str, Any]], chunk_size: int = 1000) -> None:
        for start in range(0, len(rows), chunk_size):
            chunk = rows[start : start + chunk_size]
            payload = [{"import_run_id": run_id, **row} for row in chunk]
            session.execute(insert(TradingRecord), payload)

    def _build_upload_path(self, owner_user_id: int, run_id: int, file_name: str) -> Path:
        return get_settings().upload_root / "trading" / str(owner_user_id) / str(run_id) / file_name

    def _sanitize_file_name(self, file_name: str) -> str:
        candidate = Path(file_name or "upload.csv").name
        sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", candidate).strip("._")
        return sanitized or "upload.csv"

    def _resolve_file_format(self, file_name: str) -> str:
        suffix = Path(file_name).suffix.lower()
        if suffix == ".csv":
            return "csv"
        if suffix == ".xlsx":
            return "xlsx"
        raise ImportValidationError("Only .csv and .xlsx files are supported")

    def _normalize_text(self, value: Any) -> str | None:
        if value is None or pd.isna(value):
            return None
        text = str(value).strip()
        return text or None

    def _normalize_nullable_text(self, value: Any) -> str | None:
        return self._normalize_text(value)

    def _to_decimal(self, value: Any) -> Decimal:
        return Decimal(str(value)).quantize(DECIMAL_QUANTUM)
