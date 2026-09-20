from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuthenticatedUserResponse(BaseModel):
    id: UUID
    username: str
    display_name: str
    organization_scope: Optional[str] = None
    roles: List[str]


class UserResponse(AuthenticatedUserResponse):
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
