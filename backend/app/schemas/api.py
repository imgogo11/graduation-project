# 作用:
# - 这是 API Schema 模块，用来定义健康检查、导入记录、股票查询和电商查询的请求/响应模型。
# 关联文件:
# - 被 backend/app/api/routes/health.py、imports.py、stocks.py、commerce.py 直接依赖。
# - 被 backend/tests/test_database_pipeline.py 间接用于导入接口调用。
#
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    environment: str
    database_ok: bool
    detail: str


class ImportRequest(BaseModel):
    manifest_path: str | None = Field(default=None, description="Optional manifest path override")


class ImportRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_name: str
    source_type: str
    source_name: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    record_count: int | None
    error_message: str | None


class StockDailyPriceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    trade_date: date
    open: Decimal
    close: Decimal
    high: Decimal
    low: Decimal
    volume: Decimal
    amount: Decimal | None
    amplitude: Decimal | None
    pct_change: Decimal | None
    change: Decimal | None
    turnover: Decimal | None
    adjust: str
    source_dataset: str


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: str
    seller_id: str | None
    product_name: str | None
    product_category_name: str | None
    product_category_name_english: str | None
    base_price: Decimal | None
    source_dataset: str


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: str
    customer_id: str | None
    order_status: str | None
    order_purchase_timestamp: datetime | None
    total_amount: Decimal | None
    source_dataset: str
