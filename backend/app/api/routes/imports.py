from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.models import User
from app.repositories.imports import ImportRunRepository
from app.schemas.trading import DeleteImportRunResponse, ImportRunRead, ImportStatsRead
from app.services.algo_indexes import algo_index_manager
from app.services.audit_logs import audit_log_service
from app.services.imports import ImportConflictError, ImportExecutionError, ImportService, ImportValidationError


router = APIRouter()
service = ImportService()


def _resolve_owner_scope(current_user: User, owner_user_id: int | None) -> int | None:
    if current_user.role == "admin":
        return owner_user_id
    return current_user.id


def _get_visible_run_or_404(session: Session, *, run_id: int, current_user: User):
    owner_scope = None if current_user.role == "admin" else current_user.id
    run = ImportRunRepository.get_visible_run(session, run_id=run_id, owner_user_id=owner_scope)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import run not found")
    return run


@router.get("/runs", response_model=list[ImportRunRead])
def list_import_runs(
    limit: int = 20,
    owner_user_id: int | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> list[ImportRunRead]:
    return service.list_runs(
        session,
        owner_user_id=_resolve_owner_scope(current_user, owner_user_id),
        limit=limit,
    )


@router.get("/stats", response_model=ImportStatsRead)
def get_import_stats(
    owner_user_id: int | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> ImportStatsRead:
    return service.build_stats(session, owner_user_id=_resolve_owner_scope(current_user, owner_user_id))


@router.post("/trading", response_model=ImportRunRead)
async def import_trading_file(
    request: Request,
    dataset_name: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> ImportRunRead:
    if not file.filename:
        audit_log_service.record_event(
            category="data_ops",
            event_type="import_run.create",
            success=False,
            status_code=status.HTTP_400_BAD_REQUEST,
            actor_user_id=current_user.id,
            actor_username_snapshot=current_user.username,
            actor_role=current_user.role,
            target_type="import_run",
            target_label=dataset_name,
            request_path="/api/imports/trading",
            http_method="POST",
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
            detail_json={"reason": "Uploaded file name is required"},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file name is required")

    file_bytes = await file.read()
    if not file_bytes:
        audit_log_service.record_event(
            category="data_ops",
            event_type="import_run.create",
            success=False,
            status_code=status.HTTP_400_BAD_REQUEST,
            actor_user_id=current_user.id,
            actor_username_snapshot=current_user.username,
            actor_role=current_user.role,
            target_type="import_run",
            target_label=dataset_name,
            request_path="/api/imports/trading",
            http_method="POST",
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
            detail_json={"reason": "Uploaded file is empty"},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    try:
        run = service.import_uploaded_file(
            session,
            owner=current_user,
            dataset_name=dataset_name,
            original_file_name=file.filename,
            file_bytes=file_bytes,
        )
    except ImportConflictError as exc:
        audit_log_service.record_event(
            category="data_ops",
            event_type="import_run.create",
            success=False,
            status_code=status.HTTP_409_CONFLICT,
            actor_user_id=current_user.id,
            actor_username_snapshot=current_user.username,
            actor_role=current_user.role,
            target_type="import_run",
            target_label=dataset_name,
            request_path="/api/imports/trading",
            http_method="POST",
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
            detail_json={"reason": str(exc)},
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ImportValidationError as exc:
        audit_log_service.record_event(
            category="data_ops",
            event_type="import_run.create",
            success=False,
            status_code=status.HTTP_400_BAD_REQUEST,
            actor_user_id=current_user.id,
            actor_username_snapshot=current_user.username,
            actor_role=current_user.role,
            target_type="import_run",
            target_label=dataset_name,
            request_path="/api/imports/trading",
            http_method="POST",
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
            detail_json={"reason": str(exc)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ImportExecutionError as exc:
        failure_reason = str(exc.__cause__) if isinstance(exc.__cause__, ImportValidationError) else str(exc)
        failure_code = status.HTTP_400_BAD_REQUEST if isinstance(exc.__cause__, ImportValidationError) else status.HTTP_500_INTERNAL_SERVER_ERROR
        audit_log_service.record_event(
            category="data_ops",
            event_type="import_run.create",
            success=False,
            status_code=failure_code,
            actor_user_id=current_user.id,
            actor_username_snapshot=current_user.username,
            actor_role=current_user.role,
            target_type="import_run",
            target_label=dataset_name,
            request_path="/api/imports/trading",
            http_method="POST",
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
            detail_json={"reason": failure_reason},
        )
        if isinstance(exc.__cause__, ImportValidationError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc.__cause__)) from exc
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    algo_index_manager.prepare_after_import(int(run.id))
    try:
        algo_index_manager.enqueue_build(int(run.id))
    except Exception:
        pass

    serialized = service.serialize_run(
        session,
        run,
        owner_user_id=_resolve_owner_scope(current_user, None),
    )
    audit_log_service.record_event(
        category="data_ops",
        event_type="import_run.create",
        success=True,
        status_code=status.HTTP_200_OK,
        actor_user_id=current_user.id,
        actor_username_snapshot=current_user.username,
        actor_role=current_user.role,
        target_type="import_run",
        target_label=serialized.dataset_name,
        import_run_id=serialized.id,
        request_path="/api/imports/trading",
        http_method="POST",
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
        detail_json={"record_count": serialized.record_count},
    )
    return serialized


@router.delete("/runs/{run_id}", response_model=DeleteImportRunResponse)
def delete_import_run(
    run_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> DeleteImportRunResponse:
    try:
        run = _get_visible_run_or_404(session, run_id=run_id, current_user=current_user)
    except HTTPException:
        audit_log_service.record_event(
            category="data_ops",
            event_type="import_run.delete",
            success=False,
            status_code=status.HTTP_404_NOT_FOUND,
            actor_user_id=current_user.id,
            actor_username_snapshot=current_user.username,
            actor_role=current_user.role,
            target_type="import_run",
            target_label=str(run_id),
            import_run_id=run_id,
            request_path=f"/api/imports/runs/{run_id}",
            http_method="DELETE",
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
            detail_json={"reason": "Import run not found"},
        )
        raise
    service.delete_run(session, run=run)
    algo_index_manager.invalidate(run_id)
    audit_log_service.record_event(
        category="data_ops",
        event_type="import_run.delete",
        success=True,
        status_code=status.HTTP_200_OK,
        actor_user_id=current_user.id,
        actor_username_snapshot=current_user.username,
        actor_role=current_user.role,
        target_type="import_run",
        target_label=run.dataset_name,
        import_run_id=run_id,
        request_path=f"/api/imports/runs/{run_id}",
        http_method="DELETE",
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )
    return DeleteImportRunResponse(id=run_id, status="deleted")
