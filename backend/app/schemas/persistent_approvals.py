from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.national_materials import NationalMaterialDraftResponse, SourceMappingResponse


class PersistentApprovalDecision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    NEEDS_MORE_INFO = "NEEDS_MORE_INFO"


class PersistentApprovalDecisionRequest(BaseModel):
    decision: PersistentApprovalDecision
    reviewer_name: Optional[str] = None
    reviewer_role: Optional[str] = None
    reviewer_note: Optional[str] = None


class PersistentApprovalResubmitRequest(BaseModel):
    submitter_note: str = Field(..., min_length=1, max_length=500)


class PersistentApprovalCaseResponse(BaseModel):
    id: UUID
    approval_case_id: str
    match_candidate_id: Optional[UUID] = None
    proposed_national_material_id: Optional[UUID] = None
    proposed_national_material_code: str
    proposed_standard_description: Optional[str] = None
    hybrid_score: Optional[float] = None
    hybrid_classification: Optional[str] = None
    required_approval_level: str
    current_stage: str
    approval_status: str
    l1_reviewer: Optional[str] = None
    l1_decision: Optional[str] = None
    l1_reviewed_at: Optional[datetime] = None
    l1_notes: Optional[str] = None
    l2_reviewer: Optional[str] = None
    l2_decision: Optional[str] = None
    l2_reviewed_at: Optional[datetime] = None
    l2_notes: Optional[str] = None
    procurement_impact: Dict[str, Any] = Field(default_factory=dict)
    mapping_preview: Dict[str, Any] = Field(default_factory=dict)
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    national_material: Optional[NationalMaterialDraftResponse] = None
    mappings: List[SourceMappingResponse] = Field(default_factory=list)
    mapping_count: int = 0
    actor_identity_verified: bool = False
    created_at: datetime
    updated_at: datetime


class PersistentApprovalCaseCreateResponse(BaseModel):
    success: bool = True
    idempotent_replay: bool = False
    actor_identity_verified: bool = False
    case: PersistentApprovalCaseResponse


class PersistentApprovalDecisionResponse(BaseModel):
    success: bool = True
    actor_identity_verified: bool = False
    case: PersistentApprovalCaseResponse


class PersistentApprovalCaseListResponse(BaseModel):
    status: str = "success"
    count: int
    total: int
    page: int
    limit: int
    actor_identity_verified: bool = False
    items: List[PersistentApprovalCaseResponse] = Field(default_factory=list)
