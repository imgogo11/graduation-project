from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ImportRunRead(BaseModel):
    id: int
    owner_user_id: int | None
    owner_username: str | None
    dataset_name: str
    asset_class: str | None
    source_type: str
    source_name: str
    original_file_name: str | None
    file_format: str | None
    status: str
    started_at: datetime
    completed_at: datetime | None
    record_count: int | None
    error_message: str | None
    deleted_at: datetime | None


class ImportMonthlyStatRead(BaseModel):
    month: str
    runs: int
    records: int


class ImportOwnerSummaryRead(BaseModel):
    owner_user_id: int
    owner_username: str | None
    runs: int
    records: int


class ImportStatsRead(BaseModel):
    total_runs: int
    completed_runs: int
    failed_runs: int
    total_records: int
    active_datasets: int
    monthly_imports: list[ImportMonthlyStatRead]
    owner_summaries: list[ImportOwnerSummaryRead]


class DeleteImportRunResponse(BaseModel):
    id: int
    status: str


class TradingInstrumentRead(BaseModel):
    instrument_code: str
    instrument_name: str | None
    first_trade_date: date | None
    last_trade_date: date | None
    record_count: int


class TradingRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    import_run_id: int
    instrument_code: str
    instrument_name: str | None
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    amount: Decimal


class TradingRangeMaxMatchRead(BaseModel):
    trade_date: date
    series_index: int


class TradingRangeMaxAmountRead(BaseModel):
    import_run_id: int
    instrument_code: str
    start_date: date
    end_date: date
    max_amount: Decimal
    matches: list[TradingRangeMaxMatchRead]
