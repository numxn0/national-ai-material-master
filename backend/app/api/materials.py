from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.schemas import (
    SourceMaterialResponse,
    NationalMaterialResponse,
    IngestionBatchResponse,
    CSVIngestResponse,
    IngestionBatchDetailResponse,
    IngestionRowErrorResponse,
    PersistedMaterialsPageResponse,
    PersistedSourceMaterialResponse,
    CSVPreviewResponse,
    TextNormalizationRequest,
    TextNormalizationResponse,
    AttributeExtractionRequest,
    AttributeExtractionResponse,
    EXAMPLE_SOURCE_MATERIAL,
    EXAMPLE_NATIONAL_MATERIAL,
    EXAMPLE_INGESTION_BATCH,
)
from app.db.models import IngestionBatch, IngestionRowError, SourceMaterial
from app.db.session import get_db
from app.services.auth import AuthenticatedUser, assert_cpse_scope
from app.services.durable_ingestion import ingest_csv_content
from app.services.ingestion_preview import parse_csv_content
from app.services.normalization import (
    normalize_punctuation,
    normalize_uom,
    normalize_category,
    tokenize_description,
    build_standard_description,
)
from app.services.attribute_extraction import extract_attributes

router = APIRouter(prefix="/materials", tags=["Materials"])

# Mock in-memory placeholder dataset for initial prototyping
PLACEHOLDER_MATERIALS = [
    {
        "id": "mat-001",
        "item_code": "CR-BEAR-6205",
        "raw_description": "BALL BEARING 6205-2RS DEEP GROOVE SKF",
        "standardized_name": "Deep Groove Ball Bearing 6205-2RS SKF",
        "category": "Mechanical Spares",
        "unit_of_measure": "NOS",
        "source_psu": "Indian Railways (Northern)",
        "status": "Standardized",
        "created_at": "2026-09-18T10:00:00Z"
    },
    {
        "id": "mat-002",
        "item_code": "CIL-BLT-1250",
        "raw_description": "HEX BOLT M12X50 GRADE 8.8 FULL THREAD ZINC",
        "standardized_name": "Hexagon Head Bolt M12x50 Gr 8.8 Zinc Plated",
        "category": "Fasteners",
        "unit_of_measure": "KGS",
        "source_psu": "Coal India Limited",
        "status": "Pending Review",
        "created_at": "2026-09-18T10:30:00Z"
    },
    {
        "id": "mat-003",
        "item_code": "SAIL-VLV-80MM",
        "raw_description": "GATE VALVE 80MM FLANGED CAST STEEL CLASS 150",
        "standardized_name": "Cast Steel Gate Valve 80mm NB Flanged Cl-150",
        "category": "Valves & Piping",
        "unit_of_measure": "NOS",
        "source_psu": "Steel Authority of India Ltd (SAIL)",
        "status": "Under Approval",
        "created_at": "2026-09-18T11:00:00Z"
    }
]

@router.get("/canonical/source-example", response_model=SourceMaterialResponse, tags=["Canonical Materials"])
async def get_canonical_source_example():
    """
    Retrieve typed example of a normalized CPSE Source Material record.
    Shaped by SourceMaterialResponse Pydantic schema.
    """
    return EXAMPLE_SOURCE_MATERIAL

@router.get("/canonical/national-example", response_model=NationalMaterialResponse, tags=["Canonical Materials"])
async def get_canonical_national_example():
    """
    Retrieve typed example of an authoritative National Material Master (Golden Record).
    Shaped by NationalMaterialResponse Pydantic schema.
    """
    return EXAMPLE_NATIONAL_MATERIAL

@router.get("/canonical/batch-example", response_model=IngestionBatchResponse, tags=["Canonical Ingestion"])
async def get_canonical_batch_example():
    """
    Retrieve typed example of an Ingestion Batch metadata record.
    Shaped by IngestionBatchResponse Pydantic schema.
    """
    return EXAMPLE_INGESTION_BATCH

@router.get("/preview-sample", response_model=CSVPreviewResponse, tags=["Material Ingestion Preview"])
async def preview_sample_data():
    """
    Parses sample-data/sample_materials_raw.csv and returns normalized SourceMaterial-shaped
    preview records, detected headers, column mappings, and validation summaries.
    No data is saved or persisted.
    """
    sample_paths = [
        Path("..") / "sample-data" / "sample_materials_raw.csv",
        Path("sample-data") / "sample_materials_raw.csv",
        Path(__file__).resolve().parents[3] / "sample-data" / "sample_materials_raw.csv",
        Path(__file__).resolve().parents[2] / "sample-data" / "sample_materials_raw.csv",
    ]
    sample_file = None
    for p in sample_paths:
        if p.exists():
            sample_file = p
            break

    if not sample_file:
        raise HTTPException(
            status_code=404,
            detail="Sample data file sample_materials_raw.csv could not be found."
        )

    try:
        with open(sample_file, "r", encoding="utf-8") as f:
            content = f.read()
        return parse_csv_content(
            csv_text_or_bytes=content,
            file_name="sample_materials_raw.csv"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse sample materials CSV: {str(exc)}"
        )

@router.post("/preview-csv", response_model=CSVPreviewResponse, tags=["Material Ingestion Preview"])
async def preview_uploaded_csv(
    file: UploadFile = File(..., description="Uploaded CSV catalog file"),
    source_cpse: Optional[str] = Form(None, description="Optional CPSE enterprise name"),
    source_system: Optional[str] = Form(None, description="Optional originating ERP system name")
):
    """
    Receives an uploaded CSV file, dynamically detects and maps columns, cleans descriptions,
    normalizes UOMs, and produces SourceMaterial-shaped preview objects with validation errors.
    Pure in-memory preview without database persistence.
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Please upload a standard comma-separated (.csv) file."
        )

    try:
        content_bytes = await file.read()
        return parse_csv_content(
            csv_text_or_bytes=content_bytes,
            default_cpse=source_cpse,
            default_system=source_system,
            file_name=file.filename
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing CSV preview: {str(exc)}"
        )

@router.post("/ingest-csv", response_model=CSVIngestResponse, tags=["Durable Material Ingestion"])
async def ingest_uploaded_csv(
    file: UploadFile = File(..., description="Uploaded CSV catalog file"),
    source_cpse: Optional[str] = Form(None, description="Optional CPSE enterprise name"),
    source_system: Optional[str] = Form(None, description="Optional originating ERP system name"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "CPSE_USER")),
):
    """
    Persist a CSV catalog as an idempotent ingestion batch.
    POST /preview-csv remains the non-persistent preview path.
    """
    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Please upload a standard comma-separated (.csv) file."
        )

    try:
        assert_cpse_scope(current_user, source_cpse)
        content_bytes = await file.read()
        batch, idempotent_replay, error_count = ingest_csv_content(
            db,
            content_bytes=content_bytes,
            file_name=filename,
            source_cpse=source_cpse,
            source_system=source_system,
        )
        return CSVIngestResponse(
            message="CSV ingestion batch replayed from existing durable records." if idempotent_replay else "CSV ingestion batch persisted successfully.",
            idempotent_replay=idempotent_replay,
            batch=IngestionBatchResponse.model_validate(batch),
            processed_records=batch.processed_records,
            failed_records=batch.failed_records,
            error_count=error_count,
        )
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"CSV ingestion failed: {str(exc)}")

@router.post("/normalize-text", response_model=TextNormalizationResponse, tags=["Data Cleaning & Normalization"])
async def normalize_material_text(payload: TextNormalizationRequest):
    """
    Standardizes a raw CPSE/PSU material description, normalizes UOM and category,
    expands technical abbreviations, and generates normalized tokens.
    Pure rule-based normalization engine without database persistence.
    """
    if not payload.raw_description or not payload.raw_description.strip():
        raise HTTPException(
            status_code=400,
            detail="raw_description cannot be empty or whitespace only."
        )

    cleaned_desc = normalize_punctuation(payload.raw_description).lower()
    standard_desc = build_standard_description(payload.raw_description)
    norm_uom = normalize_uom(payload.uom)
    norm_category = normalize_category(payload.category)
    tokens = tokenize_description(standard_desc)

    return TextNormalizationResponse(
        raw_description=payload.raw_description,
        cleaned_description=cleaned_desc,
        standard_description=standard_desc,
        normalized_uom=norm_uom,
        normalized_category=norm_category,
        normalized_tokens=tokens,
    )

@router.post("/extract-attributes", response_model=AttributeExtractionResponse, tags=["Rule-Based Attribute Extraction"])
async def extract_material_attributes(payload: AttributeExtractionRequest):
    """
    Extracts structured technical attributes from raw/normalized CPSE material descriptions
    using deterministic domain rules, regex parsers, and catalog lookups.
    Pure in-memory extraction without database persistence.
    """
    if not payload.raw_description or not payload.raw_description.strip():
        raise HTTPException(
            status_code=400,
            detail="raw_description cannot be empty or whitespace only."
        )

    standard_desc = build_standard_description(payload.raw_description)
    attrs, inferred_cat, confidence, missing_crit, notes = extract_attributes(
        raw_description=payload.raw_description,
        category=payload.category,
        uom=payload.uom,
    )

    return AttributeExtractionResponse(
        raw_description=payload.raw_description,
        standard_description=standard_desc,
        inferred_category=inferred_cat,
        extracted_attributes=attrs,
        missing_critical_attributes=missing_crit,
        extraction_confidence=confidence,
        extraction_notes=notes,
    )

@router.get("/batches/{batch_id}", response_model=IngestionBatchDetailResponse, tags=["Durable Material Ingestion"])
async def get_ingestion_batch(
    batch_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Retrieve durable ingestion batch metadata and paginated row errors.
    """
    batch = db.get(IngestionBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Ingestion batch '{batch_id}' not found.")

    offset = (page - 1) * limit
    errors = db.execute(
        select(IngestionRowError)
        .where(IngestionRowError.ingestion_batch_id == batch_id)
        .order_by(IngestionRowError.row_number.asc(), IngestionRowError.created_at.asc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()
    error_count = db.scalar(
        select(func.count()).select_from(IngestionRowError).where(IngestionRowError.ingestion_batch_id == batch_id)
    ) or 0

    return IngestionBatchDetailResponse(
        batch=IngestionBatchResponse.model_validate(batch),
        error_count=error_count,
        errors=[IngestionRowErrorResponse.model_validate(err) for err in errors],
        page=page,
        limit=limit,
    )

@router.get("", response_model=Dict[str, Any])
async def list_materials(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    category: Optional[str] = None,
    status: Optional[str] = None,
    batch_id: Optional[UUID] = Query(None, description="Optional durable ingestion batch ID"),
    db: Session = Depends(get_db),
):
    """
    Placeholder endpoint: List all ingested materials with pagination and filtering.
    """
    if batch_id is not None:
        batch = db.get(IngestionBatch, batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail=f"Ingestion batch '{batch_id}' not found.")

        offset = (page - 1) * limit
        stmt = (
            select(SourceMaterial)
            .where(SourceMaterial.ingestion_batch_id == batch_id)
            .order_by(SourceMaterial.created_at.asc(), SourceMaterial.source_material_code.asc())
            .offset(offset)
            .limit(limit)
        )
        items = db.execute(stmt).scalars().all()
        total = db.scalar(
            select(func.count()).select_from(SourceMaterial).where(SourceMaterial.ingestion_batch_id == batch_id)
        ) or 0
        return PersistedMaterialsPageResponse(
            batch_id=batch_id,
            count=len(items),
            total=total,
            page=page,
            limit=limit,
            items=[PersistedSourceMaterialResponse.model_validate(item) for item in items],
        ).model_dump(mode="json")

    filtered = PLACEHOLDER_MATERIALS
    if category:
        filtered = [m for m in filtered if m["category"].lower() == category.lower()]
    if status:
        filtered = [m for m in filtered if m["status"].lower() == status.lower()]

    return {
        "status": "success",
        "message": "Materials catalog retrieved successfully (placeholder mode)",
        "count": len(filtered),
        "total": len(PLACEHOLDER_MATERIALS),
        "page": page,
        "items": filtered
    }

@router.get("/{material_id}", response_model=Dict[str, Any])
async def get_material_detail(material_id: str):
    """
    Placeholder endpoint: Retrieve single material details and metadata.
    """
    for item in PLACEHOLDER_MATERIALS:
        if item["id"] == material_id:
            return {
                "status": "success",
                "message": "Material retrieved",
                "data": item
            }
    raise HTTPException(status_code=404, detail="Material ID not found")

@router.post("/upload", response_model=Dict[str, Any])
async def upload_materials_csv(file: UploadFile = File(...)):
    """
    Placeholder endpoint: Ingest bulk material catalogs from CSV/Excel.
    Actual parsing and staging will be plugged into Supabase in future sprints.
    """
    return {
        "status": "success",
        "message": f"File '{file.filename}' received successfully. Ingestion queued.",
        "placeholder_details": {
            "filename": file.filename,
            "content_type": file.content_type,
            "staged_records": 128,
            "status": "Awaiting AI Pipeline Deduplication"
        }
    }
