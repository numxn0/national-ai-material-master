from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import (
    BatchEmbeddingGenerationResponse,
    PersistentEmbeddingCompareRequest,
    PersistentEmbeddingCompareResponse,
    PersistentEmbeddingMetadataResponse,
    PersistentEmbeddingProviderMetadata,
)
from app.services.persistent_embeddings import (
    EmbeddingProviderUnavailable,
    compare_source_material_embeddings,
    embedding_payload,
    generate_batch_source_embeddings,
    get_latest_source_embedding,
    interpret_similarity,
    provider_payload,
)

router = APIRouter(prefix="/embeddings", tags=["Persistent Semantic Embeddings"])


@router.post("/generate/batch/{batch_id}", response_model=BatchEmbeddingGenerationResponse)
async def generate_embeddings_for_batch(batch_id: UUID, db: Session = Depends(get_db)):
    try:
        batch, rows, provider = generate_batch_source_embeddings(db, batch_id)
    except EmbeddingProviderUnavailable as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc))
    if not batch:
        raise HTTPException(status_code=404, detail=f"Ingestion batch '{batch_id}' not found.")

    statuses = [status for _, status in rows]
    return BatchEmbeddingGenerationResponse(
        batch_id=batch_id,
        total_materials=len(rows),
        generated_count=sum(1 for status in statuses if status == "generated"),
        reused_count=sum(1 for status in statuses if status == "reused"),
        updated_count=sum(1 for status in statuses if status == "updated"),
        fallback_count=sum(1 for status in statuses if status == "fallback_generated"),
        provider=PersistentEmbeddingProviderMetadata(**provider_payload(provider)),
        items=[
            PersistentEmbeddingMetadataResponse(**embedding_payload(row, status))
            for row, status in rows
        ],
    )


@router.get("/material/{source_material_id}", response_model=PersistentEmbeddingMetadataResponse)
async def get_source_material_embedding(source_material_id: UUID, db: Session = Depends(get_db)):
    found, row = get_latest_source_embedding(db, source_material_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"Source material '{source_material_id}' not found.")
    if not row:
        raise HTTPException(status_code=404, detail=f"No embedding exists for source material '{source_material_id}'.")
    return PersistentEmbeddingMetadataResponse(**embedding_payload(row, "reused"))


@router.post("/compare", response_model=PersistentEmbeddingCompareResponse)
async def compare_persisted_source_embeddings(
    payload: PersistentEmbeddingCompareRequest = Body(...),
    db: Session = Depends(get_db),
):
    try:
        _, _, emb_a, status_a, emb_b, status_b, score, provider = compare_source_material_embeddings(
            db,
            payload.source_material_a_id,
            payload.source_material_b_id,
        )
        db.commit()
    except KeyError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=f"Source material '{exc.args[0]}' not found.")
    except EmbeddingProviderUnavailable as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc))

    return PersistentEmbeddingCompareResponse(
        source_material_a_id=payload.source_material_a_id,
        source_material_b_id=payload.source_material_b_id,
        semantic_similarity_score=score,
        provider=PersistentEmbeddingProviderMetadata(**provider_payload(provider)),
        embedding_a=PersistentEmbeddingMetadataResponse(**embedding_payload(emb_a, status_a)),
        embedding_b=PersistentEmbeddingMetadataResponse(**embedding_payload(emb_b, status_b)),
        material_a_text_hash=emb_a.source_text_hash,
        material_b_text_hash=emb_b.source_text_hash,
        interpretation=interpret_similarity(score),
    )
