from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.schemas import (
    IngestionBatchResponse,
    IntegrationImportRunDetailResponse,
    IntegrationImportRunResponse,
    SapConnectionTestResponse,
    SapImportMaterialsRequest,
    SapImportMaterialsResponse,
)
from app.services.sap_import import (
    SapImportError,
    get_import_run_with_batch,
    import_run_payload,
    import_sap_materials,
    test_sap_connection,
)
from app.services.auth import AuthenticatedUser, assert_cpse_scope
from app.db.models import SapSyncConfiguration, IntegrationImportRun
from app.services.ps_completion import create_sap_sync_config, sap_live_preflight

router = APIRouter(prefix="/integrations", tags=["ERP Integrations"])


@router.post("/sap/test-connection", response_model=SapConnectionTestResponse)
async def test_sap_odata_connection():
    try:
        return SapConnectionTestResponse(**test_sap_connection())
    except SapImportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/sap/preflight")
async def sap_live_configuration_preflight(
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "CPSE_USER", "AUDITOR")),
):
    result = sap_live_preflight()
    if not result["ready"] and result["mode"] == "live":
        return {
            **result,
            "status": "NOT_READY",
            "message": "Live SAP OData is not ready. Supply real configuration through environment/secret management.",
        }
    return {**result, "status": "READY"}


@router.post("/sap/sync-configurations")
async def create_sync_configuration(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "CPSE_USER")),
):
    config = create_sap_sync_config(db, payload, current_user)
    return {
        "status": "success",
        "configuration": {
            "id": str(config.id),
            "connection_name": config.connection_name,
            "source_cpse": config.source_cpse,
            "source_system": config.source_system,
            "entity_set": config.entity_set,
            "mode": config.mode,
            "base_url_sanitized": config.base_url_sanitized,
            "auth_mode": config.auth_mode,
            "secrets_persisted": False,
        },
    }


@router.get("/sap/sync-configurations")
async def list_sync_configurations(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "CPSE_USER", "AUDITOR")),
):
    configs = db.query(SapSyncConfiguration).order_by(SapSyncConfiguration.created_at.desc()).all()
    return {
        "status": "success",
        "count": len(configs),
        "items": [
            {
                "id": str(config.id),
                "connection_name": config.connection_name,
                "source_cpse": config.source_cpse,
                "entity_set": config.entity_set,
                "mode": config.mode,
                "last_successful_import_at": config.last_successful_import_at,
                "last_delta_token": config.last_delta_token,
                "secrets_persisted": False,
            }
            for config in configs
        ],
    }


@router.post("/sap/import-materials", response_model=SapImportMaterialsResponse)
async def import_sap_odata_materials(
    payload: SapImportMaterialsRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "CPSE_USER")),
):
    try:
        assert_cpse_scope(current_user, payload.source_cpse)
        run, batch, idempotent_replay, connector_metadata, warnings = import_sap_materials(
            db,
            source_cpse=payload.source_cpse,
            source_system=payload.source_system,
            connection_name=payload.connection_name,
            entity_set=payload.entity_set,
            max_records=payload.max_records,
            idempotency_key=payload.idempotency_key,
        )
        return SapImportMaterialsResponse(
            idempotent_replay=idempotent_replay,
            import_run=IntegrationImportRunResponse(**import_run_payload(run)),
            ingestion_batch=IngestionBatchResponse.model_validate(batch) if batch else None,
            received_count=run.received_count,
            imported_count=run.imported_count,
            rejected_count=run.rejected_count,
            connector_metadata=connector_metadata,
            warnings=warnings,
        )
    except SapImportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/import-runs/{import_run_id}", response_model=IntegrationImportRunDetailResponse)
async def get_integration_import_run(
    import_run_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "CPSE_USER", "AUDITOR")),
):
    run, batch = get_import_run_with_batch(db, import_run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Integration import run '{import_run_id}' not found.")
    return IntegrationImportRunDetailResponse(
        import_run=IntegrationImportRunResponse(**import_run_payload(run)),
        ingestion_batch=IngestionBatchResponse.model_validate(batch) if batch else None,
    )


@router.get("/import-runs")
async def list_import_runs(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "CPSE_USER", "AUDITOR")),
):
    runs = db.query(IntegrationImportRun).order_by(IntegrationImportRun.created_at.desc()).limit(100).all()
    return {"status": "success", "count": len(runs), "items": [IntegrationImportRunResponse(**import_run_payload(run)).model_dump(mode="json") for run in runs]}
