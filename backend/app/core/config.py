import os
from typing import List
from pydantic_settings import BaseSettings

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
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
