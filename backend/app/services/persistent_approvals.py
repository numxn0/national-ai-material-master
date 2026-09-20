import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import ApprovalCase, MaterialMapping, MatchCandidate, NationalMaterial, SourceMaterial
from app.services.national_material_registry import mapping_payloads
from app.services.persistent_audit import append_audit_event

L1_ROLES = {"L1_REVIEWER", "L1_NODAL_OFFICER"}
L2_ROLES = {"L2_AUTHORITY", "MINISTRY_AUTHORITY"}
DECISIONS = {"APPROVE", "REJECT", "NEEDS_MORE_INFO"}
TERMINAL_STAGES = {"APPROVED", "REJECTED"}


class ApprovalWorkflowError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _case_id(national_material_code: str) -> str:
    safe_code = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in national_material_code)
    return f"CASE-{safe_code}"[:255]


def _source_summary(source: Optional[SourceMaterial]) -> Optional[Dict[str, Any]]:
    if source is None:
        return None
    return {
        "id": str(source.id),
        "source_cpse": source.source_cpse,
        "source_system": source.source_system,
        "source_material_code": source.source_material_code,
        "standard_description": source.standard_description,
        "raw_description": source.raw_description,
        "category": source.category,
        "uom": source.uom,
        "attributes": source.attributes or {},
    }


def _procurement_impact(national: NationalMaterial, candidate: Optional[MatchCandidate], mappings: List[MaterialMapping]) -> Dict[str, Any]:
    cpses = []
    for mapping in mappings:
        if mapping.source_material and mapping.source_material.source_cpse:
            cpses.append(mapping.source_material.source_cpse)
    affected_cpses = list(dict.fromkeys(cpses))
    score = candidate.hybrid_score if candidate and candidate.hybrid_score is not None else None
    if score is None:
        score = max((mapping.confidence_score for mapping in mappings), default=0.0)

    category = (national.category or "").upper()
    if "BEAR" in category:
        base_spend = 2400000.0
    elif "VALVE" in category:
        base_spend = 4800000.0
    elif "PIPE" in category or "TUBE" in category:
        base_spend = 3200000.0
    elif "CABLE" in category or "ELECTRICAL" in category:
        base_spend = 6500000.0
    elif "MOTOR" in category:
        base_spend = 5500000.0
    elif "FASTENER" in category:
        base_spend = 1200000.0
    else:
        base_spend = 2000000.0

    if score >= 0.85:
        savings_pct = 0.14
        risk = "LOW"
    elif score >= 0.65:
        savings_pct = 0.12
        risk = "MEDIUM"
    else:
        savings_pct = 0.09
        risk = "HIGH"

    return {
        "duplicate_count": max(len(mappings), 1),
        "estimated_annual_spend_overlap": base_spend,
        "standardization_savings_percent": round(savings_pct * 100, 1),
        "estimated_savings_inr": round(base_spend * savings_pct, 2),
        "affected_cpses": affected_cpses,
        "procurement_risk_level": risk,
        "is_demo_estimate": True,
    }


def _mapping_preview(national: NationalMaterial, mappings: List[MaterialMapping]) -> Dict[str, Any]:
    codes = []
    cpses = []
    for mapping in mappings:
        source = mapping.source_material
        if source:
            codes.append(source.source_material_code)
            cpses.append(source.source_cpse)
    max_confidence = max((mapping.confidence_score for mapping in mappings), default=0.0)
    return {
        "source_material_codes": list(dict.fromkeys(codes)),
        "source_cpses": list(dict.fromkeys(cpses)),
        "target_national_code": national.national_material_code,
        "target_description": national.standard_description,
        "mapping_type": "UNIFIED_CANONICAL" if max_confidence >= 0.85 else "CATALOG_ALIAS",
    }


def _load_case_options(stmt):
    return stmt.options(
        selectinload(ApprovalCase.match_candidate).selectinload(MatchCandidate.source_material_a),
        selectinload(ApprovalCase.match_candidate).selectinload(MatchCandidate.source_material_b),
        selectinload(ApprovalCase.proposed_national_material)
        .selectinload(NationalMaterial.mappings)
        .selectinload(MaterialMapping.national_material),
        selectinload(ApprovalCase.proposed_national_material)
        .selectinload(NationalMaterial.mappings)
        .selectinload(MaterialMapping.source_material),
    )


def get_case(db: Session, approval_case_id: uuid.UUID) -> Optional[ApprovalCase]:
    return db.execute(
        _load_case_options(select(ApprovalCase).where(ApprovalCase.id == approval_case_id))
    ).scalar_one_or_none()


def get_existing_case_for_national(db: Session, national_id: uuid.UUID) -> Optional[ApprovalCase]:
    return db.execute(
        _load_case_options(select(ApprovalCase).where(ApprovalCase.proposed_national_material_id == national_id))
    ).scalar_one_or_none()


def create_case_from_national_material(
    db: Session,
    national_material_code: str,
    *,
    actor_name: str = "APPROVAL_CASE_SERVICE",
    actor_role: str = "SYSTEM_PROCESS",
    actor_username: Optional[str] = None,
    actor_identity_verified: bool = False,
) -> Tuple[ApprovalCase, bool]:
    with db.begin():
        national = db.execute(
            select(NationalMaterial)
            .options(
                selectinload(NationalMaterial.originating_match_candidate)
                .selectinload(MatchCandidate.source_material_a),
                selectinload(NationalMaterial.originating_match_candidate)
                .selectinload(MatchCandidate.source_material_b),
                selectinload(NationalMaterial.mappings).selectinload(MaterialMapping.source_material),
                selectinload(NationalMaterial.mappings).selectinload(MaterialMapping.national_material),
            )
            .where(NationalMaterial.national_material_code == national_material_code)
        ).scalar_one_or_none()
        if not national:
            raise ApprovalWorkflowError(404, f"National material code '{national_material_code}' not found.")

        existing = get_existing_case_for_national(db, national.id)
        if existing:
            return existing, True

        if national.status != "DRAFT":
            raise ApprovalWorkflowError(
                409,
                f"Only DRAFT national materials can enter approval. Current status is '{national.status}'.",
            )

        candidate = national.originating_match_candidate
        mappings = list(national.mappings)
        case = ApprovalCase(
            approval_case_id=_case_id(national.national_material_code),
            match_candidate_id=national.originating_match_candidate_id,
            proposed_national_material_id=national.id,
            proposed_national_material_code=national.national_material_code,
            proposed_standard_description=national.standard_description,
            hybrid_score=candidate.hybrid_score if candidate else None,
            hybrid_classification=candidate.classification if candidate else None,
            required_approval_level="L1_AND_L2",
            current_stage="PENDING_L1",
            approval_status="PENDING",
            procurement_impact=_procurement_impact(national, candidate, mappings),
            mapping_preview=_mapping_preview(national, mappings),
            metadata_json={
                "actor_identity_verified": actor_identity_verified,
                "created_by_username": actor_username,
                "originating_match_candidate_id": str(national.originating_match_candidate_id)
                if national.originating_match_candidate_id
                else None,
                "source_materials": [
                    _source_summary(mapping.source_material)
                    for mapping in mappings
                    if mapping.source_material is not None
                ],
            },
        )
        db.add(case)
        db.flush()
        append_audit_event(
            db,
            actor=actor_name,
            actor_role=actor_role,
            action="APPROVAL_CASE_CREATED",
            entity_type="approval_case",
            entity_id=str(case.id),
            old_value=None,
            new_value={
                "approval_case_id": case.approval_case_id,
                "match_candidate_id": case.match_candidate_id,
                "proposed_national_material_id": case.proposed_national_material_id,
                "proposed_national_material_code": case.proposed_national_material_code,
                "current_stage": case.current_stage,
                "approval_status": case.approval_status,
                "mapping_ids": [mapping.id for mapping in mappings],
                "actor_username": actor_username,
                "actor_identity_verified": actor_identity_verified,
            },
            reason="Persistent approval case created for DRAFT national material.",
        )
        return case, False


def list_cases(
    db: Session,
    *,
    page: int = 1,
    limit: int = 50,
    current_stage: Optional[str] = None,
    approval_status: Optional[str] = None,
    national_material_code: Optional[str] = None,
) -> Tuple[int, List[ApprovalCase]]:
    conditions = []
    if current_stage:
        conditions.append(ApprovalCase.current_stage == current_stage)
    if approval_status:
        conditions.append(ApprovalCase.approval_status == approval_status)
    if national_material_code:
        conditions.append(ApprovalCase.proposed_national_material_code == national_material_code)

    total = db.scalar(select(func.count()).select_from(ApprovalCase).where(*conditions)) or 0
    items = db.execute(
        _load_case_options(
            select(ApprovalCase)
            .where(*conditions)
            .order_by(ApprovalCase.created_at.desc(), ApprovalCase.approval_case_id.asc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).scalars().all()
    return total, items


def apply_decision(
    db: Session,
    approval_case_id: uuid.UUID,
    *,
    decision: str,
    reviewer_name: str,
    reviewer_role: str,
    reviewer_note: Optional[str] = None,
    actor_username: Optional[str] = None,
    actor_identity_verified: bool = False,
) -> ApprovalCase:
    normalized_decision = decision.upper()
    normalized_role = reviewer_role.upper()
    if normalized_decision not in DECISIONS:
        raise ApprovalWorkflowError(422, f"Decision '{decision}' is invalid.")

    with db.begin():
        case = get_case(db, approval_case_id)
        if not case:
            raise ApprovalWorkflowError(404, f"Approval case '{approval_case_id}' not found.")
        if case.current_stage in TERMINAL_STAGES or case.approval_status in {"APPROVED", "REJECTED"}:
            raise ApprovalWorkflowError(409, "Terminal approval cases cannot receive further decisions.")

        national = case.proposed_national_material
        if not national:
            raise ApprovalWorkflowError(409, "Approval case is not linked to a national material.")
        mappings = list(national.mappings)
        now = _now()
        old_case_state = {
            "current_stage": case.current_stage,
            "approval_status": case.approval_status,
            "l1_decision": case.l1_decision,
            "l2_decision": case.l2_decision,
        }
        old_national_state = {
            "status": national.status,
            "approved_by": national.approved_by,
        }
        old_mapping_states = [
            {
                "id": mapping.id,
                "approval_status": mapping.approval_status,
                "reviewer_id": mapping.reviewer_id,
                "reviewed_at": mapping.reviewed_at,
            }
            for mapping in mappings
        ]
        stage_prefix = "L1" if case.current_stage == "PENDING_L1" else "L2" if case.current_stage == "PENDING_L2" else None

        if case.current_stage == "PENDING_L1":
            if normalized_role not in L1_ROLES:
                raise ApprovalWorkflowError(403, "PENDING_L1 decisions require L1_REVIEWER or L1_NODAL_OFFICER.")
            case.l1_reviewer = reviewer_name
            case.l1_decision = normalized_decision
            case.l1_reviewed_at = now
            case.l1_notes = reviewer_note

            if normalized_decision == "APPROVE":
                case.current_stage = "PENDING_L2"
                case.approval_status = "PENDING"
                for mapping in mappings:
                    mapping.approval_status = "PENDING_L2"
            elif normalized_decision == "REJECT":
                _reject_case(case, national, mappings)
            else:
                case.current_stage = "NEEDS_MORE_INFO"
                case.approval_status = "NEEDS_MORE_INFO"
                for mapping in mappings:
                    mapping.approval_status = "NEEDS_MORE_INFO"
        elif case.current_stage == "PENDING_L2":
            if normalized_role not in L2_ROLES:
                raise ApprovalWorkflowError(403, "PENDING_L2 decisions require L2_AUTHORITY or MINISTRY_AUTHORITY.")
            case.l2_reviewer = reviewer_name
            case.l2_decision = normalized_decision
            case.l2_reviewed_at = now
            case.l2_notes = reviewer_note

            if normalized_decision == "APPROVE":
                case.current_stage = "APPROVED"
                case.approval_status = "APPROVED"
                national.status = "ACTIVE"
                national.approved_by = reviewer_name
                national.updated_at = now
                for mapping in mappings:
                    mapping.approval_status = "APPROVED"
                    mapping.reviewer_id = reviewer_name
                    mapping.reviewed_at = now
                if case.match_candidate:
                    case.match_candidate.status = "APPROVED"
                    case.match_candidate.updated_at = now
            elif normalized_decision == "REJECT":
                _reject_case(case, national, mappings)
            else:
                case.current_stage = "NEEDS_MORE_INFO"
                case.approval_status = "NEEDS_MORE_INFO"
                for mapping in mappings:
                    mapping.approval_status = "NEEDS_MORE_INFO"
        elif case.current_stage == "NEEDS_MORE_INFO":
            raise ApprovalWorkflowError(409, "Case needs more information before another reviewer decision.")
        else:
            raise ApprovalWorkflowError(409, f"Unsupported approval stage '{case.current_stage}'.")

        case.updated_at = now
        db.flush()
        metadata = dict(case.metadata_json or {})
        metadata["actor_identity_verified"] = actor_identity_verified
        metadata["last_actor_username"] = actor_username
        case.metadata_json = metadata
        action = f"APPROVAL_{stage_prefix}_{'APPROVED' if normalized_decision == 'APPROVE' else normalized_decision}"
        append_audit_event(
            db,
            actor=reviewer_name,
            actor_role=normalized_role,
            action=action,
            entity_type="approval_case",
            entity_id=str(case.id),
            old_value=old_case_state,
            new_value={
                "current_stage": case.current_stage,
                "approval_status": case.approval_status,
                "l1_reviewer": case.l1_reviewer,
                "l1_decision": case.l1_decision,
                "l1_reviewed_at": case.l1_reviewed_at,
                "l2_reviewer": case.l2_reviewer,
                "l2_decision": case.l2_decision,
                "l2_reviewed_at": case.l2_reviewed_at,
                "actor_username": actor_username,
                "actor_identity_verified": actor_identity_verified,
            },
            reason=reviewer_note or f"{stage_prefix} reviewer submitted {normalized_decision}.",
        )
        append_audit_event(
            db,
            actor=reviewer_name,
            actor_role=normalized_role,
            action="MATERIAL_MAPPINGS_STATUS_CHANGED",
            entity_type="material_mapping",
            entity_id=str(case.id),
            old_value={"mappings": old_mapping_states},
            new_value={
                "approval_case_id": case.id,
                "mappings": [
                    {
                        "id": mapping.id,
                        "approval_status": mapping.approval_status,
                        "reviewer_id": mapping.reviewer_id,
                        "reviewed_at": mapping.reviewed_at,
                    }
                    for mapping in mappings
                ],
            },
            reason=f"Mapping statuses updated after {stage_prefix} {normalized_decision}.",
        )
        if stage_prefix == "L2" and normalized_decision == "APPROVE":
            append_audit_event(
                db,
                actor=reviewer_name,
                actor_role=normalized_role,
                action="NATIONAL_MATERIAL_PUBLISHED",
                entity_type="national_material",
                entity_id=str(national.id),
                old_value=old_national_state,
                new_value={
                    "status": national.status,
                    "approved_by": national.approved_by,
                    "national_material_code": national.national_material_code,
                    "actor_username": actor_username,
                    "actor_identity_verified": actor_identity_verified,
                },
                reason="L2 approval published the DRAFT national material as ACTIVE.",
            )
        return case


def _reject_case(case: ApprovalCase, national: NationalMaterial, mappings: List[MaterialMapping]) -> None:
    now = _now()
    case.current_stage = "REJECTED"
    case.approval_status = "REJECTED"
    national.status = "REJECTED"
    national.updated_at = now
    for mapping in mappings:
        mapping.approval_status = "REJECTED"
    if case.match_candidate:
        case.match_candidate.status = "REJECTED"
        case.match_candidate.updated_at = now


def resubmit_case(
    db: Session,
    approval_case_id: uuid.UUID,
    submitter_note: str,
    *,
    actor_name: str = "APPROVAL_SUBMITTER",
    actor_role: str = "DECLARED_SUBMITTER",
    actor_username: Optional[str] = None,
    actor_identity_verified: bool = False,
) -> ApprovalCase:
    with db.begin():
        case = get_case(db, approval_case_id)
        if not case:
            raise ApprovalWorkflowError(404, f"Approval case '{approval_case_id}' not found.")
        if case.current_stage != "NEEDS_MORE_INFO" or case.approval_status != "NEEDS_MORE_INFO":
            raise ApprovalWorkflowError(409, "Only NEEDS_MORE_INFO cases can be resubmitted.")
        national = case.proposed_national_material
        if not national:
            raise ApprovalWorkflowError(409, "Approval case is not linked to a national material.")
        now = _now()
        metadata = dict(case.metadata_json or {})
        resubmissions = list(metadata.get("resubmissions") or [])
        resubmissions.append({"submitter_note": submitter_note, "submitted_at": now.isoformat()})
        metadata["resubmissions"] = resubmissions
        metadata["actor_identity_verified"] = actor_identity_verified
        metadata["last_actor_username"] = actor_username
        case.metadata_json = metadata
        case.current_stage = "PENDING_L1"
        case.approval_status = "PENDING"
        case.updated_at = now
        old_mapping_states = [
            {"id": mapping.id, "approval_status": mapping.approval_status}
            for mapping in national.mappings
        ]
        for mapping in national.mappings:
            mapping.approval_status = "PENDING_L1"
        db.flush()
        append_audit_event(
            db,
            actor=actor_name,
            actor_role=actor_role,
            action="APPROVAL_CASE_RESUBMITTED",
            entity_type="approval_case",
            entity_id=str(case.id),
            old_value={"current_stage": "NEEDS_MORE_INFO", "approval_status": "NEEDS_MORE_INFO"},
            new_value={
                "current_stage": case.current_stage,
                "approval_status": case.approval_status,
                "submitter_note": submitter_note,
                "actor_username": actor_username,
                "actor_identity_verified": actor_identity_verified,
            },
            reason="Approval case resubmitted after requested information was supplied.",
        )
        append_audit_event(
            db,
            actor=actor_name,
            actor_role=actor_role,
            action="MATERIAL_MAPPINGS_STATUS_CHANGED",
            entity_type="material_mapping",
            entity_id=str(case.id),
            old_value={"mappings": old_mapping_states},
            new_value={
                "approval_case_id": case.id,
                "mappings": [
                    {"id": mapping.id, "approval_status": mapping.approval_status}
                    for mapping in national.mappings
                ],
            },
            reason="Mappings returned to PENDING_L1 after case resubmission.",
        )
        return case


def case_payload(case: ApprovalCase) -> Dict[str, Any]:
    national = case.proposed_national_material
    mappings = list(national.mappings) if national else []
    return {
        "id": case.id,
        "approval_case_id": case.approval_case_id,
        "match_candidate_id": case.match_candidate_id,
        "proposed_national_material_id": case.proposed_national_material_id,
        "proposed_national_material_code": case.proposed_national_material_code,
        "proposed_standard_description": case.proposed_standard_description,
        "hybrid_score": case.hybrid_score,
        "hybrid_classification": case.hybrid_classification,
        "required_approval_level": case.required_approval_level,
        "current_stage": case.current_stage,
        "approval_status": case.approval_status,
        "l1_reviewer": case.l1_reviewer,
        "l1_decision": case.l1_decision,
        "l1_reviewed_at": case.l1_reviewed_at,
        "l1_notes": case.l1_notes,
        "l2_reviewer": case.l2_reviewer,
        "l2_decision": case.l2_decision,
        "l2_reviewed_at": case.l2_reviewed_at,
        "l2_notes": case.l2_notes,
        "procurement_impact": case.procurement_impact or {},
        "mapping_preview": case.mapping_preview or {},
        "metadata_json": case.metadata_json or {},
        "national_material": national,
        "mappings": mapping_payloads(mappings, national) if national else [],
        "mapping_count": len(mappings),
        "actor_identity_verified": bool((case.metadata_json or {}).get("actor_identity_verified")),
        "created_at": case.created_at,
        "updated_at": case.updated_at,
    }
