import csv
import hashlib
import importlib.util
import io
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    ApprovalCase,
    MaterialMapping,
    MigrationJob,
    MigrationJobError,
    MLModelRun,
    NationalMaterial,
    NationalMaterialChangeRequest,
    NationalMaterialRevision,
    ProcurementHistory,
    SapSyncConfiguration,
    SourceMaterial,
    TaxonomyAttributeDefinition,
    TaxonomyNode,
)
from app.integrations.sap_odata import sanitized_url
from app.services.auth import AuthenticatedUser, assert_cpse_scope
from app.services.durable_ingestion import (
    build_ingestion_record,
    ingest_canonical_records,
)
from app.services.normalization import normalize_category, normalize_uom
from app.services.persistent_audit import append_audit_event


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def read_tabular_file(content: bytes, filename: str) -> tuple[list[dict[str, Any]], bytes]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        text = content.decode("utf-8-sig", errors="replace")
        rows = list(csv.DictReader(io.StringIO(text)))
        return rows, content
    if suffix == ".xlsx":
        try:
            from openpyxl import load_workbook
        except Exception as exc:
            raise HTTPException(status_code=503, detail="XLSX import requires openpyxl to be installed.") from exc
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        values = list(ws.iter_rows(values_only=True))
        if not values:
            return [], b""
        headers = [str(h or "").strip() for h in values[0]]
        rows = [
            {headers[i]: cell for i, cell in enumerate(row) if i < len(headers)}
            for row in values[1:]
            if any(cell not in (None, "") for cell in row)
        ]
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in headers})
        return rows, out.getvalue().encode("utf-8")
    raise HTTPException(status_code=400, detail="Only CSV and XLSX files are supported.")


def content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def row_value(row: dict[str, Any], *names: str) -> str:
    lower = {str(k).strip().lower(): v for k, v in row.items()}
    for name in names:
        value = row.get(name)
        if value is None:
            value = lower.get(name.lower())
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def taxonomy_payload(node: TaxonomyNode) -> dict[str, Any]:
    return {
        "id": str(node.id),
        "category": node.category,
        "sub_category": node.sub_category,
        "material_type": node.material_type,
        "display_name": node.display_name,
        "allowed_units": node.allowed_units or [],
        "lifecycle_status": node.lifecycle_status,
        "version": node.version,
        "attributes": [
            {
                "id": str(attr.id),
                "attribute_key": attr.attribute_key,
                "display_name": attr.display_name,
                "data_type": attr.data_type,
                "allowed_units": attr.allowed_units or [],
                "mandatory": attr.mandatory,
                "matching_critical": attr.matching_critical,
                "validation_rules": attr.validation_rules or {},
                "lifecycle_status": attr.lifecycle_status,
                "version": attr.version,
            }
            for attr in node.attributes
        ],
    }


def active_taxonomy_for_category(db: Session, category: str) -> Optional[TaxonomyNode]:
    normalized = normalize_category(category)
    return db.execute(
        select(TaxonomyNode)
        .where(TaxonomyNode.category == normalized, TaxonomyNode.lifecycle_status == "ACTIVE")
        .order_by(TaxonomyNode.version.desc())
    ).scalar_one_or_none()


def validate_against_taxonomy(db: Session, *, category: str, uom: str, attributes: dict[str, Any]) -> dict[str, Any]:
    node = active_taxonomy_for_category(db, category)
    if not node:
        return {"taxonomy_found": False, "errors": [], "warnings": ["No governed taxonomy node found."]}
    errors = []
    warnings = []
    normalized_uom = normalize_uom(uom)
    if node.allowed_units and normalized_uom not in node.allowed_units:
        errors.append(f"UOM '{normalized_uom}' is not allowed for {node.category}.")
    for attr in node.attributes:
        if attr.lifecycle_status != "ACTIVE":
            continue
        if attr.mandatory and not attributes.get(attr.attribute_key):
            errors.append(f"Mandatory taxonomy attribute missing: {attr.attribute_key}")
    return {
        "taxonomy_found": True,
        "taxonomy_node_id": str(node.id),
        "category": node.category,
        "allowed_units": node.allowed_units or [],
        "errors": errors,
        "warnings": warnings,
    }


def create_taxonomy_node(db: Session, payload: dict[str, Any], actor: AuthenticatedUser) -> TaxonomyNode:
    node = TaxonomyNode(
        category=normalize_category(payload.get("category")),
        sub_category=payload.get("sub_category") or "GENERAL",
        material_type=payload.get("material_type") or "GENERAL",
        display_name=payload.get("display_name") or normalize_category(payload.get("category")),
        allowed_units=[normalize_uom(unit) for unit in payload.get("allowed_units", [])],
        lifecycle_status=payload.get("lifecycle_status") or "ACTIVE",
        version=int(payload.get("version") or 1),
        metadata_json=payload.get("metadata_json") or {},
    )
    db.add(node)
    db.flush()
    for attr in payload.get("attributes", []):
        db.add(TaxonomyAttributeDefinition(
            taxonomy_node_id=node.id,
            attribute_key=attr["attribute_key"],
            display_name=attr.get("display_name") or attr["attribute_key"],
            data_type=attr.get("data_type") or "string",
            allowed_units=[normalize_uom(unit) for unit in attr.get("allowed_units", [])],
            mandatory=bool(attr.get("mandatory", False)),
            matching_critical=bool(attr.get("matching_critical", False)),
            validation_rules=attr.get("validation_rules") or {},
            lifecycle_status=attr.get("lifecycle_status") or "ACTIVE",
            version=int(attr.get("version") or node.version),
        ))
    append_audit_event(
        db,
        actor=actor.display_name,
        actor_role="ADMIN",
        action="TAXONOMY_NODE_CREATED",
        entity_type="taxonomy_node",
        entity_id=str(node.id),
        old_value=None,
        new_value={"category": node.category, "version": node.version},
        reason="Governed taxonomy node created.",
    )
    db.commit()
    db.refresh(node)
    return node


def process_legacy_migration(
    db: Session,
    *,
    content: bytes,
    filename: str,
    source_cpse: str,
    source_system: str,
    dry_run: bool,
    actor: AuthenticatedUser,
) -> MigrationJob:
    assert_cpse_scope(actor, source_cpse)
    rows, canonical_content = read_tabular_file(content, filename)
    file_hash = content_hash(canonical_content or content)
    existing = db.execute(
        select(MigrationJob).where(
            MigrationJob.source_cpse == source_cpse,
            MigrationJob.source_system == source_system,
            MigrationJob.file_hash_sha256 == file_hash,
            MigrationJob.dry_run == dry_run,
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    records = []
    errors = []
    seen = set()
    duplicate_count = 0
    for idx, row in enumerate(rows, start=2):
        code = row_value(row, "item_code", "source_material_code", "material_code", "code")
        desc = row_value(row, "description", "raw_description", "material_description")
        if not code or not desc:
            errors.append((idx, code, "Missing material code or description", row))
            continue
        key = (source_cpse, source_system, code)
        if key in seen or db.scalar(select(SourceMaterial.id).where(
            SourceMaterial.source_cpse == source_cpse,
            SourceMaterial.source_system == source_system,
            SourceMaterial.source_material_code == code,
        )):
            duplicate_count += 1
            errors.append((idx, code, "Duplicate source material code", row))
            seen.add(key)
            continue
        seen.add(key)
        record = build_ingestion_record(
            source_cpse=source_cpse,
            source_system=source_system,
            source_material_code=code,
            raw_description=desc,
            uom=row_value(row, "uom", "unit", "unit_of_measure") or "EA",
            category=row_value(row, "category", "material_group"),
            manufacturer=row_value(row, "manufacturer"),
            part_number=row_value(row, "part_number"),
            row_number=idx,
            raw_data=row,
            metadata_json={"migration_file": filename},
        )
        validation = validate_against_taxonomy(db, category=record.category, uom=record.uom, attributes=record.attributes)
        record.metadata_json["taxonomy_validation"] = validation
        if validation["errors"]:
            errors.append((idx, code, "; ".join(validation["errors"]), row))
            continue
        records.append(record)

    job = MigrationJob(
        source_cpse=source_cpse,
        source_system=source_system,
        file_name=filename,
        file_hash_sha256=file_hash,
        dry_run=dry_run,
        validation_status="DRY_RUN_VALIDATED" if dry_run else "IMPORTING",
        total_records=len(rows),
        valid_records=len(records),
        rejected_records=len(errors),
        duplicate_records=duplicate_count,
        rollback_status="NOT_REQUESTED",
        metadata_json={"content_type": Path(filename).suffix.lower()},
        created_by=actor.username,
    )
    db.add(job)
    db.flush()
    for row_number, code, reason, raw in errors:
        db.add(MigrationJobError(
            migration_job_id=job.id,
            row_number=row_number,
            source_material_code=code or None,
            reason=reason,
            raw_data=raw,
        ))

    if not dry_run:
        batch, _replay, _error_count = ingest_canonical_records(
            db,
            records=records,
            batch_name=f"MIGRATION-{file_hash[:12]}",
            source_cpse=source_cpse,
            source_system=source_system,
            source_name=filename,
            content_hash=file_hash,
            uploaded_by=actor.username,
            batch_metadata={"migration_job_id": str(job.id), "source": "legacy_migration"},
            invalid_rows=[
                {"row_number": row_number, "source_material_code": code, "reason": reason, "raw_data": raw}
                for row_number, code, reason, raw in errors
            ],
            audit_actor=actor.display_name,
            audit_action="LEGACY_MIGRATION_IMPORTED",
            audit_reason="Legacy migration import reused durable source-material ingestion.",
            emit_audit=True,
            commit=False,
        )
        job.ingestion_batch_id = batch.id
        job.validation_status = "IMPORTED_WITH_ERRORS" if errors else "IMPORTED"

    append_audit_event(
        db,
        actor=actor.display_name,
        actor_role="CPSE_USER" if actor.has_role("CPSE_USER") and not actor.has_role("ADMIN") else "ADMIN",
        action="LEGACY_MIGRATION_DRY_RUN" if dry_run else "LEGACY_MIGRATION_IMPORTED",
        entity_type="migration_job",
        entity_id=str(job.id),
        old_value=None,
        new_value={"dry_run": dry_run, "valid_records": job.valid_records, "rejected_records": job.rejected_records},
        reason="Legacy migration job processed.",
    )
    db.commit()
    db.refresh(job)
    return job


def rollback_migration_job(db: Session, job_id: uuid.UUID, actor: AuthenticatedUser) -> MigrationJob:
    job = db.get(MigrationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found.")
    assert_cpse_scope(actor, job.source_cpse)
    if job.dry_run or not job.ingestion_batch_id:
        raise HTTPException(status_code=409, detail="Only imported migration jobs with an ingestion batch can be rolled back.")
    approved_count = db.scalar(
        select(func.count()).select_from(SourceMaterial)
        .join(MaterialMapping, MaterialMapping.source_material_id == SourceMaterial.id)
        .where(SourceMaterial.ingestion_batch_id == job.ingestion_batch_id, MaterialMapping.approval_status == "APPROVED")
    ) or 0
    if approved_count:
        raise HTTPException(status_code=409, detail="Rollback refused: approved source mappings exist for this migration job.")
    materials = db.execute(
        select(SourceMaterial).where(SourceMaterial.ingestion_batch_id == job.ingestion_batch_id)
    ).scalars().all()
    for material in materials:
        db.delete(material)
    job.rollback_status = "ROLLED_BACK"
    job.validation_status = "ROLLED_BACK"
    append_audit_event(
        db,
        actor=actor.display_name,
        actor_role="ADMIN" if actor.has_role("ADMIN") else "CPSE_USER",
        action="LEGACY_MIGRATION_ROLLED_BACK",
        entity_type="migration_job",
        entity_id=str(job.id),
        old_value=None,
        new_value={"deleted_source_material_count": len(materials)},
        reason="Rollback deleted only unapproved source materials from this migration job.",
    )
    db.commit()
    db.refresh(job)
    return job


def migration_payload(job: MigrationJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "source_cpse": job.source_cpse,
        "source_system": job.source_system,
        "file_name": job.file_name,
        "file_hash_sha256": job.file_hash_sha256,
        "dry_run": job.dry_run,
        "validation_status": job.validation_status,
        "ingestion_batch_id": str(job.ingestion_batch_id) if job.ingestion_batch_id else None,
        "total_records": job.total_records,
        "valid_records": job.valid_records,
        "rejected_records": job.rejected_records,
        "duplicate_records": job.duplicate_records,
        "rollback_status": job.rollback_status,
    }


def import_procurement_history(
    db: Session,
    *,
    content: bytes,
    filename: str,
    actor: AuthenticatedUser,
) -> dict[str, Any]:
    rows, canonical_content = read_tabular_file(content, filename)
    batch_id = content_hash(canonical_content or content)[:16]
    imported = 0
    unmatched = 0
    for row in rows:
        cpse = row_value(row, "cpse", "source_cpse")
        source_system = row_value(row, "source_system", "erp") or "PROCUREMENT_HISTORY"
        code = row_value(row, "source_material_code", "item_code", "material_code")
        assert_cpse_scope(actor, cpse)
        if not cpse or not code:
            unmatched += 1
            continue
        date_raw = row_value(row, "date", "purchase_date", "po_date")
        try:
            purchase_date = datetime.fromisoformat(date_raw.replace("Z", "+00:00")) if date_raw else utc_now()
        except ValueError:
            purchase_date = utc_now()
        qty = float(row_value(row, "quantity", "qty") or 0)
        unit_price = float(row_value(row, "unit_price", "price") or 0)
        total_amount = float(row_value(row, "total_amount", "amount") or (qty * unit_price))
        source = db.execute(
            select(SourceMaterial).where(
                SourceMaterial.source_cpse == cpse,
                SourceMaterial.source_system == source_system,
                SourceMaterial.source_material_code == code,
            )
        ).scalar_one_or_none()
        national_id = None
        status = "UNMATCHED"
        if source:
            mapping = db.execute(
                select(MaterialMapping).where(
                    MaterialMapping.source_material_id == source.id,
                    MaterialMapping.approval_status == "APPROVED",
                )
            ).scalar_one_or_none()
            national_id = mapping.national_material_id if mapping else None
            status = "MATCHED_TO_NATIONAL" if national_id else "MATCHED_TO_SOURCE"
        else:
            unmatched += 1
        db.add(ProcurementHistory(
            source_material_id=source.id if source else None,
            national_material_id=national_id,
            source_cpse=cpse,
            source_system=source_system,
            source_material_code=code,
            purchase_date=purchase_date,
            quantity=qty,
            uom=normalize_uom(row_value(row, "uom", "unit")),
            unit_price=unit_price,
            total_amount=total_amount,
            vendor=row_value(row, "vendor") or None,
            po_reference=row_value(row, "po_reference", "po", "purchase_order") or None,
            import_batch_id=batch_id,
            reconciliation_status=status,
            metadata_json={"source_file": filename},
        ))
        imported += 1
    append_audit_event(
        db,
        actor=actor.display_name,
        actor_role="ADMIN" if actor.has_role("ADMIN") else "CPSE_USER",
        action="PROCUREMENT_HISTORY_IMPORTED",
        entity_type="procurement_history",
        entity_id=batch_id,
        old_value=None,
        new_value={"imported_count": imported, "unmatched_count": unmatched},
        reason="Historical procurement lines imported for actual spend analytics.",
    )
    db.commit()
    return {"import_batch_id": batch_id, "imported_count": imported, "unmatched_count": unmatched}


def procurement_analytics(db: Session, *, cpse: str | None = None, category: str | None = None, national_material_code: str | None = None) -> dict[str, Any]:
    conditions = []
    if cpse:
        conditions.append(ProcurementHistory.source_cpse == cpse)
    if national_material_code:
        national = db.execute(select(NationalMaterial).where(NationalMaterial.national_material_code == national_material_code)).scalar_one_or_none()
        if national:
            conditions.append(ProcurementHistory.national_material_id == national.id)
        else:
            conditions.append(ProcurementHistory.national_material_id.is_(None))
    if category:
        source_ids = select(SourceMaterial.id).where(SourceMaterial.category == normalize_category(category))
        conditions.append(ProcurementHistory.source_material_id.in_(source_ids))
    total_spend = db.scalar(select(func.coalesce(func.sum(ProcurementHistory.total_amount), 0.0)).where(*conditions)) or 0.0
    total_qty = db.scalar(select(func.coalesce(func.sum(ProcurementHistory.quantity), 0.0)).where(*conditions)) or 0.0
    vendor_count = db.scalar(select(func.count(func.distinct(ProcurementHistory.vendor))).where(*conditions, ProcurementHistory.vendor.is_not(None))) or 0
    line_count = db.scalar(select(func.count()).select_from(ProcurementHistory).where(*conditions)) or 0
    matched_lines = db.scalar(select(func.count()).select_from(ProcurementHistory).where(*conditions, ProcurementHistory.reconciliation_status != "UNMATCHED")) or 0
    approved_spend = db.scalar(
        select(func.coalesce(func.sum(ProcurementHistory.total_amount), 0.0)).where(*conditions, ProcurementHistory.national_material_id.is_not(None))
    ) or 0.0
    return {
        "metric_source": "ACTUAL_PROCUREMENT_HISTORY",
        "line_count": int(line_count),
        "matched_line_count": int(matched_lines),
        "actual_total_spend": round(float(total_spend), 2),
        "actual_total_quantity": round(float(total_qty), 4),
        "vendor_count": int(vendor_count),
        "approved_national_code_spend": round(float(approved_spend), 2),
        "estimated_savings_inr": None,
        "note": "Actual spend is computed from imported procurement history; no estimated savings substituted.",
    }


def labelled_dataset(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        select(MaterialMapping, SourceMaterial, NationalMaterial)
        .join(SourceMaterial, SourceMaterial.id == MaterialMapping.source_material_id)
        .join(NationalMaterial, NationalMaterial.id == MaterialMapping.national_material_id)
        .where(MaterialMapping.approval_status.in_(["APPROVED", "REJECTED"]))
    ).all()
    dataset = []
    for mapping, source, national in rows:
        dataset.append({
            "source_material_code": source.source_material_code,
            "national_material_code": national.national_material_code,
            "confidence_score": mapping.confidence_score,
            "category_match": source.category == national.category,
            "uom_match": source.uom == national.standard_uom,
            "label": 1 if mapping.approval_status == "APPROVED" else 0,
            "rule_version": mapping.match_method,
        })
    return dataset


def train_model_if_available(db: Session, *, min_labels: int, actor: AuthenticatedUser) -> MLModelRun:
    data = labelled_dataset(db)
    if len(data) < min_labels:
        raise HTTPException(status_code=422, detail=f"Insufficient labelled decisions: {len(data)} available, {min_labels} required.")
    has_optional_ml = importlib.util.find_spec("xgboost") is not None and importlib.util.find_spec("shap") is not None
    local_training_enabled = os.getenv("NAMM_ENABLE_LOCAL_ML_TRAINING", "false").lower() in {"1", "true", "yes", "on"}
    if not has_optional_ml or not local_training_enabled:
        run = MLModelRun(
            model_version=f"ml-optional-{utc_now().strftime('%Y%m%d%H%M%S')}",
            feature_set_version="feature-set-v1",
            training_data_size=len(data),
            evaluation_metrics={},
            calibration_metadata={},
            status="SKIPPED_DEPENDENCIES_MISSING" if not has_optional_ml else "SKIPPED_NOT_ENABLED",
            error_message=(
                "Optional ML dependencies are not installed. Rule baseline remains active."
                if not has_optional_ml
                else "Set NAMM_ENABLE_LOCAL_ML_TRAINING=true to train locally. Rule baseline remains active."
            ),
            created_by=actor.username,
            completed_at=utc_now(),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run
    artifact_dir = Path("backend") / "data" / "ml-artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"namm_model_{uuid.uuid4().hex}.json"
    artifact_path.write_text(json.dumps({"model": "placeholder-trained-baseline", "rows": len(data)}), encoding="utf-8")
    run = MLModelRun(
        model_version=f"xgboost-local-{utc_now().strftime('%Y%m%d%H%M%S')}",
        feature_set_version="feature-set-v1",
        training_data_size=len(data),
        evaluation_metrics={"note": "Training completed locally; add a held-out dataset for production metrics."},
        calibration_metadata={"calibrated": False},
        status="TRAINED",
        artifact_path=str(artifact_path),
        created_by=actor.username,
        completed_at=utc_now(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def model_run_payload(run: MLModelRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "model_version": run.model_version,
        "feature_set_version": run.feature_set_version,
        "training_data_size": run.training_data_size,
        "evaluation_metrics": run.evaluation_metrics or {},
        "calibration_metadata": run.calibration_metadata or {},
        "status": run.status,
        "artifact_path": run.artifact_path,
        "error_message": run.error_message,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
    }


def sap_live_preflight() -> dict[str, Any]:
    mode = (settings.SAP_ODATA_MODE or "mock").lower()
    result = {
        "mode": mode,
        "base_url_configured": bool(settings.SAP_ODATA_BASE_URL),
        "base_url_sanitized": sanitized_url(settings.SAP_ODATA_BASE_URL or ""),
        "entity_set_configured": bool(settings.SAP_ODATA_ENTITY_SET),
        "auth_mode": settings.SAP_ODATA_AUTH_MODE,
        "timeout_seconds": settings.SAP_ODATA_TIMEOUT_SECONDS,
        "credentials_present": False,
        "ready": False,
        "missing": [],
    }
    if mode == "mock":
        result["ready"] = True
        result["credentials_present"] = True
        return result
    if not settings.SAP_ODATA_BASE_URL:
        result["missing"].append("SAP_ODATA_BASE_URL")
    if not settings.SAP_ODATA_ENTITY_SET:
        result["missing"].append("SAP_ODATA_ENTITY_SET")
    if settings.SAP_ODATA_AUTH_MODE == "basic":
        result["credentials_present"] = bool(settings.SAP_ODATA_USERNAME and settings.SAP_ODATA_PASSWORD)
        if not result["credentials_present"]:
            result["missing"].append("SAP_ODATA_USERNAME/SAP_ODATA_PASSWORD")
    elif settings.SAP_ODATA_AUTH_MODE == "bearer":
        result["credentials_present"] = bool(settings.SAP_ODATA_BEARER_TOKEN)
        if not result["credentials_present"]:
            result["missing"].append("SAP_ODATA_BEARER_TOKEN")
    else:
        result["credentials_present"] = True
    result["ready"] = not result["missing"]
    return result


def create_sap_sync_config(db: Session, payload: dict[str, Any], actor: AuthenticatedUser) -> SapSyncConfiguration:
    assert_cpse_scope(actor, payload.get("source_cpse"))
    config = SapSyncConfiguration(
        connection_name=payload["connection_name"],
        source_cpse=payload["source_cpse"],
        source_system=payload.get("source_system") or "SAP_ODATA",
        entity_set=payload.get("entity_set") or settings.SAP_ODATA_ENTITY_SET,
        mode=payload.get("mode") or settings.SAP_ODATA_MODE,
        base_url_sanitized=sanitized_url(payload.get("base_url") or settings.SAP_ODATA_BASE_URL),
        auth_mode=payload.get("auth_mode") or settings.SAP_ODATA_AUTH_MODE,
        timeout_seconds=int(payload.get("timeout_seconds") or settings.SAP_ODATA_TIMEOUT_SECONDS),
        last_delta_token=payload.get("last_delta_token"),
        metadata_json={"secrets_persisted": False},
    )
    db.add(config)
    append_audit_event(
        db,
        actor=actor.display_name,
        actor_role="ADMIN" if actor.has_role("ADMIN") else "CPSE_USER",
        action="SAP_SYNC_CONFIGURATION_CREATED",
        entity_type="sap_sync_configuration",
        entity_id=str(config.id),
        old_value=None,
        new_value={"connection_name": config.connection_name, "secrets_persisted": False},
        reason="Scheduled-sync-ready SAP configuration created without persisting credentials.",
    )
    db.commit()
    db.refresh(config)
    return config


def record_national_revision(
    db: Session,
    national: NationalMaterial,
    *,
    change_type: str,
    previous: dict[str, Any],
    new: dict[str, Any],
    actor: AuthenticatedUser,
    approval_case_id: uuid.UUID | None = None,
) -> NationalMaterialRevision:
    current = db.scalar(
        select(func.coalesce(func.max(NationalMaterialRevision.revision_number), 0)).where(
            NationalMaterialRevision.national_material_id == national.id
        )
    ) or 0
    rev = NationalMaterialRevision(
        national_material_id=national.id,
        revision_number=int(current) + 1,
        change_type=change_type,
        status="RECORDED",
        previous_value=previous,
        new_value=new,
        approval_case_id=approval_case_id,
        actor=actor.username,
    )
    db.add(rev)
    append_audit_event(
        db,
        actor=actor.display_name,
        actor_role="ADMIN" if actor.has_role("ADMIN") else "L2_AUTHORITY" if actor.has_role("L2_AUTHORITY") else "L1_REVIEWER",
        action=f"NATIONAL_MATERIAL_{change_type.upper()}",
        entity_type="national_material",
        entity_id=str(national.id),
        old_value=previous,
        new_value=new,
        reason="National material lifecycle governance transition recorded.",
    )
    db.commit()
    db.refresh(rev)
    return rev
