import csv
import hashlib
import io
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import IngestionBatch, IngestionRowError, SourceMaterial
from app.schemas.material import SourceMaterialResponse
from app.services.attribute_extraction import extract_attributes
from app.services.ingestion_preview import detect_columns, parse_csv_content
from app.services.normalization import (
    build_standard_description,
    normalize_category,
    normalize_punctuation,
    normalize_uom,
    tokenize_description,
)
from app.services.persistent_audit import append_audit_event


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _decode_csv(content_bytes: bytes) -> str:
    for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            return content_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content_bytes.decode("utf-8", errors="replace")


def _stable(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(key): _stable(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple, set)):
        return [_stable(item) for item in value]
    return value


def _content_hash(payload: Any) -> str:
    encoded = json.dumps(_stable(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _raw_row_contexts(content_bytes: bytes, default_cpse: Optional[str], default_system: Optional[str]) -> Dict[Tuple[str, str, str], List[Dict[str, Any]]]:
    content = _decode_csv(content_bytes)
    f = io.StringIO(content.strip())
    reader = csv.DictReader(f)
    if not reader.fieldnames:
        return {}

    column_mapping = detect_columns([h.strip() for h in reader.fieldnames if h and h.strip()])
    contexts: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for row_number, row in enumerate(reader, start=2):
        extracted: Dict[str, str] = {}
        for raw_col, val in row.items():
            if raw_col in column_mapping:
                extracted[column_mapping[raw_col]] = str(val).strip() if val is not None else ""

        source_code = extracted.get("source_material_code") or ""
        raw_desc = extracted.get("raw_description") or ""
        if not source_code or not raw_desc:
            continue

        source_cpse = extracted.get("source_cpse") or default_cpse or "UNSPECIFIED_CPSE"
        source_system = extracted.get("source_system") or default_system or "CSV_INGESTION"
        key = (source_cpse, source_system, source_code)
        contexts.setdefault(key, []).append({"row_number": row_number, "raw_data": row})
    return contexts


def _next_row_context(contexts: Dict[Tuple[str, str, str], List[Dict[str, Any]]], key: Tuple[str, str, str]) -> Dict[str, Any]:
    values = contexts.get(key) or []
    if values:
        return values.pop(0)
    return {"row_number": None, "raw_data": {}}


def _resolved_origin(preview, source_cpse: Optional[str], source_system: Optional[str]) -> Tuple[str, str]:
    cpse = source_cpse or preview.summary.source_cpse_detected
    system = source_system or preview.summary.source_system_detected
    if not cpse and preview.valid_records:
        cpse = preview.valid_records[0].source_cpse
    if not system and preview.valid_records:
        system = preview.valid_records[0].source_system
    return cpse or "UNSPECIFIED_CPSE", system or "CSV_INGESTION"


def _status(processed: int, failed: int) -> str:
    if processed > 0 and failed == 0:
        return "COMPLETED"
    if processed > 0 and failed > 0:
        return "COMPLETED_WITH_ERRORS"
    return "FAILED"


@dataclass
class CanonicalIngestionRecord:
    source_cpse: str
    source_system: str
    source_material_code: str
    raw_description: str
    cleaned_description: str
    standard_description: str
    category: str
    sub_category: str
    material_type: Optional[str]
    material_grade: Optional[str]
    manufacturer: Optional[str]
    part_number: Optional[str]
    model_number: Optional[str]
    uom: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    normalized_tokens: List[str] = field(default_factory=list)
    match_status: str = "UNPROCESSED"
    approval_status: str = "PENDING_INGESTION"
    row_number: int = 0
    raw_data: Dict[str, Any] = field(default_factory=dict)
    metadata_json: Dict[str, Any] = field(default_factory=dict)


def source_material_to_ingestion_record(record: SourceMaterialResponse, *, row_number: int = 0, raw_data: Optional[Dict[str, Any]] = None) -> CanonicalIngestionRecord:
    return CanonicalIngestionRecord(
        source_cpse=record.source_cpse,
        source_system=record.source_system,
        source_material_code=record.source_material_code,
        raw_description=record.raw_description,
        cleaned_description=record.cleaned_description or normalize_punctuation(record.raw_description).lower(),
        standard_description=record.standard_description or build_standard_description(record.raw_description),
        category=record.category,
        sub_category=record.sub_category,
        material_type=record.material_type,
        material_grade=record.material_grade,
        manufacturer=record.manufacturer,
        part_number=record.part_number,
        model_number=record.model_number,
        uom=record.uom,
        attributes=record.attributes or {},
        normalized_tokens=record.normalized_tokens or [],
        match_status=_enum_value(record.match_status),
        approval_status=_enum_value(record.approval_status),
        row_number=row_number,
        raw_data=raw_data or {},
    )


def build_ingestion_record(
    *,
    source_cpse: str,
    source_system: str,
    source_material_code: str,
    raw_description: str,
    uom: Optional[str] = None,
    category: Optional[str] = None,
    manufacturer: Optional[str] = None,
    part_number: Optional[str] = None,
    model_number: Optional[str] = None,
    material_type: Optional[str] = None,
    material_grade: Optional[str] = None,
    row_number: int = 0,
    raw_data: Optional[Dict[str, Any]] = None,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> CanonicalIngestionRecord:
    normalized_uom = normalize_uom(uom)
    normalized_category = normalize_category(category)
    attrs, inferred_category, _confidence, _missing, _notes = extract_attributes(
        raw_description=raw_description,
        category=normalized_category,
        uom=normalized_uom,
    )
    final_category = normalize_category(category or inferred_category)
    standard_description = build_standard_description(raw_description)
    return CanonicalIngestionRecord(
        source_cpse=source_cpse or "UNSPECIFIED_CPSE",
        source_system=source_system or "ERP_INTEGRATION",
        source_material_code=source_material_code.strip(),
        raw_description=raw_description.strip(),
        cleaned_description=normalize_punctuation(raw_description).lower(),
        standard_description=standard_description,
        category=final_category,
        sub_category=str(attrs.get("sub_category") or final_category or "UNASSIGNED"),
        material_type=material_type or attrs.get("material_type"),
        material_grade=material_grade or attrs.get("material_grade") or attrs.get("grade"),
        manufacturer=manufacturer.strip() if manufacturer else None,
        part_number=part_number.strip() if part_number else None,
        model_number=model_number.strip() if model_number else None,
        uom=normalized_uom,
        attributes=attrs,
        normalized_tokens=tokenize_description(standard_description),
        row_number=row_number,
        raw_data=raw_data or {},
        metadata_json=metadata_json or {},
    )


def ingest_canonical_records(
    db: Session,
    *,
    records: List[CanonicalIngestionRecord],
    batch_name: str,
    source_cpse: str,
    source_system: str,
    source_name: str,
    content_hash: Optional[str] = None,
    uploaded_by: str = "SYSTEM",
    batch_metadata: Optional[Dict[str, Any]] = None,
    invalid_rows: Optional[List[Dict[str, Any]]] = None,
    audit_actor: str = "SYSTEM",
    audit_action: str = "MATERIALS_INGESTED",
    audit_reason: str = "Material ingestion completed and source materials were persisted.",
    emit_audit: bool = True,
    commit: bool = True,
) -> Tuple[IngestionBatch, bool, int]:
    file_hash = content_hash or _content_hash(
        {
            "records": [record.__dict__ for record in records],
            "source_cpse": source_cpse,
            "source_system": source_system,
            "source_name": source_name,
        }
    )

    existing_batch = db.execute(
        select(IngestionBatch).where(
            IngestionBatch.file_hash_sha256 == file_hash,
            IngestionBatch.source_cpse == source_cpse,
            IngestionBatch.source_system == source_system,
        )
    ).scalar_one_or_none()
    if existing_batch:
        error_count = db.scalar(
            select(func.count()).select_from(IngestionRowError).where(
                IngestionRowError.ingestion_batch_id == existing_batch.id
            )
        ) or 0
        return existing_batch, True, error_count

    invalid_rows = invalid_rows or []
    batch = IngestionBatch(
        batch_name=batch_name,
        source_cpse=source_cpse,
        source_system=source_system,
        file_name=source_name,
        file_hash_sha256=file_hash,
        uploaded_by=uploaded_by,
        total_records=len(records) + len(invalid_rows),
        processed_records=0,
        failed_records=0,
        status="INGESTING",
        error_summary={},
        metadata_json=batch_metadata or {},
    )
    db.add(batch)
    db.flush()

    error_count = 0
    for invalid in invalid_rows:
        db.add(IngestionRowError(
            ingestion_batch_id=batch.id,
            row_number=int(invalid.get("row_number") or 0),
            source_material_code=invalid.get("source_material_code"),
            raw_data=invalid.get("raw_data") or {},
            reason=invalid.get("reason") or "Invalid source material record",
        ))
        error_count += 1

    seen_keys = set()
    processed = 0
    for record in records:
        key = (record.source_cpse, record.source_system, record.source_material_code)
        reason = None
        if not record.source_material_code or not record.raw_description:
            reason = "Missing required source material code or description"
        elif key in seen_keys:
            reason = "Duplicate source material code within ingestion payload"
        else:
            existing_material = db.execute(
                select(SourceMaterial.id).where(
                    SourceMaterial.source_cpse == record.source_cpse,
                    SourceMaterial.source_system == record.source_system,
                    SourceMaterial.source_material_code == record.source_material_code,
                )
            ).scalar_one_or_none()
            if existing_material:
                reason = "Source material already exists for source_cpse/source_system/source_material_code"

        if reason:
            db.add(IngestionRowError(
                ingestion_batch_id=batch.id,
                row_number=record.row_number or 0,
                source_material_code=record.source_material_code,
                raw_data=record.raw_data or {},
                reason=reason,
            ))
            error_count += 1
            seen_keys.add(key)
            continue

        seen_keys.add(key)
        db.add(SourceMaterial(
            ingestion_batch_id=batch.id,
            source_cpse=record.source_cpse,
            source_system=record.source_system,
            source_material_code=record.source_material_code,
            raw_description=record.raw_description,
            cleaned_description=record.cleaned_description,
            standard_description=record.standard_description,
            category=record.category,
            sub_category=record.sub_category,
            material_type=record.material_type,
            material_grade=record.material_grade,
            manufacturer=record.manufacturer,
            part_number=record.part_number,
            model_number=record.model_number,
            uom=record.uom,
            attributes=record.attributes,
            normalized_tokens=record.normalized_tokens,
            metadata_json={
                **(record.metadata_json or {}),
                "row_number": record.row_number,
                "raw_data": record.raw_data,
                "source_name": source_name,
                "file_hash_sha256": file_hash,
            },
            match_status=record.match_status,
            approval_status=record.approval_status,
        ))
        processed += 1

    batch.processed_records = processed
    batch.failed_records = error_count
    batch.status = _status(processed, error_count)
    batch.error_summary = {"error_count": error_count}
    batch.completed_at = datetime.now(timezone.utc)
    if emit_audit:
        append_audit_event(
            db,
            actor=audit_actor,
            actor_role="SYSTEM_PROCESS",
            action=audit_action,
            entity_type="ingestion_batch",
            entity_id=str(batch.id),
            old_value=None,
            new_value={
                "batch_id": batch.id,
                "source_name": batch.file_name,
                "file_hash_sha256": batch.file_hash_sha256,
                "source_cpse": batch.source_cpse,
                "source_system": batch.source_system,
                "total_records": batch.total_records,
                "processed_records": batch.processed_records,
                "failed_records": batch.failed_records,
                "status": batch.status,
            },
            reason=audit_reason,
        )
    if commit:
        db.commit()
        db.refresh(batch)
    return batch, False, error_count


def ingest_csv_content(
    db: Session,
    *,
    content_bytes: bytes,
    file_name: str,
    source_cpse: Optional[str] = None,
    source_system: Optional[str] = None,
) -> Tuple[IngestionBatch, bool, int]:
    file_hash = hashlib.sha256(content_bytes).hexdigest()
    preview = parse_csv_content(
        csv_text_or_bytes=content_bytes,
        default_cpse=source_cpse,
        default_system=source_system,
        file_name=file_name,
    )
    resolved_cpse, resolved_system = _resolved_origin(preview, source_cpse, source_system)

    contexts = _raw_row_contexts(content_bytes, source_cpse, source_system)
    records: List[CanonicalIngestionRecord] = []
    for record in preview.valid_records:
        key = (record.source_cpse, record.source_system, record.source_material_code)
        context = _next_row_context(contexts, key)
        records.append(source_material_to_ingestion_record(
            record,
            row_number=context.get("row_number") or 0,
            raw_data=context.get("raw_data") or {},
        ))

    invalid_rows = [
        {
            "row_number": invalid.row_number,
            "source_material_code": invalid.item_code,
            "raw_data": invalid.raw_data,
            "reason": invalid.reason,
        }
        for invalid in preview.invalid_rows
    ]
    return ingest_canonical_records(
        db,
        records=records,
        batch_name=f"INGEST-{file_hash[:12]}",
        source_cpse=resolved_cpse,
        source_system=resolved_system,
        source_name=file_name,
        content_hash=file_hash,
        uploaded_by="CSV_UPLOAD",
        batch_metadata={
            "detected_columns": preview.detected_columns,
            "mapped_columns": preview.mapped_columns,
        },
        invalid_rows=invalid_rows,
        audit_actor="CSV_UPLOAD",
        audit_action="MATERIALS_INGESTED",
        audit_reason="CSV ingestion completed and source materials were persisted.",
        emit_audit=True,
        commit=True,
    )
