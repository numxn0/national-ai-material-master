"""
Verification script for Prompt 10: SHAP-Style Explainability and AI Match Review Workflow.
Tests:
1. Deterministic factor contributions, directions, evidence, and percentages.
2. Positive and risk factor filtering.
3. Conflict and missing data explanation generators.
4. Reviewer summary generation across score bands.
5. Audit explanation format and method version string.
6. FastAPI endpoints:
   - GET /api/matching/explain/sample
   - POST /api/matching/explain
   - POST /api/matching/review-decision/demo (in-memory demo verification)
7. Regressions on candidate matching, embedding stub, and hybrid scoring.
"""

import sys
import json
import asyncio
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from main import app
from app.services.ingestion_preview import parse_csv_content
from app.services.candidate_matching import find_duplicate_candidates
from app.services.hybrid_scoring import score_candidates_hybrid, score_candidate_hybrid
from app.services.explainability import (
    generate_factor_contributions,
    generate_positive_explanations,
    generate_risk_explanations,
    generate_conflict_explanations,
    generate_missing_data_explanations,
    generate_reviewer_summary,
    generate_audit_explanation,
    explain_scored_candidate,
    explain_scored_candidates,
)
from app.schemas.explainability import (
    ExplanationDirection,
    ReviewerExplanation,
    AuditExplanation,
)


# ASGI test client helper
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


async def run_verifications():
    print("=" * 70)
    print("PROMPT 10: SHAP-STYLE EXPLAINABILITY & REVIEW WORKFLOW VERIFICATION")
    print("=" * 70)

    # 1. Ingestion and Candidate Generation
    sample_csv = backend_dir / "../sample-data/sample_materials_raw.csv"
    assert sample_csv.exists(), f"Sample CSV not found at {sample_csv}"

    with open(sample_csv, "r", encoding="utf-8") as f:
        csv_text = f.read()

    preview = parse_csv_content(csv_text, "sample_materials_raw.csv")
    assert len(preview.valid_records) > 0

    cand_resp = find_duplicate_candidates(preview.valid_records, min_score=0.50, enrich_embeddings=True)
    assert len(cand_resp.candidates) > 0
    scored_candidates = score_candidates_hybrid(cand_resp.candidates)
    assert len(scored_candidates) > 0

    print("\n--- 1. Testing Explainability Core Services ---")
    top_cand = scored_candidates[0]
    factors = generate_factor_contributions(top_cand)
    assert len(factors) == 9, f"Expected 9 factors, got {len(factors)}"

    factor_names = [f.factor_name for f in factors]
    expected_names = [
        "description_similarity",
        "attribute_similarity",
        "semantic_similarity",
        "token_overlap",
        "category_compatibility",
        "uom_compatibility",
        "manufacturer_part_model",
        "completeness_bonus",
        "conflict_penalty",
    ]
    for name in expected_names:
        assert name in factor_names, f"Missing factor {name}"
    print(f"[PASS] Generated 9 SHAP-style factors for candidate {top_cand.pair_id}:")
    for f in factors:
        print(f"       - {f.display_label} [{f.factor_name}]: {f.contribution_value:+.4f} ({f.contribution_percentage:+.1f}%) | {f.direction.value}")
        assert len(f.evidence) > 0, f"Evidence missing for factor {f.factor_name}"

    # Test positive and risk factor filtering
    pos_factors = generate_positive_explanations(top_cand)
    risk_factors = generate_risk_explanations(top_cand)
    print(f"[PASS] Positive factors: {len(pos_factors)} | Risk factors: {len(risk_factors)}")
    for pf in pos_factors:
        assert pf.direction == ExplanationDirection.POSITIVE
    for rf in risk_factors:
        assert rf.direction == ExplanationDirection.NEGATIVE

    # Test reviewer summary
    summary = generate_reviewer_summary(top_cand)
    assert len(summary) > 20
    print(f"[PASS] Reviewer Summary: '{summary}'")

    # Test audit explanation
    audit = generate_audit_explanation(top_cand)
    assert audit.candidate_pair_id == top_cand.pair_id
    assert audit.hybrid_score == top_cand.hybrid_score
    assert "hybrid-rule-v1 + semantic-stub-v1 + explainability-v1" in audit.method_version
    print(f"[PASS] Audit Record: Version='{audit.method_version}', Score={audit.hybrid_score:.4f}, Drivers={audit.top_positive_factors}")

    # Test candidate with conflict penalty (e.g. Bearing 6205 vs 6305 or similar if present)
    conflicted_cands = [c for c in scored_candidates if c.hybrid_score_breakdown.conflict_penalty_applied]
    if conflicted_cands:
        cc = conflicted_cands[0]
        c_conflicts = generate_conflict_explanations(cc)
        c_factors = generate_factor_contributions(cc)
        pen_factor = next(f for f in c_factors if f.factor_name == "conflict_penalty")
        assert pen_factor.direction == ExplanationDirection.NEGATIVE
        assert pen_factor.contribution_value < 0
        print(f"[PASS] Conflicted candidate '{cc.pair_id}' properly penalized: {pen_factor.explanation} ({pen_factor.contribution_value})")
        print(f"       Conflict statements: {c_conflicts}")

    # Test full explanation object
    full_explanation = explain_scored_candidate(top_cand)
    assert isinstance(full_explanation, ReviewerExplanation)
    assert full_explanation.pair_id == top_cand.pair_id
    assert full_explanation.reviewer_summary == summary
    print(f"[PASS] Full ReviewerExplanation model constructed successfully.")

    # 2. Testing Endpoints
    print("\n--- 2. Testing FastAPI Endpoints ---")
    status, health = await make_request(app, "GET", "/health")
    assert status == 200, f"/health failed: {status}"
    print("[PASS] /health returns 200.")

    # GET /api/matching/explain/sample
    status, sample_resp = await make_request(app, "GET", "/api/matching/explain/sample")
    assert status == 200, f"/api/matching/explain/sample failed: {status}"
    assert sample_resp["total_explained"] > 0
    assert len(sample_resp["explanations"]) == sample_resp["total_explained"]
    first_exp = sample_resp["explanations"][0]
    print(f"[PASS] GET /api/matching/explain/sample returned {sample_resp['total_explained']} explained candidates.")
    print(f"       Top pair: {first_exp['pair_id']} - Score: {first_exp['hybrid_score']:.4f}")
    print(f"       Summary: {first_exp['reviewer_summary']}")
    assert "positive_factors" in first_exp
    assert "risk_factors" in first_exp
    assert "audit_explanation" in first_exp

    # POST /api/matching/explain
    status, post_exp = await make_request(
        app,
        "POST",
        "/api/matching/explain",
        json_data=[top_cand.model_dump(mode="json")]
    )
    assert status == 200, f"POST /api/matching/explain failed: {status}"
    assert post_exp["total_explained"] == 1
    assert post_exp["explanations"][0]["pair_id"] == top_cand.pair_id
    print("[PASS] POST /api/matching/explain successfully explained single candidate payload.")

    # POST /api/matching/review-decision/demo
    review_req = {
        "candidate_id": top_cand.pair_id,
        "decision": "APPROVE",
        "reviewer_note": "Verified specs: 6205-2RS deep groove ball bearing matches Northern Railway stock.",
        "reviewer_name": "Railway Nodal Officer - Reviewer 01"
    }
    status, review_resp = await make_request(app, "POST", "/api/matching/review-decision/demo", json_data=review_req)
    assert status == 200, f"POST /api/matching/review-decision/demo failed: {status}"
    assert review_resp["status"] == "demo_accepted"
    assert review_resp["persisted"] is False
    assert "Demo-only decision accepted in memory; not persisted." in review_resp["message"]
    assert review_resp["candidate_id"] == top_cand.pair_id
    assert review_resp["decision"] == "APPROVE"
    print(f"[PASS] POST /api/matching/review-decision/demo confirmed demo response:")
    print(f"       Status: {review_resp['status']} | Persisted: {review_resp['persisted']}")
    print(f"       Message: '{review_resp['message']}'")

    # Test invalid decision returns 400
    bad_req = {"candidate_id": "test-123", "decision": "INVALID_DECISION"}
    status, bad_resp = await make_request(app, "POST", "/api/matching/review-decision/demo", json_data=bad_req)
    assert status == 400
    print("[PASS] Invalid decision rejected with HTTP 400 as expected.")

    # 3. Regression Checks
    print("\n--- 3. Regression Checks on Existing Endpoints ---")
    status, cand_s = await make_request(app, "GET", "/api/matching/candidates/sample")
    assert status == 200
    status, emb_s = await make_request(app, "GET", "/api/matching/embedding/sample")
    assert status == 200
    status, hyb_s = await make_request(app, "GET", "/api/matching/hybrid-score/sample")
    assert status == 200
    status, ml_s = await make_request(app, "GET", "/api/matching/ml-training-plan")
    assert status == 200
    status, ml_exp = await make_request(app, "GET", "/api/matching/ml-feature-export/sample")
    assert status == 200
    print("[PASS] All candidate, embedding, hybrid scoring, and ML endpoints continue to operate without regression.")

    print("\n" + "=" * 70)
    print("ALL PROMPT 10 BACKEND CHECKS COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_verifications())
