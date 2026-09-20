from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.models import NationalMaterial, NationalMaterialChangeRequest, NationalMaterialRevision
from app.db.session import get_db
from app.services.auth import AuthenticatedUser
from app.services.ps_completion import record_national_revision

router = APIRouter(prefix="/national-governance", tags=["National Code Lifecycle Governance"])


@router.get("/materials/{national_material_code}/current")
async def current_national_material(national_material_code: str, db: Session = Depends(get_db)):
    material = db.execute(select(NationalMaterial).where(NationalMaterial.national_material_code == national_material_code)).scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="National material not found.")
    return {
        "id": str(material.id),
        "national_material_code": material.national_material_code,
        "status": material.status,
        "version": material.version,
        "replacement_national_material_id": str(material.replacement_national_material_id) if material.replacement_national_material_id else None,
    }


@router.get("/materials/{national_material_code}/revisions")
async def revision_history(national_material_code: str, db: Session = Depends(get_db)):
    material = db.execute(select(NationalMaterial).where(NationalMaterial.national_material_code == national_material_code)).scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="National material not found.")
    revisions = db.execute(
        select(NationalMaterialRevision)
        .where(NationalMaterialRevision.national_material_id == material.id)
        .order_by(NationalMaterialRevision.revision_number.asc())
    ).scalars().all()
    return {
        "status": "success",
        "count": len(revisions),
        "items": [
            {
                "id": str(rev.id),
                "revision_number": rev.revision_number,
                "change_type": rev.change_type,
                "status": rev.status,
                "previous_value": rev.previous_value,
                "new_value": rev.new_value,
                "actor": rev.actor,
                "created_at": rev.created_at,
            }
            for rev in revisions
        ],
    }


@router.post("/materials/{national_material_code}/change-request")
async def create_change_request(
    national_material_code: str,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "L1_REVIEWER", "L2_AUTHORITY")),
):
    material = db.execute(select(NationalMaterial).where(NationalMaterial.national_material_code == national_material_code)).scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="National material not found.")
    if material.status == "ACTIVE":
        material.status = "UNDER_REVIEW"
    req = NationalMaterialChangeRequest(
        national_material_id=material.id,
        change_type=payload.get("change_type") or "REVISION",
        requested_payload=payload,
        status="PENDING_APPROVAL",
        requested_by=current_user.username,
    )
    db.add(req)
    rev = record_national_revision(
        db,
        material,
        change_type="CHANGE_REQUESTED",
        previous={"status": "ACTIVE"},
        new={"status": material.status, "requested_payload": payload},
        actor=current_user,
    )
    return {"status": "success", "change_request_id": str(req.id), "revision_id": str(rev.id), "material_status": material.status}


@router.post("/materials/{national_material_code}/deprecate")
async def deprecate_material(
    national_material_code: str,
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "L2_AUTHORITY")),
):
    material = db.execute(select(NationalMaterial).where(NationalMaterial.national_material_code == national_material_code)).scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="National material not found.")
    replacement_code = payload.get("replacement_national_material_code")
    replacement = None
    if replacement_code:
        replacement = db.execute(select(NationalMaterial).where(NationalMaterial.national_material_code == replacement_code)).scalar_one_or_none()
        if not replacement:
            raise HTTPException(status_code=404, detail="Replacement national material not found.")
    before = {"status": material.status, "replacement_national_material_id": str(material.replacement_national_material_id) if material.replacement_national_material_id else None}
    material.status = "REPLACED" if replacement else "DEPRECATED"
    material.replacement_national_material_id = replacement.id if replacement else None
    material.version += 1
    rev = record_national_revision(
        db,
        material,
        change_type="REPLACED" if replacement else "DEPRECATED",
        previous=before,
        new={"status": material.status, "replacement_national_material_id": str(material.replacement_national_material_id) if material.replacement_national_material_id else None},
        actor=current_user,
    )
    return {"status": "success", "material_status": material.status, "revision_id": str(rev.id)}
