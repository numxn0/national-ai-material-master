from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.schemas import AuthenticatedUserResponse
from app.services.auth import AuthenticatedUser

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/me", response_model=AuthenticatedUserResponse)
async def get_me(current_user: AuthenticatedUser = Depends(get_current_user)):
    return AuthenticatedUserResponse(
        id=current_user.id,
        username=current_user.username,
        display_name=current_user.display_name,
        organization_scope=current_user.organization_scope,
        roles=sorted(current_user.roles),
    )
