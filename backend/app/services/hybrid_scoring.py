"""
Hybrid Match Scoring Service with Rule-Based Fusion and XGBoost-Ready Feature Engineering.

Combines:
- RapidFuzz fuzzy text similarity (25%)
- Rule-based attribute similarity (20%)
- Deterministic semantic vector similarity (20%)
- Normalized token overlap (10%)
- Taxonomy category compatibility (10%)
- Unit of Measure compatibility (5%)
- Manufacturer & part number parity (5%)
- Technical attribute completeness bonus (5%)

Applies rigorous conflict penalty caps:
- Category incompatible: cap at 0.30
- Bearing number conflict: cap at 0.40
- Multiple critical conflicts: cap at 0.45
- Part number conflict: cap at 0.50
- Single critical conflict: cap at 0.60
"""

import math
from typing import List, Tuple, Optional, Dict, Any

from app.schemas.matching import CandidateMatchResult, ConflictSignal, MatchingSignal
from app.schemas.hybrid_scoring import (
    HybridClassification,
    MatchFeatureVector,
    HybridScoreBreakdown,
    HybridScoredCandidate,
)
from app.services.embedding_service import compare_semantic_similarity


def _clean_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip().upper()


def _count_missing_critical_attributes(candidate: CandidateMatchResult) -> int:
    """
    Checks for critical missing technical attributes based on material category.
    """
    cat = _clean_str(getattr(candidate.source_material_a, "category", ""))
    attrs_a = getattr(candidate.source_material_a, "attributes", {}) or {}
    attrs_b = getattr(candidate.source_material_b, "attributes", {}) or {}

    missing_count = 0
    if "BEAR" in cat:
        for k in ["bearing_number"]:
            if k not in attrs_a: missing_count += 1
            if k not in attrs_b: missing_count += 1
    elif "PIPE" in cat or "TUBE" in cat:
        for k in ["schedule", "nominal_bore", "diameter_mm", "nominal_diameter"]:
            if not any(x in attrs_a for x in ["nominal_bore", "diameter_mm", "nominal_diameter"]):
                missing_count += 1
                break
        if "schedule" not in attrs_a and "schedule" not in attrs_b:
            missing_count += 1
    elif "CABLE" in cat:
        for k in ["cross_section_sqmm", "number_of_cores", "voltage"]:
            if k not in attrs_a: missing_count += 1
            if k not in attrs_b: missing_count += 1
    elif "VALVE" in cat:
        for k in ["pressure_rating"]:
            if k not in attrs_a: missing_count += 1
            if k not in attrs_b: missing_count += 1

    return missing_count


def build_match_feature_vector(candidate: CandidateMatchResult) -> MatchFeatureVector:
    """
    Constructs a 14-dimensional normalized feature vector from a candidate duplicate pair.
    """
    # 1. Text & Semantic features
    desc_sim = float(candidate.score_breakdown.description_similarity)
    tok_sim = float(candidate.score_breakdown.token_overlap)

    if candidate.semantic_similarity_score is not None:
        sem_sim = float(candidate.semantic_similarity_score)
    else:
        sem_sim, _, _, _ = compare_semantic_similarity(
            candidate.source_material_a, candidate.source_material_b
        )

    # 2. Attribute features
    attr_sim = float(candidate.score_breakdown.attribute_similarity)
    exact_attr_matches = sum(
        1 for sig in candidate.matching_signals if sig.signal_type == "ATTRIBUTE_MATCH"
    )
    conflicting_attrs = len(candidate.conflict_signals)
    critical_conflicts = sum(
        1 for cs in candidate.conflict_signals if cs.severity == "CRITICAL"
    )
    missing_critical = _count_missing_critical_attributes(candidate)

    # 3. Category & UOM features
    cat_comp = float(candidate.score_breakdown.category_compatibility)
    uom_comp = float(candidate.score_breakdown.uom_compatibility)

    # 4. Manufacturer & Part features
    mfg_a = _clean_str(getattr(candidate.source_material_a, "manufacturer", ""))
    mfg_b = _clean_str(getattr(candidate.source_material_b, "manufacturer", ""))
    if mfg_a and mfg_b:
        mfg_match = 1.0 if mfg_a == mfg_b else 0.1
    elif mfg_a or mfg_b:
        mfg_match = 0.5
    else:
        mfg_match = 0.7

    pn_a = _clean_str(getattr(candidate.source_material_a, "part_number", ""))
    pn_b = _clean_str(getattr(candidate.source_material_b, "part_number", ""))
    if pn_a and pn_b:
        pn_match = 1.0 if pn_a == pn_b else 0.0
    elif pn_a or pn_b:
        pn_match = 0.5
    else:
        pn_match = 0.7

    mod_a = _clean_str(getattr(candidate.source_material_a, "model_number", ""))
    mod_b = _clean_str(getattr(candidate.source_material_b, "model_number", ""))
    if mod_a and mod_b:
        mod_match = 1.0 if mod_a == mod_b else 0.0
    elif mod_a or mod_b:
        mod_match = 0.5
    else:
        mod_match = 0.7

    # 5. Governance features
    cpse_a = _clean_str(getattr(candidate.source_material_a, "source_cpse", ""))
    cpse_b = _clean_str(getattr(candidate.source_material_b, "source_cpse", ""))
    source_cpse_match = 1.0 if (cpse_a and cpse_a == cpse_b) else 0.0

    confidence_gap = round(abs(desc_sim - attr_sim), 4)
    requires_human_review = (
        critical_conflicts > 0 or confidence_gap >= 0.25 or attr_sim < 0.60
    )

    return MatchFeatureVector(
        description_similarity=round(desc_sim, 4),
        token_similarity=round(tok_sim, 4),
        semantic_similarity_score=round(sem_sim, 4),
        attribute_similarity=round(attr_sim, 4),
        exact_attribute_match_count=exact_attr_matches,
        conflicting_attribute_count=conflicting_attrs,
        critical_attribute_conflict_count=critical_conflicts,
        missing_critical_attribute_count=missing_critical,
        category_compatibility=round(cat_comp, 4),
        uom_compatibility=round(uom_comp, 4),
        manufacturer_match=round(mfg_match, 4),
        part_number_match=round(pn_match, 4),
        model_number_match=round(mod_match, 4),
        source_cpse_match=source_cpse_match,
        confidence_gap=confidence_gap,
        requires_human_review=requires_human_review,
    )


def apply_conflict_penalties(
    base_score: float,
    conflict_signals: List[ConflictSignal],
    features: MatchFeatureVector
) -> Tuple[float, bool, Optional[str], Optional[float]]:
    """
    Evaluates hard conflict penalties and caps:
    - critical conflict present: cap score at 0.60
    - multiple critical conflicts: cap score at 0.45
    - category incompatible: cap score at 0.30
    - part number conflict: cap score at 0.50
    - bearing number conflict: cap score at 0.40
    """
    caps: List[Tuple[float, str]] = []

    # 1. Category incompatible
    if features.category_compatibility == 0.0:
        caps.append((0.30, "Taxonomy domain incompatible (cap: 0.30)"))

    # 2. Bearing number conflict
    for cs in conflict_signals:
        if cs.attribute == "bearing_number" and cs.severity == "CRITICAL":
            caps.append((0.40, f"Critical bearing series mismatch ({cs.value_a} vs {cs.value_b}) (cap: 0.40)"))
            break

    # 3. Part number conflict
    for cs in conflict_signals:
        if cs.attribute == "part_number" and cs.severity == "CRITICAL":
            caps.append((0.50, f"OEM part number conflict ({cs.value_a} vs {cs.value_b}) (cap: 0.50)"))
            break

    # 4. Multiple critical conflicts
    if features.critical_attribute_conflict_count >= 2:
        caps.append((0.45, f"Multiple critical attribute conflicts ({features.critical_attribute_conflict_count}) (cap: 0.45)"))
    elif features.critical_attribute_conflict_count == 1:
        caps.append((0.60, "Critical attribute conflict present (cap: 0.60)"))

    if not caps:
        return base_score, False, None, None

    # Pick the most restrictive (lowest) cap
    caps.sort(key=lambda x: x[0])
    lowest_cap, reason = caps[0]

    if base_score > lowest_cap:
        return round(lowest_cap, 4), True, reason, lowest_cap

    return base_score, False, None, None


def calculate_rule_based_hybrid_score(
    features: MatchFeatureVector,
    conflict_signals: List[ConflictSignal]
) -> Tuple[float, HybridScoreBreakdown]:
    """
    Computes rule-based hybrid score using weighted fusion and conflict penalty caps:
    - 25% description similarity
    - 20% attribute similarity
    - 20% semantic similarity
    - 10% token similarity
    - 10% category compatibility
    - 5% UOM compatibility
    - 5% manufacturer / part / model compatibility
    - 5% critical completeness bonus
    """
    # 1. Component contributions
    desc_contrib = round(0.25 * features.description_similarity, 4)
    attr_contrib = round(0.20 * features.attribute_similarity, 4)
    sem_contrib = round(0.20 * features.semantic_similarity_score, 4)
    tok_contrib = round(0.10 * features.token_similarity, 4)
    cat_contrib = round(0.10 * features.category_compatibility, 4)
    uom_contrib = round(0.05 * features.uom_compatibility, 4)

    # OEM & Part combined score
    mfg_part_score = (
        0.5 * features.part_number_match +
        0.3 * features.manufacturer_match +
        0.2 * features.model_number_match
    )
    mfg_part_contrib = round(0.05 * mfg_part_score, 4)

    # Completeness bonus (awarded when key technical specs are fully specified)
    if features.missing_critical_attribute_count == 0 and features.exact_attribute_match_count >= 1:
        comp_bonus_val = 1.0
    elif features.missing_critical_attribute_count == 0:
        comp_bonus_val = 0.7
    else:
        comp_bonus_val = max(0.0, 1.0 - (0.4 * features.missing_critical_attribute_count))
    completeness_bonus = round(0.05 * comp_bonus_val, 4)

    raw_composite = round(
        desc_contrib +
        attr_contrib +
        sem_contrib +
        tok_contrib +
        cat_contrib +
        uom_contrib +
        mfg_part_contrib +
        completeness_bonus,
        4
    )

    # 2. Apply conflict penalties & caps
    final_score, pen_applied, pen_desc, cap_val = apply_conflict_penalties(
        raw_composite, conflict_signals, features
    )
    final_score = round(max(0.0, min(1.0, final_score)), 4)

    breakdown = HybridScoreBreakdown(
        description_contribution=desc_contrib,
        attribute_contribution=attr_contrib,
        semantic_contribution=sem_contrib,
        token_contribution=tok_contrib,
        category_contribution=cat_contrib,
        uom_contribution=uom_contrib,
        mfg_part_contribution=mfg_part_contrib,
        completeness_bonus=completeness_bonus,
        raw_composite_score=raw_composite,
        conflict_penalty_applied=pen_applied,
        conflict_penalty_description=pen_desc,
        score_cap_applied=cap_val,
        final_hybrid_score=final_score,
    )

    return final_score, breakdown


def classify_hybrid_score(score: float) -> HybridClassification:
    """
    Assigns final decision tier based on hybrid score thresholds.
    """
    if score >= 0.92:
        return HybridClassification.AUTO_MATCH_RECOMMENDED
    elif score >= 0.80:
        return HybridClassification.STRONG_REVIEW_CANDIDATE
    elif score >= 0.65:
        return HybridClassification.MANUAL_REVIEW_REQUIRED
    elif score >= 0.50:
        return HybridClassification.WEAK_MATCH_REVIEW_OPTIONAL
    return HybridClassification.REJECTED_BY_SCORING


def generate_hybrid_recommendation(
    candidate: CandidateMatchResult,
    hybrid_score: float,
    classification: HybridClassification,
    features: MatchFeatureVector,
    breakdown: HybridScoreBreakdown
) -> str:
    """
    Generates actionable, governance-grade recommendation rationale.
    """
    if breakdown.conflict_penalty_applied and breakdown.conflict_penalty_description:
        return f"Score penalized: {breakdown.conflict_penalty_description}. Manual engineering verification required before alias creation."

    if classification == HybridClassification.AUTO_MATCH_RECOMMENDED:
        return "Exemplary candidate duplicate: High text & semantic alignment, matched technical parameters, and zero critical discrepancies. Recommended for automated master SKU alias linkage."
    elif classification == HybridClassification.STRONG_REVIEW_CANDIDATE:
        return "Strong duplicate candidate: Minor catalog phrasing or manufacturer variance. Recommended for expedited Tier-1 Nodal Officer approval."
    elif classification == HybridClassification.MANUAL_REVIEW_REQUIRED:
        if features.confidence_gap >= 0.20:
            return f"Moderate candidate with confidence gap ({int(features.confidence_gap * 100)}% divergence between text and parameters). Requires engineering inspection."
        return "Viable candidate duplicate: Strong textual overlap, verify slight specification tolerances."
    elif classification == HybridClassification.WEAK_MATCH_REVIEW_OPTIONAL:
        return "Weak duplicate signal: Low attribute parity or high catalog ambiguity. Alias creation optional upon physical item inspection."
    else:
        return "Rejected: Insufficient similarity or conflicting functional specifications. Maintain as distinct inventory SKUs."


def score_candidate_hybrid(candidate: CandidateMatchResult) -> HybridScoredCandidate:
    """
    Executes end-to-end hybrid scoring for a single candidate duplicate pair.
    """
    feature_vector = build_match_feature_vector(candidate)
    hybrid_score, breakdown = calculate_rule_based_hybrid_score(
        feature_vector, candidate.conflict_signals
    )
    classification = classify_hybrid_score(hybrid_score)
    recommendation = generate_hybrid_recommendation(
        candidate, hybrid_score, classification, feature_vector, breakdown
    )

    return HybridScoredCandidate(
        pair_id=candidate.pair_id,
        source_material_a=candidate.source_material_a,
        source_material_b=candidate.source_material_b,
        rapidfuzz_score=candidate.score,
        hybrid_score=hybrid_score,
        hybrid_classification=classification,
        hybrid_score_breakdown=breakdown,
        feature_vector=feature_vector,
        hybrid_recommendation=recommendation,
        matching_signals=candidate.matching_signals,
        conflict_signals=candidate.conflict_signals,
    )


def score_candidates_hybrid(
    candidates: List[CandidateMatchResult]
) -> List[HybridScoredCandidate]:
    """
    Scores a batch of candidate pairs and ranks them descending by hybrid score.
    """
    scored = [score_candidate_hybrid(c) for c in candidates]
    scored.sort(key=lambda x: x.hybrid_score, reverse=True)
    return scored
