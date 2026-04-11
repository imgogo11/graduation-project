from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.models import User
from app.repositories.imports import ImportRunRepository
from app.schemas.trading import (
    TradingAnomalyReportRead,
    TradingCorrelationMatrixRead,
    TradingCrossSectionRead,
    TradingIndicatorSeriesRead,
    TradingQualityReportRead,
    TradingRiskMetricsRead,
    TradingRunComparisonRead,
    TradingScopeComparisonRead,
    TradingSummaryRead,
)
from app.services.trading_analysis import (
    TradingAnalysisDataUnavailableError,
    TradingAnalysisNotFoundError,
    TradingAnalysisService,
    TradingAnalysisValidationError,
)


router = APIRouter()
service = TradingAnalysisService()
COMPLETED_RUN_STATUSES = ("completed",)


def _ensure_run_visible(session: Session, *, import_run_id: int, current_user: User) -> None:
    owner_scope = None if current_user.role == "admin" else current_user.id
    run = ImportRunRepository.get_visible_run(
        session,
        run_id=import_run_id,
        owner_user_id=owner_scope,
        statuses=COMPLETED_RUN_STATUSES,
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import run not found")


def _handle_analysis_error(exc: Exception) -> HTTPException:
    if isinstance(exc, TradingAnalysisValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, TradingAnalysisDataUnavailableError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, TradingAnalysisNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    raise exc


@router.get("/summary", response_model=TradingSummaryRead)
def get_trading_summary(
    import_run_id: int,
    instrument_code: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> TradingSummaryRead:
    _ensure_run_visible(session, import_run_id=import_run_id, current_user=current_user)
    try:
        return service.build_summary(
            session,
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle_analysis_error(exc) from exc


@router.get("/quality", response_model=TradingQualityReportRead)
def get_trading_quality_report(
    import_run_id: int,
    instrument_code: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> TradingQualityReportRead:
    _ensure_run_visible(session, import_run_id=import_run_id, current_user=current_user)
    try:
        return service.build_quality_report(
            session,
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle_analysis_error(exc) from exc


@router.get("/indicators", response_model=TradingIndicatorSeriesRead)
def get_trading_indicators(
    import_run_id: int,
    instrument_code: str,
    start_date: date | None = None,
    end_date: date | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> TradingIndicatorSeriesRead:
    _ensure_run_visible(session, import_run_id=import_run_id, current_user=current_user)
    try:
        return service.build_indicator_series(
            session,
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle_analysis_error(exc) from exc


@router.get("/risk", response_model=TradingRiskMetricsRead)
def get_trading_risk_metrics(
    import_run_id: int,
    instrument_code: str,
    start_date: date | None = None,
    end_date: date | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> TradingRiskMetricsRead:
    _ensure_run_visible(session, import_run_id=import_run_id, current_user=current_user)
    try:
        return service.build_risk_metrics(
            session,
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle_analysis_error(exc) from exc


@router.get("/anomalies", response_model=TradingAnomalyReportRead)
def get_trading_anomalies(
    import_run_id: int,
    instrument_code: str,
    start_date: date | None = None,
    end_date: date | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> TradingAnomalyReportRead:
    _ensure_run_visible(session, import_run_id=import_run_id, current_user=current_user)
    try:
        return service.list_anomalies(
            session,
            import_run_id=import_run_id,
            instrument_code=instrument_code,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle_analysis_error(exc) from exc


@router.get("/cross-section", response_model=TradingCrossSectionRead)
def get_trading_cross_section(
    import_run_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    metric: str = "total_return",
    top_n: int | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> TradingCrossSectionRead:
    _ensure_run_visible(session, import_run_id=import_run_id, current_user=current_user)
    try:
        return service.build_cross_section(
            session,
            import_run_id=import_run_id,
            start_date=start_date,
            end_date=end_date,
            metric=metric,
            top_n=top_n,
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle_analysis_error(exc) from exc


@router.get("/correlation", response_model=TradingCorrelationMatrixRead)
def get_trading_correlation_matrix(
    import_run_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    instrument_codes: str | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> TradingCorrelationMatrixRead:
    _ensure_run_visible(session, import_run_id=import_run_id, current_user=current_user)
    selected_codes = [item.strip() for item in instrument_codes.split(",") if item.strip()] if instrument_codes else None
    try:
        return service.build_correlation_matrix(
            session,
            import_run_id=import_run_id,
            start_date=start_date,
            end_date=end_date,
            instrument_codes=selected_codes,
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle_analysis_error(exc) from exc


@router.get("/compare-runs", response_model=TradingRunComparisonRead)
def compare_trading_runs(
    base_run_id: int,
    target_run_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> TradingRunComparisonRead:
    _ensure_run_visible(session, import_run_id=base_run_id, current_user=current_user)
    _ensure_run_visible(session, import_run_id=target_run_id, current_user=current_user)
    try:
        return service.compare_runs(session, base_run_id=base_run_id, target_run_id=target_run_id)
    except Exception as exc:  # noqa: BLE001
        raise _handle_analysis_error(exc) from exc


@router.get("/compare-scopes", response_model=TradingScopeComparisonRead)
def compare_trading_scopes(
    base_run_id: int,
    target_run_id: int,
    base_instrument_code: str | None = None,
    target_instrument_code: str | None = None,
    base_start_date: date | None = None,
    base_end_date: date | None = None,
    target_start_date: date | None = None,
    target_end_date: date | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> TradingScopeComparisonRead:
    _ensure_run_visible(session, import_run_id=base_run_id, current_user=current_user)
    _ensure_run_visible(session, import_run_id=target_run_id, current_user=current_user)
    try:
        return service.compare_scopes(
            session,
            base_run_id=base_run_id,
            target_run_id=target_run_id,
            base_instrument_code=base_instrument_code,
            target_instrument_code=target_instrument_code,
            base_start_date=base_start_date,
            base_end_date=base_end_date,
            target_start_date=target_start_date,
            target_end_date=target_end_date,
        )
    except Exception as exc:  # noqa: BLE001
        raise _handle_analysis_error(exc) from exc
