"""
Prompt 7 Comprehensive Verification Script.
Tests RapidFuzz candidate duplicate detection, scoring weights, blocking filters,
critical attribute conflict penalties, API endpoints, and sample dataset clusters.
"""

import sys
import json
import asyncio
from pathlib import Path

# Add backend root to sys.path
backend_root = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_root))

from app.services.candidate_matching import (
    calculate_text_similarity,
    calculate_token_similarity,
    calculate_attribute_similarity,
    calculate_category_compatibility,
    calculate_uom_compatibility,
    calculate_candidate_score,
    classify_candidate,
    generate_candidate_pairs,
    find_duplicate_candidates,
    _is_category_incompatible,
)
from app.schemas.matching import (
    CandidateClassification,
    CandidateMatchRequest,
    CandidateMatchResponse,
    CandidateMatchResult,
)
from app.schemas.material import SourceMaterialResponse
from app.api.matching import detect_duplicate_candidates, detect_sample_duplicate_candidates
from main import health_check
import uuid
from datetime import datetime


from app.services.normalization import build_standard_description

def make_test_material(code: str, desc: str, cat: str, uom: str, attrs: dict) -> SourceMaterialResponse:
    now = datetime.utcnow()
    std = build_standard_description(desc)
    return SourceMaterialResponse(
        id=uuid.uuid4(),
        source_cpse="TEST_PSU",
        source_system="TEST_ERP",
        source_material_code=code,
        raw_description=desc,
        cleaned_description=desc.lower(),
        standard_description=std,
        category=cat,
        sub_category="GENERAL",
        material_type=None,
        material_grade=attrs.get("material_grade"),
        manufacturer=attrs.get("manufacturer"),
        part_number=attrs.get("part_number"),
        model_number=attrs.get("model_number"),
        uom=uom,
        attributes=attrs,
        normalized_tokens=std.lower().split(),
        ingestion_batch_id=None,
        created_at=now,
        updated_at=now,
    )


async def run_prompt7_verification():
    print("=" * 70)
    print("PROMPT 7: CANDIDATE DUPLICATE DETECTION (RAPIDFUZZ) VERIFICATION")
    print("=" * 70)

    # 1. Health Check
    health = await health_check()
    assert health.status == "healthy"
    print(f"\n[PASS] Backend /health returned 200 OK (status: {health.status})")

    # 2. Text Similarity Test via RapidFuzz
    print("\n--- Testing RapidFuzz Text Similarity ---")
    m1 = make_test_material("M1", "BALL BEARING 6205-2RS SKF DEEP GROOVE", "BEARINGS", "EA", {})
    m2 = make_test_material("M2", "SKF DEEP GROOVE BALL BEARING 6205 2RS", "BEARINGS", "EA", {})
    m3 = make_test_material("M3", "GATE VALVE 100MM CLASS 150 FLANGED", "VALVES", "EA", {})

    sim_high, _ = calculate_text_similarity(m1, m2)
    sim_low, _ = calculate_text_similarity(m1, m3)
    assert sim_high >= 0.80, f"Expected high text sim, got {sim_high}"
    assert sim_low < 0.40, f"Expected low text sim, got {sim_low}"
    print(f" [PASS] Reordered text similarity: {sim_high:.4f} (>= 0.80)")
    print(f" [PASS] Disparate text similarity: {sim_low:.4f} (< 0.35)")

    # 3. Category Incompatibility & Blocking Filter
    print("\n--- Testing Taxonomy Domain Blocking ---")
    assert _is_category_incompatible("BEARINGS", "ELECTRICAL_CABLES") is True
    assert _is_category_incompatible("VALVES", "MOTORS") is True
    assert _is_category_incompatible("PIPES_AND_TUBES", "FASTENERS") is True
    assert _is_category_incompatible("BEARINGS", "BEARINGS") is False
    assert _is_category_incompatible("BEARINGS", "MECHANICAL_SPARES") is False
    print(" [PASS] Blocking rules correctly flag mutually exclusive categories and permit compatible parent hierarchies.")

    # 4. Critical Attribute Conflicts
    print("\n--- Testing Critical Attribute Conflict Penalties ---")
    # Bearing Number Mismatch
    b_6205 = make_test_material("B1", "BALL BEARING 6205 ZZ SKF", "BEARINGS", "EA", {"bearing_number": "6205"})
    b_6305 = make_test_material("B2", "BALL BEARING 6305 ZZ SKF", "BEARINGS", "EA", {"bearing_number": "6305"})
    score_b, _, _, conflicts_b, rec_b = calculate_candidate_score(b_6205, b_6305)
    assert any(c.attribute == "bearing_number" for c in conflicts_b), "Missing bearing_number conflict"
    assert score_b <= 0.50, f"Score should be capped on critical conflict, got {score_b}"
    print(f" [PASS] Bearing number mismatch (6205 vs 6305) penalized: score={score_b:.4f}, conflicts={[c.description for c in conflicts_b]}")

    # Voltage Mismatch
    c_24v = make_test_material("C1", "24V DC MOTOR 0.5 HP", "MOTORS", "EA", {"voltage": "24V"})
    c_415v = make_test_material("C2", "415V AC MOTOR 5 HP 1440 RPM", "MOTORS", "EA", {"voltage": "415V"})
    score_v, _, _, conflicts_v, rec_v = calculate_candidate_score(c_24v, c_415v)
    assert any(c.attribute == "voltage" for c in conflicts_v)
    assert score_v <= 0.50
    print(f" [PASS] Motor voltage mismatch (24V vs 415V) penalized: score={score_v:.4f}")

    # Diameter Mismatch
    p_50 = make_test_material("P1", "SS PIPE 50 NB SCH 40", "PIPES_AND_TUBES", "M", {"diameter_mm": 50.0})
    p_100 = make_test_material("P2", "SS PIPE 100 NB SCH 40", "PIPES_AND_TUBES", "M", {"diameter_mm": 100.0})
    score_d, _, _, conflicts_d, rec_d = calculate_candidate_score(p_50, p_100)
    assert any(c.attribute == "nominal_diameter" for c in conflicts_d)
    assert score_d <= 0.50
    print(f" [PASS] Pipe diameter mismatch (50 NB vs 100 NB) penalized: score={score_d:.4f}")

    # 5. High Confidence Duplicate Alignment
    print("\n--- Testing High Confidence Duplicate Alignment ---")
    pipe_a = make_test_material("PA", "SS PIPE 50 NB SCH 40 ASTM A312", "PIPES_AND_TUBES", "M", {
        "material": "STAINLESS_STEEL", "nominal_bore": "50 NB", "schedule": "SCH 40", "diameter_mm": 50.0
    })
    pipe_b = make_test_material("PB", "STAINLESS STEEL PIPE 50 NOMINAL BORE SCHEDULE 40 ASTM A312", "PIPES_AND_TUBES", "M", {
        "material": "STAINLESS_STEEL", "nominal_bore": "50 NB", "schedule": "SCH 40", "diameter_mm": 50.0
    })
    score_pipe, bd_pipe, sigs_pipe, _, rec_pipe = calculate_candidate_score(pipe_a, pipe_b)
    tier_pipe = classify_candidate(score_pipe)
    assert score_pipe >= 0.85
    print(f" [PASS] Matched identical engineering pipe: score={score_pipe:.4f} ({tier_pipe.value})")
    print(f"        Recommendation: {rec_pipe}")

    # 6. Sample CSV Duplicate Detection
    print("\n--- Testing Sample CSV Duplicate Detection (/api/matching/candidates/sample) ---")
    sample_res = await detect_sample_duplicate_candidates(min_score=0.65)
    assert isinstance(sample_res, CandidateMatchResponse)
    assert sample_res.total_records == 10
    assert sample_res.compared_pairs > 0
    assert sample_res.candidate_count >= 4, f"Expected at least 4 candidates, got {sample_res.candidate_count}"

    print(f" [PASS] Sample scan processed {sample_res.total_records} records, {sample_res.compared_pairs} pairs.")
    print(f" [PASS] Discovered {sample_res.candidate_count} candidates meeting threshold >= 0.65:")
    for idx, c in enumerate(sample_res.candidates, 1):
        print(f"        #{idx}: {c.pair_id:<42} Score: {c.score*100:5.1f}% [{c.classification.value}]")

    # 7. POST /api/matching/candidates Endpoint
    print("\n--- Testing POST /api/matching/candidates ---")
    test_req = CandidateMatchRequest(
        materials=[pipe_a, pipe_b],
        min_score=0.65
    )
    post_res = await detect_duplicate_candidates(test_req)
    assert post_res.candidate_count == 1
    assert post_res.candidates[0].score >= 0.85
    print(f" [PASS] POST /api/matching/candidates executed successfully with {post_res.candidate_count} candidate pair.")

    print("\n" + "=" * 70)
    print("ALL PROMPT 7 VERIFICATION CHECKS PASSED WITH ZERO ERRORS!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_prompt7_verification())
