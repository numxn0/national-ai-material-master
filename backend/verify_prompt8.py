"""
Verification script for Prompt 8: Embedding Similarity Architecture with Lightweight Local Stub
Pure asyncio ASGI test harness (no external testclient required).
"""

import sys
import os
import json
import asyncio
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.services.embedding_service import (
    generate_stub_embedding,
    calculate_cosine_similarity,
    create_material_embedding_text,
    compare_semantic_similarity,
    enrich_candidates_with_semantic_score,
)
from main import app

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
    print("=== Testing Embedding Service Core Functions ===")
    
    # 1. Determinism Test
    text_1 = "BALL BEARING 6205-2RS SKF DEEP GROOVE BEARINGS SKF"
    vec_1a = generate_stub_embedding(text_1, dimensions=64)
    vec_1b = generate_stub_embedding(text_1, dimensions=64)
    assert len(vec_1a) == 64, f"Expected 64 dimensions, got {len(vec_1a)}"
    assert vec_1a == vec_1b, "generate_stub_embedding must be strictly deterministic across repeated calls!"
    print("[PASS] Determinism test passed.")

    # 2. Similarity vs Dissimilarity Test
    text_similar = "SKF DEEP GROOVE BALL BEARING 6205 2RS BORE 25MM BEARINGS SKF"
    text_dissimilar = "1.1KV 3 CORE 185 SQMM XLPE ARMOURED ALUMINIUM CABLE ELECTRICAL_CABLES"
    
    vec_sim = generate_stub_embedding(text_similar, dimensions=64)
    vec_dissim = generate_stub_embedding(text_dissimilar, dimensions=64)
    
    sim_score = calculate_cosine_similarity(vec_1a, vec_sim)
    dissim_score = calculate_cosine_similarity(vec_1a, vec_dissim)
    
    print(f"Similar pair similarity (Bearings): {sim_score:.4f}")
    print(f"Dissimilar pair similarity (Bearing vs Cable): {dissim_score:.4f}")
    
    assert sim_score > 0.70, f"Expected similar bearing pair score > 0.70, got {sim_score}"
    assert dissim_score < 0.30, f"Expected dissimilar bearing vs cable score < 0.30, got {dissim_score}"
    assert sim_score > dissim_score, "Similar pair must score higher than dissimilar pair"
    print("[PASS] Semantic similarity contrast test passed.")

    # 3. Embedding Text Construction Test
    sample_mat = {
        "standard_description": "STAINLESS STEEL PIPE 50 NOMINAL BORE SCHEDULE 40",
        "category": "PIPES_AND_TUBES",
        "sub_category": "PIPES",
        "material_type": "ASTM A312",
        "material_grade": "SS304",
        "manufacturer": "SAIL",
        "part_number": "PIP-50-40",
        "attributes": {
            "schedule": "SCH 40",
            "nominal_bore": "50 NB"
        }
    }
    emb_text = create_material_embedding_text(sample_mat)
    print(f"Generated embedding text: '{emb_text}'")
    assert "STAINLESS STEEL PIPE" in emb_text
    assert "PIPES_AND_TUBES" in emb_text
    assert "SS304" in emb_text
    print("[PASS] Material embedding text construction passed.")

    # 4. FastAPI ASGI Endpoints Verification
    print("\n=== Testing FastAPI Endpoints ===")

    # 4.1 Health Check
    s, b = await make_request("GET", "/health")
    assert s == 200, f"/health failed with {s}: {b}"
    print("[PASS] /health returns 200.")

    # 4.2 POST /api/matching/embedding/generate
    gen_payload = json.dumps({
        "text": "BALL BEARING 6205 2RS SKF",
        "dimensions": 64
    }).encode("utf-8")
    headers_json = [
        [b"content-type", b"application/json"],
        [b"content-length", str(len(gen_payload)).encode()],
    ]
    s, b = await make_request("POST", "/api/matching/embedding/generate", body=gen_payload, headers=headers_json)
    assert s == 200, f"Generate failed with {s}: {b}"
    gen_data = json.loads(b)
    assert gen_data["dimensions"] == 64
    assert len(gen_data["vector_preview_first_8_values"]) == 8
    assert "metadata" in gen_data
    assert gen_data["metadata"]["pgvector_ready"] is True
    assert "deterministic" in gen_data["note"].lower()
    print("[PASS] POST /api/matching/embedding/generate passed.")

    # 4.3 POST /api/matching/embedding/compare
    mat_a = {
        "id": "11111111-1111-1111-1111-111111111111",
        "source_cpse": "IR_NORTH",
        "source_system": "SAP",
        "source_material_code": "CR-BEAR-6205",
        "raw_description": "BALL BEARING 6205-2RS SKF DEEP GROOVE",
        "standard_description": "BALL BEARING 6205-2RS SKF DEEP GROOVE",
        "category": "BEARINGS",
        "sub_category": "BALL_BEARINGS",
        "uom": "NOS",
        "attributes": {"bearing_number": "6205-2RS"},
        "normalized_tokens": ["ball", "bearing", "6205", "skf"],
        "match_status": "UNPROCESSED",
        "approval_status": "PENDING_INGESTION",
        "created_at": "2026-09-19T00:00:00Z",
        "updated_at": "2026-09-19T00:00:00Z"
    }
    mat_b = {
        "id": "22222222-2222-2222-2222-222222222222",
        "source_cpse": "NR_WORKSHOP",
        "source_system": "ORACLE",
        "source_material_code": "NR-6205-2RS",
        "raw_description": "SKF DEEP GROOVE BALL BEARING 6205 2RS BORE 25MM",
        "standard_description": "SKF DEEP GROOVE BALL BEARING 6205 2RS BORE 25MM",
        "category": "BEARINGS",
        "sub_category": "BALL_BEARINGS",
        "uom": "NOS",
        "attributes": {"bearing_number": "6205-2RS", "bore_mm": 25},
        "normalized_tokens": ["skf", "deep", "groove", "ball", "bearing", "6205"],
        "match_status": "UNPROCESSED",
        "approval_status": "PENDING_INGESTION",
        "created_at": "2026-09-19T00:00:00Z",
        "updated_at": "2026-09-19T00:00:00Z"
    }
    comp_payload = json.dumps({
        "material_a": mat_a,
        "material_b": mat_b,
        "dimensions": 64
    }).encode("utf-8")
    headers_comp = [
        [b"content-type", b"application/json"],
        [b"content-length", str(len(comp_payload)).encode()],
    ]
    s, b = await make_request("POST", "/api/matching/embedding/compare", body=comp_payload, headers=headers_comp)
    assert s == 200, f"Compare failed with {s}: {b}"
    comp_data = json.loads(b)
    assert comp_data["semantic_similarity_score"] > 0.70
    assert "interpretation" in comp_data
    assert comp_data["pgvector_ready"] is True
    print(f"[PASS] POST /api/matching/embedding/compare passed (score: {comp_data['semantic_similarity_score']}).")

    # 4.4 GET /api/matching/embedding/sample
    s, b = await make_request("GET", "/api/matching/embedding/sample")
    assert s == 200, f"Sample comparisons failed with {s}: {b}"
    sample_data = json.loads(b)
    assert sample_data["total_comparisons"] >= 3
    pair_types = [c["pair_type"] for c in sample_data["comparisons"]]
    assert "SIMILAR_PAIR" in pair_types
    assert "DISSIMILAR_PAIR" in pair_types
    print(f"[PASS] GET /api/matching/embedding/sample passed ({sample_data['total_comparisons']} comparisons returned).")
    for comp in sample_data["comparisons"]:
        print(f"  [{comp['pair_type']}] {comp['material_a_code']} vs {comp['material_b_code']}: {comp['semantic_similarity_score']:.4f} - {comp['category_context']}")

    # 4.5 GET /api/matching/candidates/sample (verify candidate enrichment)
    s, b = await make_request("GET", "/api/matching/candidates/sample?min_score=0.65")
    assert s == 200, f"Candidate sample failed with {s}: {b}"
    cand_data = json.loads(b)
    assert cand_data["candidate_count"] > 0
    top_cand = cand_data["candidates"][0]
    assert "semantic_similarity_score" in top_cand
    assert top_cand["semantic_similarity_score"] is not None
    assert "semantic_method" in top_cand
    print(f"[PASS] GET /api/matching/candidates/sample passed (top candidate score={top_cand['score']:.4f}, semantic_preview={top_cand['semantic_similarity_score']:.4f}).")

    print("\n>>> ALL PROMPT 8 BACKEND VERIFICATIONS SUCCEEDED! <<<")

if __name__ == "__main__":
    asyncio.run(run_tests())
