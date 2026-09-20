from .materials import router as materials_router
from .matching import router as matching_router
from .approvals import router as approvals_router
from .audit import router as audit_router
from .demo import router as demo_router
from .national_materials import router as national_materials_router
from .embeddings import router as embeddings_router
from .analytics import router as analytics_router
from .integrations import router as integrations_router
from .auth import router as auth_router
from .taxonomy import router as taxonomy_router
from .legacy_migration import router as legacy_migration_router
from .procurement import router as procurement_router
from .ml import router as ml_router
from .national_governance import router as national_governance_router

__all__ = [
    "materials_router",
    "matching_router",
    "approvals_router",
    "audit_router",
    "demo_router",
    "national_materials_router",
    "embeddings_router",
    "analytics_router",
    "integrations_router",
    "auth_router",
    "taxonomy_router",
    "legacy_migration_router",
    "procurement_router",
    "ml_router",
    "national_governance_router",
]
