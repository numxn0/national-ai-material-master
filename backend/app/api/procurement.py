from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.services.auth import AuthenticatedUser
from app.services.ps_completion import import_procurement_history, procurement_analytics

router = APIRouter(prefix="/procurement", tags=["Historical Procurement"])


@router.post("/history/import")
async def import_history(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "CPSE_USER")),
):
    result = import_procurement_history(
        db,
        content=await file.read(),
        filename=file.filename or "procurement-history.csv",
        actor=current_user,
    )
    return {"status": "success", **result}


@router.get("/analytics")
async def get_procurement_analytics(
    cpse: str | None = Query(None),
    category: str | None = Query(None),
    national_material_code: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "CPSE_USER", "AUDITOR")),
):
    return procurement_analytics(db, cpse=cpse, category=category, national_material_code=national_material_code)
