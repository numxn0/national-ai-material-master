import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IngestionBatch, IntegrationImportRun
from app.integrations.sap_odata import (
    CONNECTOR_TYPE,
    ConnectorConfigurationError,
    ConnectorRequestError,
    get_sap_connector,
    sanitized_error,
)
from app.services.durable_ingestion import build_ingestion_record, ingest_canonical_records
from app.services.persistent_audit import append_audit_event


class SapImportError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _odata_value(row: Dict[str, Any], *names: str) -> Optional[str]:
    lower = {str(key).lower(): value for key, value in row.items()}
    for name in names:
        value = row.get(name)
        if value is None:
            value = lower.get(name.lower())
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _run_payload(run: IntegrationImportRun) -> Dict[str, Any]:
    return {
        "id": run.id,
        "connector_type": run.connector_type,
        "connector_mode": run.connector_mode,
        "connection_name": run.connection_name,
        "source_cpse": run.source_cpse,
        "source_system": run.source_system,
        "ingestion_batch_id": run.ingestion_batch_id,
        "status": run.status,
        "received_count": run.received_count,
        "imported_count": run.imported_count,
        "rejected_count": run.rejected_count,
        "metadata_json": run.metadata_json or {},
        "error_summary": run.error_summary or {},
        "idempotency_key": run.idempotency_key,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "completed_at": run.completed_at,
    }


def map_sap_record_to_ingestion_record(
    row: Dict[str, Any],
    *,
    default_source_cpse: str,
    default_source_system: str,
    row_number: int,
) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
    code = _odata_value(row, "Material", "MaterialCode", "MATNR", "material_code", "source_material_code")
    description = _odata_value(row, "MaterialDescription", "Description", "MAKTX", "description", "raw_description")
    if not code or not description:
        return None, {
            "row_number": row_number,
            "source_material_code": code,
            "raw_data": row,
            "reason": "SAP OData record missing material code or description",
        }

    source_cpse = (
        _odata_value(row, "CPSE", "CompanyCode", "company_code", "source_cpse")
        or default_source_cpse
        or "UNSPECIFIED_CPSE"
    )
    source_system = _odata_value(row, "SourceSystem", "source_system") or default_source_system or "SAP_ODATA"
    category = _odata_value(row, "MaterialGroup", "Category", "category")
    uom = _odata_value(row, "BaseUnit", "UOM", "UnitOfMeasure", "uom")
    record = build_ingestion_record(
        source_cpse=source_cpse,
        source_system=source_system,
        source_material_code=code,
        raw_description=description,
        uom=uom,
        category=category,
        manufacturer=_odata_value(row, "ManufacturerName", "Manufacturer", "manufacturer"),
        part_number=_odata_value(row, "ManufacturerPartNumber", "PartNumber", "part_number"),
        model_number=_odata_value(row, "ModelNumber", "model_number"),
        row_number=row_number,
        raw_data=row,
        metadata_json={
            "connector_type": CONNECTOR_TYPE,
            "odata_entity": row.get("__metadata", {}).get("uri") if isinstance(row.get("__metadata"), dict) else None,
            "plant": _odata_value(row, "Plant", "plant"),
            "specification": _odata_value(row, "Specification", "specification"),
        },
    )
    return record, None


def test_sap_connection() -> Dict[str, Any]:
    try:
        connector = get_sap_connector()
        result = connector.test_connection()
        return {
            "status": result.status,
            "connector_type": connector.connector_type,
            "connector_mode": connector.mode,
            "message": result.message,
            "metadata": result.metadata,
            "capabilities": result.capabilities,
        }
    except ConnectorConfigurationError as exc:
        raise SapImportError(400, sanitized_error(exc))
    except ConnectorRequestError as exc:
        raise SapImportError(503, sanitized_error(exc))


def get_import_run(db: Session, import_run_id: uuid.UUID) -> Optional[IntegrationImportRun]:
    return db.get(IntegrationImportRun, import_run_id)


def get_import_run_with_batch(db: Session, import_run_id: uuid.UUID) -> Tuple[Optional[IntegrationImportRun], Optional[IngestionBatch]]:
    run = get_import_run(db, import_run_id)
    batch = db.get(IngestionBatch, run.ingestion_batch_id) if run and run.ingestion_batch_id else None
    return run, batch


def import_sap_materials(
    db: Session,
    *,
    source_cpse: str,
    source_system: str,
    connection_name: str,
    entity_set: Optional[str],
    max_records: Optional[int],
    idempotency_key: Optional[str],
) -> Tuple[IntegrationImportRun, Optional[IngestionBatch], bool, Dict[str, Any], List[str]]:
    if idempotency_key:
        existing = db.execute(
            select(IntegrationImportRun).where(
                IntegrationImportRun.connector_type == CONNECTOR_TYPE,
                IntegrationImportRun.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing:
            batch = db.get(IngestionBatch, existing.ingestion_batch_id) if existing.ingestion_batch_id else None
            return existing, batch, True, existing.metadata_json.get("connector", {}) if existing.metadata_json else {}, []

    try:
        connector = get_sap_connector(entity_set=entity_set)
    except ConnectorConfigurationError as exc:
        raise SapImportError(400, sanitized_error(exc)) from exc
    connector_metadata = connector.metadata()
    now = _utc_now()
    run = IntegrationImportRun(
        connector_type=CONNECTOR_TYPE,
        connector_mode=connector.mode,
        connection_name=connection_name,
        source_cpse=source_cpse,
        source_system=source_system,
        status="STARTED",
        received_count=0,
        imported_count=0,
        rejected_count=0,
        metadata_json={
            "connector": connector_metadata,
            "entity_set_requested": entity_set,
            "max_records": max_records,
        },
        error_summary={},
        idempotency_key=idempotency_key,
    )
    db.add(run)
    db.flush()
    append_audit_event(
        db,
        actor="SAP_ODATA_IMPORT",
        actor_role="SYSTEM_PROCESS",
        action="ERP_IMPORT_STARTED",
        entity_type="integration_import_run",
        entity_id=str(run.id),
        old_value=None,
        new_value={
            "connector_type": run.connector_type,
            "connector_mode": run.connector_mode,
            "connection_name": run.connection_name,
            "source_cpse": run.source_cpse,
            "source_system": run.source_system,
            "metadata": run.metadata_json,
        },
        reason="SAP OData import run started.",
    )

    try:
        rows = connector.fetch_materials(entity_set=entity_set, max_records=max_records)
        records = []
        invalid_rows = []
        for index, row in enumerate(rows, start=1):
            record, invalid = map_sap_record_to_ingestion_record(
                row,
                default_source_cpse=source_cpse,
                default_source_system=source_system,
                row_number=index,
            )
            if invalid:
                invalid_rows.append(invalid)
            elif record:
                records.append(record)

        batch_name = f"SAP-IMPORT-{str(run.id)[:8]}"
        batch, batch_replay, error_count = ingest_canonical_records(
            db,
            records=records,
            batch_name=batch_name,
            source_cpse=source_cpse,
            source_system=source_system,
            source_name=f"{connector_metadata.get('entity_set') or entity_set or 'sap_odata'}:{connection_name}",
            uploaded_by="SAP_ODATA_IMPORT",
            batch_metadata={
                "connector_type": CONNECTOR_TYPE,
                "connector_mode": connector.mode,
                "entity_set": connector_metadata.get("entity_set") or entity_set,
                "source_system": source_system,
                "received_record_count": len(rows),
                "connector": connector_metadata,
            },
            invalid_rows=invalid_rows,
            audit_actor="SAP_ODATA_IMPORT",
            emit_audit=False,
            commit=False,
        )
        run.ingestion_batch_id = batch.id
        run.status = "COMPLETED" if batch.status == "COMPLETED" else "COMPLETED_WITH_ERRORS" if batch.processed_records else "FAILED"
        run.received_count = len(rows)
        run.imported_count = batch.processed_records
        run.rejected_count = error_count
        run.error_summary = {"error_count": error_count}
        run.metadata_json = {
            **(run.metadata_json or {}),
            "connector": connector_metadata,
            "ingestion_batch_id": str(batch.id),
            "batch_status": batch.status,
            "received_record_count": len(rows),
        }
        run.completed_at = _utc_now()
        run.updated_at = run.completed_at
        append_audit_event(
            db,
            actor="SAP_ODATA_IMPORT",
            actor_role="SYSTEM_PROCESS",
            action="ERP_IMPORT_COMPLETED",
            entity_type="integration_import_run",
            entity_id=str(run.id),
            old_value={"status": "STARTED"},
            new_value={
                "status": run.status,
                "ingestion_batch_id": run.ingestion_batch_id,
                "received_count": run.received_count,
                "imported_count": run.imported_count,
                "rejected_count": run.rejected_count,
                "connector": connector_metadata,
            },
            reason="SAP OData import run completed.",
        )
        db.commit()
        db.refresh(run)
        db.refresh(batch)
        warnings = []
        if batch_replay:
            warnings.append("Ingestion batch was reused because an identical sanitized import payload already exists.")
        return run, batch, False, connector_metadata, warnings
    except Exception as exc:
        run.status = "FAILED"
        run.error_summary = {"message": sanitized_error(exc)}
        run.completed_at = _utc_now()
        run.updated_at = run.completed_at
        append_audit_event(
            db,
            actor="SAP_ODATA_IMPORT",
            actor_role="SYSTEM_PROCESS",
            action="ERP_IMPORT_FAILED",
            entity_type="integration_import_run",
            entity_id=str(run.id),
            old_value={"status": "STARTED"},
            new_value={"status": run.status, "error_summary": run.error_summary},
            reason="SAP OData import run failed with a sanitized error.",
        )
        db.commit()
        raise SapImportError(503, run.error_summary["message"]) from exc


def import_run_payload(run: IntegrationImportRun) -> Dict[str, Any]:
    return _run_payload(run)
