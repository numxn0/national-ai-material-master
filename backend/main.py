from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uvicorn

from app.core.config import settings
from app.schemas.common import HealthCheckResponse
from app.api import (
    materials_router,
    matching_router,
    approvals_router,
    audit_router,
    demo_router,
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
    allow_origins=["*"],  # For rapid hackathon prototyping
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
        }
    }

# Register API Routers
app.include_router(materials_router, prefix=settings.API_PREFIX)
app.include_router(matching_router, prefix=settings.API_PREFIX)
app.include_router(approvals_router, prefix=settings.API_PREFIX)
app.include_router(audit_router, prefix=settings.API_PREFIX)
app.include_router(demo_router, prefix=settings.API_PREFIX)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
