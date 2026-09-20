from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NationalMaterialDraftResponse(BaseModel):
    id: UUID
    national_material_code: str
    originating_match_candidate_id: Optional[UUID] = None
    standard_description: str
    category: str
    sub_category: str
    material_type: Optional[str] = None
    material_grade: Optional[str] = None
    standard_uom: str
    canonical_attributes: Dict[str, Any] = Field(default_factory=dict)
    classification_path: Optional[str] = None
    status: str
    created_by: str
    approved_by: Optional[str] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SourceMappingResponse(BaseModel):
    id: UUID
    source_material_id: UUID
    national_material_id: UUID
    national_material_code: str
    national_material_status: str
    confidence_score: float
    match_method: str
    match_explanation: Dict[str, Any] = Field(default_factory=dict)
    approval_status: str
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


class NationalMaterialDetailResponse(BaseModel):
    national_material: NationalMaterialDraftResponse
    mappings: List[SourceMappingResponse] = Field(default_factory=list)


class DraftFromCandidateResponse(BaseModel):
    success: bool = True
    idempotent_replay: bool = False
    national_material: NationalMaterialDraftResponse
    mappings: List[SourceMappingResponse] = Field(default_factory=list)
