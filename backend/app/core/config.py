import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_DB_PATH = BACKEND_DIR / "data" / "namm.db"

class Settings(BaseSettings):
    PROJECT_NAME: str = "National AI Material Master"
    VERSION: str = "0.1.0"
    DESCRIPTION: str = "SIH Prototype: AI-driven Material Master Deduplication, Standardization, and Governance Engine"
    API_PREFIX: str = "/api"
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]
    
    # Target Database (Supabase PostgreSQL)
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "https://mock-sih.supabase.co")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "mock-key")
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{DEFAULT_SQLITE_DB_PATH.as_posix()}"
    )

    # Semantic embedding provider configuration
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "stub")
    SENTENCE_TRANSFORMER_MODEL: str = os.getenv(
        "SENTENCE_TRANSFORMER_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2",
    )
    EMBEDDING_DIMENSIONS: int = int(os.getenv("EMBEDDING_DIMENSIONS", "64"))
    EMBEDDING_ALLOW_STUB_FALLBACK: bool = os.getenv("EMBEDDING_ALLOW_STUB_FALLBACK", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    # SAP OData integration. Secrets must never be returned in API responses.
    SAP_ODATA_MODE: str = os.getenv("SAP_ODATA_MODE", "mock")
    SAP_ODATA_BASE_URL: str = os.getenv("SAP_ODATA_BASE_URL", "")
    SAP_ODATA_ENTITY_SET: str = os.getenv("SAP_ODATA_ENTITY_SET", "A_Material")
    SAP_ODATA_TIMEOUT_SECONDS: int = int(os.getenv("SAP_ODATA_TIMEOUT_SECONDS", "10"))
    SAP_ODATA_AUTH_MODE: str = os.getenv("SAP_ODATA_AUTH_MODE", "none")
    SAP_ODATA_USERNAME: str = os.getenv("SAP_ODATA_USERNAME", "")
    SAP_ODATA_PASSWORD: str = os.getenv("SAP_ODATA_PASSWORD", "")
    SAP_ODATA_BEARER_TOKEN: str = os.getenv("SAP_ODATA_BEARER_TOKEN", "")
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
