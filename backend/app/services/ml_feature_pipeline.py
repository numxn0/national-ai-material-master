"""
ML Feature Pipeline & Training Specification for Future Supervised Learning (XGBoost).

Converts hybrid-scored candidate duplicate pairs into clean, structured training rows
ready for downstream model training, feature importance evaluation, and calibration.
Note: XGBoost is intentionally not installed or executed in this phase; feature vectors
and training schemas are established cleanly for drop-in activation upon collecting
officer review labels.
"""

from typing import List, Dict, Any, Optional

from app.schemas.hybrid_scoring import (
    HybridScoredCandidate,
    MLFeatureExportRow,
    MLTrainingPlanResponse,
)


FEATURE_DOCUMENTATION: Dict[str, str] = {
    "description_similarity": "RapidFuzz Levenshtein token set/sort ratio score [0.0 - 1.0]",
    "token_similarity": "Jaccard coefficient over normalized engineering terms [0.0 - 1.0]",
    "semantic_similarity_score": "Cosine similarity of dense vector embeddings [0.0 - 1.0]",
    "attribute_similarity": "Ratio of matching technical attribute specifications [0.0 - 1.0]",
    "exact_attribute_match_count": "Count of identical technical parameters (bore, schedule, etc.)",
    "conflicting_attribute_count": "Total count of divergent attribute values between records",
    "critical_attribute_conflict_count": "Count of high-severity discrepancies (e.g. bearing series, pipe size)",
    "missing_critical_attribute_count": "Expected mandatory domain attributes omitted from records",
    "category_compatibility": "Taxonomy domain hierarchy compatibility [0.0 - 1.0]",
    "uom_compatibility": "Unit of Measure class alignment (count vs weight vs length) [0.0 - 1.0]",
    "manufacturer_match": "OEM manufacturer parity score [0.0 - 1.0]",
    "part_number_match": "OEM catalog part number equivalence score [0.0 - 1.0]",
    "model_number_match": "Model identifier equivalence score [0.0 - 1.0]",
    "source_cpse_match": "Binary indicator: 1.0 if both records originate from same PSU",
    "confidence_gap": "Absolute delta between text similarity and attribute similarity",
    "requires_human_review": "Boolean flag indicating review threshold triggering",
}


def export_feature_vector_for_training(
    candidate: HybridScoredCandidate,
    label: Optional[int] = None,
    review_status: str = "UNLABELED"
) -> MLFeatureExportRow:
    """
    Transforms a single hybrid-scored candidate pair into a flat ML feature training row.
    """
    fv = candidate.feature_vector

    return MLFeatureExportRow(
        pair_id=candidate.pair_id,
        source_material_a_code=candidate.source_material_a.source_material_code,
        source_material_b_code=candidate.source_material_b.source_material_code,
        source_cpse_a=candidate.source_material_a.source_cpse,
        source_cpse_b=candidate.source_material_b.source_cpse,
        description_similarity=fv.description_similarity,
        token_similarity=fv.token_similarity,
        semantic_similarity_score=fv.semantic_similarity_score,
        attribute_similarity=fv.attribute_similarity,
        exact_attribute_match_count=fv.exact_attribute_match_count,
        conflicting_attribute_count=fv.conflicting_attribute_count,
        critical_attribute_conflict_count=fv.critical_attribute_conflict_count,
        missing_critical_attribute_count=fv.missing_critical_attribute_count,
        category_compatibility=fv.category_compatibility,
        uom_compatibility=fv.uom_compatibility,
        manufacturer_match=fv.manufacturer_match,
        part_number_match=fv.part_number_match,
        model_number_match=fv.model_number_match,
        source_cpse_match=fv.source_cpse_match,
        confidence_gap=fv.confidence_gap,
        requires_human_review=fv.requires_human_review,
        rule_hybrid_score=candidate.hybrid_score,
        rule_classification=candidate.hybrid_classification.value,
        label=label,
        review_status=review_status,
    )


def export_candidates_training_dataset(
    candidates: List[HybridScoredCandidate]
) -> List[Dict[str, Any]]:
    """
    Exports a list of candidates into a list of flattened dictionaries suitable
    for pandas DataFrame conversion or CSV export.
    """
    return [export_feature_vector_for_training(c).model_dump() for c in candidates]


def describe_xgboost_training_plan() -> MLTrainingPlanResponse:
    """
    Provides a comprehensive architectural roadmap for future supervised model training.
    """
    feature_names = list(FEATURE_DOCUMENTATION.keys())

    return MLTrainingPlanResponse(
        model_target="XGBoost Classifier (Planned - Gradient Boosted Trees)",
        current_status="FEATURE_EXTRACTION_READY / TRAINING_PLACEHOLDER",
        feature_count=len(feature_names),
        feature_names=feature_names,
        training_sample_requirement="Minimum 500 validated dual-officer decisions (>= 250 positive duplicate merges + >= 250 negative distinct item decisions)",
        objective_function="binary:logistic",
        evaluation_metric="logloss, auc, pr-auc, brier_score",
        retraining_trigger="Triggered bi-weekly or whenever 250 new audited Nodal Officer decisions are committed to PostgreSQL audit_logs table.",
        why_placeholder_for_now="In enterprise GovTech workflows, training an ML classifier prior to collecting validated domain decisions leads to arbitrary data leakage and uncalibrated probabilities. The hybrid rule-based engine provides immediate, 100% explainable duplicate suggestions while systematically capturing feature vectors for offline supervised training once sufficient officer decisions accumulate.",
        features_documentation=FEATURE_DOCUMENTATION,
    )
