from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uvicorn
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.session import SessionLocal
from app.schemas.common import HealthCheckResponse
from app.api import (
    materials_router,
    matching_router,
    approvals_router,
    audit_router,
    demo_router,
    national_materials_router,
    embeddings_router,
    analytics_router,
    integrations_router,
    auth_router,
    taxonomy_router,
    legacy_migration_router,
    procurement_router,
    ml_router,
    national_governance_router,
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for frontend Vite dev server and preview ports
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health", response_model=HealthCheckResponse, tags=["Health Check"])
async def health_check():
    """
    Health check endpoint returning system status, version, and AI component readiness.
    """
    return HealthCheckResponse(
        status="healthy",
        service=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment="development",
        timestamp=datetime.utcnow()
    )

@app.get("/health/ready", tags=["Health Check"])
async def readiness_check():
    """
    Readiness check for database-backed deployments.
    """
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "service": settings.PROJECT_NAME,
            "database": "reachable",
            "timestamp": datetime.utcnow(),
        }
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Database readiness check failed: {exc.__class__.__name__}"
        )

# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API Gateway",
        "status": "online",
        "documentation": "/docs",
        "health_check": "/health",
        "api_routes": {
            "materials": f"{settings.API_PREFIX}/materials",
            "matching": f"{settings.API_PREFIX}/matching",
            "approvals": f"{settings.API_PREFIX}/approvals",
            "audit": f"{settings.API_PREFIX}/audit",
            "demo": f"{settings.API_PREFIX}/demo/summary",
            "national_materials": f"{settings.API_PREFIX}/national-materials",
            "embeddings": f"{settings.API_PREFIX}/embeddings",
            "analytics": f"{settings.API_PREFIX}/analytics/summary",
            "integrations": f"{settings.API_PREFIX}/integrations",
            "auth": f"{settings.API_PREFIX}/auth/me",
            "taxonomy": f"{settings.API_PREFIX}/taxonomy/nodes",
            "migration": f"{settings.API_PREFIX}/migration/legacy-materials",
            "procurement": f"{settings.API_PREFIX}/procurement/analytics",
            "ml": f"{settings.API_PREFIX}/ml/evaluate",
            "national_governance": f"{settings.API_PREFIX}/national-governance",
        }
    }

# Register API Routers
app.include_router(materials_router, prefix=settings.API_PREFIX)
app.include_router(matching_router, prefix=settings.API_PREFIX)
app.include_router(approvals_router, prefix=settings.API_PREFIX)
app.include_router(audit_router, prefix=settings.API_PREFIX)
app.include_router(demo_router, prefix=settings.API_PREFIX)
app.include_router(national_materials_router, prefix=settings.API_PREFIX)
app.include_router(embeddings_router, prefix=settings.API_PREFIX)
app.include_router(analytics_router, prefix=settings.API_PREFIX)
app.include_router(integrations_router, prefix=settings.API_PREFIX)
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(taxonomy_router, prefix=settings.API_PREFIX)
app.include_router(legacy_migration_router, prefix=settings.API_PREFIX)
app.include_router(procurement_router, prefix=settings.API_PREFIX)
app.include_router(ml_router, prefix=settings.API_PREFIX)
app.include_router(national_governance_router, prefix=settings.API_PREFIX)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
