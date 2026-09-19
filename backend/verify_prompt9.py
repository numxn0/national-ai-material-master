"""
Verification script for Prompt 9: Hybrid Match Scoring Engine With XGBoost-Ready Placeholder
Pure asyncio ASGI test harness.
"""

import sys
import os
import json
import asyncio
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from main import app
from app.schemas.hybrid_scoring import (
    HybridClassification,
    MatchFeatureVector,
    HybridScoreBreakdown,
)
from app.schemas.matching import ConflictSignal
from app.services.hybrid_scoring import (
    apply_conflict_penalties,
    calculate_rule_based_hybrid_score,
    classify_hybrid_score,
)
from app.services.ml_feature_pipeline import describe_xgboost_training_plan

async def make_request(method, path, body=b"", headers=None):
    if headers is None:
        headers = []
    
    query_string = b""
    if "?" in path:
        path_part, query_part = path.split("?", 1)
        path = path_part
        query_string = query_part.encode("utf-8")

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": query_string,
        "headers": [[b"host", b"testserver"]] + headers,
    }
    status_code = None
    response_body = []
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        nonlocal status_code
        if message["type"] == "http.response.start":
            status_code = message["status"]
        elif message["type"] == "http.response.body":
            response_body.append(message.get("body", b""))

    await app(scope, receive, send)
    res_str = b"".join(response_body).decode("utf-8")
    return status_code, res_str


async def run_tests():
    print("======================================================================")
    print("PROMPT 9: HYBRID MATCH SCORING & ML FEATURE PIPELINE VERIFICATION")
    print("======================================================================")

    # 1. Test Conflict Penalties & Caps
    print("\n--- 1. Testing Conflict Penalty Caps ---")
    mock_features = MatchFeatureVector(
        description_similarity=0.95,
        token_similarity=0.90,
        semantic_similarity_score=0.92,
        attribute_similarity=0.95,
        exact_attribute_match_count=4,
        conflicting_attribute_count=1,
        critical_attribute_conflict_count=1,
        missing_critical_attribute_count=0,
        category_compatibility=1.0,
        uom_compatibility=1.0,
        manufacturer_match=1.0,
        part_number_match=1.0,
        model_number_match=1.0,
        source_cpse_match=0.0,
        confidence_gap=0.0,
        requires_human_review=True,
    )

    # 1.1 Single critical conflict (general) -> cap at 0.60
    conflicts_single = [ConflictSignal(
        attribute="schedule",
        value_a="SCH 40",
        value_b="SCH 80",
        severity="CRITICAL",
        description="Schedule mismatch"
    )]
    score, breakdown = calculate_rule_based_hybrid_score(mock_features, conflicts_single)
    assert score <= 0.60, f"Expected score <= 0.60, got {score}"
    assert breakdown.conflict_penalty_applied is True
    print(f"[PASS] Single critical conflict capped at: {score:.4f} (<= 0.60)")

    # 1.2 Bearing number conflict -> cap at 0.40
    conflicts_bearing = [ConflictSignal(
        attribute="bearing_number",
        value_a="6205",
        value_b="6305",
        severity="CRITICAL",
        description="Bearing series mismatch"
    )]
    score, breakdown = calculate_rule_based_hybrid_score(mock_features, conflicts_bearing)
    assert score <= 0.40, f"Expected score <= 0.40 for bearing conflict, got {score}"
    assert breakdown.score_cap_applied == 0.40
    print(f"[PASS] Bearing number conflict capped at: {score:.4f} (<= 0.40)")

    # 1.3 Multiple critical conflicts -> cap at 0.45
    mock_multi = mock_features.model_copy(update={"critical_attribute_conflict_count": 2})
    conflicts_multi = [
        ConflictSignal(attribute="voltage", value_a="1.1KV", value_b="3.3KV", severity="CRITICAL", description="Voltage mismatch"),
        ConflictSignal(attribute="number_of_cores", value_a="3", value_b="4", severity="CRITICAL", description="Core count mismatch"),
    ]
    score, breakdown = calculate_rule_based_hybrid_score(mock_multi, conflicts_multi)
    assert score <= 0.45, f"Expected score <= 0.45 for multiple critical conflicts, got {score}"
    print(f"[PASS] Multiple critical conflicts capped at: {score:.4f} (<= 0.45)")

    # 1.4 Incompatible category -> cap at 0.30
    mock_cat_incomp = mock_features.model_copy(update={"category_compatibility": 0.0})
    score, breakdown = calculate_rule_based_hybrid_score(mock_cat_incomp, [])
    assert score <= 0.30, f"Expected score <= 0.30 for category incompatible, got {score}"
    print(f"[PASS] Category incompatible capped at: {score:.4f} (<= 0.30)")

    # 2. Test Classification Thresholds
    print("\n--- 2. Testing Hybrid Classification Decision Tiers ---")
    assert classify_hybrid_score(0.95) == HybridClassification.AUTO_MATCH_RECOMMENDED
    assert classify_hybrid_score(0.85) == HybridClassification.STRONG_REVIEW_CANDIDATE
    assert classify_hybrid_score(0.72) == HybridClassification.MANUAL_REVIEW_REQUIRED
    assert classify_hybrid_score(0.55) == HybridClassification.WEAK_MATCH_REVIEW_OPTIONAL
    assert classify_hybrid_score(0.42) == HybridClassification.REJECTED_BY_SCORING
    print("[PASS] Classification thresholds verified across all 5 decision bands.")

    # 3. Test FastAPI ASGI Endpoints
    print("\n--- 3. Testing Hybrid Scoring & ML Endpoints ---")
    
    # 3.1 Health Check
    s, b = await make_request("GET", "/health")
    assert s == 200, f"/health failed: {s}"
    print("[PASS] /health returns 200.")

    # 3.2 GET /api/matching/hybrid-score/sample
    s, b = await make_request("GET", "/api/matching/hybrid-score/sample")
    assert s == 200, f"/api/matching/hybrid-score/sample failed with {s}: {b}"
    hybrid_sample = json.loads(b)
    assert hybrid_sample["total_candidates_scored"] > 0
    assert len(hybrid_sample["candidates"]) > 0
    top_c = hybrid_sample["candidates"][0]
    assert "hybrid_score" in top_c
    assert "hybrid_classification" in top_c
    assert "hybrid_score_breakdown" in top_c
    assert "feature_vector" in top_c
    assert "hybrid_recommendation" in top_c
    print(f"[PASS] GET /api/matching/hybrid-score/sample returned {hybrid_sample['total_candidates_scored']} candidates.")
    print(f"       Top candidate: {top_c['pair_id']} - Hybrid Score: {top_c['hybrid_score']:.4f} [{top_c['hybrid_classification']}]")
    print(f"       Breakdown: Desc={top_c['hybrid_score_breakdown']['description_contribution']:.3f}, Attr={top_c['hybrid_score_breakdown']['attribute_contribution']:.3f}, Sem={top_c['hybrid_score_breakdown']['semantic_contribution']:.3f}")
    
    # Verify ranked order descending
    scores = [c["hybrid_score"] for c in hybrid_sample["candidates"]]
    assert scores == sorted(scores, reverse=True), "Candidates must be sorted descending by hybrid_score!"
    print("[PASS] Candidates strictly sorted descending by hybrid score.")

    # 3.3 POST /api/matching/hybrid-score
    post_payload = json.dumps({
        "candidates": [
            {
                "pair_id": top_c["pair_id"],
                "source_material_a": top_c["source_material_a"],
                "source_material_b": top_c["source_material_b"],
                "score": top_c["rapidfuzz_score"],
                "classification": "POSSIBLE_DUPLICATE",
                "score_breakdown": {
                    "description_similarity": top_c["feature_vector"]["description_similarity"],
                    "attribute_similarity": top_c["feature_vector"]["attribute_similarity"],
                    "token_overlap": top_c["feature_vector"]["token_similarity"],
                    "category_compatibility": top_c["feature_vector"]["category_compatibility"],
                    "uom_compatibility": top_c["feature_vector"]["uom_compatibility"],
                    "mfg_part_compatibility": top_c["feature_vector"]["manufacturer_match"],
                    "final_score": top_c["rapidfuzz_score"],
                },
                "matching_signals": top_c["matching_signals"],
                "conflict_signals": top_c["conflict_signals"],
                "recommendation": "Candidate match",
                "semantic_similarity_score": top_c["feature_vector"]["semantic_similarity_score"],
                "semantic_method": "DETERMINISTIC_TOKEN_HASH_STUB (Preview)"
            }
        ]
    }).encode("utf-8")
    headers_json = [
        [b"content-type", b"application/json"],
        [b"content-length", str(len(post_payload)).encode()],
    ]
    s, b = await make_request("POST", "/api/matching/hybrid-score", body=post_payload, headers=headers_json)
    assert s == 200, f"POST /api/matching/hybrid-score failed with {s}: {b}"
    post_data = json.loads(b)
    assert post_data["total_candidates_scored"] == 1
    assert post_data["candidates"][0]["hybrid_score"] > 0.0
    print("[PASS] POST /api/matching/hybrid-score executed successfully.")

    # 3.4 GET /api/matching/ml-training-plan
    s, b = await make_request("GET", "/api/matching/ml-training-plan")
    assert s == 200, f"GET /api/matching/ml-training-plan failed with {s}: {b}"
    plan_data = json.loads(b)
    assert plan_data["feature_count"] == len(plan_data["feature_names"])
    assert plan_data["feature_count"] >= 14
    assert "XGBoost" in plan_data["model_target"]
    assert "FEATURE_EXTRACTION_READY" in plan_data["current_status"]
    print(f"[PASS] GET /api/matching/ml-training-plan passed ({plan_data['feature_count']} features documented).")

    # 3.5 GET /api/matching/ml-feature-export/sample
    s, b = await make_request("GET", "/api/matching/ml-feature-export/sample")
    assert s == 200, f"GET /api/matching/ml-feature-export/sample failed with {s}: {b}"
    export_data = json.loads(b)
    assert export_data["total_rows"] > 0
    sample_row = export_data["rows"][0]
    assert sample_row["label"] is None, "Training export label must be None (null) before officer review!"
    assert sample_row["review_status"] == "UNLABELED"
    assert "description_similarity" in sample_row
    assert "critical_attribute_conflict_count" in sample_row
    print(f"[PASS] GET /api/matching/ml-feature-export/sample passed ({export_data['total_rows']} training rows with null labels).")

    # 3.6 Regression check on previous endpoints
    s, _ = await make_request("GET", "/api/matching/candidates/sample")
    assert s == 200, f"Candidates sample regression failed: {s}"
    s, _ = await make_request("GET", "/api/matching/embedding/sample")
    assert s == 200, f"Embedding sample regression failed: {s}"
    print("[PASS] Previous endpoints regression check succeeded.")

    print("\n======================================================================")
    print("ALL PROMPT 9 BACKEND CHECKS COMPLETED SUCCESSFULLY!")
    print("======================================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
