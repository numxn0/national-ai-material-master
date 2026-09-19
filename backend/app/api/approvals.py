from fastapi import APIRouter, Body, HTTPException, Query
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel

from app.schemas.approval_workflow import (
    ApprovalCase,
    ApprovalStage,
    ApprovalWorkflowStatus,
    ApprovalActionRequest,
    ApprovalActionResponse,
    ApprovalQueueResponse,
)
from app.services.approval_workflow import (
    build_demo_approval_queue,
    simulate_l1_review,
    simulate_l2_review,
)
from app.services.audit_trail import create_audit_event, GENESIS_HASH

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
