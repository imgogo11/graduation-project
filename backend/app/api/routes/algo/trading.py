from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.models import User
from app.repositories.imports import ImportRunRepository
from app.schemas.trading import TradingJointAnomalyRankingRead, TradingRangeKthVolumeRead, TradingRangeMaxAmountRead
from app.services.algo_trading import (
    PERSISTENT_SEGMENT_TREE_METHOD,
    TradingAlgoQueryNotFoundError,
    TradingAlgoQueryValidationError,
    TradingAlgoService,
)


router = APIRouter()
service = TradingAlgoService()


def _ensure_run_visible(session: Session, *, import_run_id: int, current_user: User) -> None:
    owner_scope = None if current_user.role == "admin" else current_user.id
    run = ImportRunRepository.get_visible_run(session, run_id=import_run_id, owner_user_id=owner_scope)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import run not found")


@router.get("/range-max-amount", response_model=TradingRangeMaxAmountRead)
def get_range_max_amount(
    import_run_id: int,
    instrument_code: str,
    start_date: date,
    end_date: date,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> TradingRangeMaxAmountRead:
    _ensure_run_visible(session, import_run_id=import_run_id, current_user=current_user)
    try:
        return service.query_range_max_amount(
            session,
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            start_date=start_date,
            end_date=end_date,
        )
    except TradingAlgoQueryValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TradingAlgoQueryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/joint-anomaly-ranking", response_model=TradingJointAnomalyRankingRead)
def get_joint_anomaly_ranking(
    import_run_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    top_n: int = 50,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> TradingJointAnomalyRankingRead:
    _ensure_run_visible(session, import_run_id=import_run_id, current_user=current_user)
    try:
        return service.query_joint_anomaly_ranking(
            session,
            import_run_id=import_run_id,
            start_date=start_date,
            end_date=end_date,
            top_n=top_n,
        )
    except TradingAlgoQueryValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TradingAlgoQueryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/range-kth-volume", response_model=TradingRangeKthVolumeRead)
def get_range_kth_volume(
    import_run_id: int,
    instrument_code: str,
    start_date: date,
    end_date: date,
    k: int,
    method: str = PERSISTENT_SEGMENT_TREE_METHOD,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> TradingRangeKthVolumeRead:
    _ensure_run_visible(session, import_run_id=import_run_id, current_user=current_user)
    try:
        return service.query_range_kth_volume(
            session,
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            start_date=start_date,
            end_date=end_date,
            k=k,
            method=method,
        )
    except TradingAlgoQueryValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TradingAlgoQueryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
