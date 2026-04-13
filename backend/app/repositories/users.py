from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ImportRun
from app.models import User, utc_now


class UserRepository:
    @staticmethod
    def get_by_id(session: Session, user_id: int) -> User | None:
        return session.get(User, user_id)

    @staticmethod
    def get_by_username(session: Session, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        return session.scalar(stmt)

    @staticmethod
    def list_users(
        session: Session,
        *,
        role: str | None = None,
        query: str | None = None,
    ) -> list[User]:
        stmt = select(User)
        if role is not None:
            stmt = stmt.where(User.role == role)
        if query:
            stmt = stmt.where(User.username.ilike(f"%{query}%"))
        stmt = stmt.order_by(User.created_at.desc(), User.id.desc())
        return list(session.scalars(stmt))

    @staticmethod
    def list_owner_ids_with_import_runs(session: Session, *, user_ids: list[int]) -> set[int]:
        if not user_ids:
            return set()
        stmt = select(ImportRun.owner_user_id).where(ImportRun.owner_user_id.in_(user_ids)).distinct()
        return {int(user_id) for user_id in session.scalars(stmt) if user_id is not None}

    @staticmethod
    def create_user(
        session: Session,
        *,
        username: str,
        password_hash: str,
        role: str = "user",
        is_active: bool = True,
    ) -> User:
        user = User(
            username=username,
            password_hash=password_hash,
            role=role,
            is_active=is_active,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    @staticmethod
    def update_last_login(session: Session, user: User) -> User:
        user.last_login_at = utc_now()
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    @staticmethod
    def save_user(session: Session, user: User) -> User:
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    @staticmethod
    def delete_user(session: Session, user: User) -> None:
        session.delete(user)
        session.commit()
