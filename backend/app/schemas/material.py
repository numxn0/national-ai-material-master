from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

from .mapping import MatchStatus, ApprovalStatus


class MaterialAttribute(BaseModel):
    category: str = Field(..., description="Top-level taxonomy category")
    sub_category: str = Field(..., description="Sub-category taxonomy grouping")
    attribute_key: str = Field(..., description="Technical parameter key name, e.g., nominal_bore_nb")
    display_name: str = Field(..., description="Human-readable label for user interfaces")
    data_type: str = Field(default="STRING", description="Data type: NUMERIC, STRING, BOOLEAN, ENUM")
    allowed_units: List[str] = Field(default_factory=list, description="Permissible units of measure, e.g., ['mm', 'inch']")
    is_mandatory: bool = Field(default=False, description="Flag indicating if attribute is required for specification completeness")
    is_critical_for_matching: bool = Field(default=False, description="Flag indicating if attribute carries high weight in AI deduplication")
    validation_rule: Optional[Dict[str, Any]] = Field(default=None, description="Optional regex or numeric bounds constraint")

    model_config = ConfigDict(from_attributes=True)


class SourceMaterialBase(BaseModel):
    source_cpse: str = Field(..., description="Originating CPSE name or code (e.g., SAIL, ONGC, INDIAN_RAILWAYS)")
    source_system: str = Field(..., description="Originating ERP or MMS system identifier (e.g., SAP_ECC_PRD)")
    source_material_code: str = Field(..., description="Original item code in CPSE catalog")
    raw_description: str = Field(..., description="Unmodified verbatim description from source system")
    cleaned_description: Optional[str] = Field(None, description="Sanitized, lowercased, and whitespace-collapsed text")
    standard_description: Optional[str] = Field(None, description="Structured standard description formatted according to taxonomy")
    category: str = Field(..., description="Standardized top-level engineering domain")
    sub_category: str = Field(..., description="Standardized secondary category")
    material_type: Optional[str] = Field(None, description="Specific item form factor or type")
    material_grade: Optional[str] = Field(None, description="Metallurgical, electrical, or standard grade (e.g., SS304, IS 694)")
    manufacturer: Optional[str] = Field(None, description="Normalized OEM manufacturer name")
    part_number: Optional[str] = Field(None, description="Cleaned manufacturer catalog part number")
    model_number: Optional[str] = Field(None, description="OEM commercial model or series designation")
    uom: str = Field(..., description="Standardized Unit of Measure (e.g., NOS, MTR, KGS)")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Extracted physical and engineering parameters")
    normalized_tokens: List[str] = Field(default_factory=list, description="Lemmatized, stemmed search tokens")
    ingestion_batch_id: Optional[UUID] = Field(None, description="Reference to parent ingestion batch job")
    match_status: MatchStatus = Field(default=MatchStatus.UNPROCESSED, description="AI matching pipeline status")
    approval_status: ApprovalStatus = Field(default=ApprovalStatus.PENDING_INGESTION, description="Workflow governance state")


class SourceMaterialCreate(SourceMaterialBase):
    pass


class SourceMaterialResponse(SourceMaterialBase):
    id: UUID = Field(..., description="Globally unique identifier for the source material record")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record ingestion timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of latest record mutation")

    model_config = ConfigDict(from_attributes=True)


class NationalMaterialBase(BaseModel):
    national_material_code: str = Field(..., description="Hierarchical national standard SKU (e.g., NAMM-PIP-SS-0042)")
    standard_description: str = Field(..., description="Authoritative golden record title")
    category: str = Field(..., description="Standardized national category")
    sub_category: str = Field(..., description="Standardized national sub-category")
    material_type: str = Field(..., description="Canonical physical design/component classification")
    material_grade: Optional[str] = Field(None, description="Certified material grade standard")
    standard_uom: str = Field(..., description="Authoritative ISO/BIS national procurement Unit of Measure")
    canonical_attributes: Dict[str, Any] = Field(default_factory=dict, description="Certified specification dictionary")
    classification_path: str = Field(..., description="Hierarchical taxonomy classification path")
    status: str = Field(default="ACTIVE", description="Lifecycle state: DRAFT, ACTIVE, UNDER_REVIEW, DEPRECATED")


class NationalMaterialCreate(NationalMaterialBase):
    created_by: str = Field(default="SYSTEM", description="User or agent creating the national master record")
    approved_by: Optional[str] = Field(None, description="Nodal authority ratifying the canonical record")


class NationalMaterialResponse(NationalMaterialBase):
    id: UUID = Field(..., description="Globally unique identifier for the national master record")
    created_by: str = Field(..., description="User or agent creating the national master record")
    approved_by: Optional[str] = Field(None, description="Nodal authority ratifying the canonical record")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Latest amendment timestamp")

    model_config = ConfigDict(from_attributes=True)


class TextNormalizationRequest(BaseModel):
    raw_description: str = Field(..., description="Raw material description from CPSE catalog")
    uom: Optional[str] = Field(None, description="Optional raw Unit of Measure (e.g., MTR, NOS, KGS)")
    category: Optional[str] = Field(None, description="Optional raw category or commodity group")


class TextNormalizationResponse(BaseModel):
    raw_description: str = Field(..., description="Original raw description text")
    cleaned_description: str = Field(..., description="Sanitized, lowercase text for indexing")
    standard_description: str = Field(..., description="Standardized, abbreviation-expanded uppercase technical title")
    normalized_uom: str = Field(..., description="Canonical standard Unit of Measure code")
    normalized_category: str = Field(..., description="Standardized taxonomy classification group")
    normalized_tokens: List[str] = Field(default_factory=list, description="Extracted domain keywords and technical identifiers")
