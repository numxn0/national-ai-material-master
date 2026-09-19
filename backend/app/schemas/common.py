from datetime import datetime
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field

class APIResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class HealthCheckResponse(BaseModel):
    status: str = "healthy"
    service: str = "National AI Material Master API"
    version: str
    environment: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    database_target: str = "Supabase PostgreSQL (pgvector ready)"
    ai_pipeline_status: Dict[str, str] = Field(default_factory=lambda: {
        "rapidfuzz": "placeholder - ready for integration",
        "embeddings": "placeholder - ready for integration",
        "xgboost_classifier": "placeholder - ready for integration",
        "paddle_ocr": "planned for milestone 2",
    })
