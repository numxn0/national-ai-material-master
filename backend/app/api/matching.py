from fastapi import APIRouter, Body, HTTPException, Query
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from pathlib import Path

from app.schemas import (
    MaterialMappingResponse,
    EXAMPLE_MATERIAL_MAPPING,
    CandidateMatchRequest,
    CandidateMatchResponse,
    SourceMaterialResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingVectorMetadata,
    SemanticSimilarityRequest,
    SemanticSimilarityResponse,
    SemanticSampleComparisonItem,
    SemanticSampleComparisonResponse,
    HybridClassification,
    MatchFeatureVector,
    HybridScoreBreakdown,
    HybridScoredCandidate,
    HybridScoringRequest,
    HybridScoringResponse,
    MLFeatureExportRow,
    MLTrainingPlanResponse,
    ExplanationDirection,
    ExplanationFactor,
    AuditExplanation,
    ReviewerExplanation,
    ExplainabilityRequest,
    ExplainabilityResponse,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
)
from app.services.candidate_matching import find_duplicate_candidates
from app.services.ingestion_preview import parse_csv_content
from app.services.embedding_service import (
    generate_stub_embedding,
    calculate_cosine_similarity,
    create_material_embedding_text,
    compare_semantic_similarity,
)
from app.services.hybrid_scoring import (
    score_candidates_hybrid,
    score_candidate_hybrid,
)
from app.services.ml_feature_pipeline import (
    export_candidates_training_dataset,
    describe_xgboost_training_plan,
)
from app.services.explainability import (
    explain_scored_candidate,
    explain_scored_candidates,
    generate_factor_contributions,
    generate_reviewer_summary,
)
from datetime import datetime, timezone

router = APIRouter(prefix="/matching", tags=["AI Matching & Deduplication"])

class MatchTriggerRequest(BaseModel):
    source_batch_id: str = "batch-2026-001"
    fuzzy_threshold: int = 80
    include_vector_search: bool = True
    classifier_model: str = "xgboost_v1"

# Mock placeholder matching candidates queue
PLACEHOLDER_MATCH_QUEUE = [
    {
        "pair_id": "match-881",
        "confidence_score": 0.94,
        "classification": "HIGH_CONFIDENCE_DUPLICATE",
        "item_incoming": {
            "code": "RAIL-BLT-1250",
            "description": "HEX BOLT M12X50 SS304 FULL THREAD",
            "source_entity": "Indian Railways (Central)",
            "unit": "NOS",
            "price_inr": 42.50
        },
        "item_master_candidate": {
            "code": "CIL-BLT-1250",
            "description": "Hexagon Head Bolt M12x50 Grade 8.8 Stainless Steel 304",
            "source_entity": "Coal India Master Catalog",
            "unit": "NOS",
            "price_inr": 45.00
        },
        "similarity_breakdown": {
            "rapidfuzz_token_set_ratio": 89.4,
            "vector_cosine_similarity": 0.962,
            "attribute_dimension_match": "100% (M12 diameter, 50mm length)",
            "material_grade_match": "SS 304 (Exact)"
        },
        "shap_key_features": [
            {"feature": "Dimension Match (M12x50)", "impact": "+0.45"},
            {"feature": "Material Match (SS304)", "impact": "+0.32"},
            {"feature": "UOM Match (NOS)", "impact": "+0.12"},
            {"feature": "Prefix Variation", "impact": "-0.05"}
        ],
        "suggested_action": "MERGE_AS_ALIAS"
    },
    {
        "pair_id": "match-882",
        "confidence_score": 0.78,
        "classification": "AMBIGUOUS_REQUIRES_REVIEW",
        "item_incoming": {
            "code": "ONGC-VLV-100",
            "description": "BALL VALVE 100MM CL300 FLANGED ASTM A216",
            "source_entity": "ONGC Hazira",
            "unit": "NOS",
            "price_inr": 18500.00
        },
        "item_master_candidate": {
            "code": "IOCL-VLV-4INCH",
            "description": "4 INCH BALL VALVE CLASS 300 FLANGE END WCB",
            "source_entity": "IOCL Panipat",
            "unit": "NOS",
            "price_inr": 19200.00
        },
        "similarity_breakdown": {
            "rapidfuzz_token_set_ratio": 72.1,
            "vector_cosine_similarity": 0.884,
            "attribute_dimension_match": "100% (100mm == 4 inch)",
            "material_grade_match": "A216 WCB (Equivalent ASTM Grade)"
        },
        "shap_key_features": [
            {"feature": "Size Equivalence (100mm vs 4in)", "impact": "+0.38"},
            {"feature": "Pressure Class (CL300)", "impact": "+0.28"},
            {"feature": "Description Jargon Divergence", "impact": "-0.11"}
        ],
        "suggested_action": "MANUAL_VERIFY"
    }
]

from app.schemas import MaterialMappingResponse, EXAMPLE_MATERIAL_MAPPING

@router.get("/canonical/example", response_model=MaterialMappingResponse, tags=["Canonical Mappings"])
async def get_canonical_mapping_example():
    """
    Retrieve typed example of an AI-generated Material Mapping linkage.
    Shaped by MaterialMappingResponse Pydantic schema.
    """
    return EXAMPLE_MATERIAL_MAPPING

@router.post("/candidates", response_model=CandidateMatchResponse, tags=["Candidate Duplicate Detection"])
async def detect_duplicate_candidates(payload: CandidateMatchRequest):
    """
    Generates candidate duplicate material pairs from provided source material records
    using RapidFuzz string distance, blocking filters, and attribute-aware comparison.
    Pure in-memory candidate detection.
    """
    if not payload.materials:
        return CandidateMatchResponse(
            total_records=0,
            compared_pairs=0,
            candidate_count=0,
            candidates=[]
        )

    min_score = payload.min_score if payload.min_score is not None else 0.65
    return find_duplicate_candidates(payload.materials, min_score=min_score)

@router.get("/candidates/sample", response_model=CandidateMatchResponse, tags=["Candidate Duplicate Detection"])
async def detect_sample_duplicate_candidates(
    min_score: float = Query(0.65, ge=0.0, le=1.0, description="Minimum candidate duplicate score")
):
    """
    Loads sample_materials_raw.csv, runs ingestion preview with attribute extraction,
    and runs RapidFuzz candidate duplicate detection over real CPSE sample records.
    Returns ranked duplicate pairs, similarity breakdowns, and explanations.
    """
    sample_paths = [
        Path("..") / "sample-data" / "sample_materials_raw.csv",
        Path("sample-data") / "sample_materials_raw.csv",
        Path(__file__).resolve().parents[3] / "sample-data" / "sample_materials_raw.csv",
        Path(__file__).resolve().parents[2] / "sample-data" / "sample_materials_raw.csv",
    ]
    sample_file = None
    for p in sample_paths:
        if p.exists():
            sample_file = p
            break

    if not sample_file:
        raise HTTPException(
            status_code=404,
            detail="Sample data file sample_materials_raw.csv could not be found."
        )

    try:
        with open(sample_file, "r", encoding="utf-8") as f:
            content = f.read()
        preview_res = parse_csv_content(
            csv_text_or_bytes=content,
            file_name="sample_materials_raw.csv"
        )
        return find_duplicate_candidates(preview_res.valid_records, min_score=min_score)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate sample candidate matches: {str(exc)}"
        )

@router.post("/embedding/generate", response_model=EmbeddingResponse, tags=["Semantic Embeddings (pgvector-ready)"])
async def generate_material_embedding(payload: EmbeddingRequest):
    """
    Generates deterministic local embedding stub for input material text.
    Returns 8-value preview and metadata. Full vector is not returned to avoid bloated payloads.
    Ready for future pgvector vector(N) column storage.
    """
    dims = payload.dimensions or 64
    normalized_text = payload.text.strip().upper()
    vector = generate_stub_embedding(normalized_text, dimensions=dims)
    preview = vector[:8]

    metadata = EmbeddingVectorMetadata(
        dimensions=dims,
        method="DETERMINISTIC_TOKEN_HASH_STUB",
        vector_preview_first_8_values=preview,
        l2_normalized=True,
        pgvector_ready=True,
        model_target="sentence-transformers/all-MiniLM-L6-v2 (Planned)",
        note="Deterministic local feature hashing stub for development without heavy model downloads or GPU."
    )

    return EmbeddingResponse(
        input_text=payload.text,
        normalized_embedding_text=normalized_text,
        dimensions=dims,
        vector_preview_first_8_values=preview,
        metadata=metadata,
        note="Deterministic local embedding stub. Full pgvector persistence & transformer weights will be activated in future milestones."
    )

@router.post("/embedding/compare", response_model=SemanticSimilarityResponse, tags=["Semantic Embeddings (pgvector-ready)"])
async def compare_material_semantic_similarity(payload: SemanticSimilarityRequest):
    """
    Computes semantic similarity between two material records using deterministic
    embedding stub and cosine distance.
    """
    dims = payload.dimensions or 64
    score, text_a, text_b, interpretation = compare_semantic_similarity(
        payload.material_a,
        payload.material_b,
        dimensions=dims
    )
    vec_a = generate_stub_embedding(text_a, dimensions=dims)
    vec_b = generate_stub_embedding(text_b, dimensions=dims)

    return SemanticSimilarityResponse(
        material_a_text=text_a,
        material_b_text=text_b,
        semantic_similarity_score=score,
        interpretation=interpretation,
        embedding_method="DETERMINISTIC_TOKEN_HASH_STUB",
        pgvector_ready=True,
        dimensions=dims,
        vector_a_preview=vec_a[:8],
        vector_b_preview=vec_b[:8],
        note="Semantic embedding placeholder / pgvector-ready"
    )

@router.get("/embedding/sample", response_model=SemanticSampleComparisonResponse, tags=["Semantic Embeddings (pgvector-ready)"])
async def get_sample_semantic_comparisons():
    """
    Loads sample_materials_raw.csv, performs ingestion preview, and selects representative
    similar pairs (Bearings, Valves/Pipes) and dissimilar pairs (Bearings vs Cables)
    to demonstrate deterministic semantic embedding comparisons.
    """
    sample_paths = [
        Path("..") / "sample-data" / "sample_materials_raw.csv",
        Path("sample-data") / "sample_materials_raw.csv",
        Path(__file__).resolve().parents[3] / "sample-data" / "sample_materials_raw.csv",
        Path(__file__).resolve().parents[2] / "sample-data" / "sample_materials_raw.csv",
    ]
    sample_file = None
    for p in sample_paths:
        if p.exists():
            sample_file = p
            break

    if not sample_file:
        raise HTTPException(
            status_code=404,
            detail="Sample data file sample_materials_raw.csv could not be found."
        )

    try:
        with open(sample_file, "r", encoding="utf-8") as f:
            content = f.read()
        preview_res = parse_csv_content(
            csv_text_or_bytes=content,
            file_name="sample_materials_raw.csv"
        )
        records = preview_res.valid_records
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse sample materials for semantic evaluation: {str(exc)}"
        )

    by_code = {r.source_material_code: r for r in records}
    comparisons: List[SemanticSampleComparisonItem] = []

    # 1. Similar Bearing Pair: CR-BEAR-6205 vs NR-6205-2RS
    if "CR-BEAR-6205" in by_code and "NR-6205-2RS" in by_code:
        mat_a = by_code["CR-BEAR-6205"]
        mat_b = by_code["NR-6205-2RS"]
        score, text_a, text_b, interp = compare_semantic_similarity(mat_a, mat_b)
        comparisons.append(SemanticSampleComparisonItem(
            pair_type="SIMILAR_PAIR",
            category_context="Bearings: 6205-2RS Deep Groove SKF Ball Bearings (Railways Northern vs Workshop)",
            material_a_code=mat_a.source_material_code,
            material_b_code=mat_b.source_material_code,
            material_a_text=text_a,
            material_b_text=text_b,
            semantic_similarity_score=score,
            interpretation=interp,
            embedding_method="DETERMINISTIC_TOKEN_HASH_STUB",
            vector_a_preview=generate_stub_embedding(text_a)[:8],
            vector_b_preview=generate_stub_embedding(text_b)[:8],
        ))

    # 2. Similar Valve Pair: IOCL-VLV-4INCH vs ONGC-VLV-100
    if "IOCL-VLV-4INCH" in by_code and "ONGC-VLV-100" in by_code:
        mat_a = by_code["IOCL-VLV-4INCH"]
        mat_b = by_code["ONGC-VLV-100"]
        score, text_a, text_b, interp = compare_semantic_similarity(mat_a, mat_b)
        comparisons.append(SemanticSampleComparisonItem(
            pair_type="SIMILAR_PAIR",
            category_context="Valves & Piping: 4 Inch / 100mm Ball Valve Class 300 WCB (IOCL vs ONGC)",
            material_a_code=mat_a.source_material_code,
            material_b_code=mat_b.source_material_code,
            material_a_text=text_a,
            material_b_text=text_b,
            semantic_similarity_score=score,
            interpretation=interp,
            embedding_method="DETERMINISTIC_TOKEN_HASH_STUB",
            vector_a_preview=generate_stub_embedding(text_a)[:8],
            vector_b_preview=generate_stub_embedding(text_b)[:8],
        ))

    # 3. Similar Pipe Pair (if available or synthetic exemplary pair)
    pipes = [r for r in records if "PIPE" in (r.category or "") or "PIPE" in (r.standard_description or "") or "PIPE" in (r.raw_description or "")]
    if len(pipes) >= 2:
        mat_a = pipes[0]
        mat_b = pipes[1]
        score, text_a, text_b, interp = compare_semantic_similarity(mat_a, mat_b)
        comparisons.append(SemanticSampleComparisonItem(
            pair_type="SIMILAR_PAIR",
            category_context="Pipes & Tubes: Stainless Steel Schedule 40 Seamless Pipes",
            material_a_code=mat_a.source_material_code,
            material_b_code=mat_b.source_material_code,
            material_a_text=text_a,
            material_b_text=text_b,
            semantic_similarity_score=score,
            interpretation=interp,
            embedding_method="DETERMINISTIC_TOKEN_HASH_STUB",
            vector_a_preview=generate_stub_embedding(text_a)[:8],
            vector_b_preview=generate_stub_embedding(text_b)[:8],
        ))
    else:
        pipe_desc_a = "STAINLESS STEEL PIPE 50 NOMINAL BORE SCHEDULE 40 ASTM A312 PIPES_AND_TUBES SS304"
        pipe_desc_b = "SEAMLESS PIPE 2 INCH SCH 40 SS304 ASTM A312 PIPES_AND_TUBES"
        vec_a = generate_stub_embedding(pipe_desc_a)
        vec_b = generate_stub_embedding(pipe_desc_b)
        pipe_score = calculate_cosine_similarity(vec_a, vec_b)
        comparisons.append(SemanticSampleComparisonItem(
            pair_type="SIMILAR_PAIR",
            category_context="Pipes & Tubes: Stainless Steel 50 NB / 2 Inch Sch 40 ASTM A312 Pipe (Exemplary Pair)",
            material_a_code="SAIL-PIP-50NB",
            material_b_code="IOCL-PIP-2INCH",
            material_a_text=pipe_desc_a,
            material_b_text=pipe_desc_b,
            semantic_similarity_score=pipe_score,
            interpretation="High semantic similarity - strong vector alignment across domain specifications and technical descriptors.",
            embedding_method="DETERMINISTIC_TOKEN_HASH_STUB",
            vector_a_preview=vec_a[:8],
            vector_b_preview=vec_b[:8],
        ))

    # 4. Similar Cable Pair: NTPC-CBL-3C185 vs BHEL-CBL-185-3C
    if "NTPC-CBL-3C185" in by_code and "BHEL-CBL-185-3C" in by_code:
        mat_a = by_code["NTPC-CBL-3C185"]
        mat_b = by_code["BHEL-CBL-185-3C"]
        score, text_a, text_b, interp = compare_semantic_similarity(mat_a, mat_b)
        comparisons.append(SemanticSampleComparisonItem(
            pair_type="SIMILAR_PAIR",
            category_context="Electrical Cables: 1.1KV 3-Core 185 sqmm XLPE Armoured Aluminium (NTPC vs BHEL)",
            material_a_code=mat_a.source_material_code,
            material_b_code=mat_b.source_material_code,
            material_a_text=text_a,
            material_b_text=text_b,
            semantic_similarity_score=score,
            interpretation=interp,
            embedding_method="DETERMINISTIC_TOKEN_HASH_STUB",
            vector_a_preview=generate_stub_embedding(text_a)[:8],
            vector_b_preview=generate_stub_embedding(text_b)[:8],
        ))

    # 5. Dissimilar Pair: CR-BEAR-6205 (Ball Bearing) vs NTPC-CBL-3C185 (Electrical Cable)
    if "CR-BEAR-6205" in by_code and "NTPC-CBL-3C185" in by_code:
        mat_a = by_code["CR-BEAR-6205"]
        mat_b = by_code["NTPC-CBL-3C185"]
        score, text_a, text_b, interp = compare_semantic_similarity(mat_a, mat_b)
        comparisons.append(SemanticSampleComparisonItem(
            pair_type="DISSIMILAR_PAIR",
            category_context="Cross-Domain Contrast: Deep Groove Ball Bearing vs 1.1KV Armoured Cable",
            material_a_code=mat_a.source_material_code,
            material_b_code=mat_b.source_material_code,
            material_a_text=text_a,
            material_b_text=text_b,
            semantic_similarity_score=score,
            interpretation=interp,
            embedding_method="DETERMINISTIC_TOKEN_HASH_STUB",
            vector_a_preview=generate_stub_embedding(text_a)[:8],
            vector_b_preview=generate_stub_embedding(text_b)[:8],
        ))

    return SemanticSampleComparisonResponse(
        total_comparisons=len(comparisons),
        comparisons=comparisons,
        method="DETERMINISTIC_TOKEN_HASH_STUB",
        dimensions=64,
        pgvector_ready=True,
        note="Local deterministic embedding stub, model integration planned"
    )

@router.post("/hybrid-score", response_model=HybridScoringResponse, tags=["Hybrid Match Scoring & ML Features"])
async def calculate_candidates_hybrid_score(payload: HybridScoringRequest):
    """
    Computes rule-based hybrid match scores and 14-dim feature vectors for candidate pairs.
    Combines RapidFuzz (25%), attributes (20%), semantic embeddings (20%), token overlap (10%),
    category compatibility (10%), UOM (5%), OEM/part parity (5%), and completeness bonus (5%),
    subject to hard conflict penalty caps.
    """
    if not payload.candidates:
        return HybridScoringResponse(
            total_candidates_scored=0,
            auto_match_count=0,
            strong_review_count=0,
            manual_review_count=0,
            weak_review_count=0,
            rejected_count=0,
            candidates=[],
        )

    scored = score_candidates_hybrid(payload.candidates)
    return HybridScoringResponse(
        total_candidates_scored=len(scored),
        auto_match_count=sum(1 for c in scored if c.hybrid_classification == HybridClassification.AUTO_MATCH_RECOMMENDED),
        strong_review_count=sum(1 for c in scored if c.hybrid_classification == HybridClassification.STRONG_REVIEW_CANDIDATE),
        manual_review_count=sum(1 for c in scored if c.hybrid_classification == HybridClassification.MANUAL_REVIEW_REQUIRED),
        weak_review_count=sum(1 for c in scored if c.hybrid_classification == HybridClassification.WEAK_MATCH_REVIEW_OPTIONAL),
        rejected_count=sum(1 for c in scored if c.hybrid_classification == HybridClassification.REJECTED_BY_SCORING),
        candidates=scored,
    )

@router.get("/hybrid-score/sample", response_model=HybridScoringResponse, tags=["Hybrid Match Scoring & ML Features"])
async def get_sample_hybrid_scores(
    min_candidate_score: float = Query(0.50, ge=0.0, le=1.0, description="Minimum initial candidate filter score")
):
    """
    Loads sample_materials_raw.csv, performs CSV preview, detects candidates with RapidFuzz,
    enriches with semantic vectors, evaluates rule-based hybrid scores, and returns ranked candidates.
    """
    sample_paths = [
        Path("..") / "sample-data" / "sample_materials_raw.csv",
        Path("sample-data") / "sample_materials_raw.csv",
        Path(__file__).resolve().parents[3] / "sample-data" / "sample_materials_raw.csv",
        Path(__file__).resolve().parents[2] / "sample-data" / "sample_materials_raw.csv",
    ]
    sample_file = None
    for p in sample_paths:
        if p.exists():
            sample_file = p
            break

    if not sample_file:
        raise HTTPException(
            status_code=404,
            detail="Sample data file sample_materials_raw.csv could not be found."
        )

    try:
        with open(sample_file, "r", encoding="utf-8") as f:
            content = f.read()
        preview_res = parse_csv_content(
            csv_text_or_bytes=content,
            file_name="sample_materials_raw.csv"
        )
        cand_resp = find_duplicate_candidates(
            preview_res.valid_records,
            min_score=min_candidate_score,
            enrich_embeddings=True
        )
        scored = score_candidates_hybrid(cand_resp.candidates)

        return HybridScoringResponse(
            total_candidates_scored=len(scored),
            auto_match_count=sum(1 for c in scored if c.hybrid_classification == HybridClassification.AUTO_MATCH_RECOMMENDED),
            strong_review_count=sum(1 for c in scored if c.hybrid_classification == HybridClassification.STRONG_REVIEW_CANDIDATE),
            manual_review_count=sum(1 for c in scored if c.hybrid_classification == HybridClassification.MANUAL_REVIEW_REQUIRED),
            weak_review_count=sum(1 for c in scored if c.hybrid_classification == HybridClassification.WEAK_MATCH_REVIEW_OPTIONAL),
            rejected_count=sum(1 for c in scored if c.hybrid_classification == HybridClassification.REJECTED_BY_SCORING),
            candidates=scored,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate sample hybrid scores: {str(exc)}"
        )

@router.get("/ml-training-plan", response_model=MLTrainingPlanResponse, tags=["Hybrid Match Scoring & ML Features"])
async def get_ml_training_plan():
    """
    Returns the architectural specification and roadmap for future supervised XGBoost training.
    """
    return describe_xgboost_training_plan()

@router.get("/ml-feature-export/sample", response_model=Dict[str, Any], tags=["Hybrid Match Scoring & ML Features"])
async def get_sample_ml_feature_export(
    min_candidate_score: float = Query(0.50, ge=0.0, le=1.0)
):
    """
    Generates structured training rows from sample material candidate pairs with null labels,
    ready for future supervised learning pipelines or dataset export.
    """
    sample_paths = [
        Path("..") / "sample-data" / "sample_materials_raw.csv",
        Path("sample-data") / "sample_materials_raw.csv",
        Path(__file__).resolve().parents[3] / "sample-data" / "sample_materials_raw.csv",
        Path(__file__).resolve().parents[2] / "sample-data" / "sample_materials_raw.csv",
    ]
    sample_file = None
    for p in sample_paths:
        if p.exists():
            sample_file = p
            break

    if not sample_file:
        raise HTTPException(
            status_code=404,
            detail="Sample data file sample_materials_raw.csv could not be found."
        )

    try:
        with open(sample_file, "r", encoding="utf-8") as f:
            content = f.read()
        preview_res = parse_csv_content(
            csv_text_or_bytes=content,
            file_name="sample_materials_raw.csv"
        )
        cand_resp = find_duplicate_candidates(
            preview_res.valid_records,
            min_score=min_candidate_score,
            enrich_embeddings=True
        )
        scored = score_candidates_hybrid(cand_resp.candidates)
        rows = export_candidates_training_dataset(scored)

        return {
            "status": "success",
            "total_rows": len(rows),
            "feature_count": 16,
            "target_model": "XGBoost Classifier (Planned)",
            "rows": rows,
            "note": "Supervised labels set to null pending verified Nodal Officer decisions."
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export ML feature rows: {str(exc)}"
        )


# ==============================================================================
# PROMPT 10: SHAP-STYLE EXPLAINABILITY & REVIEW WORKFLOW ENDPOINTS
# ==============================================================================

@router.post("/explain", response_model=ExplainabilityResponse)
async def explain_hybrid_scored_candidates(payload: Any = Body(...)):
    """
    Generate SHAP-style factor attributions, positive drivers, risk explanations,
    reviewer summaries, and audit records for one or more hybrid-scored candidates.
    """
    candidates_to_explain: List[HybridScoredCandidate] = []

    try:
        if isinstance(payload, list):
            candidates_to_explain = [HybridScoredCandidate(**c) if isinstance(c, dict) else c for c in payload]
        elif isinstance(payload, dict):
            if "candidates" in payload and isinstance(payload["candidates"], list):
                candidates_to_explain = [
                    HybridScoredCandidate(**c) if isinstance(c, dict) else c
                    for c in payload["candidates"]
                ]
            elif "candidate" in payload and isinstance(payload["candidate"], dict):
                candidates_to_explain = [HybridScoredCandidate(**payload["candidate"])]
            elif "pair_id" in payload:
                candidates_to_explain = [HybridScoredCandidate(**payload)]
            else:
                raise ValueError("Payload missing candidate duplicate data.")
        else:
            raise ValueError("Invalid request format for explainability.")

        explanations = explain_scored_candidates(candidates_to_explain)
        return ExplainabilityResponse(
            total_explained=len(explanations),
            explanations=explanations,
            version="explainability-v1.0",
            model_placeholder="Deterministic SHAP-Style Factor Attribution (SHAP Library Planned Post-XGBoost)"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to generate explainability output: {str(exc)}"
        )


@router.get("/explain/sample", response_model=ExplainabilityResponse)
async def explain_sample_hybrid_candidates(
    min_candidate_score: float = Query(0.50, ge=0.0, le=1.0, description="Minimum initial candidate threshold")
):
    """
    Runs end-to-end ingestion preview, RapidFuzz candidate pruning, semantic stub enrichment,
    rule-based hybrid scoring, and generates human-readable SHAP-style explanations for all sample candidates.
    """
    sample_file = None
    for p in [
        Path("sample-data/sample_materials_raw.csv"),
        Path("../sample-data/sample_materials_raw.csv"),
        Path("../../sample-data/sample_materials_raw.csv"),
    ]:
        if p.exists():
            sample_file = p
            break

    if not sample_file:
        raise HTTPException(
            status_code=404,
            detail="Sample data file sample_materials_raw.csv could not be found."
        )

    try:
        with open(sample_file, "r", encoding="utf-8") as f:
            content = f.read()

        preview_res = parse_csv_content(
            csv_text_or_bytes=content,
            file_name="sample_materials_raw.csv"
        )
        cand_resp = find_duplicate_candidates(
            preview_res.valid_records,
            min_score=min_candidate_score,
            enrich_embeddings=True
        )
        scored = score_candidates_hybrid(cand_resp.candidates)
        explanations = explain_scored_candidates(scored)

        return ExplainabilityResponse(
            total_explained=len(explanations),
            explanations=explanations,
            version="explainability-v1.0",
            model_placeholder="Deterministic SHAP-Style Factor Attribution (SHAP Library Planned Post-XGBoost)"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate sample explainability output: {str(exc)}"
        )


@router.post("/review-decision/demo", response_model=ReviewDecisionResponse)
async def submit_review_decision_demo(payload: ReviewDecisionRequest = Body(...)):
    """
    Demo-only endpoint: Accept reviewer decision (APPROVE, REJECT, NEEDS_MORE_INFO)
    and optional remarks from CPSE Nodal Officers.
    Strictly in-memory: returns an acknowledgement and guaranteed non-persisted response.
    """
    valid_decisions = {"APPROVE", "REJECT", "NEEDS_MORE_INFO"}
    norm_decision = payload.decision.strip().upper()

    if norm_decision not in valid_decisions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid decision '{payload.decision}'. Allowed decisions: {sorted(list(valid_decisions))}"
        )

    # Note: Deliberately non-persisted per architectural constraints
    return ReviewDecisionResponse(
        status="demo_accepted",
        candidate_id=payload.candidate_id,
        decision=norm_decision,
        reviewer_note=payload.reviewer_note,
        reviewer_name=payload.reviewer_name or "CPSE Nodal Officer (Demo)",
        message="Demo-only decision accepted in memory; not persisted.",
        persisted=False,
        recorded_at=datetime.now(timezone.utc).isoformat()
    )


@router.get("", response_model=Dict[str, Any])
@router.get("/queue", response_model=Dict[str, Any])
async def get_matching_review_queue():
    """
    Placeholder endpoint: Fetch items flagged by AI engine as potential duplicates.
    """
    return {
        "status": "success",
        "message": "AI duplicate review queue loaded (placeholder mode)",
        "count": len(PLACEHOLDER_MATCH_QUEUE),
        "data": PLACEHOLDER_MATCH_QUEUE,
        "note": "AI inference engine placeholder. Real RapidFuzz and pgvector will be connected in future sprints."
    }

@router.post("/trigger", response_model=Dict[str, Any])
async def trigger_matching_job(payload: MatchTriggerRequest = Body(...)):
    """
    Placeholder endpoint: Manually trigger an AI deduplication job across ingested records.
    """
    return {
        "status": "success",
        "message": f"Deduplication job queued for batch '{payload.source_batch_id}'",
        "job_id": "job_ai_2026_9941",
        "parameters": payload.dict(),
        "estimated_items_to_scan": 5420,
        "status_code": "PIPELINE_STAGED"
    }

@router.post("/action", response_model=Dict[str, Any])
async def record_matching_decision(
    pair_id: str = Body(..., embed=True),
    decision: str = Body(..., embed=True), # 'MERGE', 'REJECT', 'FLAG_FOR_INSPECTION'
    remarks: str = Body("", embed=True)
):
    """
    Placeholder endpoint: Record reviewer's action on an AI matched pair.
    """
    return {
        "status": "success",
        "message": f"Decision '{decision}' recorded for candidate pair '{pair_id}'",
        "audit_reference": "AUD-DEC-2026-00412"
    }
