from __future__ import annotations

import re

from app.core.security import hash_password
from app.models import User
from app.repositories.users import UserRepository
from app.schemas.admin_users import AdminManagedUserRead


class AdminUserValidationError(ValueError):
    """Raised when admin-submitted user changes are invalid."""


class AdminUserConflictError(ValueError):
    """Raised when an admin update conflicts with an existing user."""


class AdminUserDeleteBlockedError(ValueError):
    """Raised when a user cannot be deleted because business data exists."""


class AdminUserService:
    USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]{3,32}$")

    def list_managed_users(
        self,
        session,
        *,
        query: str | None = None,
        user_id: int | None = None,
    ) -> list[AdminManagedUserRead]:
        users = UserRepository.list_users(
            session,
            query=(query or "").strip() or None,
            user_id=user_id,
        )
        owner_ids_with_data = UserRepository.list_owner_ids_with_import_runs(
            session,
            user_ids=[user.id for user in users],
        )
        return [
            AdminManagedUserRead(
                id=user.id,
                username=user.username,
                role=user.role,
                is_active=user.is_active,
                created_at=user.created_at,
                last_login_at=user.last_login_at,
                has_business_data=user.id in owner_ids_with_data,
            )
            for user in users
        ]

    def update_managed_user(
        self,
        session,
        *,
        actor_admin: User,
        target_user: User,
        username: str | None = None,
        password: str | None = None,
        is_active: bool | None = None,
    ) -> AdminManagedUserRead:
        self._ensure_editable_target(actor_admin=actor_admin, target_user=target_user)

        if username is not None:
            normalized_username = self._normalize_username(username)
            existing = UserRepository.get_by_username(session, normalized_username)
            if existing is not None and existing.id != target_user.id:
                raise AdminUserConflictError("用户名已存在")
            target_user.username = normalized_username

        if password is not None:
            self._validate_password(password)
            target_user.password_hash = hash_password(password)

        if is_active is not None:
            target_user.is_active = bool(is_active)

        saved = UserRepository.save_user(session, target_user)
        return self._serialize_user(session, saved)

    def set_managed_user_active(
        self,
        session,
        *,
        actor_admin: User,
        target_user: User,
        is_active: bool,
    ) -> AdminManagedUserRead:
        return self.update_managed_user(
            session,
            actor_admin=actor_admin,
            target_user=target_user,
            is_active=is_active,
        )

    def delete_managed_user(self, session, *, actor_admin: User, target_user: User) -> None:
        self._ensure_editable_target(actor_admin=actor_admin, target_user=target_user)
        if UserRepository.list_owner_ids_with_import_runs(session, user_ids=[target_user.id]):
            raise AdminUserDeleteBlockedError("该用户已有业务数据，不能删除，只能禁用")
        UserRepository.delete_user(session, target_user)

    def _serialize_user(self, session, user: User) -> AdminManagedUserRead:
        owner_ids_with_data = UserRepository.list_owner_ids_with_import_runs(session, user_ids=[user.id])
        return AdminManagedUserRead(
            id=user.id,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            has_business_data=user.id in owner_ids_with_data,
        )

    def _ensure_editable_target(self, *, actor_admin: User, target_user: User) -> None:
        if target_user.id == actor_admin.id:
            raise AdminUserValidationError("管理员不能编辑或删除自己的账号")
        if target_user.role != "user":
            raise AdminUserValidationError("只能管理普通用户账号")

    def _normalize_username(self, username: str) -> str:
        normalized = username.strip().lower()
        if not self.USERNAME_PATTERN.fullmatch(normalized):
            raise AdminUserValidationError("用户名必须是 3-32 位字母、数字或下划线")
        return normalized

    def _validate_password(self, password: str) -> None:
        if len(password) < 8:
            raise AdminUserValidationError("密码至少需要 8 位")
