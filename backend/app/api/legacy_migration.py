import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.models import MigrationJob, MigrationJobError
from app.db.session import get_db
from app.services.auth import AuthenticatedUser
from app.services.ps_completion import migration_payload, process_legacy_migration, rollback_migration_job

router = APIRouter(prefix="/migration", tags=["Legacy Migration Workbench"])


@router.post("/legacy-materials")
async def upload_legacy_materials(
    file: UploadFile = File(...),
    source_cpse: str = Form(...),
    source_system: str = Form(...),
    dry_run: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "CPSE_USER")),
):
    content = await file.read()
    job = process_legacy_migration(
        db,
        content=content,
        filename=file.filename or "legacy-materials.csv",
        source_cpse=source_cpse,
        source_system=source_system,
        dry_run=dry_run,
        actor=current_user,
    )
    return {"status": "success", "job": migration_payload(job)}


@router.get("/jobs/{job_id}")
async def get_migration_job(job_id: UUID, db: Session = Depends(get_db)):
    job = db.get(MigrationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found.")
    errors = db.execute(select(MigrationJobError).where(MigrationJobError.migration_job_id == job.id)).scalars().all()
    return {
        "status": "success",
        "job": migration_payload(job),
        "error_count": len(errors),
        "errors": [
            {
                "row_number": error.row_number,
                "source_material_code": error.source_material_code,
                "reason": error.reason,
                "resolved": error.resolved,
            }
            for error in errors
        ],
    }


@router.get("/jobs/{job_id}/errors.csv")
async def download_migration_errors(job_id: UUID, db: Session = Depends(get_db)):
    job = db.get(MigrationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Migration job not found.")
    errors = db.execute(select(MigrationJobError).where(MigrationJobError.migration_job_id == job.id)).scalars().all()
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=["row_number", "source_material_code", "reason", "resolved"])
    writer.writeheader()
    for error in errors:
        writer.writerow({
            "row_number": error.row_number,
            "source_material_code": error.source_material_code,
            "reason": error.reason,
            "resolved": error.resolved,
        })
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=migration_errors.csv"})


@router.post("/jobs/{job_id}/rollback")
async def rollback_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "CPSE_USER")),
):
    job = rollback_migration_job(db, job_id, current_user)
    return {"status": "success", "job": migration_payload(job)}
