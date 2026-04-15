from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any
import unicodedata

import pandas as pd
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ImportRun, TradingRecord, User, utc_now
from app.repositories.imports import ImportRunRepository
from app.repositories.users import UserRepository
from app.schemas.trading import ImportMonthlyStatRead, ImportOwnerSummaryRead, ImportRunRead, ImportStatsRead


class ImportExecutionError(RuntimeError):
    def __init__(self, run_id: int, message: str):
        self.run_id = run_id
        super().__init__(message)


class ImportValidationError(ValueError):
    """Raised when an uploaded trading file cannot be parsed or validated."""


class ImportConflictError(ValueError):
    """Raised when an uploaded dataset conflicts with an existing active dataset."""


HEAD_FILE_PATH = Path(__file__).with_name("trading_head.json")
NUMERIC_REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")
DECIMAL_QUANTUM = Decimal("0.0001")
IMPORT_FORMAT_ERROR_PREFIX = "导入失败，数据不符合格式"
VISIBLE_HISTORY_STATUSES = ("completed",)


@dataclass(frozen=True, slots=True)
class TradingHeadDictionary:
    version: str
    required_columns: tuple[str, ...]
    optional_columns: tuple[str, ...]
    canonical_columns: tuple[str, ...]
    alias_to_column: dict[str, str]


@dataclass(slots=True)
class NormalizedTradingDataset:
    rows: list[dict[str, Any]]
    columns: list[str]
    row_count: int
    original_columns: list[str]
    ignored_columns: list[str]
    column_mapping: dict[str, str]


@lru_cache(maxsize=1)
def load_trading_head_dictionary() -> TradingHeadDictionary:
    raw = json.loads(HEAD_FILE_PATH.read_text(encoding="utf-8"))
    required_columns = tuple(str(item) for item in raw["required_columns"])
    optional_columns = tuple(str(item) for item in raw["optional_columns"])
    canonical_columns = required_columns + tuple(item for item in optional_columns if item not in required_columns)

    columns = raw["columns"]
    alias_to_column: dict[str, str] = {}
    for canonical_name in canonical_columns:
        column_definition = columns.get(canonical_name)
        if not isinstance(column_definition, dict):
            raise RuntimeError(f"Trading head dictionary is missing definition for {canonical_name}")

        aliases = [canonical_name, *[str(item) for item in column_definition.get("aliases", [])]]
        for alias in aliases:
            normalized_alias = normalize_header_token(alias)
            if not normalized_alias:
                continue
            existing = alias_to_column.get(normalized_alias)
            if existing and existing != canonical_name:
                raise RuntimeError(
                    f"Trading head dictionary alias collision: {alias!r} maps to both {existing} and {canonical_name}"
                )
            alias_to_column[normalized_alias] = canonical_name

    return TradingHeadDictionary(
        version=str(raw["version"]),
        required_columns=required_columns,
        optional_columns=optional_columns,
        canonical_columns=canonical_columns,
        alias_to_column=alias_to_column,
    )


def normalize_header_token(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return text.replace("\ufeff", "").strip()


def build_import_format_error(detail: str) -> str:
    return f"{IMPORT_FORMAT_ERROR_PREFIX}：{detail}"


class ImportService:
    def import_uploaded_file(
        self,
        session: Session,
        *,
        owner: User,
        dataset_name: str,
        original_file_name: str,
        file_bytes: bytes,
    ) -> ImportRun:
        cleaned_dataset_name = dataset_name.strip()
        if not cleaned_dataset_name:
            raise ImportValidationError("Dataset name is required")

        duplicate_run = ImportRunRepository.get_active_upload_run_by_dataset_name(
            session,
            owner_user_id=owner.id,
            dataset_name=cleaned_dataset_name,
        )
        if duplicate_run is not None:
            raise ImportConflictError("当前用户已存在同名数据集，不能重复导入")

        head_dictionary = load_trading_head_dictionary()
        safe_file_name = self._sanitize_file_name(original_file_name)
        file_format = self._resolve_file_format(safe_file_name)
        try:
            run = ImportRunRepository.create_run(
                session,
                owner_user_id=owner.id,
                dataset_name=cleaned_dataset_name,
                source_type="upload",
                source_name="user.upload",
                source_uri=None,
                original_file_name=safe_file_name,
                file_format=file_format,
                metadata_json={
                    "required_columns": list(head_dictionary.required_columns),
                    "optional_columns": list(head_dictionary.optional_columns),
                    "template_version": head_dictionary.version,
                    "head_file": HEAD_FILE_PATH.name,
                },
            )
        except IntegrityError as exc:
            session.rollback()
            if self._is_active_dataset_name_conflict(exc):
                raise ImportConflictError("当前用户已存在同名数据集，不能重复导入") from exc
            raise

        try:
            upload_path = self._build_upload_path(owner.id, run.id, safe_file_name)
            upload_path.parent.mkdir(parents=True, exist_ok=True)
            upload_path.write_bytes(file_bytes)

            dataset = self._load_and_normalize_dataset(upload_path, file_format)
            run.metadata_json = {
                **run.metadata_json,
                "original_columns": dataset.original_columns,
                "matched_columns": dataset.columns,
                "ignored_columns": dataset.ignored_columns,
                "column_mapping": dataset.column_mapping,
            }
            session.add(run)
            manifest_record = ImportRunRepository.add_manifest(
                session,
                import_run_id=run.id,
                manifest_path=str(upload_path),
                created_at=utc_now(),
                record_count=dataset.row_count,
                columns_json=dataset.columns,
                metadata_json={
                    "file_format": file_format,
                    "head_version": head_dictionary.version,
                    "original_columns": dataset.original_columns,
                    "matched_columns": dataset.columns,
                    "ignored_columns": dataset.ignored_columns,
                    "column_mapping": dataset.column_mapping,
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
        runs = ImportRunRepository.list_runs(
            session,
            owner_user_id=owner_user_id,
            statuses=VISIBLE_HISTORY_STATUSES,
            limit=limit,
        )
        display_id_map = self._build_display_id_map(
            ImportRunRepository.list_all_visible_runs(
                session,
                owner_user_id=owner_user_id,
                statuses=VISIBLE_HISTORY_STATUSES,
            )
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
            ImportRunRepository.list_all_visible_runs(
                session,
                owner_user_id=owner_user_id,
                statuses=VISIBLE_HISTORY_STATUSES,
            )
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
        completed_dataset_names: set[str] = set()

        for run in runs:
            month_key = run.started_at.strftime("%Y-%m")
            monthly_imports[month_key]["runs"] += 1
            monthly_imports[month_key]["records"] += run.record_count or 0

            if run.owner_user_id is not None:
                owner_summaries[run.owner_user_id]["runs"] += 1
                owner_summaries[run.owner_user_id]["records"] += run.record_count or 0

            total_records += run.record_count or 0
            if run.status == "completed":
                completed_runs += 1
                completed_dataset_names.add(run.dataset_name)
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
            available_datasets=len(completed_dataset_names),
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

        head_dictionary = load_trading_head_dictionary()
        original_columns = [str(column) for column in frame.columns]
        canonical_to_original, column_mapping, ignored_columns = self._resolve_column_mapping(
            original_columns,
            head_dictionary=head_dictionary,
        )

        missing_columns = [column for column in head_dictionary.required_columns if column not in canonical_to_original]
        if missing_columns:
            missing_preview = ", ".join(missing_columns)
            raise ImportValidationError(build_import_format_error(f"缺少必要列：{missing_preview}"))

        rename_map = {original: canonical for canonical, original in canonical_to_original.items()}
        selected_columns = [column for column in head_dictionary.canonical_columns if column in canonical_to_original]
        normalized = frame.rename(columns=rename_map)[selected_columns].copy()

        normalized["stock_code"] = normalized["stock_code"].map(self._normalize_text)
        if normalized["stock_code"].isna().any():
            raise ImportValidationError(build_import_format_error("stock_code 存在空值"))

        parsed_dates = pd.to_datetime(normalized["trade_date"], errors="coerce")
        if parsed_dates.isna().any():
            raise ImportValidationError(build_import_format_error("trade_date 存在无法识别的日期"))
        normalized["trade_date"] = parsed_dates.dt.date

        for column in NUMERIC_REQUIRED_COLUMNS:
            parsed = pd.to_numeric(normalized[column], errors="coerce")
            if parsed.isna().any():
                raise ImportValidationError(build_import_format_error(f"{column} 存在非法数值"))
            normalized[column] = parsed

        if "stock_name" in normalized.columns:
            normalized["stock_name"] = normalized["stock_name"].map(self._normalize_nullable_text)
        else:
            normalized["stock_name"] = None

        if "amount" in normalized.columns:
            parsed_amount = pd.to_numeric(normalized["amount"], errors="coerce")
            if parsed_amount.isna().any():
                raise ImportValidationError(build_import_format_error("amount 存在非法数值"))
            normalized["amount"] = parsed_amount
        else:
            normalized["amount"] = None

        # Accept turnover as a separate optional header without treating it as amount yet.
        if "turnover" in normalized.columns:
            parsed_turnover = pd.to_numeric(normalized["turnover"], errors="coerce")
            if parsed_turnover.isna().any():
                raise ImportValidationError(build_import_format_error("turnover 存在非法数值"))
            normalized["turnover"] = parsed_turnover
        else:
            normalized["turnover"] = None

        normalized = normalized[list(head_dictionary.canonical_columns)]

        duplicate_mask = normalized.duplicated(subset=["stock_code", "trade_date"], keep=False)
        if duplicate_mask.any():
            duplicates = normalized.loc[duplicate_mask, ["stock_code", "trade_date"]].drop_duplicates()
            preview = ", ".join(
                f"{row.stock_code}@{row.trade_date.isoformat()}" for row in duplicates.head(3).itertuples()
            )
            raise ImportValidationError(build_import_format_error(f"存在重复的 stock_code/trade_date：{preview}"))

        normalized = normalized.sort_values(["stock_code", "trade_date"]).reset_index(drop=True)
        rows = [
            {
                "stock_code": str(row["stock_code"]),
                "stock_name": row["stock_name"],
                "trade_date": row["trade_date"],
                "open": self._to_decimal(row["open"]),
                "high": self._to_decimal(row["high"]),
                "low": self._to_decimal(row["low"]),
                "close": self._to_decimal(row["close"]),
                "volume": self._to_decimal(row["volume"]),
                "amount": self._to_optional_decimal(row["amount"]),
            }
            for row in normalized.to_dict(orient="records")
        ]

        matched_columns = [column for column in head_dictionary.canonical_columns if column in canonical_to_original]
        return NormalizedTradingDataset(
            rows=rows,
            columns=matched_columns,
            row_count=len(rows),
            original_columns=original_columns,
            ignored_columns=ignored_columns,
            column_mapping=column_mapping,
        )

    def _resolve_column_mapping(
        self,
        original_columns: list[str],
        *,
        head_dictionary: TradingHeadDictionary,
    ) -> tuple[dict[str, str], dict[str, str], list[str]]:
        canonical_to_original: dict[str, str] = {}
        column_mapping: dict[str, str] = {}
        ignored_columns: list[str] = []

        for original_column in original_columns:
            canonical_name = head_dictionary.alias_to_column.get(normalize_header_token(original_column))
            if canonical_name is None:
                ignored_columns.append(original_column)
                continue

            if canonical_name in canonical_to_original:
                existing_column = canonical_to_original[canonical_name]
                raise ImportValidationError(
                    build_import_format_error(
                        f"列头 {existing_column} 与 {original_column} 同时匹配到 {canonical_name}"
                    )
                )

            canonical_to_original[canonical_name] = original_column
            column_mapping[original_column] = canonical_name

        return canonical_to_original, column_mapping, ignored_columns

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

    def _to_optional_decimal(self, value: Any) -> Decimal | None:
        if value is None or pd.isna(value):
            return None
        return self._to_decimal(value)

    def _is_active_dataset_name_conflict(self, error: IntegrityError) -> bool:
        message = str(error.orig).lower() if error.orig is not None else str(error).lower()
        return "uq_import_runs_owner_dataset_name_active_upload" in message or (
            "import_runs" in message and "dataset_name" in message and "owner_user_id" in message
        )


