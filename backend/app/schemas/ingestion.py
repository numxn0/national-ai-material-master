from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class IngestionStatus(str, Enum):
    PENDING = "PENDING"
    INGESTING = "INGESTING"
    SANITIZING = "SANITIZING"
    MATCHING = "MATCHING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IngestionBatchBase(BaseModel):
    batch_name: str = Field(..., description="Human-readable batch identifier or code (e.g., BATCH-2026-09-RAILWAYS-01)")
    source_cpse: str = Field(..., description="Originating CPSE name or code (e.g., INDIAN_RAILWAYS, ONGC)")
    source_system: str = Field(..., description="Originating ERP or MMS system identifier (e.g., SAP_ECC_PRD)")
    file_name: str = Field(..., description="Original filename of the ingested catalog sheet")
    total_records: int = Field(default=0, ge=0, description="Total number of material rows detected in source file")
    processed_records: int = Field(default=0, ge=0, description="Number of material rows successfully normalized")
    failed_records: int = Field(default=0, ge=0, description="Number of material rows rejected due to schema or validation errors")
    status: IngestionStatus = Field(default=IngestionStatus.PENDING, description="Current lifecycle status of the batch job")


class IngestionBatchCreate(IngestionBatchBase):
    uploaded_by: str = Field(default="SYSTEM", description="User ID or service account initiating the batch upload")
    file_hash_sha256: Optional[str] = Field(None, description="SHA-256 cryptographic hash of the raw upload file for audit verification")


class IngestionBatchResponse(IngestionBatchBase):
    id: UUID = Field(..., description="Globally unique identifier for the ingestion batch")
    uploaded_by: str = Field(..., description="User ID or service account that initiated the upload")
    file_hash_sha256: Optional[str] = Field(None, description="SHA-256 cryptographic hash of raw file")
    error_summary: Dict[str, Any] = Field(default_factory=dict, description="Summary of encountered validation errors if any")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Batch initialization timestamp")
    completed_at: Optional[datetime] = Field(None, description="Batch processing completion timestamp")

    model_config = ConfigDict(from_attributes=True)


from typing import List
from .material import SourceMaterialResponse


class CSVPreviewRowError(BaseModel):
    row_number: int = Field(..., description="1-indexed row number in the CSV source file")
    item_code: Optional[str] = Field(None, description="Item code if extracted from the rejected row")
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Raw dictionary content of the rejected row")
    reason: str = Field(..., description="Validation failure explanation")


class CSVPreviewSummary(BaseModel):
    file_name: str = Field(..., description="Name of the uploaded or analyzed CSV file")
    total_rows: int = Field(..., description="Total rows parsed in file")
    valid_records_count: int = Field(..., description="Total valid normalized records produced")
    invalid_records_count: int = Field(..., description="Total rejected/invalid rows")
    detected_columns_count: int = Field(..., description="Count of raw CSV headers discovered")
    mapped_columns_count: int = Field(..., description="Count of CSV headers successfully mapped to canonical schema")
    source_cpse_detected: Optional[str] = Field(None, description="Detected or default CPSE organization")
    source_system_detected: Optional[str] = Field(None, description="Detected or default source ERP system")


class CSVPreviewResponse(BaseModel):
    success: bool = True
    message: str = "CSV material ingestion preview generated successfully"
    summary: CSVPreviewSummary
    detected_columns: List[str] = Field(default_factory=list, description="Original column headers found in CSV")
    mapped_columns: Dict[str, str] = Field(default_factory=dict, description="Mapping from source column to canonical field")
    valid_records: List[SourceMaterialResponse] = Field(default_factory=list, description="Normalized SourceMaterial-shaped preview records")
    invalid_rows: List[CSVPreviewRowError] = Field(default_factory=list, description="Rows rejected during parsing with reasons")
