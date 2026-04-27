from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any
from uuid import uuid4

import pandas as pd
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ImportPreviewSession, ImportRun, TradingRecord, User, utc_now
from app.repositories.imports import (
    ImportMappingTemplateRepository,
    ImportPreviewSessionRepository,
    ImportRunRepository,
)
from app.repositories.users import UserRepository
from app.schemas.trading import (
    ImportCommitRequest,
    ImportFieldSuggestionRead,
    ImportMappingCandidateRead,
    ImportMappingConflictRead,
    ImportMonthlyStatRead,
    ImportOwnerSummaryRead,
    ImportPreviewRead,
    ImportRunRead,
    ImportStatsRead,
)
from app.services.import_matcher import ColumnMatcher, normalize_header_token, normalize_stock_code_value


class ImportExecutionError(RuntimeError):
    def __init__(self, run_id: int, message: str):
        self.run_id = run_id
        super().__init__(message)


class ImportValidationError(ValueError):
    """Raised when an uploaded trading file cannot be parsed or validated."""


class ImportConflictError(ValueError):
    """Raised when an uploaded dataset conflicts with an existing active dataset."""


class ImportPreviewNotFoundError(ValueError):
    """Raised when preview id does not exist or is not visible to current user."""


class ImportPreviewExpiredError(ValueError):
    """Raised when preview session is expired."""


class ImportPreviewStateError(ValueError):
    """Raised when preview session status does not allow commit."""


HEAD_FILE_PATH = Path(__file__).with_name("trading_head.json")
NUMERIC_REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")
NUMERIC_OPTIONAL_COLUMNS = (
    "amount",
    "turnover",
    "benchmark_close",
    "pe_ttm",
    "pb",
    "roe",
    "asset_liability_ratio",
    "revenue_yoy",
    "net_profit_yoy",
)
DECIMAL_QUANTUM_4 = Decimal("0.0001")
DECIMAL_QUANTUM_6 = Decimal("0.000001")
IMPORT_FORMAT_ERROR_PREFIX = "导入失败，数据不符合格式"
VISIBLE_HISTORY_STATUSES = ("completed",)
PREVIEW_TTL_HOURS = 2
MANUAL_PREVIEW_HINT = "检测到必要列映射需人工确认，请先完成文件预览并确认列头映射。"
MIGRATION_HINT = "系统数据结构尚未就绪，请联系管理员完成升级后重试。"


@dataclass(frozen=True, slots=True)
class TradingHeadDictionary:
    version: str
    required_columns: tuple[str, ...]
    optional_columns: tuple[str, ...]
    canonical_columns: tuple[str, ...]
    alias_tiers_by_column: dict[str, dict[str, tuple[str, ...]]]


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
    alias_tiers_by_column: dict[str, dict[str, tuple[str, ...]]] = {}
    for canonical_name in canonical_columns:
        column_definition = columns.get(canonical_name)
        if not isinstance(column_definition, dict):
            raise RuntimeError(f"Trading head dictionary is missing definition for {canonical_name}")
        alias_tiers_by_column[canonical_name] = _parse_alias_tiers(
            canonical_name=canonical_name,
            aliases_payload=column_definition.get("aliases", []),
        )

    return TradingHeadDictionary(
        version=str(raw["version"]),
        required_columns=required_columns,
        optional_columns=optional_columns,
        canonical_columns=canonical_columns,
        alias_tiers_by_column=alias_tiers_by_column,
    )


def _parse_alias_tiers(*, canonical_name: str, aliases_payload: Any) -> dict[str, tuple[str, ...]]:
    strong: tuple[str, ...] = ()
    medium: tuple[str, ...] = ()
    weak: tuple[str, ...] = ()
    if isinstance(aliases_payload, dict):
        strong = tuple(str(item) for item in aliases_payload.get("strong", []))
        medium = tuple(str(item) for item in aliases_payload.get("medium", []))
        weak = tuple(str(item) for item in aliases_payload.get("weak", []))
    elif isinstance(aliases_payload, list):
        strong = tuple(str(item) for item in aliases_payload)
    if canonical_name not in strong:
        strong = (canonical_name, *strong)
    return {"strong": strong, "medium": medium, "weak": weak}


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
        preview = self.preview_uploaded_file(
            session,
            owner=owner,
            dataset_name=dataset_name,
            original_file_name=original_file_name,
            file_bytes=file_bytes,
        )
        if not preview.can_auto_commit:
            raise ImportValidationError(f"{MANUAL_PREVIEW_HINT}（预览编号：{preview.preview_id}）")
        return self.commit_preview(
            session,
            owner=owner,
            payload=ImportCommitRequest(preview_id=preview.preview_id, mapping_overrides={}),
        )

    def preview_uploaded_file(
        self,
        session: Session,
        *,
        owner: User,
        dataset_name: str,
        original_file_name: str,
        file_bytes: bytes,
    ) -> ImportPreviewRead:
        self._cleanup_expired_preview_sessions(session)
        cleaned_dataset_name = dataset_name.strip()
        if not cleaned_dataset_name:
            raise ImportValidationError("Dataset name is required")
        self._assert_dataset_name_available(session, owner_user_id=owner.id, dataset_name=cleaned_dataset_name)

        safe_file_name = self._sanitize_file_name(original_file_name)
        file_format = self._resolve_file_format(safe_file_name)
        preview_id = str(uuid4())
        staged_path = self._build_preview_upload_path(owner.id, preview_id, safe_file_name)
        staged_path.parent.mkdir(parents=True, exist_ok=True)
        staged_path.write_bytes(file_bytes)
        try:
            frame = self._read_uploaded_frame(staged_path, file_format)
            if frame.empty:
                raise ImportValidationError("Uploaded file does not contain any rows")
            head_dictionary = load_trading_head_dictionary()
            original_columns = [str(column) for column in frame.columns]
            header_fingerprint = self._build_header_fingerprint(original_columns)
            template_mapping = self._load_template_mapping(
                session,
                owner_user_id=owner.id,
                header_fingerprint=header_fingerprint,
            )
            matcher = ColumnMatcher(
                required_columns=head_dictionary.required_columns,
                optional_columns=head_dictionary.optional_columns,
                alias_tiers_by_column=head_dictionary.alias_tiers_by_column,
                template_mapping=template_mapping,
            )
            sample_values = {str(column): frame[column].head(300).tolist() for column in frame.columns}
            match_result = matcher.match(original_columns=original_columns, sample_values=sample_values)
            expires_at = utc_now() + timedelta(hours=PREVIEW_TTL_HOURS)
            preview = self._build_preview_read(
                preview_id=preview_id,
                expires_at=expires_at,
                head_dictionary=head_dictionary,
                match_result=match_result,
                original_columns=original_columns,
            )
            ImportPreviewSessionRepository.create(
                session,
                preview_id=preview_id,
                owner_user_id=owner.id,
                dataset_name=cleaned_dataset_name,
                original_file_name=safe_file_name,
                file_format=file_format,
                staged_file_path=str(staged_path),
                header_fingerprint=header_fingerprint,
                preview_payload_json=preview.model_dump(mode="json"),
                expires_at=expires_at,
            )
            return preview
        except Exception:
            self._remove_path_best_effort(staged_path.parent)
            raise

    def commit_preview(
        self,
        session: Session,
        *,
        owner: User,
        payload: ImportCommitRequest,
    ) -> ImportRun:
        preview_row = self._load_preview_for_commit(session, owner_user_id=owner.id, preview_id=payload.preview_id)
        preview_payload = preview_row.preview_payload_json if isinstance(preview_row.preview_payload_json, dict) else {}
        required_confirmation_needed = bool(preview_payload.get("required_confirmation_needed"))
        if required_confirmation_needed and not payload.required_confirmation_ack:
            raise ImportValidationError("必要列存在置信问题，请先在映射弹窗确认必要列后再导入。")
        required_issue_columns = [
            str(column)
            for column in (preview_payload.get("required_issue_columns") or [])
            if str(column)
        ]
        if required_confirmation_needed:
            self._assert_required_issue_columns_confirmed(
                required_issue_columns=required_issue_columns,
                mapping_overrides=payload.mapping_overrides,
            )
        suggested_mapping = {
            str(canonical): str(original)
            for canonical, original in (preview_payload.get("suggested_mapping") or {}).items()
            if canonical and original
        }
        head_dictionary = load_trading_head_dictionary()
        staged_path = Path(preview_row.staged_file_path)
        if not staged_path.exists():
            raise ImportValidationError("预览文件不存在或已失效，请重新上传文件并执行预览。")
        frame = self._read_uploaded_frame(staged_path, preview_row.file_format)
        if frame.empty:
            raise ImportValidationError("Uploaded file does not contain any rows")
        original_columns = [str(column) for column in frame.columns]
        canonical_to_original = self._merge_mapping_overrides(
            base_mapping=suggested_mapping,
            mapping_overrides=payload.mapping_overrides,
            head_dictionary=head_dictionary,
            original_columns=original_columns,
        )
        dataset = self._normalize_dataset_from_frame(
            frame,
            head_dictionary=head_dictionary,
            canonical_to_original=canonical_to_original,
        )
        self._assert_dataset_name_available(
            session,
            owner_user_id=owner.id,
            dataset_name=preview_row.dataset_name,
        )
        run = self._persist_completed_run(
            session,
            owner=owner,
            dataset_name=preview_row.dataset_name,
            safe_file_name=preview_row.original_file_name,
            file_format=preview_row.file_format,
            staged_path=staged_path,
            dataset=dataset,
            head_dictionary=head_dictionary,
            preview_id=preview_row.id,
        )
        try:
            # Persist only committed mappings:
            # required mappings are always persisted;
            # optional mappings are persisted only when explicitly sent in mapping_overrides.
            ImportMappingTemplateRepository.upsert(
                session,
                owner_user_id=owner.id,
                header_fingerprint=preview_row.header_fingerprint,
                mapping_json=canonical_to_original,
            )
        except Exception:
            session.rollback()
        try:
            ImportPreviewSessionRepository.mark_committed(session, preview_row, run_id=run.id)
        except Exception:
            session.rollback()
        self._remove_path_best_effort(staged_path.parent)
        return run

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

    def _persist_completed_run(
        self,
        session: Session,
        *,
        owner: User,
        dataset_name: str,
        safe_file_name: str,
        file_format: str,
        staged_path: Path,
        dataset: NormalizedTradingDataset,
        head_dictionary: TradingHeadDictionary,
        preview_id: str | None,
    ) -> ImportRun:
        try:
            run = ImportRunRepository.create_run(
                session,
                owner_user_id=owner.id,
                dataset_name=dataset_name,
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
                    "preview_id": preview_id,
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
            upload_path.write_bytes(staged_path.read_bytes())
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
                    "preview_id": preview_id,
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

    def _build_preview_read(
        self,
        *,
        preview_id: str,
        expires_at,
        head_dictionary: TradingHeadDictionary,
        match_result,
        original_columns: list[str],
    ) -> ImportPreviewRead:
        required_issue_columns = self._resolve_required_issue_columns(
            required_columns=head_dictionary.required_columns,
            field_suggestions=match_result.field_suggestions,
            missing_required=set(match_result.missing_required),
            conflicts=match_result.conflicts,
        )
        return ImportPreviewRead(
            preview_id=preview_id,
            expires_at=expires_at,
            can_auto_commit=match_result.can_auto_commit,
            required_confirmation_needed=bool(required_issue_columns),
            required_issue_columns=required_issue_columns,
            matcher_engine=match_result.matcher_engine,
            required_columns=list(head_dictionary.required_columns),
            optional_columns=list(head_dictionary.optional_columns),
            original_columns=original_columns,
            ignored_columns=list(match_result.ignored_columns),
            suggested_mapping=match_result.suggested_mapping,
            missing_required=list(match_result.missing_required),
            conflicts=[
                ImportMappingConflictRead(
                    canonical_column=item.canonical_column,
                    primary_original_column=item.primary_original_column,
                    secondary_original_column=item.secondary_original_column,
                    gap=item.gap,
                    message=item.message,
                )
                for item in match_result.conflicts
            ],
            field_suggestions=[
                ImportFieldSuggestionRead(
                    canonical_column=field.canonical_column,
                    required=field.required,
                    selected_original_column=field.selected_original_column,
                    selected_score=field.selected_score,
                    selected_confidence=field.selected_confidence,
                    candidates=[
                        ImportMappingCandidateRead(
                            original_column=candidate.original_column,
                            header_score=candidate.header_score,
                            value_score=candidate.value_score,
                            template_bonus=candidate.template_bonus,
                            total_score=candidate.total_score,
                            confidence=candidate.confidence,
                            reasons=list(candidate.reasons),
                        )
                        for candidate in field.candidates
                    ],
                )
                for field in match_result.field_suggestions
            ],
            action_hints=list(match_result.action_hints),
        )

    def _resolve_required_issue_columns(
        self,
        *,
        required_columns: tuple[str, ...],
        field_suggestions,
        missing_required: set[str],
        conflicts,
    ) -> list[str]:
        required_set = set(required_columns)
        conflict_columns = {
            item.canonical_column
            for item in conflicts
            if item.canonical_column in required_set
        }
        low_confidence_columns = {
            field.canonical_column
            for field in field_suggestions
            if field.required and field.selected_confidence != "high"
        }
        issue_set = required_set.intersection(missing_required.union(conflict_columns).union(low_confidence_columns))
        return [column for column in required_columns if column in issue_set]

    def _load_template_mapping(
        self,
        session: Session,
        *,
        owner_user_id: int,
        header_fingerprint: str,
    ) -> dict[str, str]:
        try:
            template = ImportMappingTemplateRepository.get_for_owner_and_fingerprint(
                session,
                owner_user_id=owner_user_id,
                header_fingerprint=header_fingerprint,
            )
        except ProgrammingError as exc:
            self._raise_migration_error_if_needed(session, exc)
            raise
        if template is None or not isinstance(template.mapping_json, dict):
            return {}
        return {
            str(canonical): str(original)
            for canonical, original in template.mapping_json.items()
            if canonical and original
        }

    def _load_preview_for_commit(self, session: Session, *, owner_user_id: int, preview_id: str) -> ImportPreviewSession:
        try:
            row = ImportPreviewSessionRepository.get_by_id(session, preview_id)
        except ProgrammingError as exc:
            self._raise_migration_error_if_needed(session, exc)
            raise
        if row is None or row.owner_user_id != owner_user_id:
            raise ImportPreviewNotFoundError("预览会话不存在或无权限访问。")
        if row.status == "committed":
            raise ImportPreviewStateError("该预览会话已提交，不能重复提交。")
        if row.status != "pending":
            raise ImportPreviewStateError(f"预览会话状态不允许提交：{row.status}")
        if self._is_preview_expired(row.expires_at):
            self._remove_path_best_effort(Path(row.staged_file_path).parent)
            ImportPreviewSessionRepository.delete_many(session, [row.id])
            raise ImportPreviewExpiredError("预览会话已过期，请重新上传文件并执行预览。")
        return row

    def _cleanup_expired_preview_sessions(self, session: Session) -> None:
        try:
            expired = ImportPreviewSessionRepository.list_expired_pending(session, now=utc_now(), limit=100)
        except ProgrammingError as exc:
            self._raise_migration_error_if_needed(session, exc)
            raise
        if not expired:
            return
        ImportPreviewSessionRepository.delete_many(session, [item.id for item in expired])
        for item in expired:
            self._remove_path_best_effort(Path(item.staged_file_path).parent)

    def _read_uploaded_frame(self, path: Path, file_format: str) -> pd.DataFrame:
        if file_format == "csv":
            return pd.read_csv(path, dtype=object)
        return pd.read_excel(path, engine="openpyxl", dtype=object)

    def _normalize_dataset_from_frame(
        self,
        frame: pd.DataFrame,
        *,
        head_dictionary: TradingHeadDictionary,
        canonical_to_original: dict[str, str],
    ) -> NormalizedTradingDataset:
        missing_columns = [column for column in head_dictionary.required_columns if column not in canonical_to_original]
        if missing_columns:
            raise ImportValidationError(build_import_format_error(f"缺少必要列：{', '.join(missing_columns)}"))

        selected_columns = [column for column in head_dictionary.canonical_columns if column in canonical_to_original]
        normalized = pd.DataFrame(index=frame.index)
        for canonical in selected_columns:
            normalized[canonical] = frame[canonical_to_original[canonical]]

        normalized["stock_code"] = normalized["stock_code"].map(normalize_stock_code_value)
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
        for optional_numeric_column in NUMERIC_OPTIONAL_COLUMNS:
            self._normalize_optional_numeric_column(normalized, optional_numeric_column)
        self._normalize_optional_datetime_column(normalized, "valuation_as_of")
        self._normalize_optional_date_column(normalized, "fundamental_report_date")
        for optional_column in head_dictionary.optional_columns:
            if optional_column not in normalized.columns:
                normalized[optional_column] = None

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
                "open": self._to_decimal(row["open"], quantum=DECIMAL_QUANTUM_4),
                "high": self._to_decimal(row["high"], quantum=DECIMAL_QUANTUM_4),
                "low": self._to_decimal(row["low"], quantum=DECIMAL_QUANTUM_4),
                "close": self._to_decimal(row["close"], quantum=DECIMAL_QUANTUM_4),
                "volume": self._to_decimal(row["volume"], quantum=DECIMAL_QUANTUM_4),
                "amount": self._to_optional_decimal(row["amount"], quantum=DECIMAL_QUANTUM_4),
                "turnover": self._to_optional_decimal(row["turnover"], quantum=DECIMAL_QUANTUM_6),
                "benchmark_close": self._to_optional_decimal(row["benchmark_close"], quantum=DECIMAL_QUANTUM_4),
                "pe_ttm": self._to_optional_decimal(row["pe_ttm"], quantum=DECIMAL_QUANTUM_6),
                "pb": self._to_optional_decimal(row["pb"], quantum=DECIMAL_QUANTUM_6),
                "roe": self._to_optional_decimal(row["roe"], quantum=DECIMAL_QUANTUM_6),
                "asset_liability_ratio": self._to_optional_decimal(row["asset_liability_ratio"], quantum=DECIMAL_QUANTUM_6),
                "revenue_yoy": self._to_optional_decimal(row["revenue_yoy"], quantum=DECIMAL_QUANTUM_6),
                "net_profit_yoy": self._to_optional_decimal(row["net_profit_yoy"], quantum=DECIMAL_QUANTUM_6),
                "valuation_as_of": self._to_optional_datetime(row["valuation_as_of"]),
                "fundamental_report_date": self._to_optional_date(row["fundamental_report_date"]),
            }
            for row in normalized.to_dict(orient="records")
        ]
        column_mapping: dict[str, str] = {}
        for canonical, original in canonical_to_original.items():
            if original in column_mapping:
                column_mapping[original] = f"{column_mapping[original]},{canonical}"
            else:
                column_mapping[original] = canonical
        ignored_columns = [str(column) for column in frame.columns if str(column) not in column_mapping]
        matched_columns = [column for column in head_dictionary.canonical_columns if column in canonical_to_original]
        return NormalizedTradingDataset(
            rows=rows,
            columns=matched_columns,
            row_count=len(rows),
            original_columns=[str(column) for column in frame.columns],
            ignored_columns=ignored_columns,
            column_mapping=column_mapping,
        )

    def _merge_mapping_overrides(
        self,
        *,
        base_mapping: dict[str, str],
        mapping_overrides: dict[str, str | None],
        head_dictionary: TradingHeadDictionary,
        original_columns: list[str],
    ) -> dict[str, str]:
        resolved_required = {
            canonical: original
            for canonical, original in base_mapping.items()
            if canonical in head_dictionary.required_columns and original in original_columns
        }
        resolved = dict(resolved_required)
        for canonical, original in mapping_overrides.items():
            if canonical not in head_dictionary.canonical_columns:
                raise ImportValidationError(f"未知映射目标列：{canonical}")
            if original is None:
                resolved.pop(canonical, None)
                continue
            if original not in original_columns:
                raise ImportValidationError(f"映射源列不存在：{original}")
            resolved[canonical] = original

        duplicates = [
            value
            for value, count in self._count_values(list(resolved.values())).items()
            if count > 1 and not self._is_allowed_reused_source(value, resolved)
        ]
        if duplicates:
            raise ImportValidationError(build_import_format_error(f"映射冲突：同一源列被重复使用（{', '.join(duplicates)}）"))
        missing_required = [item for item in head_dictionary.required_columns if item not in resolved]
        if missing_required:
            raise ImportValidationError(build_import_format_error(f"缺少必要列：{', '.join(missing_required)}"))
        return resolved

    def _count_values(self, values: list[str]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for value in values:
            counts[value] = counts.get(value, 0) + 1
        return counts

    def _is_allowed_reused_source(self, source_column: str, resolved_mapping: dict[str, str]) -> bool:
        return (
            source_column == resolved_mapping.get("trade_date")
            and source_column == resolved_mapping.get("valuation_as_of")
        )

    def _assert_required_issue_columns_confirmed(
        self,
        *,
        required_issue_columns: list[str],
        mapping_overrides: dict[str, str | None],
    ) -> None:
        unresolved_columns = [
            canonical
            for canonical in required_issue_columns
            if canonical not in mapping_overrides or mapping_overrides.get(canonical) is None
        ]
        if unresolved_columns:
            raise ImportValidationError(
                f"必要列存在冲突或低置信问题，请先手动确认以下必要列映射并开启导入：{', '.join(unresolved_columns)}"
            )

    def _assert_dataset_name_available(self, session: Session, *, owner_user_id: int, dataset_name: str) -> None:
        duplicate_run = ImportRunRepository.get_active_upload_run_by_dataset_name(
            session,
            owner_user_id=owner_user_id,
            dataset_name=dataset_name,
        )
        if duplicate_run is not None:
            raise ImportConflictError("当前用户已存在同名数据集，不能重复导入")

    def _bulk_insert_records(self, session: Session, *, run_id: int, rows: list[dict[str, Any]], chunk_size: int = 1000) -> None:
        for start in range(0, len(rows), chunk_size):
            chunk = rows[start : start + chunk_size]
            payload = [{"import_run_id": run_id, **row} for row in chunk]
            session.execute(insert(TradingRecord), payload)

    def _build_upload_path(self, owner_user_id: int, run_id: int, file_name: str) -> Path:
        return get_settings().upload_root / "trading" / str(owner_user_id) / str(run_id) / file_name

    def _build_preview_upload_path(self, owner_user_id: int, preview_id: str, file_name: str) -> Path:
        return get_settings().upload_root / "preview" / str(owner_user_id) / preview_id / file_name

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

    def _normalize_optional_numeric_column(self, frame: pd.DataFrame, column: str) -> None:
        if column not in frame.columns:
            frame[column] = None
            return
        raw = frame[column].map(self._normalize_optional_cell)
        parsed = pd.to_numeric(raw, errors="coerce")
        invalid_mask = raw.notna() & parsed.isna()
        if invalid_mask.any():
            raise ImportValidationError(build_import_format_error(f"{column} 存在非法数值"))
        frame[column] = parsed

    def _normalize_optional_datetime_column(self, frame: pd.DataFrame, column: str) -> None:
        if column not in frame.columns:
            frame[column] = None
            return
        raw = frame[column].map(self._normalize_optional_cell)
        parsed = pd.to_datetime(raw, errors="coerce")
        invalid_mask = raw.notna() & parsed.isna()
        if invalid_mask.any():
            raise ImportValidationError(build_import_format_error(f"{column} 存在无法识别的日期时间"))
        frame[column] = parsed

    def _normalize_optional_date_column(self, frame: pd.DataFrame, column: str) -> None:
        if column not in frame.columns:
            frame[column] = None
            return
        raw = frame[column].map(self._normalize_optional_cell)
        parsed = pd.to_datetime(raw, errors="coerce")
        invalid_mask = raw.notna() & parsed.isna()
        if invalid_mask.any():
            raise ImportValidationError(build_import_format_error(f"{column} 存在无法识别的日期"))
        frame[column] = parsed.dt.date

    def _normalize_optional_cell(self, value: Any) -> Any:
        if value is None or pd.isna(value):
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    def _to_decimal(self, value: Any, *, quantum: Decimal = DECIMAL_QUANTUM_4) -> Decimal:
        return Decimal(str(value)).quantize(quantum)

    def _to_optional_decimal(self, value: Any, *, quantum: Decimal = DECIMAL_QUANTUM_4) -> Decimal | None:
        if value is None or pd.isna(value):
            return None
        return self._to_decimal(value, quantum=quantum)

    def _to_optional_datetime(self, value: Any) -> datetime | None:
        if value is None or pd.isna(value):
            return None
        if isinstance(value, pd.Timestamp):
            return value.to_pydatetime()
        if isinstance(value, datetime):
            return value
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        if isinstance(parsed, pd.Timestamp):
            return parsed.to_pydatetime()
        return None

    def _to_optional_date(self, value: Any) -> date | None:
        if value is None or pd.isna(value):
            return None
        if isinstance(value, pd.Timestamp):
            return value.date()
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        if isinstance(parsed, pd.Timestamp):
            return parsed.date()
        return None

    def _build_header_fingerprint(self, original_columns: list[str]) -> str:
        normalized = sorted(normalize_header_token(column) for column in original_columns if normalize_header_token(column))
        payload = "|".join(normalized)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _remove_path_best_effort(self, path: Path) -> None:
        try:
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass

    def _is_preview_expired(self, expires_at) -> bool:
        now = utc_now()
        if getattr(expires_at, "tzinfo", None) is None:
            return expires_at < now.replace(tzinfo=None)
        return expires_at < now

    def _raise_migration_error_if_needed(self, session: Session, error: ProgrammingError) -> None:
        session.rollback()
        message = str(error).lower()
        if "import_preview_sessions" in message or "import_mapping_templates" in message:
            raise ImportValidationError(MIGRATION_HINT) from error

    def _is_active_dataset_name_conflict(self, error: IntegrityError) -> bool:
        message = str(error.orig).lower() if error.orig is not None else str(error).lower()
        return "uq_import_runs_owner_dataset_name_active_upload" in message or (
            "import_runs" in message and "dataset_name" in message and "owner_user_id" in message
        )


