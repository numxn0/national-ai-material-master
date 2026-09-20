from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.auth import AuthenticatedUser, authenticate_user

security = HTTPBasic(auto_error=False)


def _auth_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing HTTP Basic credentials.",
        headers={"WWW-Authenticate": "Basic"},
    )


def get_current_user(
    credentials: HTTPBasicCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    if credentials is None:
        raise _auth_error()
    user = authenticate_user(db, credentials.username, credentials.password)
    if user is None:
        raise _auth_error()
    return user


def require_roles(*roles: str) -> Callable:
    allowed = {role.upper() for role in roles}

    def dependency(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if current_user.has_role("ADMIN") or current_user.roles.intersection(allowed):
            return current_user
        raise HTTPException(status_code=403, detail="Authenticated user lacks the required role.")

    return dependency
