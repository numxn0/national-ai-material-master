from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class AnalyticsCpseBreakdown(BaseModel):
    cpse_name: str
    material_count: int
    batch_count: int
    candidate_involvement_count: int
    approved_mapping_count: int


class AnalyticsCategoryBreakdown(BaseModel):
    category: str
    material_count: int
    candidate_involvement_count: int
    active_national_material_count: int


class AnalyticsRecentActivity(BaseModel):
    timestamp: datetime
    action: str
    actor: str
    entity_type: str
    entity_id: str
    summary: str


class AnalyticsIngestionTimelinePoint(BaseModel):
    date: str
    batches_created: int
    source_materials_processed: int
    rejected_rows: int


class AnalyticsAuditChainSummary(BaseModel):
    chain_key: str = "primary"
    last_sequence_number: int = 0
    last_hash: str = "0" * 64
    last_event_id: Optional[str] = None
    updated_at: Optional[datetime] = None


class AnalyticsSummaryResponse(BaseModel):
    total_source_materials: int = 0
    total_ingestion_batches: int = 0
    batches_completed: int = 0
    batches_with_errors: int = 0
    total_match_candidates: int = 0
    duplicate_candidate_count: int = 0
    candidate_counts_by_classification: Dict[str, int] = Field(default_factory=dict)
    candidate_counts_by_status: Dict[str, int] = Field(default_factory=dict)
    pending_l1_count: int = 0
    pending_l2_count: int = 0
    needs_more_info_count: int = 0
    approved_mapping_count: int = 0
    rejected_mapping_count: int = 0
    national_material_draft_count: int = 0
    national_material_active_count: int = 0
    national_material_rejected_count: int = 0
    estimated_approved_savings_inr: float = 0.0
    actual_procurement_spend_inr: float = 0.0
    actual_procurement_quantity: float = 0.0
    procurement_vendor_count: int = 0
    approved_national_code_spend_inr: float = 0.0
    procurement_metric_source: str = "NO_PROCUREMENT_HISTORY"
    audit_event_count: int = 0
    audit_chain: AnalyticsAuditChainSummary = Field(default_factory=AnalyticsAuditChainSummary)
    cpse_breakdown: List[AnalyticsCpseBreakdown] = Field(default_factory=list)
    category_breakdown: List[AnalyticsCategoryBreakdown] = Field(default_factory=list)
    recent_activity: List[AnalyticsRecentActivity] = Field(default_factory=list)
    ingestion_timeline: List[AnalyticsIngestionTimelinePoint] = Field(default_factory=list)
    days: int = 30
    generated_at: datetime
