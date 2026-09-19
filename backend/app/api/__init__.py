from .materials import router as materials_router
from .matching import router as matching_router
from .approvals import router as approvals_router
from .audit import router as audit_router
from .demo import router as demo_router

__all__ = [
    "materials_router",
    "matching_router",
    "approvals_router",
    "audit_router",
    "demo_router",
]
