"""
Audit Trail Service with Cryptographic SHA-256 Tamper-Evident Chaining.
Implements blockchain-inspired sequential hash linking for material master governance,
demo pipeline event generation, and full cryptographic integrity verification.
Strictly non-persisted demonstration logic adhering to Prompt 11 requirements.
"""

import json
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from app.schemas.audit import (
    AuditTrailEvent,
    AuditTrailResponse,
    AuditChainVerificationResponse,
)

GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"


def _deterministic_serialize(val: Any) -> str:
    """Serializes arbitrary dictionaries or primitives into a canonical JSON string."""
    if val is None:
        return ""
    try:
        return json.dumps(val, sort_keys=True, separators=(",", ":"))
    except Exception:
        return str(val)


def compute_event_hash(
    previous_hash: str,
    audit_id: str,
    timestamp: str,
    actor: str,
    action: str,
    entity_id: str,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None
) -> str:
    """
    Computes a cryptographic SHA-256 tamper-evident hash for an audit log event.
    Chains the immediately preceding event's hash to guarantee chronological immutability.
    Formula: SHA-256(previous_hash | audit_id | timestamp | actor | action | entity_id | payload_hash)
    """
    payload_str = f"{_deterministic_serialize(old_value)}|{_deterministic_serialize(new_value)}|{reason or ''}"
    payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    raw_signature_source = (
        f"{previous_hash}|"
        f"{audit_id}|"
        f"{timestamp}|"
        f"{actor}|"
        f"{action}|"
        f"{entity_id}|"
        f"{payload_hash}"
    )
    return hashlib.sha256(raw_signature_source.encode("utf-8")).hexdigest()


def create_audit_event(
    audit_id: str,
    timestamp: str,
    actor: str,
    actor_role: str,
    action: str,
    entity_type: str,
    entity_id: str,
    previous_hash: str,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None,
    method_version: str = "hybrid-rule-v1 + audit-hashchain-v1"
) -> AuditTrailEvent:
    """
    Creates an AuditTrailEvent sealed with a cryptographic SHA-256 signature chained to previous_hash.
    """
    signature = compute_event_hash(
        previous_hash=previous_hash,
        audit_id=audit_id,
        timestamp=timestamp,
        actor=actor,
        action=action,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        reason=reason
    )

    verification_status = "GENESIS" if previous_hash == GENESIS_HASH else "VERIFIED"

    return AuditTrailEvent(
        audit_id=audit_id,
        timestamp=timestamp,
        actor=actor,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        reason=reason,
        method_version=method_version,
        previous_hash=previous_hash,
        hash_signature=signature,
        verification_status=verification_status,
    )


def verify_audit_chain_integrity(events: List[AuditTrailEvent]) -> AuditChainVerificationResponse:
    """
    Sequentially traverses an audit trail and cryptographically validates:
    1. Genesis block references the designated 64-zero parent hash.
    2. Every event's recomputed SHA-256 signature exactly matches its stored hash_signature.
    3. Every subsequent event's previous_hash exactly equals the hash_signature of the prior event.
    Returns full validation status and detailed diagnostic information.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    if not events:
        return AuditChainVerificationResponse(
            chain_status="CHAIN_INTACT",
            verified_event_count=0,
            genesis_hash=GENESIS_HASH,
            latest_hash=GENESIS_HASH,
            is_valid=True,
            verification_timestamp=now_iso,
            message="Audit chain is empty. Zero events to verify."
        )

    for idx, event in enumerate(events):
        # 1. Check parent hash linkage
        if idx == 0:
            if event.previous_hash != GENESIS_HASH:
                return AuditChainVerificationResponse(
                    chain_status="CHAIN_BROKEN",
                    verified_event_count=0,
                    genesis_hash=event.previous_hash,
                    latest_hash=events[-1].hash_signature,
                    is_valid=False,
                    verification_timestamp=now_iso,
                    message=f"Genesis block {event.audit_id} invalid: expected parent hash {GENESIS_HASH}, got {event.previous_hash}."
                )
        else:
            prior_signature = events[idx - 1].hash_signature
            if event.previous_hash != prior_signature:
                return AuditChainVerificationResponse(
                    chain_status="CHAIN_BROKEN",
                    verified_event_count=idx,
                    genesis_hash=events[0].previous_hash,
                    latest_hash=events[-1].hash_signature,
                    is_valid=False,
                    verification_timestamp=now_iso,
                    message=f"Tampering detected at block index {idx} ({event.audit_id}): previous_hash {event.previous_hash[:12]} does not match prior block signature {prior_signature[:12]}."
                )

        # 2. Check internal signature recomputation
        expected_sig = compute_event_hash(
            previous_hash=event.previous_hash,
            audit_id=event.audit_id,
            timestamp=event.timestamp,
            actor=event.actor,
            action=event.action,
            entity_id=event.entity_id,
            old_value=event.old_value,
            new_value=event.new_value,
            reason=event.reason
        )

        if expected_sig != event.hash_signature:
            return AuditChainVerificationResponse(
                chain_status="CHAIN_BROKEN",
                verified_event_count=idx,
                genesis_hash=events[0].previous_hash,
                latest_hash=events[-1].hash_signature,
                is_valid=False,
                verification_timestamp=now_iso,
                message=f"Data corruption detected at block index {idx} ({event.audit_id}): hash signature recomputation mismatch."
            )

    return AuditChainVerificationResponse(
        chain_status="CHAIN_INTACT",
        verified_event_count=len(events),
        genesis_hash=events[0].previous_hash,
        latest_hash=events[-1].hash_signature,
        is_valid=True,
        verification_timestamp=now_iso,
        message=f"Cryptographic audit chain completely verified: all {len(events)} events have valid sequential SHA-256 signatures."
    )


def build_demo_audit_trail() -> AuditTrailResponse:
    """
    Constructs a realistic, 8-stage cryptographic audit trail demonstrating
    the end-to-end governance lifecycle of the National AI Material Master.
    """
    events: List[AuditTrailEvent] = []
    current_parent_hash = GENESIS_HASH

    # 1. Genesis Initialization
    e1 = create_audit_event(
        audit_id="AUD-2026-0001",
        timestamp="2026-09-19T06:00:00.000000Z",
        actor="system.genesis@namm.gov.in",
        actor_role="SYSTEM_AI_ENGINE",
        action="SYSTEM_GENESIS_INITIALIZED",
        entity_type="system_governance",
        entity_id="NAMM-CORE-CLUSTER-01",
        previous_hash=current_parent_hash,
        old_value=None,
        new_value={"state": "INITIALIZED", "version": "v1.0.0", "chain": "SHA-256-TAMPER-EVIDENT"},
        reason="Genesis block established for the National AI Material Master catalog governance ledger."
    )
    events.append(e1)
    current_parent_hash = e1.hash_signature

    # 2. Batch Ingestion Completed
    e2 = create_audit_event(
        audit_id="AUD-2026-0002",
        timestamp="2026-09-19T06:15:30.000000Z",
        actor="ingestion.service@namm.gov.in",
        actor_role="SYSTEM_AI_ENGINE",
        action="BATCH_INGESTION_COMPLETED",
        entity_type="ingestion_batch",
        entity_id="BATCH-MULTI-CPSE-20260919",
        previous_hash=current_parent_hash,
        old_value={"records_loaded": 0},
        new_value={"cpses": ["BHEL", "IOCL", "NTPC", "SAIL"], "total_records": 10, "valid_count": 10},
        reason="Automated CSV parsing, header mapping, and canonical schema conversion completed."
    )
    events.append(e2)
    current_parent_hash = e2.hash_signature

    # 3. Taxonomy Normalization Verified
    e3 = create_audit_event(
        audit_id="AUD-2026-0003",
        timestamp="2026-09-19T06:20:12.000000Z",
        actor="officer.sharma@bhel.gov.in",
        actor_role="NODAL_OFFICER",
        action="TAXONOMY_SCHEMA_VERIFIED",
        entity_type="canonical_taxonomy",
        entity_id="TAXONOMY-CORE-V1",
        previous_hash=current_parent_hash,
        old_value={"unmapped_terms": 4},
        new_value={"standard_categories": 6, "uom_mappings": 24, "unmapped_terms": 0},
        reason="Verified domain standardization for Bearings, Valves, Pipes, Fasteners, Cables, and Motors."
    )
    events.append(e3)
    current_parent_hash = e3.hash_signature

    # 4. Candidate Duplicate Generation
    e4 = create_audit_event(
        audit_id="AUD-2026-0004",
        timestamp="2026-09-19T06:30:45.000000Z",
        actor="matching.engine@namm.gov.in",
        actor_role="SYSTEM_AI_ENGINE",
        action="CANDIDATE_DUPLICATE_PAIRS_DETECTED",
        entity_type="candidate_matching_run",
        entity_id="RUN-RAPIDFUZZ-BLOCKING-01",
        previous_hash=current_parent_hash,
        old_value={"candidate_pairs": 0},
        new_value={"candidate_pairs_detected": 7, "comparison_technique": "RAPIDFUZZ_TOKEN_SET + DOMAIN_BLOCKING"},
        reason="RapidFuzz duplicate candidate screening executed with domain blocking constraints."
    )
    events.append(e4)
    current_parent_hash = e4.hash_signature

    # 5. Hybrid Match Scoring Evaluated
    e5 = create_audit_event(
        audit_id="AUD-2026-0005",
        timestamp="2026-09-19T06:35:18.000000Z",
        actor="scoring.engine@namm.gov.in",
        actor_role="SYSTEM_AI_ENGINE",
        action="HYBRID_SCORING_EVALUATED",
        entity_type="candidate_pair",
        entity_id="PAIR-CR-BEAR-6205-BHEL-BRG-6205",
        previous_hash=current_parent_hash,
        old_value={"initial_rapidfuzz_score": 0.88},
        new_value={
            "hybrid_score": 0.942,
            "classification": "AUTO_MATCH_RECOMMENDED",
            "feature_vector_dimensions": 16,
            "conflict_penalties": 0.0
        },
        reason="Rule-based fusion completed: 25% text + 20% attribute + 20% semantic stub + 10% token + 10% category + 5% UOM + 5% OEM."
    )
    events.append(e5)
    current_parent_hash = e5.hash_signature

    # 6. National Material Code Proposed
    e6 = create_audit_event(
        audit_id="AUD-2026-0006",
        timestamp="2026-09-19T06:40:05.000000Z",
        actor="taxonomy.generator@namm.gov.in",
        actor_role="SYSTEM_AI_ENGINE",
        action="NATIONAL_CODE_PROPOSED",
        entity_type="national_material",
        entity_id="NAMM-BRG-6205-2RS",
        previous_hash=current_parent_hash,
        old_value=None,
        new_value={
            "proposed_code": "NAMM-BRG-6205-2RS",
            "category": "BEARINGS",
            "standard_description": "DEEP GROOVE BALL BEARING 6205 2RS C3",
            "mapped_source_items": ["CR-BEAR-6205", "BHEL-BRG-6205"]
        },
        reason="Deterministic domain rule applied for deep groove ball bearing with synthetic rubber contact seals."
    )
    events.append(e6)
    current_parent_hash = e6.hash_signature

    # 7. Level-1 Nodal Review Completed
    e7 = create_audit_event(
        audit_id="AUD-2026-0007",
        timestamp="2026-09-19T07:05:40.000000Z",
        actor="officer.sharma@bhel.gov.in",
        actor_role="NODAL_OFFICER",
        action="L1_NODAL_VERIFIED",
        entity_type="approval_case",
        entity_id="CASE-CR-BEAR-6205-BHEL-BRG-6205",
        previous_hash=current_parent_hash,
        old_value={"stage": "PENDING_L1", "approval_status": "PENDING"},
        new_value={"stage": "PENDING_L2", "l1_decision": "APPROVE", "l1_notes": "Dimensional and C3 radial clearance alignment verified against IS 6455 standard."},
        reason="Level-1 Technical Nodal verification approved; forwarded to Ministry Oversight Authority for ratification."
    )
    events.append(e7)
    current_parent_hash = e7.hash_signature

    # 8. Level-2 Ministry Ratification
    e8 = create_audit_event(
        audit_id="AUD-2026-0008",
        timestamp="2026-09-19T07:45:10.000000Z",
        actor="dg.verma@dpe.gov.in",
        actor_role="MINISTRY_AUTHORITY",
        action="L2_MINISTRY_RATIFIED",
        entity_type="approval_case",
        entity_id="CASE-CR-BEAR-6205-BHEL-BRG-6205",
        previous_hash=current_parent_hash,
        old_value={"stage": "PENDING_L2", "approval_status": "PENDING"},
        new_value={
            "stage": "COMPLETED",
            "approval_status": "APPROVED_AS_UNIFIED_SKU",
            "published_national_code": "NAMM-BRG-6205-2RS",
            "estimated_annual_savings_inr": 336000.0
        },
        reason="Director General ratified cross-CPSE procurement harmonization under Department of Public Enterprises guidelines."
    )
    events.append(e8)

    verification = verify_audit_chain_integrity(events)

    return AuditTrailResponse(
        total_events=len(events),
        chain_verified=verification.is_valid,
        genesis_hash=events[0].previous_hash,
        latest_hash=events[-1].hash_signature,
        events=events,
        tamper_evident=True,
        note="Demo-only audit trail: cryptographically hashed in memory without database persistence."
    )
