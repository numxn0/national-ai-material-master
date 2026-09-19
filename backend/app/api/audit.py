from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any, List
from datetime import datetime

from app.schemas.audit import (
    AuditLogResponse,
    AuditTrailResponse,
    AuditChainVerificationResponse,
)
from app.schemas.examples import EXAMPLE_AUDIT_LOG
from app.services.audit_trail import (
    build_demo_audit_trail,
    verify_audit_chain_integrity,
)

router = APIRouter(prefix="/audit", tags=["Audit & Compliance Trail"])


# --- Legacy Placeholder Data ---
PLACEHOLDER_AUDIT_LOGS = [
    {
        "log_id": "aud-801",
        "timestamp": "2026-09-18T10:14:22Z",
        "actor": "officer.sharma@railways.gov.in",
        "action": "MERGE_APPROVED",
        "target_entity": "ITEM: CR-BEAR-6205",
        "details": "Merged duplicate item Northern Railways 6205 into National Master SKU-BEAR-0992",
        "ai_confidence_snapshot": 0.96,
        "verification_tier": "L1",
        "hash_signature": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    },
    {
        "log_id": "aud-802",
        "timestamp": "2026-09-18T09:45:00Z",
        "actor": "SYSTEM_AI_ENGINE",
        "action": "DUPLICATE_CANDIDATES_FLAGGED",
        "target_entity": "BATCH: batch-2026-001",
        "details": "AI detected 48 potential duplicate items with confidence >= 0.85",
        "ai_confidence_snapshot": 0.88,
        "verification_tier": "AUTOMATED",
        "hash_signature": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb"
    },
    {
        "log_id": "aud-803",
        "timestamp": "2026-09-18T08:30:10Z",
        "actor": "admin.verma@nic.in",
        "action": "TAXONOMY_SCHEMA_UPDATED",
        "target_entity": "CATEGORY: Fasteners (IS 1364)",
        "details": "Added standardized metric thread dimension requirement to master schema",
        "ai_confidence_snapshot": None,
        "verification_tier": "L2_ADMIN",
        "hash_signature": "3e23e8160039594a33894f6564e1b1348bbd7a0088d42c4acb73eeaed59c009d"
    }
]


# --- Prompt 11 Cryptographic Audit Trail Endpoints ---

@router.get("/demo-trail", response_model=AuditTrailResponse, tags=["Audit & Compliance Trail"])
async def get_demo_audit_trail():
    """
    Returns an ordered, cryptographically SHA-256 chained audit trail for the demonstration pipeline.
    Chained from Genesis block to latest approval action with verifiable hash signatures.
    Strictly in-memory and non-persisted.
    """
    try:
        return build_demo_audit_trail()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate demo audit trail: {str(exc)}"
        )


@router.get("/demo-verify", response_model=AuditChainVerificationResponse, tags=["Audit & Compliance Trail"])
@router.post("/demo-verify", response_model=AuditChainVerificationResponse, tags=["Audit & Compliance Trail"])
async def verify_demo_audit_chain():
    """
    Cryptographically verifies sequential SHA-256 hash chaining across all events in the demo audit trail.
    Detects any block tampering, parent hash divergence, or corrupted payloads.
    """
    try:
        trail = build_demo_audit_trail()
        return verify_audit_chain_integrity(trail.events)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to verify audit chain integrity: {str(exc)}"
        )


# --- Legacy / Canonical Endpoints ---

@router.get("/canonical/example", response_model=AuditLogResponse, tags=["Canonical Audit"])
async def get_canonical_audit_example():
    """
    Retrieve typed example of an immutable cryptographic Audit Log record.
    Shaped by AuditLogResponse Pydantic schema.
    """
    return EXAMPLE_AUDIT_LOG


@router.get("", response_model=Dict[str, Any])
@router.get("/logs", response_model=Dict[str, Any])
async def get_audit_trail(
    limit: int = Query(20, ge=1, le=100),
    action: str = None
):
    """
    Placeholder endpoint: Retrieve immutable compliance audit trail.
    """
    logs = PLACEHOLDER_AUDIT_LOGS
    if action:
        logs = [l for l in logs if l["action"] == action]

    return {
        "status": "success",
        "message": "Audit logs retrieved (placeholder mode)",
        "total": len(logs),
        "logs": logs
    }


@router.get("/metrics", response_model=Dict[str, Any])
async def get_compliance_metrics():
    """
    Placeholder endpoint: Summary of standardization and catalog governance health.
    """
    return {
        "status": "success",
        "data": {
            "total_items_cataloged": 142580,
            "duplicate_reduction_rate": "18.4%",
            "procurement_savings_identified_cr": 42.8,
            "human_in_loop_agreement_rate": "97.2%",
            "immutable_log_count": 89412
        }
    }
