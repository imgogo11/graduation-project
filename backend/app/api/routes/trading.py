from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.models import User
from app.repositories.imports import ImportRunRepository
from app.repositories.trading import TradingRepository
from app.schemas.trading import TradingStockRead, TradingRecordRead


router = APIRouter()
COMPLETED_RUN_STATUSES = ("completed",)


def _get_accessible_run(session: Session, *, run_id: int, current_user: User):
    owner_scope = None if current_user.role == "admin" else current_user.id
    run = ImportRunRepository.get_visible_run(
        session,
        run_id=run_id,
        owner_user_id=owner_scope,
        statuses=COMPLETED_RUN_STATUSES,
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import run not found")
    return run


@router.get("/stocks", response_model=list[TradingStockRead])
def list_trading_stocks(
    import_run_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> list[TradingStockRead]:
    _get_accessible_run(session, run_id=import_run_id, current_user=current_user)
    rows = TradingRepository.list_stocks(session, import_run_id=import_run_id)
    return [TradingStockRead.model_validate(row) for row in rows]


@router.get("/records", response_model=list[TradingRecordRead])
def list_trading_records(
    import_run_id: int,
    stock_code: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> list[TradingRecordRead]:
    _get_accessible_run(session, run_id=import_run_id, current_user=current_user)
    rows = TradingRepository.list_records(
        session,
        import_run_id=import_run_id,
        stock_code=stock_code,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    return [TradingRecordRead.model_validate(item) for item in rows]

