"""
Pydantic schemas for the Demo Summary and Pipeline Health Overview endpoint.
Summarizes module readiness, sample dataset counts, candidate duplicates,
approval cases, cryptographic audit chain integrity, and planned production integrations.
"""

from typing import Dict, List, Any
from pydantic import BaseModel, Field, ConfigDict


class ModuleStatus(BaseModel):
    name: str = Field(..., description="Module display name")
    key: str = Field(..., description="Module identifier key")
    status: str = Field(..., description="'READY', 'DEMO_READY', 'VERIFIED', or 'PLANNED'")
    description: str = Field(..., description="Short functional summary")
    implementation: str = Field(..., description="Active implementation technique")

    model_config = ConfigDict(from_attributes=True)


class DemoSummaryResponse(BaseModel):
    service_status: str = Field(default="operational", description="Overall backend service status")
    service_name: str = Field(default="National AI Material Master", description="Platform title")
    version: str = Field(default="1.0.0-sih-prototype", description="System prototype release")
    timestamp: str = Field(..., description="ISO UTC timestamp of summary generation")
    
    # Core Demo Metrics
    sample_material_count: int = Field(..., description="Total raw sample records in catalog pool")
    candidate_count: int = Field(..., description="Identified candidate duplicate pairs")
    high_confidence_match_count: int = Field(..., description="Pairs with hybrid score >= 0.85")
    approval_case_count: int = Field(..., description="Governance approval cases in queue")
    pending_l1_count: int = Field(..., description="Cases awaiting L1 Technical Nodal verification")
    pending_l2_count: int = Field(..., description="Cases awaiting L2 Ministry Authority ratification")
    audit_event_count: int = Field(..., description="Cryptographically chained audit trail events")
    audit_chain_status: str = Field(default="CHAIN_INTACT", description="'CHAIN_INTACT' or 'CHAIN_BROKEN'")
    total_estimated_savings_inr: float = Field(..., description="Aggregate cross-CPSE procurement savings (INR)")

    # Pipeline Modules Readiness
    modules: List[ModuleStatus] = Field(default_factory=list, description="Detailed readiness status of all 11 pipeline stages")

    # Architecture & Non-Persistence Disclosure
    persistence_status: str = Field(
        default="demo_in_memory_only",
        description="Explicit guarantee of in-memory demonstration execution"
    )
    is_database_connected: bool = Field(
        default=False,
        description="Explicit confirmation that live database connection is not active"
    )
    planned_production_integrations: List[str] = Field(
        default_factory=list,
        description="Planned production integrations (Supabase, pgvector, Transformer embeddings, XGBoost, SHAP, RBAC)"
    )
    notes: str = Field(
        default="All metrics generated dynamically in-memory from sample CPSE datasets without disk or database persistence.",
        description="Compliance note"
    )

    model_config = ConfigDict(from_attributes=True)
