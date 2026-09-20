import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import IngestionBatch, MaterialEmbedding, NationalMaterial, SourceMaterial
from app.services.embedding_service import calculate_cosine_similarity, generate_stub_embedding

STUB_MODEL_NAME = "deterministic-token-hash"
STUB_MODEL_VERSION = "stub-v1"


class EmbeddingProviderUnavailable(Exception):
    pass


@dataclass(frozen=True)
class ProviderMetadata:
    provider_requested: str
    provider_used: str
    model_name: str
    model_version: str
    dimensions: int
    fallback_reason: Optional[str] = None


class EmbeddingProvider(Protocol):
    metadata: ProviderMetadata

    def embed(self, texts: List[str]) -> List[List[float]]:
        ...


class StubEmbeddingProvider:
    def __init__(self, *, provider_requested: str = "stub", dimensions: int = 64, fallback_reason: Optional[str] = None):
        self.metadata = ProviderMetadata(
            provider_requested=provider_requested,
            provider_used="stub",
            model_name=STUB_MODEL_NAME,
            model_version=STUB_MODEL_VERSION,
            dimensions=dimensions,
            fallback_reason=fallback_reason,
        )

    def embed(self, texts: List[str]) -> List[List[float]]:
        return [generate_stub_embedding(text, dimensions=self.metadata.dimensions) for text in texts]


class SentenceTransformerEmbeddingProvider:
    def __init__(self, *, model_name: str, dimensions: int, provider_requested: str = "sentence_transformer"):
        if model_name.startswith("__unavailable__"):
            raise RuntimeError("Forced sentence-transformer unavailability for verification.")
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:
            raise RuntimeError(f"sentence-transformers is not installed: {exc}") from exc

        self._model = SentenceTransformer(model_name)
        model_dim = int(getattr(self._model, "get_sentence_embedding_dimension", lambda: dimensions)() or dimensions)
        self.metadata = ProviderMetadata(
            provider_requested=provider_requested,
            provider_used="sentence_transformer",
            model_name=model_name,
            model_version=model_name,
            dimensions=model_dim,
            fallback_reason=None,
        )

    def embed(self, texts: List[str]) -> List[List[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [[float(x) for x in vector] for vector in vectors]


def get_embedding_provider() -> EmbeddingProvider:
    requested = (settings.EMBEDDING_PROVIDER or "stub").strip().lower()
    dimensions = int(settings.EMBEDDING_DIMENSIONS or 64)
    if requested == "stub":
        return StubEmbeddingProvider(provider_requested="stub", dimensions=dimensions)
    if requested == "sentence_transformer":
        try:
            return SentenceTransformerEmbeddingProvider(
                model_name=settings.SENTENCE_TRANSFORMER_MODEL,
                dimensions=dimensions,
                provider_requested="sentence_transformer",
            )
        except Exception as exc:
            if settings.EMBEDDING_ALLOW_STUB_FALLBACK:
                return StubEmbeddingProvider(
                    provider_requested="sentence_transformer",
                    dimensions=dimensions,
                    fallback_reason=str(exc),
                )
            raise EmbeddingProviderUnavailable(f"Sentence transformer provider unavailable: {exc}") from exc
    raise EmbeddingProviderUnavailable(f"Unsupported EMBEDDING_PROVIDER '{settings.EMBEDDING_PROVIDER}'.")


def build_material_embedding_text(material: Any) -> str:
    attrs = getattr(material, "attributes", None) or getattr(material, "canonical_attributes", None) or {}
    if "attributes" in attrs and isinstance(attrs["attributes"], dict):
        attrs = attrs["attributes"]
    attr_parts = []
    for key in sorted(attrs):
        value = attrs[key]
        if value not in (None, "", [], {}):
            attr_parts.append(f"{key}:{value}")
    parts = [
        getattr(material, "standard_description", None),
        getattr(material, "category", None),
        getattr(material, "sub_category", None),
        getattr(material, "standard_uom", None) or getattr(material, "uom", None),
        " ".join(attr_parts[:20]),
    ]
    return " ".join(str(part).strip().upper() for part in parts if part not in (None, ""))


def source_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _embedding_query_for_source(source_material_id, metadata: ProviderMetadata):
    return select(MaterialEmbedding).where(
        MaterialEmbedding.source_material_id == source_material_id,
        MaterialEmbedding.provider_requested == metadata.provider_requested,
        MaterialEmbedding.provider_used == metadata.provider_used,
        MaterialEmbedding.model_name == metadata.model_name,
        MaterialEmbedding.model_version == metadata.model_version,
        MaterialEmbedding.dimensions == metadata.dimensions,
    )


def _embedding_query_for_national(national_material_id, metadata: ProviderMetadata):
    return select(MaterialEmbedding).where(
        MaterialEmbedding.national_material_id == national_material_id,
        MaterialEmbedding.provider_requested == metadata.provider_requested,
        MaterialEmbedding.provider_used == metadata.provider_used,
        MaterialEmbedding.model_name == metadata.model_name,
        MaterialEmbedding.model_version == metadata.model_version,
        MaterialEmbedding.dimensions == metadata.dimensions,
    )


def upsert_source_material_embedding(
    db: Session,
    source_material: SourceMaterial,
    *,
    provider: Optional[EmbeddingProvider] = None,
) -> Tuple[MaterialEmbedding, str]:
    provider = provider or get_embedding_provider()
    text = build_material_embedding_text(source_material)
    text_hash = source_text_hash(text)
    existing = db.execute(_embedding_query_for_source(source_material.id, provider.metadata)).scalar_one_or_none()
    if existing and existing.source_text_hash == text_hash:
        return existing, "reused"

    vector = provider.embed([text])[0]
    metadata_json = {
        "embedding_text_hash": text_hash,
        "provider_requested": provider.metadata.provider_requested,
        "provider_used": provider.metadata.provider_used,
        "fallback_reason": provider.metadata.fallback_reason,
        "embedding_text_preview": text[:240],
        "vector_preview_first_8_values": vector[:8],
    }
    if existing:
        existing.vector_values = vector
        existing.source_text_hash = text_hash
        existing.metadata_json = metadata_json
        existing.updated_at = _now()
        return existing, "updated"

    row = MaterialEmbedding(
        source_material_id=source_material.id,
        national_material_id=None,
        provider_requested=provider.metadata.provider_requested,
        provider_used=provider.metadata.provider_used,
        model_name=provider.metadata.model_name,
        model_version=provider.metadata.model_version,
        dimensions=provider.metadata.dimensions,
        vector_values=vector,
        source_text_hash=text_hash,
        metadata_json=metadata_json,
    )
    db.add(row)
    db.flush()
    return row, "fallback_generated" if provider.metadata.fallback_reason else "generated"


def upsert_national_material_embedding(
    db: Session,
    national_material: NationalMaterial,
    *,
    provider: Optional[EmbeddingProvider] = None,
) -> Tuple[MaterialEmbedding, str]:
    provider = provider or get_embedding_provider()
    text = build_material_embedding_text(national_material)
    text_hash = source_text_hash(text)
    existing = db.execute(_embedding_query_for_national(national_material.id, provider.metadata)).scalar_one_or_none()
    if existing and existing.source_text_hash == text_hash:
        return existing, "reused"
    vector = provider.embed([text])[0]
    metadata_json = {
        "embedding_text_hash": text_hash,
        "provider_requested": provider.metadata.provider_requested,
        "provider_used": provider.metadata.provider_used,
        "fallback_reason": provider.metadata.fallback_reason,
        "embedding_text_preview": text[:240],
        "vector_preview_first_8_values": vector[:8],
    }
    if existing:
        existing.vector_values = vector
        existing.source_text_hash = text_hash
        existing.metadata_json = metadata_json
        existing.updated_at = _now()
        return existing, "updated"
    row = MaterialEmbedding(
        source_material_id=None,
        national_material_id=national_material.id,
        provider_requested=provider.metadata.provider_requested,
        provider_used=provider.metadata.provider_used,
        model_name=provider.metadata.model_name,
        model_version=provider.metadata.model_version,
        dimensions=provider.metadata.dimensions,
        vector_values=vector,
        source_text_hash=text_hash,
        metadata_json=metadata_json,
    )
    db.add(row)
    db.flush()
    return row, "fallback_generated" if provider.metadata.fallback_reason else "generated"


def generate_batch_source_embeddings(db: Session, batch_id) -> Tuple[Optional[IngestionBatch], List[Tuple[MaterialEmbedding, str]], ProviderMetadata]:
    batch = db.get(IngestionBatch, batch_id)
    if not batch:
        return None, [], ProviderMetadata(
            provider_requested=settings.EMBEDDING_PROVIDER,
            provider_used="unknown",
            model_name=settings.SENTENCE_TRANSFORMER_MODEL,
            model_version=settings.SENTENCE_TRANSFORMER_MODEL,
            dimensions=int(settings.EMBEDDING_DIMENSIONS or 64),
            fallback_reason=None,
        )
    provider = get_embedding_provider()
    materials = db.execute(
        select(SourceMaterial).where(SourceMaterial.ingestion_batch_id == batch_id).order_by(SourceMaterial.created_at.asc())
    ).scalars().all()
    rows = [upsert_source_material_embedding(db, material, provider=provider) for material in materials]
    db.commit()
    return batch, rows, provider.metadata


def get_latest_source_embedding(db: Session, source_material_id) -> Tuple[bool, Optional[MaterialEmbedding]]:
    material = db.get(SourceMaterial, source_material_id)
    if not material:
        return False, None
    row = db.execute(
        select(MaterialEmbedding)
        .where(MaterialEmbedding.source_material_id == source_material_id)
        .order_by(MaterialEmbedding.updated_at.desc())
    ).scalars().first()
    return True, row


def compare_source_material_embeddings(
    db: Session,
    source_material_a_id,
    source_material_b_id,
    *,
    provider: Optional[EmbeddingProvider] = None,
) -> Tuple[SourceMaterial, SourceMaterial, MaterialEmbedding, str, MaterialEmbedding, str, float, ProviderMetadata]:
    material_a = db.get(SourceMaterial, source_material_a_id)
    material_b = db.get(SourceMaterial, source_material_b_id)
    if not material_a or not material_b:
        missing = source_material_a_id if not material_a else source_material_b_id
        raise KeyError(str(missing))
    provider = provider or get_embedding_provider()
    emb_a, status_a = upsert_source_material_embedding(db, material_a, provider=provider)
    emb_b, status_b = upsert_source_material_embedding(db, material_b, provider=provider)
    score = calculate_cosine_similarity(emb_a.vector_values, emb_b.vector_values)
    return material_a, material_b, emb_a, status_a, emb_b, status_b, score, provider.metadata


def interpret_similarity(score: float) -> str:
    if score >= 0.85:
        return "High semantic similarity - strong vector alignment across material specifications."
    if score >= 0.70:
        return "Moderate semantic similarity - compatible material domain with technical variation."
    if score >= 0.40:
        return "Partial semantic overlap - shared engineering terms but distinct specifications."
    return "Low semantic similarity - unrelated material classes or divergent specifications."


def embedding_payload(row: MaterialEmbedding, status: str = "reused") -> Dict[str, Any]:
    return {
        "id": row.id,
        "source_material_id": row.source_material_id,
        "national_material_id": row.national_material_id,
        "provider_requested": row.provider_requested,
        "provider_used": row.provider_used,
        "model_name": row.model_name,
        "model_version": row.model_version,
        "dimensions": row.dimensions,
        "source_text_hash": row.source_text_hash,
        "metadata_json": row.metadata_json or {},
        "status": status,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def provider_payload(metadata: ProviderMetadata) -> Dict[str, Any]:
    return {
        "provider_requested": metadata.provider_requested,
        "provider_used": metadata.provider_used,
        "model_name": metadata.model_name,
        "model_version": metadata.model_version,
        "dimensions": metadata.dimensions,
        "fallback_reason": metadata.fallback_reason,
    }
