"""
Pydantic schemas for SHAP-Style Explainability and AI Match Review Workflow.
Translates hybrid scores and feature vectors into human-readable factor attributions,
positive drivers, risk analyses, conflict highlights, reviewer summaries, and audit trails.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.hybrid_scoring import (
    HybridScoredCandidate,
    HybridClassification,
)


class ExplanationDirection(str, Enum):
    POSITIVE = "POSITIVE"  # Pushes confidence toward duplicate/match
    NEGATIVE = "NEGATIVE"  # Reduces score or penalizes match
    NEUTRAL = "NEUTRAL"    # Baseline or negligible impact


class ExplanationFactor(BaseModel):
    """
    SHAP-style factor attribution for a single feature or dimension.
    """
    factor_name: str = Field(..., description="Canonical key for the feature factor")
    display_label: str = Field(..., description="Human-friendly display name")
    contribution_value: float = Field(..., description="Absolute point contribution to the final score")
    contribution_percentage: float = Field(..., description="Relative contribution percentage [0.0 - 100.0%]")
    direction: ExplanationDirection = Field(..., description="Direction of attribution (POSITIVE, NEGATIVE, NEUTRAL)")
    explanation: str = Field(..., description="Reviewer-friendly explanation sentence")
    evidence: List[str] = Field(default_factory=list, description="Concrete data tokens or attribute values as proof")

    model_config = ConfigDict(from_attributes=True)


class AuditExplanation(BaseModel):
    """
    Concise, audit-ready explanation record suitable for compliance logs and governance audits.
    """
    candidate_pair_id: str = Field(..., description="Unique deterministic identifier for candidate pair comparison")
    material_a_summary: str = Field(..., description="Brief summary of source material A")
    material_b_summary: str = Field(..., description="Brief summary of source material B")
    hybrid_score: float = Field(..., ge=0.0, le=1.0, description="Final calibrated hybrid similarity score")
    classification: str = Field(..., description="Hybrid classification decision tier")
    top_positive_factors: List[str] = Field(default_factory=list, description="Top positive drivers supporting the match")
    top_negative_risk_factors: List[str] = Field(default_factory=list, description="Top negative or risk factors reducing confidence")
    recommendation: str = Field(..., description="Actionable governance recommendation")
    method_version: str = Field(
        default="hybrid-rule-v1 + semantic-stub-v1 + explainability-v1",
        description="Version string of scoring and explainability methodology"
    )
    timestamp: Optional[str] = Field(default=None, description="ISO timestamp of explanation generation")

    model_config = ConfigDict(from_attributes=True)


class ReviewerExplanation(BaseModel):
    """
    Comprehensive reviewer-facing explanation model for a scored candidate duplicate pair.
    """
    pair_id: str = Field(..., description="Unique deterministic pair identifier")
    source_material_a_code: str = Field(..., description="Source material A catalog code")
    source_material_b_code: str = Field(..., description="Source material B catalog code")
    source_cpse_a: str = Field(..., description="Source enterprise A name")
    source_cpse_b: str = Field(..., description="Source enterprise B name")
    hybrid_score: float = Field(..., ge=0.0, le=1.0, description="Final calibrated hybrid score")
    hybrid_classification: HybridClassification = Field(..., description="Classification tier")
    reviewer_summary: str = Field(..., description="One-sentence executive reviewer guidance")
    factors: List[ExplanationFactor] = Field(default_factory=list, description="All individual factor contributions")
    positive_factors: List[ExplanationFactor] = Field(default_factory=list, description="Factors positively driving duplication")
    risk_factors: List[ExplanationFactor] = Field(default_factory=list, description="Factors introducing risk, uncertainty, or penalty")
    conflict_factors: List[str] = Field(default_factory=list, description="Explicit technical conflict statements")
    missing_data_warnings: List[str] = Field(default_factory=list, description="Attributes missing on one or both records")
    audit_explanation: AuditExplanation = Field(..., description="Audit-ready compliance summary")
    recommendation: str = Field(..., description="Standardized governance recommendation")

    model_config = ConfigDict(from_attributes=True)


class ExplainabilityRequest(BaseModel):
    candidates: Optional[List[HybridScoredCandidate]] = Field(
        default=None,
        description="List of hybrid-scored candidate duplicate pairs to explain"
    )
    candidate: Optional[HybridScoredCandidate] = Field(
        default=None,
        description="Single hybrid-scored candidate duplicate pair to explain"
    )


class ExplainabilityResponse(BaseModel):
    total_explained: int = Field(..., description="Count of candidate pairs explained")
    explanations: List[ReviewerExplanation] = Field(default_factory=list, description="List of generated explanations")
    version: str = Field(default="explainability-v1.0", description="Explainability engine version")
    model_placeholder: str = Field(
        default="Deterministic SHAP-Style Factor Attribution (SHAP Library Planned Post-XGBoost)",
        description="Status of ML explainability model"
    )

    model_config = ConfigDict(from_attributes=True)


class ReviewDecisionRequest(BaseModel):
    """
    Demo review decision request payload submitted by Nodal Reviewers.
    """
    candidate_id: str = Field(..., description="Pair ID or candidate duplicate ID")
    decision: str = Field(
        ...,
        description="Review decision: 'APPROVE', 'REJECT', or 'NEEDS_MORE_INFO'"
    )
    reviewer_note: Optional[str] = Field(default=None, description="Optional reviewer remarks or rationale")
    reviewer_name: Optional[str] = Field(default="CPSE Nodal Officer (Demo)", description="Reviewer identity")


class ReviewDecisionResponse(BaseModel):
    """
    In-memory demo response confirming receipt of review decision.
    Strictly not persisted to database.
    """
    status: str = Field(default="demo_accepted", description="Review submission status")
    candidate_id: str = Field(..., description="Candidate pair evaluated")
    decision: str = Field(..., description="Recorded decision")
    reviewer_note: Optional[str] = Field(default=None, description="Reviewer remarks")
    reviewer_name: str = Field(default="CPSE Nodal Officer (Demo)")
    message: str = Field(
        default="Demo-only decision accepted in memory; not persisted.",
        description="Mandatory system disclosure of non-persistence"
    )
    persisted: bool = Field(default=False, description="Guaranteed False in demo prototype mode")
    recorded_at: str = Field(..., description="ISO timestamp of receipt")

    model_config = ConfigDict(from_attributes=True)
