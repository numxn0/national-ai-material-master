from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class MatchMethod(str, Enum):
    EXACT_CODE = "EXACT_CODE"
    RULE_BASED = "RULE_BASED"
    COSINE_VECTOR = "COSINE_VECTOR"
    XGBOOST_HYBRID = "XGBOOST_HYBRID"
    MANUAL = "MANUAL"


class MatchStatus(str, Enum):
    UNPROCESSED = "UNPROCESSED"
    CANDIDATES_GENERATED = "CANDIDATES_GENERATED"
    NO_CANDIDATES = "NO_CANDIDATES"
    MATCH_FOUND = "MATCH_FOUND"
    NEW_CANDIDATE = "NEW_CANDIDATE"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
    NO_MATCH = "NO_MATCH"


class ApprovalStatus(str, Enum):
    PENDING_INGESTION = "PENDING_INGESTION"
    AUTO_MATCHED = "AUTO_MATCHED"
    PENDING_L1 = "PENDING_L1"
    PENDING_L2 = "PENDING_L2"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DISPUTED = "DISPUTED"


class MaterialMappingBase(BaseModel):
    source_material_id: UUID = Field(..., description="UUID of the originating CPSE source material")
    national_material_id: UUID = Field(..., description="UUID of the matched National Material Master")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="AI composite confidence score [0.0 - 1.0]")
    match_method: MatchMethod = Field(..., description="Algorithm or process that produced the match")
    match_explanation: Dict[str, Any] = Field(default_factory=dict, description="SHAP feature importances and attribute comparison delta")
    approval_status: ApprovalStatus = Field(default=ApprovalStatus.PENDING_L1, description="Governance approval stage")
    reviewer_id: Optional[str] = Field(None, description="Identifier of officer who reviewed the linkage")
    reviewed_at: Optional[datetime] = Field(None, description="Timestamp of reviewer decision")


class MaterialMappingCreate(MaterialMappingBase):
    pass


class MaterialMappingResponse(MaterialMappingBase):
    id: UUID = Field(..., description="Unique mapping linkage identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when linkage was created")

    model_config = ConfigDict(from_attributes=True)
