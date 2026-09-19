from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.material import SourceMaterialResponse


class CandidateClassification(str, Enum):
    HIGH_CONFIDENCE_DUPLICATE = "HIGH_CONFIDENCE_DUPLICATE"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    LOW_CONFIDENCE_REVIEW = "LOW_CONFIDENCE_REVIEW"
    NOT_INCLUDED = "NOT_INCLUDED"


class MatchingSignal(BaseModel):
    signal_type: str = Field(..., description="Type identifier: DESCRIPTION_SIMILARITY, ATTRIBUTE_MATCH, TOKEN_OVERLAP, CATEGORY_COMPATIBLE, UOM_COMPATIBLE, MANUFACTURER_MATCH")
    description: str = Field(..., description="Human-readable explanation of why this feature aligned")
    score: float = Field(..., ge=0.0, le=1.0, description="Normalized score for this dimension [0.0 - 1.0]")
    weight: float = Field(..., ge=0.0, le=1.0, description="Weight of this dimension in overall scoring")

    model_config = ConfigDict(from_attributes=True)


class ConflictSignal(BaseModel):
    attribute: str = Field(..., description="Attribute name that caused divergence or conflict")
    value_a: Any = Field(..., description="Value in material A")
    value_b: Any = Field(..., description="Value in material B")
    severity: str = Field(..., description="CRITICAL, MODERATE, or LOW")
    description: str = Field(..., description="Explanation of the discrepancy")

    model_config = ConfigDict(from_attributes=True)


class CandidateScoreBreakdown(BaseModel):
    description_similarity: float = Field(..., ge=0.0, le=1.0, description="RapidFuzz token_sort / token_set ratio score (30% weight)")
    attribute_similarity: float = Field(..., ge=0.0, le=1.0, description="Attribute specification parity score (25% weight)")
    token_overlap: float = Field(..., ge=0.0, le=1.0, description="Normalized token Jaccard overlap score (15% weight)")
    category_compatibility: float = Field(..., ge=0.0, le=1.0, description="Taxonomy domain compatibility score (15% weight)")
    uom_compatibility: float = Field(..., ge=0.0, le=1.0, description="Unit of Measure compatibility score (10% weight)")
    mfg_part_compatibility: float = Field(..., ge=0.0, le=1.0, description="Manufacturer and part number alignment (5% weight)")
    final_score: float = Field(..., ge=0.0, le=1.0, description="Composite weighted similarity score [0.0 - 1.0]")

    model_config = ConfigDict(from_attributes=True)


class CandidateMatchResult(BaseModel):
    pair_id: str = Field(..., description="Unique deterministic identifier for candidate pair comparison")
    source_material_a: SourceMaterialResponse = Field(..., description="Primary incoming CPSE source material record")
    source_material_b: SourceMaterialResponse = Field(..., description="Candidate matching CPSE source material record")
    score: float = Field(..., ge=0.0, le=1.0, description="Overall duplicate confidence score [0.0 - 1.0]")
    classification: CandidateClassification = Field(..., description="Automated classification tier")
    score_breakdown: CandidateScoreBreakdown = Field(..., description="Detailed weighted score components")
    matching_signals: List[MatchingSignal] = Field(default_factory=list, description="List of positive matching signals")
    conflict_signals: List[ConflictSignal] = Field(default_factory=list, description="List of conflicting or divergent attribute signals")
    recommendation: str = Field(..., description="Actionable recommendation message for catalog governance")
    semantic_similarity_score: Optional[float] = Field(default=None, description="Preview-only semantic embedding similarity [0.0 - 1.0]")
    semantic_method: Optional[str] = Field(default=None, description="Identifier for semantic scoring method, e.g., DETERMINISTIC_TOKEN_HASH_STUB (Preview)")

    model_config = ConfigDict(from_attributes=True)


class CandidateMatchRequest(BaseModel):
    materials: List[SourceMaterialResponse] = Field(..., description="List of normalized source material records to evaluate for duplicates")
    min_score: Optional[float] = Field(default=0.65, ge=0.0, le=1.0, description="Minimum similarity threshold to retain as candidate [default 0.65]")


class CandidateMatchResponse(BaseModel):
    total_records: int = Field(..., description="Total input material records evaluated")
    compared_pairs: int = Field(..., description="Total pairwise candidate combinations evaluated")
    candidate_count: int = Field(..., description="Total candidate duplicate pairs meeting min_score threshold")
    candidates: List[CandidateMatchResult] = Field(default_factory=list, description="Ranked list of detected duplicate candidates")

    model_config = ConfigDict(from_attributes=True)
