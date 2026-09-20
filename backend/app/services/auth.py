from dataclasses import dataclass
from typing import Iterable, List, Optional, Set

from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import User, UserRole

VALID_ROLES = {"ADMIN", "CPSE_USER", "L1_REVIEWER", "L2_AUTHORITY", "AUDITOR"}
password_hasher = PasswordHash.recommended()


@dataclass(frozen=True)
class AuthenticatedUser:
    id: object
    username: str
    display_name: str
    organization_scope: Optional[str]
    roles: Set[str]

    def has_role(self, *roles: str) -> bool:
        return bool(self.roles.intersection({role.upper() for role in roles}))


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password, password_hash)
    except Exception:
        return False


def normalize_roles(roles: Iterable[str]) -> List[str]:
    normalized = []
    for role in roles:
        value = str(role).strip().upper()
        if not value:
            continue
        if value not in VALID_ROLES:
            raise ValueError(f"Unsupported role '{role}'. Allowed roles: {sorted(VALID_ROLES)}")
        if value not in normalized:
            normalized.append(value)
    return normalized


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.execute(
        select(User)
        .options(selectinload(User.roles))
        .where(User.username == username)
    ).scalar_one_or_none()


def user_roles(user: User) -> List[str]:
    return sorted({role.role for role in user.roles})


def to_authenticated_user(user: User) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        organization_scope=user.organization_scope,
        roles=set(user_roles(user)),
    )


def authenticate_user(db: Session, username: str, password: str) -> Optional[AuthenticatedUser]:
    user = get_user_by_username(db, username)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return to_authenticated_user(user)


def create_or_update_local_user(
    db: Session,
    *,
    username: str,
    password: str,
    display_name: str,
    roles: Iterable[str],
    organization_scope: Optional[str] = None,
    is_active: bool = True,
) -> User:
    normalized_roles = normalize_roles(roles)
    if not normalized_roles:
        raise ValueError("At least one role is required.")
    if not password:
        raise ValueError("Password cannot be empty.")

    user = get_user_by_username(db, username)
    if user is None:
        user = User(
            username=username,
            password_hash=hash_password(password),
            display_name=display_name,
            organization_scope=organization_scope,
            is_active=is_active,
        )
        db.add(user)
        db.flush()
    else:
        user.password_hash = hash_password(password)
        user.display_name = display_name
        user.organization_scope = organization_scope
        user.is_active = is_active
        existing = {role.role: role for role in user.roles}
        for role, role_model in list(existing.items()):
            if role not in normalized_roles:
                db.delete(role_model)

    current_roles = {role.role for role in user.roles}
    for role in normalized_roles:
        if role not in current_roles:
            db.add(UserRole(user_id=user.id, role=role))
    db.commit()
    return get_user_by_username(db, username)


def assert_cpse_scope(user: AuthenticatedUser, requested_cpse: Optional[str]) -> None:
    if user.has_role("ADMIN"):
        return
    if user.has_role("CPSE_USER") and user.organization_scope:
        if not requested_cpse or requested_cpse.strip().upper() != user.organization_scope.strip().upper():
            from fastapi import HTTPException

            raise HTTPException(
                status_code=403,
                detail="CPSE_USER is scoped to a different organization.",
            )
