"""
Verification script for Prompt 11: Demo Approval Workflow and Audit Trail Layer.
Tests:
1. National material master code generation across all 5 technical domains + fallback.
2. Approval level assignment rules (L1_ONLY, L1_AND_L2, L2_SPECIALIST, REJECTED_ONLY).
3. Procurement impact estimation (spend overlap, standardization savings %, risk rating).
4. Dual-tier review simulations (L1 and L2 stage transitions).
5. Cryptographic SHA-256 audit trail chaining, genesis block linking, and tamper detection.
6. FastAPI ASGI execution of:
   - GET /api/approvals/demo-queue
   - POST /api/approvals/demo-action
   - GET /api/audit/demo-trail
   - GET /api/audit/demo-verify
"""

import sys
import copy
import json
import asyncio
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from main import app
from app.services.approval_workflow import (
    generate_national_material_code,
    assign_approval_level,
    estimate_procurement_impact,
    generate_mapping_preview,
    simulate_l1_review,
    simulate_l2_review,
    build_demo_approval_queue,
)
from app.services.audit_trail import (
    GENESIS_HASH,
    compute_event_hash,
    create_audit_event,
    verify_audit_chain_integrity,
    build_demo_audit_trail,
)
from app.schemas.approval_workflow import (
    ApprovalStage,
    ApprovalWorkflowStatus,
    ApprovalDecision,
)


# Native ASGI test client helper (requires no httpx dependency)
async def make_request(app, method: str, path: str, json_data: dict = None, query_string: str = ""):
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": query_string.encode("utf-8"),
        "headers": [(b"host", b"testserver"), (b"content-type", b"application/json")],
    }
    response_body = []
    status_code = 0
    response_headers = []

    body_bytes = json.dumps(json_data).encode("utf-8") if json_data is not None else b""
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body_bytes, "more_body": False}
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        nonlocal status_code, response_headers, response_body
        if message["type"] == "http.response.start":
            status_code = message["status"]
            response_headers = message.get("headers", [])
        elif message["type"] == "http.response.body":
            response_body.append(message.get("body", b""))

    await app(scope, receive, send)
    full_body = b"".join(response_body).decode("utf-8")
    try:
        data = json.loads(full_body) if full_body else None
    except Exception:
        data = full_body
    return status_code, data


async def run_tests():
    print("==================================================================")
    print("Starting Prompt 11 Verification: Approval Workflow & Audit Trail")
    print("==================================================================")

    # 1. National Material Code Generation
    print("\n[1/6] Testing National Material Code Generation...")
    code_brg = generate_national_material_code(
        category="BEARINGS",
        standard_description="DEEP GROOVE BALL BEARING 6205 2RS C3",
        attributes={"bearing_number": "6205", "seal_type": "2RS"}
    )
    print(f"  - Bearing Code: {code_brg}")
    assert code_brg == "NAMM-BRG-6205-2RS", f"Expected NAMM-BRG-6205-2RS, got {code_brg}"

    code_pip = generate_national_material_code(
        category="PIPES_AND_TUBES",
        standard_description="STAINLESS STEEL PIPE 50 NB SCH 40 ASTM A312 SS304",
        attributes={"material_grade": "SS304", "nominal_bore": 50, "schedule": "40"}
    )
    print(f"  - Pipe Code: {code_pip}")
    assert "NAMM-PIP-SS-050-S40" in code_pip, f"Unexpected pipe code: {code_pip}"

    code_vlv = generate_national_material_code(
        category="VALVES",
        standard_description="BALL VALVE 50 NB CLASS 150 FLANGED ASTM A216",
        attributes={"nominal_size": 50, "class_rating": "CL150"}
    )
    print(f"  - Valve Code: {code_vlv}")
    assert "NAMM-VLV-BALL-050-CL150" in code_vlv, f"Unexpected valve code: {code_vlv}"

    code_cbl = generate_national_material_code(
        category="ELECTRICAL_CABLES",
        standard_description="1.1KV 3 CORE 185 SQMM XLPE ARMOURED ALUMINIUM CABLE",
        attributes={"conductor_material": "AL", "core_count": 3, "cross_section_sqmm": 185}
    )
    print(f"  - Cable Code: {code_cbl}")
    assert code_cbl == "NAMM-CBL-AL-3C-185SQ", f"Unexpected cable code: {code_cbl}"

    code_mtr = generate_national_material_code(
        category="MOTORS",
        standard_description="3 PHASE SQUIRREL CAGE INDUCTION MOTOR 15KW 1440RPM",
        attributes={"power_kw": 15, "rpm": 1440}
    )
    print(f"  - Motor Code: {code_mtr}")
    assert code_mtr == "NAMM-MTR-15KW-1440RPM", f"Unexpected motor code: {code_mtr}"

    code_fallback = generate_national_material_code(
        category="UNKNOWN_MISC",
        standard_description="SPECIAL PROPRIETARY TOOLING JIG ASSEMBLY",
        attributes={}
    )
    print(f"  - Fallback Code: {code_fallback}")
    assert code_fallback.startswith("NAMM-DRAFT-"), f"Unexpected fallback code: {code_fallback}"
    print("  ✓ National code generation tests passed.")

    # 2. Approval Level Assignment Rules
    print("\n[2/6] Testing Approval Level Assignment Rules...")
    assert assign_approval_level("AUTO_MATCH_RECOMMENDED", 0.94) == "L1_ONLY"
    assert assign_approval_level("STRONG_REVIEW_CANDIDATE", 0.82) == "L1_AND_L2"
    assert assign_approval_level("MANUAL_REVIEW_REQUIRED", 0.68) == "L1_AND_L2"
    assert assign_approval_level("WEAK_MATCH_REVIEW_OPTIONAL", 0.52) == "L2_SPECIALIST"
    assert assign_approval_level("REJECTED_BY_SCORING", 0.20) == "REJECTED_ONLY"
    print("  ✓ Approval level assignments verified.")

    # 3. Procurement Impact Estimation
    print("\n[3/6] Testing Procurement Impact Estimation...")
    impact = estimate_procurement_impact(
        category="BEARINGS",
        hybrid_score=0.92,
        cpses=["BHEL", "SAIL"]
    )
    print(f"  - Overlap Spend: ₹{impact.estimated_annual_spend_overlap:,.2f}")
    print(f"  - Savings %: {impact.standardization_savings_percent}%")
    print(f"  - Estimated Savings: ₹{impact.estimated_savings_inr:,.2f}")
    print(f"  - Risk: {impact.procurement_risk_level}")
    assert impact.estimated_annual_spend_overlap == 2400000.0
    assert impact.estimated_savings_inr > 0
    assert impact.procurement_risk_level == "LOW"
    assert impact.is_demo_estimate is True
    print("  ✓ Procurement impact model verified.")

    # 4. Multi-Tier Review Simulation
    print("\n[4/6] Testing Multi-Tier Review Simulations (L1 and L2)...")
    queue = build_demo_approval_queue()
    assert queue.total_cases > 0, "Demo queue should have populated cases"
    print(f"  - Demo queue total cases: {queue.total_cases}")
    print(f"  - Pending L1: {queue.pending_l1_count}, Pending L2: {queue.pending_l2_count}, Completed: {queue.completed_count}")

    test_case = queue.cases[0]

    # Test L1 Review -> Transition to PENDING_L2 (or COMPLETED if L1_ONLY)
    l1_result = simulate_l1_review(
        test_case,
        decision="APPROVE",
        reviewer="Nodal Officer Sharma (BHEL)",
        notes="Technical parameter parity verified."
    )
    print(f"  - L1 Action applied. Resulting stage: {l1_result.current_stage}")
    assert l1_result.l1_decision == "APPROVE"
    assert l1_result.l1_reviewer == "Nodal Officer Sharma (BHEL)"
    if test_case.required_approval_level == "L1_ONLY":
        assert l1_result.current_stage == ApprovalStage.COMPLETED
    else:
        assert l1_result.current_stage == ApprovalStage.PENDING_L2

    # Test L2 Review -> Transition to COMPLETED
    l2_result = simulate_l2_review(
        l1_result,
        decision="APPROVE",
        reviewer="Director General Verma (DPE)",
        notes="Unified national catalog alias ratified."
    )
    print(f"  - L2 Action applied. Resulting stage: {l2_result.current_stage}")
    assert l2_result.current_stage == ApprovalStage.COMPLETED
    assert l2_result.approval_status == ApprovalWorkflowStatus.APPROVED_AS_UNIFIED_SKU
    assert l2_result.l2_decision == "APPROVE"

    # Test REJECT decision
    reject_result = simulate_l1_review(
        test_case,
        decision="REJECT",
        reviewer="Nodal Officer Sharma",
        notes="Items incompatible in operating clearance."
    )
    assert reject_result.current_stage == ApprovalStage.REJECTED
    assert reject_result.approval_status == ApprovalWorkflowStatus.REJECTED_DISTINCT
    print("  ✓ Multi-tier review state transitions verified.")

    # 5. Cryptographic SHA-256 Audit Trail & Tamper Detection
    print("\n[5/6] Testing Cryptographic SHA-256 Hash Chaining & Tamper Detection...")
    trail = build_demo_audit_trail()
    print(f"  - Audit trail event count: {trail.total_events}")
    print(f"  - Genesis hash: {trail.genesis_hash}")
    print(f"  - Latest tip hash: {trail.latest_hash}")
    assert trail.total_events >= 8, f"Expected at least 8 events, got {trail.total_events}"
    assert trail.genesis_hash == GENESIS_HASH
    assert len(trail.latest_hash) == 64

    # Verify intact chain
    verification = verify_audit_chain_integrity(trail.events)
    print(f"  - Verification status: {verification.chain_status}, Is Valid: {verification.is_valid}")
    assert verification.is_valid is True
    assert verification.chain_status == "CHAIN_INTACT"
    assert verification.verified_event_count == len(trail.events)

    # Tamper Test: Corrupt a payload inside the chain
    tampered_events = copy.deepcopy(trail.events)
    tampered_events[3].actor = "malicious_actor@attacker.com"
    tamper_check = verify_audit_chain_integrity(tampered_events)
    print(f"  - Tamper detection result: {tamper_check.chain_status} (is_valid={tamper_check.is_valid})")
    assert tamper_check.is_valid is False
    assert tamper_check.chain_status == "CHAIN_BROKEN"
    print(f"  - Tamper message: {tamper_check.message}")
    print("  ✓ Cryptographic hash chaining and tamper detection verified.")

    # 6. FastAPI Endpoints via native ASGI make_request
    print("\n[6/6] Testing FastAPI REST Endpoints via ASGI...")

    # 6a. GET /api/approvals/demo-queue
    status, q_data = await make_request(app, "GET", "/api/approvals/demo-queue")
    assert status == 200, f"demo-queue failed with status {status}: {q_data}"
    print(f"  - GET /api/approvals/demo-queue -> 200 OK (total cases: {q_data['total_cases']})")
    assert "cases" in q_data
    assert len(q_data["cases"]) > 0

    target_case_id = q_data["cases"][0]["approval_case_id"]

    # 6b. POST /api/approvals/demo-action
    action_payload = {
        "approval_case_id": target_case_id,
        "decision": "APPROVE",
        "reviewer_name": "Technical Nodal Officer Sharma",
        "reviewer_role": "NODAL_OFFICER",
        "reviewer_note": "Verified dimensional tolerance and seal compatibility in memory.",
        "stage": "L1_REVIEW"
    }
    status, act_data = await make_request(app, "POST", "/api/approvals/demo-action", json_data=action_payload)
    assert status == 200, f"demo-action failed with status {status}: {act_data}"
    print(f"  - POST /api/approvals/demo-action -> 200 OK")
    print(f"    Status: {act_data['status']}, Persisted: {act_data['persisted']}")
    print(f"    Message: {act_data['message']}")
    assert act_data["persisted"] is False
    assert "generated_audit_event" in act_data
    assert len(act_data["generated_audit_event"]["hash_signature"]) == 64

    # 6c. GET /api/audit/demo-trail
    status, trail_data = await make_request(app, "GET", "/api/audit/demo-trail")
    assert status == 200, f"demo-trail failed with status {status}: {trail_data}"
    print(f"  - GET /api/audit/demo-trail -> 200 OK (total events: {trail_data['total_events']})")
    assert trail_data["chain_verified"] is True
    assert trail_data["tamper_evident"] is True
    assert trail_data["genesis_hash"] == GENESIS_HASH

    # 6d. GET /api/audit/demo-verify
    status, v_data = await make_request(app, "GET", "/api/audit/demo-verify")
    assert status == 200, f"demo-verify failed with status {status}: {v_data}"
    print(f"  - GET /api/audit/demo-verify -> 200 OK (chain status: {v_data['chain_status']})")
    assert v_data["is_valid"] is True
    assert v_data["chain_status"] == "CHAIN_INTACT"

    print("\n==================================================================")
    print("ALL PROMPT 11 VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("==================================================================")


if __name__ == "__main__":
    asyncio.run(run_tests())
