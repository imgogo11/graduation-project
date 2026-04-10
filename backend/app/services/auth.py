from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.repositories.users import UserRepository
from app.schemas.auth import AuthTokenRead, UserRead


class AuthConflictError(ValueError):
    """Raised when a user already exists."""


class AuthInvalidCredentialsError(ValueError):
    """Raised when a login attempt fails."""


class AuthValidationError(ValueError):
    """Raised when submitted credentials are invalid."""


class AuthService:
    USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]{3,32}$")

    def register_user(self, session: Session, *, username: str, password: str) -> User:
        normalized_username = self._normalize_username(username)
        self._validate_password(password)
        existing = UserRepository.get_by_username(session, normalized_username)
        if existing is not None:
            raise AuthConflictError("Username already exists")
        return UserRepository.create_user(
            session,
            username=normalized_username,
            password_hash=hash_password(password),
            role="user",
        )

    def authenticate_user(self, session: Session, *, username: str, password: str) -> User:
        normalized_username = self._normalize_username(username)
        user = UserRepository.get_by_username(session, normalized_username)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthInvalidCredentialsError("Invalid username or password")
        if not user.is_active:
            raise AuthInvalidCredentialsError("User account is inactive")
        return UserRepository.update_last_login(session, user)

    def ensure_admin_user(self, session: Session, *, username: str, password: str) -> User:
        normalized_username = self._normalize_username(username)
        self._validate_password(password)
        existing = UserRepository.get_by_username(session, normalized_username)
        if existing is None:
            return UserRepository.create_user(
                session,
                username=normalized_username,
                password_hash=hash_password(password),
                role="admin",
                is_active=True,
            )

        existing.password_hash = hash_password(password)
        existing.role = "admin"
        existing.is_active = True
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    def build_token_response(self, user: User) -> AuthTokenRead:
        return AuthTokenRead(
            access_token=create_access_token(user_id=user.id, username=user.username, role=user.role),
            user=UserRead.model_validate(user),
        )

    def _normalize_username(self, username: str) -> str:
        normalized = username.strip().lower()
        if not self.USERNAME_PATTERN.fullmatch(normalized):
            raise AuthValidationError("Username must be 3-32 characters of letters, numbers, or underscores")
        return normalized

    def _validate_password(self, password: str) -> None:
        if len(password) < 8:
            raise AuthValidationError("Password must be at least 8 characters long")
