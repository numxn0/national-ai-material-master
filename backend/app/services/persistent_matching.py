import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import IngestionBatch, MatchCandidate, MLModelRun, SourceMaterial
from app.schemas.material import SourceMaterialResponse
from app.services.candidate_matching import find_duplicate_candidates
from app.services.explainability import explain_scored_candidate
from app.services.hybrid_scoring import score_candidates_hybrid
from app.services.persistent_audit import append_audit_event
from app.services.persistent_embeddings import compare_source_material_embeddings, get_embedding_provider, provider_payload

METHOD_VERSION = "candidate-rules-v1 + hybrid-rule-v1 + explainability-v1"


def orm_source_to_schema(material: SourceMaterial) -> SourceMaterialResponse:
    return SourceMaterialResponse(
        id=material.id,
        source_cpse=material.source_cpse,
        source_system=material.source_system,
        source_material_code=material.source_material_code,
        raw_description=material.raw_description,
        cleaned_description=material.cleaned_description,
        standard_description=material.standard_description,
        category=material.category,
        sub_category=material.sub_category,
        material_type=material.material_type,
        material_grade=material.material_grade,
        manufacturer=material.manufacturer,
        part_number=material.part_number,
        model_number=material.model_number,
        uom=material.uom,
        attributes=material.attributes or {},
        normalized_tokens=material.normalized_tokens or [],
        ingestion_batch_id=material.ingestion_batch_id,
        match_status=material.match_status if material.match_status in {"UNPROCESSED", "MATCH_FOUND", "NEW_CANDIDATE", "AMBIGUOUS_MATCH", "NO_MATCH", "CANDIDATES_GENERATED", "NO_CANDIDATES"} else "UNPROCESSED",
        approval_status=material.approval_status,
        created_at=material.created_at,
        updated_at=material.updated_at,
    )


def deterministic_pair_id(material_a_id: uuid.UUID, material_b_id: uuid.UUID) -> str:
    left, right = sorted([str(material_a_id), str(material_b_id)])
    return f"PAIR-{left}-{right}"


def material_summary(material: SourceMaterialResponse) -> Dict[str, Any]:
    return {
        "id": str(material.id),
        "source_cpse": material.source_cpse,
        "source_system": material.source_system,
        "source_material_code": material.source_material_code,
        "standard_description": material.standard_description,
        "raw_description": material.raw_description,
        "category": material.category,
        "uom": material.uom,
        "attributes": material.attributes,
    }


def run_persistent_matching(db: Session, batch_id: uuid.UUID, min_score: float = 0.65) -> Dict[str, Any]:
    batch = db.get(IngestionBatch, batch_id)
    if not batch:
        return {"found": False}

    target_rows = db.execute(
        select(SourceMaterial).where(SourceMaterial.ingestion_batch_id == batch_id)
    ).scalars().all()
    target_ids = {row.id for row in target_rows}

    all_rows = db.execute(select(SourceMaterial)).scalars().all()
    material_by_id = {row.id: row for row in all_rows}
    schema_materials = [orm_source_to_schema(row) for row in all_rows]

    candidate_response = find_duplicate_candidates(
        schema_materials,
        min_score=min_score,
        enrich_embeddings=True,
    )

    scoped_candidates = []
    for candidate in candidate_response.candidates:
        id_a = candidate.source_material_a.id
        id_b = candidate.source_material_b.id
        if id_a == id_b:
            continue
        if id_a in target_ids or id_b in target_ids:
            candidate.pair_id = deterministic_pair_id(id_a, id_b)
            scoped_candidates.append(candidate)

    scored_candidates = score_candidates_hybrid(scoped_candidates)
    created_count = 0
    updated_count = 0
    involved_target_ids = set()
    embedding_provider = get_embedding_provider() if scored_candidates else None

    for scored in scored_candidates:
        id_a = scored.source_material_a.id
        id_b = scored.source_material_b.id
        pair_id = deterministic_pair_id(id_a, id_b)
        candidate_score = next(
            (c.score for c in scoped_candidates if c.pair_id == pair_id),
            scored.rapidfuzz_score,
        )
        reviewer_explanation = explain_scored_candidate(scored)
        source_a_summary = material_summary(scored.source_material_a)
        source_b_summary = material_summary(scored.source_material_b)
        score_details = {
            "rule_baseline": {
                "status": "ACTIVE",
                "method_version": METHOD_VERSION,
            },
            "trained_model": {
                "status": "NOT_CONFIGURED",
                "model_version": None,
                "score": None,
            },
            "candidate_score_breakdown": next(
                (c.score_breakdown.model_dump(mode="json") for c in scoped_candidates if c.pair_id == pair_id),
                {},
            ),
            "matching_signals": [sig.model_dump(mode="json") for sig in scored.matching_signals],
            "conflict_signals": [sig.model_dump(mode="json") for sig in scored.conflict_signals],
            "hybrid_score_breakdown": scored.hybrid_score_breakdown.model_dump(mode="json"),
            "feature_vector": scored.feature_vector.model_dump(mode="json"),
            "source_material_a": source_a_summary,
            "source_material_b": source_b_summary,
        }
        if embedding_provider is not None:
            _, _, emb_a, status_a, emb_b, status_b, semantic_score, provider_meta = compare_source_material_embeddings(
                db,
                id_a,
                id_b,
                provider=embedding_provider,
            )
            score_details["persistent_semantic_embedding"] = {
                "semantic_similarity_score": semantic_score,
                "provider": provider_payload(provider_meta),
                "embedding_a_id": str(emb_a.id),
                "embedding_b_id": str(emb_b.id),
                "embedding_a_status": status_a,
                "embedding_b_status": status_b,
                "source_text_hash_a": emb_a.source_text_hash,
                "source_text_hash_b": emb_b.source_text_hash,
                "decisive_scoring_signal": False,
            }
        latest_model = db.execute(
            select(MLModelRun).where(MLModelRun.status == "TRAINED").order_by(MLModelRun.completed_at.desc()).limit(1)
        ).scalar_one_or_none()
        if latest_model:
            score_details["trained_model"] = {
                "status": "AVAILABLE",
                "model_version": latest_model.model_version,
                "score": None,
                "note": "Model metadata available; inference remains optional alongside the rule baseline.",
            }

        existing = db.execute(
            select(MatchCandidate).where(MatchCandidate.pair_id == pair_id)
        ).scalar_one_or_none()
        if existing:
            existing.source_material_a_id = id_a
            existing.source_material_b_id = id_b
            existing.candidate_score = candidate_score
            existing.hybrid_score = scored.hybrid_score
            existing.classification = scored.hybrid_classification.value
            existing.score_details = score_details
            existing.explanation = reviewer_explanation.model_dump(mode="json")
            existing.method_version = METHOD_VERSION
            if not existing.status:
                existing.status = "UNREVIEWED"
            updated_count += 1
        else:
            db.add(MatchCandidate(
                pair_id=pair_id,
                source_material_a_id=id_a,
                source_material_b_id=id_b,
                candidate_score=candidate_score,
                hybrid_score=scored.hybrid_score,
                classification=scored.hybrid_classification.value,
                status="UNREVIEWED",
                score_details=score_details,
                explanation=reviewer_explanation.model_dump(mode="json"),
                method_version=METHOD_VERSION,
            ))
            created_count += 1

        if id_a in target_ids:
            involved_target_ids.add(id_a)
        if id_b in target_ids:
            involved_target_ids.add(id_b)

    for row in target_rows:
        row.match_status = "CANDIDATES_GENERATED" if row.id in involved_target_ids else "NO_CANDIDATES"

    append_audit_event(
        db,
        actor="MATCHING_PIPELINE",
        actor_role="SYSTEM_PROCESS",
        action="MATCHING_RUN_COMPLETED",
        entity_type="ingestion_batch",
        entity_id=str(batch.id),
        old_value=None,
        new_value={
            "batch_id": batch.id,
            "candidate_count": len(scored_candidates),
            "created_count": created_count,
            "updated_count": updated_count,
            "compared_record_count": candidate_response.compared_pairs,
            "min_score": min_score,
            "method_version": METHOD_VERSION,
            "target_material_count": len(target_rows),
        },
        reason="Persistent matching pipeline completed for ingestion batch.",
        method_version=METHOD_VERSION,
    )
    db.commit()
    return {
        "found": True,
        "batch": batch,
        "candidate_count": len(scored_candidates),
        "created_count": created_count,
        "updated_count": updated_count,
        "compared_record_count": candidate_response.compared_pairs,
        "matching_config": {"min_score": min_score},
    }


def summarize_source_material(material: Optional[SourceMaterial]) -> Optional[Dict[str, Any]]:
    if material is None:
        return None
    return {
        "id": material.id,
        "source_cpse": material.source_cpse,
        "source_system": material.source_system,
        "source_material_code": material.source_material_code,
        "standard_description": material.standard_description,
        "raw_description": material.raw_description,
        "category": material.category,
        "uom": material.uom,
        "attributes": material.attributes or {},
    }


def list_persistent_match_results(
    db: Session,
    batch_id: uuid.UUID,
    *,
    page: int = 1,
    limit: int = 50,
    classification: Optional[str] = None,
    status: Optional[str] = None,
    min_hybrid_score: Optional[float] = None,
) -> Tuple[Optional[int], List[MatchCandidate], int]:
    batch = db.get(IngestionBatch, batch_id)
    if not batch:
        return None, [], 0

    target_ids_subq = select(SourceMaterial.id).where(SourceMaterial.ingestion_batch_id == batch_id)
    conditions = [
        or_(
            MatchCandidate.source_material_a_id.in_(target_ids_subq),
            MatchCandidate.source_material_b_id.in_(target_ids_subq),
        )
    ]
    if classification:
        conditions.append(MatchCandidate.classification == classification)
    if status:
        conditions.append(MatchCandidate.status == status)
    if min_hybrid_score is not None:
        conditions.append(MatchCandidate.hybrid_score >= min_hybrid_score)

    total = db.scalar(select(func.count()).select_from(MatchCandidate).where(*conditions)) or 0
    rows = db.execute(
        select(MatchCandidate)
        .options(selectinload(MatchCandidate.source_material_a), selectinload(MatchCandidate.source_material_b))
        .where(*conditions)
        .order_by(MatchCandidate.hybrid_score.desc(), MatchCandidate.updated_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    return total, rows, total
