"""
Pydantic schemas for Hybrid Match Scoring and XGBoost-Ready Feature Vectors.
Combines RapidFuzz text similarity, semantic vector embeddings, attribute matching,
taxonomy compatibility, and conflict penalties into an explainable composite score.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.material import SourceMaterialResponse
from app.schemas.matching import (
    CandidateMatchResult,
    MatchingSignal,
    ConflictSignal,
)


class HybridClassification(str, Enum):
    AUTO_MATCH_RECOMMENDED = "AUTO_MATCH_RECOMMENDED"        # >= 0.92
    STRONG_REVIEW_CANDIDATE = "STRONG_REVIEW_CANDIDATE"      # 0.80 - 0.9199
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"        # 0.65 - 0.7999
    WEAK_MATCH_REVIEW_OPTIONAL = "WEAK_MATCH_REVIEW_OPTIONAL"# 0.50 - 0.6499
    REJECTED_BY_SCORING = "REJECTED_BY_SCORING"              # < 0.50


class MatchFeatureVector(BaseModel):
    """
    14-dimensional feature vector capturing textual, semantic, attribute,
    catalog domain, and governance dimensions for candidate duplicate pairs.
    Directly exportable as training data rows for future XGBoost / LightGBM models.
    """
    # Text features
    description_similarity: float = Field(
        ..., ge=0.0, le=1.0, description="RapidFuzz token sort / token set weighted score"
    )
    token_similarity: float = Field(
        ..., ge=0.0, le=1.0, description="Normalized token Jaccard overlap score"
    )
    semantic_similarity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Dense vector cosine similarity score (pgvector-ready stub)"
    )

    # Attribute features
    attribute_similarity: float = Field(
        ..., ge=0.0, le=1.0, description="Overall attribute specification parity score"
    )
    exact_attribute_match_count: int = Field(
        ..., ge=0, description="Number of technical attributes with identical matched values"
    )
    conflicting_attribute_count: int = Field(
        ..., ge=0, description="Number of technical attributes with diverging values"
    )
    critical_attribute_conflict_count: int = Field(
        ..., ge=0, description="Number of critical attribute mismatches (bearing, diameter, schedule, rating, etc.)"
    )
    missing_critical_attribute_count: int = Field(
        ..., ge=0, description="Number of key expected attributes missing on either material record"
    )

    # Category and UOM features
    category_compatibility: float = Field(
        ..., ge=0.0, le=1.0, description="Taxonomy hierarchy compatibility score [0.0 - 1.0]"
    )
    uom_compatibility: float = Field(
        ..., ge=0.0, le=1.0, description="Unit of Measure compatibility score [0.0 - 1.0]"
    )

    # Manufacturer and Part features
    manufacturer_match: float = Field(
        ..., ge=0.0, le=1.0, description="OEM manufacturer alignment score"
    )
    part_number_match: float = Field(
        ..., ge=0.0, le=1.0, description="OEM part number alignment score"
    )
    model_number_match: float = Field(
        ..., ge=0.0, le=1.0, description="Model number alignment score"
    )

    # Governance / review features
    source_cpse_match: float = Field(
        ..., ge=0.0, le=1.0, description="1.0 if materials originate from the same CPSE/PSU, else 0.0"
    )
    confidence_gap: float = Field(
        ..., ge=0.0, le=1.0, description="Absolute difference between text similarity and attribute similarity"
    )
    requires_human_review: bool = Field(
        ..., description="True if critical conflicts exist or confidence gap exceeds uncertainty threshold"
    )

    model_config = ConfigDict(from_attributes=True)


class HybridScoreBreakdown(BaseModel):
    """
    Detailed component breakdown showing the exact contribution of each feature
    to the final hybrid duplicate score.
    """
    description_contribution: float = Field(..., description="Weighted description score (25% weight)")
    attribute_contribution: float = Field(..., description="Weighted attribute score (20% weight)")
    semantic_contribution: float = Field(..., description="Weighted semantic vector score (20% weight)")
    token_contribution: float = Field(..., description="Weighted token overlap score (10% weight)")
    category_contribution: float = Field(..., description="Weighted category score (10% weight)")
    uom_contribution: float = Field(..., description="Weighted UOM score (5% weight)")
    mfg_part_contribution: float = Field(..., description="Weighted OEM & part score (5% weight)")
    completeness_bonus: float = Field(..., description="Critical attribute completeness bonus (5% weight)")
    raw_composite_score: float = Field(..., description="Unpenalized weighted composite score [0.0 - 1.0]")
    conflict_penalty_applied: bool = Field(..., description="True if a hard conflict cap was triggered")
    conflict_penalty_description: Optional[str] = Field(default=None, description="Explanation of conflict penalty")
    score_cap_applied: Optional[float] = Field(default=None, description="Ceiling cap applied to final score if conflicted")
    final_hybrid_score: float = Field(..., description="Final calibrated hybrid similarity score [0.0 - 1.0]")

    model_config = ConfigDict(from_attributes=True)


class HybridScoredCandidate(BaseModel):
    """
    Enriched candidate duplicate pair with rule-based hybrid score,
    fine-grained breakdown, ML feature vector, and actionable recommendation.
    """
    pair_id: str = Field(..., description="Unique deterministic identifier for candidate pair comparison")
    source_material_a: SourceMaterialResponse = Field(..., description="Primary incoming CPSE source material record")
    source_material_b: SourceMaterialResponse = Field(..., description="Candidate matching CPSE source material record")
    rapidfuzz_score: float = Field(..., ge=0.0, le=1.0, description="Baseline RapidFuzz candidate score")
    hybrid_score: float = Field(..., ge=0.0, le=1.0, description="Final calibrated hybrid score [0.0 - 1.0]")
    hybrid_classification: HybridClassification = Field(..., description="Hybrid classification decision tier")
    hybrid_score_breakdown: HybridScoreBreakdown = Field(..., description="Component contribution breakdown")
    feature_vector: MatchFeatureVector = Field(..., description="14-dimensional ML training feature vector")
    hybrid_recommendation: str = Field(..., description="Actionable governance recommendation")
    matching_signals: List[MatchingSignal] = Field(default_factory=list, description="List of positive matching signals")
    conflict_signals: List[ConflictSignal] = Field(default_factory=list, description="List of conflicting or divergent attribute signals")

    model_config = ConfigDict(from_attributes=True)


class HybridScoringRequest(BaseModel):
    candidates: List[CandidateMatchResult] = Field(..., description="List of candidate duplicate pairs to score")


class HybridScoringResponse(BaseModel):
    total_candidates_scored: int = Field(..., description="Total candidate pairs evaluated")
    auto_match_count: int = Field(..., description="Candidates classified as AUTO_MATCH_RECOMMENDED")
    strong_review_count: int = Field(..., description="Candidates classified as STRONG_REVIEW_CANDIDATE")
    manual_review_count: int = Field(..., description="Candidates classified as MANUAL_REVIEW_REQUIRED")
    weak_review_count: int = Field(..., description="Candidates classified as WEAK_MATCH_REVIEW_OPTIONAL")
    rejected_count: int = Field(..., description="Candidates classified as REJECTED_BY_SCORING")
    candidates: List[HybridScoredCandidate] = Field(default_factory=list, description="Ranked hybrid scored candidates")
    scoring_version: str = Field(default="v1.0.0-rule-hybrid", description="Scoring engine version")
    xgboost_ready: bool = Field(default=True, description="Indicates feature vectors are compatible with XGBoost training")

    model_config = ConfigDict(from_attributes=True)


class MLFeatureExportRow(BaseModel):
    """
    Flat record representing one pairwise training instance for future supervised ML modeling.
    """
    pair_id: str
    source_material_a_code: str
    source_material_b_code: str
    source_cpse_a: str
    source_cpse_b: str
    description_similarity: float
    token_similarity: float
    semantic_similarity_score: float
    attribute_similarity: float
    exact_attribute_match_count: int
    conflicting_attribute_count: int
    critical_attribute_conflict_count: int
    missing_critical_attribute_count: int
    category_compatibility: float
    uom_compatibility: float
    manufacturer_match: float
    part_number_match: float
    model_number_match: float
    source_cpse_match: float
    confidence_gap: float
    requires_human_review: bool
    rule_hybrid_score: float
    rule_classification: str
    label: Optional[int] = Field(
        default=None,
        description="Ground-truth binary label: 1=Duplicate (Merge/Alias), 0=Distinct. Null until human officer reviews."
    )
    review_status: str = Field(
        default="UNLABELED",
        description="UNLABELED, APPROVED_MERGE, APPROVED_ALIAS, REJECTED_DISTINCT"
    )

    model_config = ConfigDict(from_attributes=True)


class MLTrainingPlanResponse(BaseModel):
    model_target: str = Field(default="XGBoost Classifier (Planned - Gradient Boosted Trees)")
    current_status: str = Field(default="FEATURE_EXTRACTION_READY / TRAINING_PLACEHOLDER")
    feature_count: int = Field(default=14)
    feature_names: List[str] = Field(default_factory=list)
    training_sample_requirement: str = Field(..., description="Minimum labeled samples needed for viable supervised training")
    objective_function: str = Field(default="binary:logistic")
    evaluation_metric: str = Field(default="logloss, auc, pr-auc")
    retraining_trigger: str = Field(..., description="Governance milestones triggering model retraining")
    why_placeholder_for_now: str = Field(..., description="Architectural rationale for decoupling feature pipeline from offline training")
    features_documentation: Dict[str, str] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)
