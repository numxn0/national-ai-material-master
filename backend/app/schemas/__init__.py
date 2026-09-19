from .common import APIResponse, HealthCheckResponse
from .material import (
    MaterialAttribute,
    SourceMaterialBase,
    SourceMaterialCreate,
    SourceMaterialResponse,
    NationalMaterialBase,
    NationalMaterialCreate,
    NationalMaterialResponse,
    TextNormalizationRequest,
    TextNormalizationResponse,
)
from .mapping import (
    MatchMethod,
    MatchStatus,
    ApprovalStatus,
    MaterialMappingBase,
    MaterialMappingCreate,
    MaterialMappingResponse,
)
from .ingestion import (
    IngestionStatus,
    IngestionBatchBase,
    IngestionBatchCreate,
    IngestionBatchResponse,
    CSVPreviewRowError,
    CSVPreviewSummary,
    CSVPreviewResponse,
)
from .audit import (
    AuditAction,
    AuditLogBase,
    AuditLogCreate,
    AuditLogResponse,
    AuditTrailEvent,
    AuditTrailResponse,
    AuditChainVerificationResponse,
)
from .extraction import (
    ExtractedAttribute,
    ExtractionConfidence,
    AttributeExtractionRequest,
    AttributeExtractionResponse,
)
from .matching import (
    CandidateClassification,
    MatchingSignal,
    ConflictSignal,
    CandidateScoreBreakdown,
    CandidateMatchResult,
    CandidateMatchRequest,
    CandidateMatchResponse,
)
from .embedding import (
    EmbeddingVectorMetadata,
    EmbeddingRequest,
    EmbeddingResponse,
    SemanticSimilarityRequest,
    SemanticSimilarityResponse,
    SemanticSampleComparisonItem,
    SemanticSampleComparisonResponse,
)
from .hybrid_scoring import (
    HybridClassification,
    MatchFeatureVector,
    HybridScoreBreakdown,
    HybridScoredCandidate,
    HybridScoringRequest,
    HybridScoringResponse,
    MLFeatureExportRow,
    MLTrainingPlanResponse,
)
from .explainability import (
    ExplanationDirection,
    ExplanationFactor,
    AuditExplanation,
    ReviewerExplanation,
    ExplainabilityRequest,
    ExplainabilityResponse,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
)
from .approval_workflow import (
    ApprovalStage,
    ApprovalWorkflowStatus,
    ApprovalDecision,
    ProcurementImpact,
    MappingPreview,
    ApprovalCase,
    ApprovalActionRequest,
    ApprovalActionResponse,
    ApprovalQueueResponse,
)
from .demo import (
    ModuleStatus,
    DemoSummaryResponse,
)
from .examples import (
    EXAMPLE_SOURCE_MATERIAL,
    EXAMPLE_NATIONAL_MATERIAL,
    EXAMPLE_MATERIAL_MAPPING,
    EXAMPLE_INGESTION_BATCH,
    EXAMPLE_AUDIT_LOG,
)

__all__ = [
    # Common
    "APIResponse",
    "HealthCheckResponse",
    # Extraction
    "ExtractedAttribute",
    "ExtractionConfidence",
    "AttributeExtractionRequest",
    "AttributeExtractionResponse",
    # Material
    "MaterialAttribute",
    "SourceMaterialBase",
    "SourceMaterialCreate",
    "SourceMaterialResponse",
    "NationalMaterialBase",
    "NationalMaterialCreate",
    "NationalMaterialResponse",
    "TextNormalizationRequest",
    "TextNormalizationResponse",
    # Mapping
    "MatchMethod",
    "MatchStatus",
    "ApprovalStatus",
    "MaterialMappingBase",
    "MaterialMappingCreate",
    "MaterialMappingResponse",
    # Ingestion
    "IngestionStatus",
    "IngestionBatchBase",
    "IngestionBatchCreate",
    "IngestionBatchResponse",
    "CSVPreviewRowError",
    "CSVPreviewSummary",
    "CSVPreviewResponse",
    # Audit
    "AuditAction",
    "AuditLogBase",
    "AuditLogCreate",
    "AuditLogResponse",
    "AuditTrailEvent",
    "AuditTrailResponse",
    "AuditChainVerificationResponse",
    # Matching
    "CandidateClassification",
    "MatchingSignal",
    "ConflictSignal",
    "CandidateScoreBreakdown",
    "CandidateMatchResult",
    "CandidateMatchRequest",
    "CandidateMatchResponse",
    # Embedding
    "EmbeddingVectorMetadata",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "SemanticSimilarityRequest",
    "SemanticSimilarityResponse",
    "SemanticSampleComparisonItem",
    "SemanticSampleComparisonResponse",
    # Hybrid Scoring & ML Features
    "HybridClassification",
    "MatchFeatureVector",
    "HybridScoreBreakdown",
    "HybridScoredCandidate",
    "HybridScoringRequest",
    "HybridScoringResponse",
    "MLFeatureExportRow",
    "MLTrainingPlanResponse",
    # Explainability & Reviewer Workflow
    "ExplanationDirection",
    "ExplanationFactor",
    "AuditExplanation",
    "ReviewerExplanation",
    "ExplainabilityRequest",
    "ExplainabilityResponse",
    "ReviewDecisionRequest",
    "ReviewDecisionResponse",
    # Approval Workflow & Dual Governance
    "ApprovalStage",
    "ApprovalWorkflowStatus",
    "ApprovalDecision",
    "ProcurementImpact",
    "MappingPreview",
    "ApprovalCase",
    "ApprovalActionRequest",
    "ApprovalActionResponse",
    "ApprovalQueueResponse",
    # Demo Summary
    "ModuleStatus",
    "DemoSummaryResponse",
    # Examples
    "EXAMPLE_SOURCE_MATERIAL",
    "EXAMPLE_NATIONAL_MATERIAL",
    "EXAMPLE_MATERIAL_MAPPING",
    "EXAMPLE_INGESTION_BATCH",
    "EXAMPLE_AUDIT_LOG",
]
