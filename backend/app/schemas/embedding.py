"""
Pydantic schemas for deterministic semantic embeddings and vector similarity.
Designed to be drop-in ready for future pgvector and Sentence Transformer models.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.material import SourceMaterialResponse


class EmbeddingVectorMetadata(BaseModel):
    dimensions: int = Field(..., description="Dimension count of the vector embedding")
    method: str = Field(
        default="DETERMINISTIC_TOKEN_HASH_STUB",
        description="Active embedding generation technique"
    )
    vector_preview_first_8_values: List[float] = Field(
        ...,
        description="First 8 floating-point values of the normalized vector"
    )
    l2_normalized: bool = Field(
        default=True,
        description="Indicates whether the vector has been normalized to unit length (L2 norm = 1.0)"
    )
    pgvector_ready: bool = Field(
        default=True,
        description="Flag denoting vector format compatibility with PostgreSQL pgvector extension"
    )
    model_target: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2 (Planned)",
        description="Future transformer model earmarked for production deployment"
    )
    note: str = Field(
        default="Deterministic local feature hashing stub for development without heavy model downloads or GPU.",
        description="Operational note explaining the stub implementation"
    )

    model_config = ConfigDict(from_attributes=True)


class EmbeddingRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Raw or standardized material text to embed")
    dimensions: Optional[int] = Field(
        default=64,
        ge=8,
        le=1024,
        description="Target embedding vector dimensions (default: 64)"
    )


class EmbeddingResponse(BaseModel):
    input_text: str = Field(..., description="Original input text provided for embedding")
    normalized_embedding_text: str = Field(
        ...,
        description="Normalized synthesized text string from which the vector was computed"
    )
    dimensions: int = Field(..., description="Dimensionality of the generated vector")
    vector_preview_first_8_values: List[float] = Field(
        ...,
        description="Preview of the first 8 values of the vector (full vector omitted for brevity)"
    )
    metadata: EmbeddingVectorMetadata = Field(..., description="Vector metadata and pgvector readiness indicators")
    note: str = Field(
        default="Deterministic local embedding stub. Full pgvector persistence & transformer weights will be activated in future milestones.",
        description="Advisory note confirming stub status"
    )

    model_config = ConfigDict(from_attributes=True)


class SemanticSimilarityRequest(BaseModel):
    material_a: SourceMaterialResponse = Field(..., description="Primary material record to compare")
    material_b: SourceMaterialResponse = Field(..., description="Secondary material record to compare")
    dimensions: Optional[int] = Field(
        default=64,
        ge=8,
        le=1024,
        description="Target embedding vector dimensions (default: 64)"
    )


class SemanticSimilarityResponse(BaseModel):
    material_a_text: str = Field(..., description="Synthesized embedding text for Material A")
    material_b_text: str = Field(..., description="Synthesized embedding text for Material B")
    semantic_similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized cosine similarity score [0.0 - 1.0]"
    )
    interpretation: str = Field(
        ...,
        description="Human-readable interpretation of semantic similarity"
    )
    embedding_method: str = Field(
        default="DETERMINISTIC_TOKEN_HASH_STUB",
        description="Method used to compute vector embeddings"
    )
    pgvector_ready: bool = Field(
        default=True,
        description="True if schemas and vectors match pgvector vector(N) specification"
    )
    dimensions: int = Field(default=64, description="Vector dimensions used")
    vector_a_preview: Optional[List[float]] = Field(
        default=None,
        description="First 8 values of vector A"
    )
    vector_b_preview: Optional[List[float]] = Field(
        default=None,
        description="First 8 values of vector B"
    )
    note: str = Field(
        default="Semantic embedding placeholder / pgvector-ready",
        description="Implementation note"
    )

    model_config = ConfigDict(from_attributes=True)


class SemanticSampleComparisonItem(BaseModel):
    pair_type: str = Field(..., description="SIMILAR_PAIR or DISSIMILAR_PAIR")
    category_context: str = Field(..., description="Contextual description of domain or relationship")
    material_a_code: str = Field(..., description="Item code of Material A")
    material_b_code: str = Field(..., description="Item code of Material B")
    material_a_text: str = Field(..., description="Synthesized embedding text for Material A")
    material_b_text: str = Field(..., description="Synthesized embedding text for Material B")
    semantic_similarity_score: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score")
    interpretation: str = Field(..., description="Interpretation of similarity result")
    embedding_method: str = Field(default="DETERMINISTIC_TOKEN_HASH_STUB")
    vector_a_preview: List[float] = Field(default_factory=list, description="First 8 vector values for A")
    vector_b_preview: List[float] = Field(default_factory=list, description="First 8 vector values for B")

    model_config = ConfigDict(from_attributes=True)


class SemanticSampleComparisonResponse(BaseModel):
    total_comparisons: int = Field(..., description="Number of sample comparisons evaluated")
    comparisons: List[SemanticSampleComparisonItem] = Field(..., description="List of comparative sample evaluations")
    method: str = Field(default="DETERMINISTIC_TOKEN_HASH_STUB")
    dimensions: int = Field(default=64)
    pgvector_ready: bool = Field(default=True)
    note: str = Field(
        default="Local deterministic embedding stub, model integration planned",
        description="Disclaimer on model integration"
    )

    model_config = ConfigDict(from_attributes=True)


class PersistentEmbeddingProviderMetadata(BaseModel):
    provider_requested: str
    provider_used: str
    model_name: str
    model_version: str
    dimensions: int
    fallback_reason: Optional[str] = None


class PersistentEmbeddingMetadataResponse(BaseModel):
    id: UUID
    source_material_id: Optional[UUID] = None
    national_material_id: Optional[UUID] = None
    provider_requested: str
    provider_used: str
    model_name: str
    model_version: str
    dimensions: int
    source_text_hash: str
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    status: str = Field(default="reused", description="generated, reused, updated, or fallback_generated")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BatchEmbeddingGenerationResponse(BaseModel):
    status: str = "success"
    batch_id: UUID
    total_materials: int
    generated_count: int
    reused_count: int
    updated_count: int
    fallback_count: int
    provider: PersistentEmbeddingProviderMetadata
    items: List[PersistentEmbeddingMetadataResponse] = Field(default_factory=list)


class PersistentEmbeddingCompareRequest(BaseModel):
    source_material_a_id: UUID
    source_material_b_id: UUID


class PersistentEmbeddingCompareResponse(BaseModel):
    source_material_a_id: UUID
    source_material_b_id: UUID
    semantic_similarity_score: float = Field(..., ge=0.0, le=1.0)
    provider: PersistentEmbeddingProviderMetadata
    embedding_a: PersistentEmbeddingMetadataResponse
    embedding_b: PersistentEmbeddingMetadataResponse
    material_a_text_hash: str
    material_b_text_hash: str
    interpretation: str
