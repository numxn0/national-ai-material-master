"""
Final Verification Script for National AI Material Master Prototype (Prompt 12).
Executes a comprehensive, non-destructive audit of all 11 REST endpoints across:
- Core Health & Platform Demo Summary
- Ingestion Preview & Rule-based Attribute Extraction
- RapidFuzz Candidate Matching & Deterministic Embedding Vectors
- Hybrid Scoring & SHAP-Style Explainability
- Dual-Tier Governance Approvals & Cryptographic Audit Trail Chaining
"""

import sys
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


async def verify_all():
    print("========================================================================")
    print("   NATIONAL AI MATERIAL MASTER — FINAL SYSTEM VERIFICATION (PROMPT 12)   ")
    print("========================================================================")

    results = []

    # 1. /health
    st, d = await make_request(app, "GET", "/health")
    assert st == 200 and d.get("status") == "healthy", f"/health failed: {st}, {d}"
    results.append(("1. System Health Check", "GET /health", st, "Healthy (0.1.0)"))
    print("  [PASS] 1. System Health Check -> 200 OK")

    # 2. /api/demo/summary
    st, d = await make_request(app, "GET", "/api/demo/summary")
    assert st == 200, f"/api/demo/summary failed: {st}, {d}"
    assert d.get("service_status") == "operational"
    assert d.get("audit_chain_status") == "CHAIN_INTACT"
    assert d.get("persistence_status") == "demo_in_memory_only"
    assert len(d.get("modules", [])) >= 9
    results.append(("2. Demo Executive Summary", "GET /api/demo/summary", st, f"{len(d['modules'])} Modules, Chain Intact"))
    print(f"  [PASS] 2. Demo Executive Summary -> 200 OK ({d['sample_material_count']} items, {d['candidate_count']} pairs, {len(d['modules'])} modules)")

    # 3. /api/materials/preview-sample
    st, d = await make_request(app, "GET", "/api/materials/preview-sample")
    assert st == 200, f"/api/materials/preview-sample failed: {st}, {d}"
    assert d.get("success") is True
    assert len(d.get("valid_records", [])) > 0
    results.append(("3. Ingestion Preview", "GET /api/materials/preview-sample", st, f"{len(d['valid_records'])} Valid Records"))
    print(f"  [PASS] 3. Ingestion Preview -> 200 OK ({len(d['valid_records'])} valid sample records)")

    # 4. /api/materials/extract-attributes
    sample_attr_req = {
        "raw_description": "DEEP GROOVE BALL BEARING 6205 2RS C3 SKF",
        "category": "BEARINGS",
        "uom": "NOS"
    }
    st, d = await make_request(app, "POST", "/api/materials/extract-attributes", json_data=sample_attr_req)
    assert st == 200, f"/api/materials/extract-attributes failed: {st}, {d}"
    assert "extracted_attributes" in d
    assert d["extracted_attributes"].get("bearing_number") == "6205"
    results.append(("4. Attribute Extraction", "POST /api/materials/extract-attributes", st, f"Bearing 6205, Conf {d['extraction_confidence']}"))
    print("  [PASS] 4. Attribute Extraction -> 200 OK (Bearing 6205 parsed)")

    # 5. /api/matching/candidates/sample
    st, d = await make_request(app, "GET", "/api/matching/candidates/sample")
    assert st == 200, f"/api/matching/candidates/sample failed: {st}, {d}"
    assert d.get("candidate_count", 0) > 0
    top_cand = d["candidates"][0]
    results.append(("5. Candidate Detection (RapidFuzz)", "GET /api/matching/candidates/sample", st, f"{d['candidate_count']} Pairs, Top {top_cand['score']}"))
    print(f"  [PASS] 5. Candidate Duplicate Detection -> 200 OK ({d['candidate_count']} candidate pairs)")

    # 6. /api/matching/embedding/sample
    st, d = await make_request(app, "GET", "/api/matching/embedding/sample")
    assert st == 200, f"/api/matching/embedding/sample failed: {st}, {d}"
    assert d.get("total_comparisons", 0) >= 5
    assert d.get("pgvector_ready") is True
    results.append(("6. Semantic Embedding (Stub)", "GET /api/matching/embedding/sample", st, f"{d['total_comparisons']} Vector Contrasts, 64-dim"))
    print(f"  [PASS] 6. Semantic Vector Similarity Stub -> 200 OK ({d['total_comparisons']} contrast pairs, pgvector-ready)")

    # 7. /api/matching/hybrid-score/sample
    st, d = await make_request(app, "GET", "/api/matching/hybrid-score/sample")
    assert st == 200, f"/api/matching/hybrid-score/sample failed: {st}, {d}"
    assert len(d.get("candidates", [])) > 0
    top_hybrid = d["candidates"][0]
    results.append(("7. Hybrid Match Scoring", "GET /api/matching/hybrid-score/sample", st, f"Top Score {top_hybrid['hybrid_score']}"))
    print(f"  [PASS] 7. Hybrid Match Scoring Engine -> 200 OK (Top hybrid score: {top_hybrid['hybrid_score']})")

    # 8. /api/matching/explain/sample
    st, d = await make_request(app, "GET", "/api/matching/explain/sample")
    assert st == 200, f"/api/matching/explain/sample failed: {st}, {d}"
    assert d.get("total_explained", 0) > 0
    results.append(("8. SHAP-Style Explainability", "GET /api/matching/explain/sample", st, f"{d['total_explained']} Pairs Explained"))
    print(f"  [PASS] 8. SHAP-Style Explainability -> 200 OK ({d['total_explained']} explanations generated)")

    # 9. /api/approvals/demo-queue
    st, d = await make_request(app, "GET", "/api/approvals/demo-queue")
    assert st == 200, f"/api/approvals/demo-queue failed: {st}, {d}"
    assert d.get("total_cases", 0) > 0
    results.append(("9. Dual Governance Approvals", "GET /api/approvals/demo-queue", st, f"{d['total_cases']} Cases (L1:{d['pending_l1_count']}, L2:{d['pending_l2_count']})"))
    print(f"  [PASS] 9. Dual Governance Approvals -> 200 OK ({d['total_cases']} cases in queue)")

    # 10. /api/audit/demo-trail
    st, d = await make_request(app, "GET", "/api/audit/demo-trail")
    assert st == 200, f"/api/audit/demo-trail failed: {st}, {d}"
    assert d.get("chain_verified") is True
    assert d.get("total_events", 0) >= 8
    results.append(("10. Cryptographic Audit Trail", "GET /api/audit/demo-trail", st, f"{d['total_events']} Blocks Chained"))
    print(f"  [PASS] 10. Cryptographic Audit Trail -> 200 OK ({d['total_events']} SHA-256 blocks chained)")

    # 11. /api/audit/demo-verify (GET & POST)
    st, d = await make_request(app, "GET", "/api/audit/demo-verify")
    assert st == 200, f"GET /api/audit/demo-verify failed: {st}, {d}"
    assert d.get("is_valid") is True
    assert d.get("chain_status") == "CHAIN_INTACT"

    st_post, d_post = await make_request(app, "POST", "/api/audit/demo-verify")
    assert st_post == 200, f"POST /api/audit/demo-verify failed: {st_post}, {d_post}"
    assert d_post.get("is_valid") is True
    assert d_post.get("chain_status") == "CHAIN_INTACT"
    results.append(("11. Audit Chain Integrity", "GET & POST /api/audit/demo-verify", st, "CHAIN_INTACT (100% Verified)"))
    print(f"  [PASS] 11. Audit Chain Integrity -> 200 OK (GET & POST Status: CHAIN_INTACT)")

    print("\n========================================================================")
    print("                      EXECUTIVE READINESS MATRIX                       ")
    print("========================================================================")
    print(f"{'Module / Capability':<35} | {'Endpoint':<34} | {'Status':<6} | {'Details'}")
    print("-" * 105)
    for name, ep, code, note in results:
        print(f"{name:<35} | {ep:<34} | {code:<6} | {note}")
    print("========================================================================")
    print(" >> ALL 11 ENDPOINTS VERIFIED OPERATIONAL (DEMO-READY, ZERO PERSISTENCE) << ")
    print("========================================================================")


if __name__ == "__main__":
    asyncio.run(verify_all())
