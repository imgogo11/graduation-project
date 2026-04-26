from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user
from app.core.database import get_db_session
from app.models import User
from app.repositories.users import UserRepository
from app.schemas.admin_users import (
    AdminManagedUserDeleteResponse,
    AdminManagedUserRead,
    AdminManagedUserUpdateRequest,
)
from app.services.admin_users import (
    AdminUserConflictError,
    AdminUserDeleteBlockedError,
    AdminUserService,
    AdminUserValidationError,
)
from app.services.audit_logs import audit_log_service


router = APIRouter()
service = AdminUserService()


def _get_target_user_or_404(session: Session, *, user_id: int) -> User:
    user = UserRepository.get_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("", response_model=list[AdminManagedUserRead])
def list_admin_users(
    query: str | None = None,
    user_id: int | None = None,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_db_session),
) -> list[AdminManagedUserRead]:
    return service.list_managed_users(session, query=query, user_id=user_id)


@router.patch("/{user_id}", response_model=AdminManagedUserRead)
def update_admin_user(
    user_id: int,
    payload: AdminManagedUserUpdateRequest,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_db_session),
) -> AdminManagedUserRead:
    target_user = _get_target_user_or_404(session, user_id=user_id)
    try:
        result = service.update_managed_user(
            session,
            actor_admin=current_admin,
            target_user=target_user,
            username=payload.username,
            password=payload.password,
            is_active=payload.is_active,
        )
    except AdminUserConflictError as exc:
        audit_log_service.record_event(
            category="admin_user",
            event_type="user.update",
            success=False,
            status_code=status.HTTP_409_CONFLICT,
            actor_user_id=current_admin.id,
            actor_username_snapshot=current_admin.username,
            actor_role=current_admin.role,
            target_type="user",
            target_label=str(user_id),
            request_path=f"/api/admin/users/{user_id}",
            http_method="PATCH",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            detail_json={"reason": str(exc)},
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AdminUserValidationError as exc:
        audit_log_service.record_event(
            category="admin_user",
            event_type="user.update",
            success=False,
            status_code=status.HTTP_400_BAD_REQUEST,
            actor_user_id=current_admin.id,
            actor_username_snapshot=current_admin.username,
            actor_role=current_admin.role,
            target_type="user",
            target_label=str(user_id),
            request_path=f"/api/admin/users/{user_id}",
            http_method="PATCH",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            detail_json={"reason": str(exc)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    audit_log_service.record_event(
        category="admin_user",
        event_type="user.update",
        success=True,
        status_code=status.HTTP_200_OK,
        actor_user_id=current_admin.id,
        actor_username_snapshot=current_admin.username,
        actor_role=current_admin.role,
        target_type="user",
        target_label=result.username,
        request_path=f"/api/admin/users/{user_id}",
        http_method="PATCH",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return result


@router.post("/{user_id}/disable", response_model=AdminManagedUserRead)
def disable_admin_user(
    user_id: int,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_db_session),
) -> AdminManagedUserRead:
    target_user = _get_target_user_or_404(session, user_id=user_id)
    try:
        result = service.set_managed_user_active(
            session,
            actor_admin=current_admin,
            target_user=target_user,
            is_active=False,
        )
    except AdminUserValidationError as exc:
        audit_log_service.record_event(
            category="admin_user",
            event_type="user.disable",
            success=False,
            status_code=status.HTTP_400_BAD_REQUEST,
            actor_user_id=current_admin.id,
            actor_username_snapshot=current_admin.username,
            actor_role=current_admin.role,
            target_type="user",
            target_label=str(user_id),
            request_path=f"/api/admin/users/{user_id}/disable",
            http_method="POST",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            detail_json={"reason": str(exc)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    audit_log_service.record_event(
        category="admin_user",
        event_type="user.disable",
        success=True,
        status_code=status.HTTP_200_OK,
        actor_user_id=current_admin.id,
        actor_username_snapshot=current_admin.username,
        actor_role=current_admin.role,
        target_type="user",
        target_label=result.username,
        request_path=f"/api/admin/users/{user_id}/disable",
        http_method="POST",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return result


@router.post("/{user_id}/enable", response_model=AdminManagedUserRead)
def enable_admin_user(
    user_id: int,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_db_session),
) -> AdminManagedUserRead:
    target_user = _get_target_user_or_404(session, user_id=user_id)
    try:
        result = service.set_managed_user_active(
            session,
            actor_admin=current_admin,
            target_user=target_user,
            is_active=True,
        )
    except AdminUserValidationError as exc:
        audit_log_service.record_event(
            category="admin_user",
            event_type="user.enable",
            success=False,
            status_code=status.HTTP_400_BAD_REQUEST,
            actor_user_id=current_admin.id,
            actor_username_snapshot=current_admin.username,
            actor_role=current_admin.role,
            target_type="user",
            target_label=str(user_id),
            request_path=f"/api/admin/users/{user_id}/enable",
            http_method="POST",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            detail_json={"reason": str(exc)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    audit_log_service.record_event(
        category="admin_user",
        event_type="user.enable",
        success=True,
        status_code=status.HTTP_200_OK,
        actor_user_id=current_admin.id,
        actor_username_snapshot=current_admin.username,
        actor_role=current_admin.role,
        target_type="user",
        target_label=result.username,
        request_path=f"/api/admin/users/{user_id}/enable",
        http_method="POST",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return result


@router.delete("/{user_id}", response_model=AdminManagedUserDeleteResponse)
def delete_admin_user(
    user_id: int,
    request: Request,
    current_admin: User = Depends(get_current_admin_user),
    session: Session = Depends(get_db_session),
) -> AdminManagedUserDeleteResponse:
    target_user = _get_target_user_or_404(session, user_id=user_id)
    try:
        service.delete_managed_user(session, actor_admin=current_admin, target_user=target_user)
    except AdminUserDeleteBlockedError as exc:
        audit_log_service.record_event(
            category="admin_user",
            event_type="user.delete",
            success=False,
            status_code=status.HTTP_409_CONFLICT,
            actor_user_id=current_admin.id,
            actor_username_snapshot=current_admin.username,
            actor_role=current_admin.role,
            target_type="user",
            target_label=str(user_id),
            request_path=f"/api/admin/users/{user_id}",
            http_method="DELETE",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            detail_json={"reason": str(exc)},
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AdminUserValidationError as exc:
        audit_log_service.record_event(
            category="admin_user",
            event_type="user.delete",
            success=False,
            status_code=status.HTTP_400_BAD_REQUEST,
            actor_user_id=current_admin.id,
            actor_username_snapshot=current_admin.username,
            actor_role=current_admin.role,
            target_type="user",
            target_label=str(user_id),
            request_path=f"/api/admin/users/{user_id}",
            http_method="DELETE",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            detail_json={"reason": str(exc)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    audit_log_service.record_event(
        category="admin_user",
        event_type="user.delete",
        success=True,
        status_code=status.HTTP_200_OK,
        actor_user_id=current_admin.id,
        actor_username_snapshot=current_admin.username,
        actor_role=current_admin.role,
        target_type="user",
        target_label=target_user.username,
        request_path=f"/api/admin/users/{user_id}",
        http_method="DELETE",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return AdminManagedUserDeleteResponse(id=user_id, status="deleted")
