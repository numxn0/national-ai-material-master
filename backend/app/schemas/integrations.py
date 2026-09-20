from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ingestion import IngestionBatchResponse


class SapConnectionTestResponse(BaseModel):
    status: str
    connector_type: str = "sap_odata"
    connector_mode: str
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    capabilities: Dict[str, Any] = Field(default_factory=dict)


class SapImportMaterialsRequest(BaseModel):
    source_cpse: str = Field(..., min_length=1)
    source_system: str = Field(default="SAP_ODATA")
    connection_name: str = Field(default="default-sap-odata")
    entity_set: Optional[str] = None
    max_records: Optional[int] = Field(default=None, ge=1, le=1000)
    idempotency_key: Optional[str] = Field(default=None, max_length=160)


class IntegrationImportRunResponse(BaseModel):
    id: UUID
    connector_type: str
    connector_mode: str
    connection_name: str
    source_cpse: str
    source_system: str
    ingestion_batch_id: Optional[UUID] = None
    status: str
    received_count: int
    imported_count: int
    rejected_count: int
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    error_summary: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SapImportMaterialsResponse(BaseModel):
    success: bool = True
    idempotent_replay: bool = False
    import_run: IntegrationImportRunResponse
    ingestion_batch: Optional[IngestionBatchResponse] = None
    received_count: int
    imported_count: int
    rejected_count: int
    connector_metadata: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


class IntegrationImportRunDetailResponse(BaseModel):
    import_run: IntegrationImportRunResponse
    ingestion_batch: Optional[IngestionBatchResponse] = None
