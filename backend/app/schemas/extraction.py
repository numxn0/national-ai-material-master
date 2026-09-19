from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class ExtractedAttribute(BaseModel):
    key: str = Field(..., description="Canonical attribute key name")
    value: Any = Field(..., description="Extracted parameter value")
    source_snippet: Optional[str] = Field(None, description="Verbatim text fragment where value was detected")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence of attribute extraction [0.0 - 1.0]")

    model_config = ConfigDict(from_attributes=True)


class ExtractionConfidence(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0, description="Overall attribute extraction completeness score")
    level: str = Field(..., description="Qualitative rating: HIGH, MEDIUM, LOW")
    matched_rules_count: int = Field(default=0, description="Total technical attributes extracted")

    model_config = ConfigDict(from_attributes=True)


class AttributeExtractionRequest(BaseModel):
    raw_description: str = Field(..., description="Raw or normalized material description")
    category: Optional[str] = Field(None, description="Optional raw or normalized material category")
    uom: Optional[str] = Field(None, description="Optional raw or normalized Unit of Measure")


class AttributeExtractionResponse(BaseModel):
    raw_description: str = Field(..., description="Original raw description input")
    standard_description: str = Field(..., description="Standardized, abbreviation-expanded golden title")
    inferred_category: str = Field(..., description="Inferred or validated canonical taxonomy classification")
    extracted_attributes: Dict[str, Any] = Field(default_factory=dict, description="Dictionary of extracted technical specifications")
    missing_critical_attributes: List[str] = Field(default_factory=list, description="Critical attributes for category not found in description")
    extraction_confidence: float = Field(..., ge=0.0, le=1.0, description="Completeness confidence score [0.0 - 1.0]")
    extraction_notes: List[str] = Field(default_factory=list, description="Parser observations, lookup results, and notes")

    model_config = ConfigDict(from_attributes=True)
