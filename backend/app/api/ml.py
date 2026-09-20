from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.models import MLModelRun
from app.db.session import get_db
from app.services.auth import AuthenticatedUser
from app.services.ps_completion import labelled_dataset, model_run_payload, train_model_if_available

router = APIRouter(prefix="/ml", tags=["ML-Ready Matching"])


@router.get("/labels/export")
async def export_labels(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "AUDITOR")),
):
    rows = labelled_dataset(db)
    return {"status": "success", "count": len(rows), "items": rows}


@router.post("/train")
async def train_model(
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN")),
):
    run = train_model_if_available(db, min_labels=int(payload.get("min_labels") or 25), actor=current_user)
    return {"status": run.status, "model_run": model_run_payload(run)}


@router.get("/evaluate")
async def evaluate_model(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "AUDITOR")),
):
    latest = db.execute(select(MLModelRun).order_by(MLModelRun.created_at.desc()).limit(1)).scalar_one_or_none()
    return {
        "status": "success",
        "rule_baseline": {"status": "ACTIVE", "version": "candidate-rules-v1 + hybrid-rule-v1"},
        "trained_model": model_run_payload(latest) if latest else None,
        "comparison_note": "Trained model metrics are available only after optional dependencies and enough labelled decisions exist.",
    }
