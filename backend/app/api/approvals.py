from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_roles
from app.db.models import MaterialMapping, NationalMaterial, SourceMaterial
from app.db.session import get_db
from app.schemas.approval_workflow import (
    ApprovalCase,
    ApprovalStage,
    ApprovalWorkflowStatus,
    ApprovalActionRequest,
    ApprovalActionResponse,
    ApprovalQueueResponse,
)
from app.schemas import (
    PersistentApprovalCaseCreateResponse,
    PersistentApprovalCaseListResponse,
    PersistentApprovalCaseResponse,
    PersistentApprovalDecisionRequest,
    PersistentApprovalDecisionResponse,
    PersistentApprovalResubmitRequest,
)
from app.services.approval_workflow import (
    build_demo_approval_queue,
    simulate_l1_review,
    simulate_l2_review,
)
from app.services.audit_trail import create_audit_event, GENESIS_HASH
from app.services.persistent_approvals import (
    ApprovalWorkflowError,
    apply_decision,
    case_payload,
    create_case_from_national_material,
    get_case,
    list_cases,
    resubmit_case,
)
from app.services.auth import AuthenticatedUser

router = APIRouter(prefix="/approvals", tags=["Dual-Tier Governance & Approvals"])


# --- Legacy Placeholder Models & Data for Backwards Compatibility ---
class LegacyApprovalActionRequest(BaseModel):
    approval_id: str
    action: str  # 'APPROVED', 'REJECTED', 'REQUEST_REVISION'
    officer_id: str
    tier_level: str = "L1"  # "L1" (Nodal Officer) or "L2" (Ministry Master Authority)
    comments: str


PLACEHOLDER_APPROVALS = [
    {
        "id": "appr-101",
        "material_code": "CR-BEAR-6205",
        "proposed_name": "Deep Groove Ball Bearing 6205-2RS (SKF/FAG Equivalent)",
        "category": "Mechanical Transmission",
        "initiator": "Procurement Cell - Northern Railway",
        "tier": "L1 Nodal Verification",
        "status": "Pending L1",
        "risk_rating": "LOW",
        "estimated_annual_saving_inr": 240000.00,
        "submission_date": "2026-09-18T09:15:00Z"
    },
    {
        "id": "appr-102",
        "material_code": "CIL-BLT-1250",
        "proposed_name": "Hexagon Head Bolt M12x50 SS304 IS 1364",
        "category": "Standard Fasteners",
        "initiator": "Central Mining Inventory Pool - CIL",
        "tier": "L2 Ministry Ratification",
        "status": "Pending L2",
        "risk_rating": "MEDIUM",
        "estimated_annual_saving_inr": 1850000.00,
        "submission_date": "2026-09-18T08:40:00Z"
    }
]


# --- Prompt 11 Demo Approval Endpoints ---

@router.get("/demo-queue", response_model=ApprovalQueueResponse, tags=["Dual-Tier Governance & Approvals"])
async def get_demo_approval_queue(
    min_score: float = Query(0.45, ge=0.0, le=1.0, description="Minimum initial candidate match score")
):
    """
    Returns dynamically generated demo approval queue with multi-tier case data,
    proposed national material codes, dual scores, procurement impacts, and mapping previews.
    Strictly in-memory and non-persisted.
    """
    return build_demo_approval_queue(min_candidate_score=min_score)


@router.post("/demo-action", response_model=ApprovalActionResponse, tags=["Dual-Tier Governance & Approvals"])
async def execute_demo_approval_action(payload: ApprovalActionRequest = Body(...)):
    """
    Demo-only approval action processing in memory:
    Applies L1 Nodal Officer verification or L2 Ministry Authority ratification,
    advances the governance stage, creates a cryptographically chained audit event,
    and returns an explicit non-persisted acknowledgement.
    """
    queue = build_demo_approval_queue()
    target_case = next(
        (c for c in queue.cases if c.approval_case_id == payload.approval_case_id or c.candidate_pair_id == payload.approval_case_id),
        None
    )

    if not target_case:
        if queue.cases:
            target_case = queue.cases[0]
            target_case.approval_case_id = payload.approval_case_id
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Approval case '{payload.approval_case_id}' not found in demo queue."
            )

    old_stage = target_case.current_stage.value
    old_status = target_case.approval_status.value

    # Process review stage simulation
    if payload.stage == "L2_REVIEW" or target_case.current_stage == ApprovalStage.PENDING_L2:
        updated_case = simulate_l2_review(
            target_case,
            decision=payload.decision.value,
            reviewer=payload.reviewer_name,
            notes=payload.reviewer_note,
        )
    else:
        updated_case = simulate_l1_review(
            target_case,
            decision=payload.decision.value,
            reviewer=payload.reviewer_name,
            notes=payload.reviewer_note,
        )

    # Generate cryptographically signed audit event
    now_iso = datetime.now(timezone.utc).isoformat()
    action_name = f"{payload.stage}_{payload.decision.value}"
    audit_evt = create_audit_event(
        audit_id=f"AUD-ACT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        timestamp=now_iso,
        actor=payload.reviewer_name,
        actor_role=payload.reviewer_role,
        action=action_name,
        entity_type="approval_case",
        entity_id=updated_case.approval_case_id,
        previous_hash=GENESIS_HASH,
        old_value={"stage": old_stage, "approval_status": old_status},
        new_value={
            "stage": updated_case.current_stage.value,
            "approval_status": updated_case.approval_status.value,
            "proposed_code": updated_case.proposed_national_material_code,
        },
        reason=payload.reviewer_note or f"Action {payload.decision.value} submitted by {payload.reviewer_name} ({payload.reviewer_role})."
    )

    return ApprovalActionResponse(
        status="demo_action_recorded",
        approval_case_id=updated_case.approval_case_id,
        decision=payload.decision.value,
        updated_case=updated_case,
        generated_audit_event=audit_evt.model_dump(),
        message="Demo-only approval action processed in memory; not persisted to database.",
        persisted=False,
    )


# --- Persistent Approval Workflow Endpoints ---

def _case_response(case) -> PersistentApprovalCaseResponse:
    return PersistentApprovalCaseResponse(**case_payload(case))


def _reject_spoofed_identity(payload: PersistentApprovalDecisionRequest, current_user: AuthenticatedUser) -> None:
    if payload.reviewer_name and payload.reviewer_name not in {current_user.display_name, current_user.username}:
        raise HTTPException(status_code=400, detail="reviewer_name must match the authenticated user.")
    if payload.reviewer_role and payload.reviewer_role.upper() not in current_user.roles and not current_user.has_role("ADMIN"):
        raise HTTPException(status_code=400, detail="reviewer_role must match an authenticated role.")


def _require_stage_role(case, current_user: AuthenticatedUser) -> str:
    if case.current_stage == "PENDING_L1":
        if not (current_user.has_role("ADMIN") or current_user.has_role("L1_REVIEWER")):
            raise HTTPException(status_code=403, detail="PENDING_L1 decisions require ADMIN or L1_REVIEWER.")
        return "L1_REVIEWER"
    if case.current_stage == "PENDING_L2":
        if not (current_user.has_role("ADMIN") or current_user.has_role("L2_AUTHORITY")):
            raise HTTPException(status_code=403, detail="PENDING_L2 decisions require ADMIN or L2_AUTHORITY.")
        return "L2_AUTHORITY"
    raise HTTPException(status_code=409, detail=f"Approval case is not pending reviewer action: {case.current_stage}.")


def _national_source_cpses(db: Session, national_material_code: str) -> set[str]:
    rows = db.execute(
        select(SourceMaterial.source_cpse)
        .join(MaterialMapping, MaterialMapping.source_material_id == SourceMaterial.id)
        .join(NationalMaterial, NationalMaterial.id == MaterialMapping.national_material_id)
        .where(NationalMaterial.national_material_code == national_material_code)
    ).scalars().all()
    return {row for row in rows if row}


@router.post(
    "/cases/from-national-material/{national_material_code}",
    response_model=PersistentApprovalCaseCreateResponse,
    tags=["Persistent Approval Workflow"],
)
async def create_persistent_approval_case(
    national_material_code: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "CPSE_USER")),
):
    try:
        if current_user.has_role("CPSE_USER") and not current_user.has_role("ADMIN") and current_user.organization_scope:
            cpses = _national_source_cpses(db, national_material_code)
            if cpses and any(cpse.upper() != current_user.organization_scope.upper() for cpse in cpses):
                raise HTTPException(status_code=403, detail="CPSE_USER is scoped to a different organization.")
        db.rollback()
        case, idempotent_replay = create_case_from_national_material(
            db,
            national_material_code,
            actor_name=current_user.display_name,
            actor_role="ADMIN" if current_user.has_role("ADMIN") else "CPSE_USER",
            actor_username=current_user.username,
            actor_identity_verified=True,
        )
        return PersistentApprovalCaseCreateResponse(
            idempotent_replay=idempotent_replay,
            actor_identity_verified=True,
            case=_case_response(case),
        )
    except HTTPException:
        raise
    except ApprovalWorkflowError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/cases", response_model=PersistentApprovalCaseListResponse, tags=["Persistent Approval Workflow"])
async def list_persistent_approval_cases(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_stage: Optional[str] = Query(None),
    approval_status: Optional[str] = Query(None),
    national_material_code: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "L1_REVIEWER", "L2_AUTHORITY", "AUDITOR")),
):
    total, cases = list_cases(
        db,
        page=page,
        limit=limit,
        current_stage=current_stage,
        approval_status=approval_status,
        national_material_code=national_material_code,
    )
    return PersistentApprovalCaseListResponse(
        count=len(cases),
        total=total,
        page=page,
        limit=limit,
        actor_identity_verified=True,
        items=[_case_response(case) for case in cases],
    )


@router.get("/cases/{approval_case_id}", response_model=PersistentApprovalCaseResponse, tags=["Persistent Approval Workflow"])
async def get_persistent_approval_case(
    approval_case_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "L1_REVIEWER", "L2_AUTHORITY", "AUDITOR")),
):
    case = get_case(db, approval_case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Approval case '{approval_case_id}' not found.")
    return _case_response(case)


@router.post(
    "/cases/{approval_case_id}/decision",
    response_model=PersistentApprovalDecisionResponse,
    tags=["Persistent Approval Workflow"],
)
async def decide_persistent_approval_case(
    approval_case_id: UUID,
    payload: PersistentApprovalDecisionRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        existing = get_case(db, approval_case_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Approval case '{approval_case_id}' not found.")
        effective_role = _require_stage_role(existing, current_user)
        _reject_spoofed_identity(payload, current_user)
        db.rollback()
        case = apply_decision(
            db,
            approval_case_id,
            decision=payload.decision.value,
            reviewer_name=current_user.display_name,
            reviewer_role=effective_role,
            reviewer_note=payload.reviewer_note,
            actor_username=current_user.username,
            actor_identity_verified=True,
        )
        return PersistentApprovalDecisionResponse(actor_identity_verified=True, case=_case_response(case))
    except HTTPException:
        raise
    except ApprovalWorkflowError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post(
    "/cases/{approval_case_id}/resubmit",
    response_model=PersistentApprovalDecisionResponse,
    tags=["Persistent Approval Workflow"],
)
async def resubmit_persistent_approval_case(
    approval_case_id: UUID,
    payload: PersistentApprovalResubmitRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "CPSE_USER", "L1_REVIEWER")),
):
    try:
        db.rollback()
        case = resubmit_case(
            db,
            approval_case_id,
            submitter_note=payload.submitter_note,
            actor_name=current_user.display_name,
            actor_role="ADMIN" if current_user.has_role("ADMIN") else sorted(current_user.roles)[0],
            actor_username=current_user.username,
            actor_identity_verified=True,
        )
        return PersistentApprovalDecisionResponse(actor_identity_verified=True, case=_case_response(case))
    except ApprovalWorkflowError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


# --- Legacy Placeholder Endpoints ---

@router.get("", response_model=Dict[str, Any])
@router.get("/pending", response_model=Dict[str, Any])
async def get_pending_approvals():
    """
    Placeholder endpoint: List pending material master changes awaiting dual sign-off.
    """
    return {
        "status": "success",
        "message": "Pending approvals retrieved (placeholder mode)",
        "count": len(PLACEHOLDER_APPROVALS),
        "data": PLACEHOLDER_APPROVALS
    }


@router.post("/action", response_model=Dict[str, Any])
async def execute_approval_action(payload: LegacyApprovalActionRequest = Body(...)):
    """
    Placeholder endpoint: Process approve/reject action for a material master change.
    """
    return {
        "status": "success",
        "message": f"Approval ID '{payload.approval_id}' marked as '{payload.action}' by Officer '{payload.officer_id}' ({payload.tier_level})",
        "audit_id": "AUD-APR-2026-9901",
        "workflow_state": "NEXT_TIER_ROUTED" if payload.tier_level == "L1" and payload.action == "APPROVED" else "FINALIZED"
    }
