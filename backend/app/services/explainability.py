"""
Explainability Service for AI Duplicate Match Review.
Generates deterministic SHAP-style factor attributions, positive drivers,
risk analyses, conflict highlights, reviewer summaries, and audit records
from hybrid scoring outputs and 16-dimensional feature vectors.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.schemas.hybrid_scoring import (
    HybridScoredCandidate,
    HybridClassification,
    MatchFeatureVector,
    HybridScoreBreakdown,
)
from app.schemas.explainability import (
    ExplanationDirection,
    ExplanationFactor,
    AuditExplanation,
    ReviewerExplanation,
)


def generate_factor_contributions(candidate: HybridScoredCandidate) -> List[ExplanationFactor]:
    """
    Generates deterministic SHAP-style factor attributions for all scoring dimensions.
    Returns fine-grained contributions with direction, human explanation, and concrete evidence.
    """
    fv: MatchFeatureVector = candidate.feature_vector
    bkd: HybridScoreBreakdown = candidate.hybrid_score_breakdown
    mat_a = candidate.source_material_a
    mat_b = candidate.source_material_b

    factors: List[ExplanationFactor] = []

    # 1. Description Text Similarity (Weight: 25%)
    desc_val = round(bkd.description_contribution, 4)
    desc_pct = round(bkd.description_contribution * 100, 1)
    if fv.description_similarity >= 0.70:
        desc_dir = ExplanationDirection.POSITIVE
        desc_expl = f"Description similarity is high ({round(fv.description_similarity * 100, 1)}%), indicating strong lexical alignment."
    elif fv.description_similarity < 0.40:
        desc_dir = ExplanationDirection.NEGATIVE
        desc_expl = f"Description similarity is low ({round(fv.description_similarity * 100, 1)}%), indicating substantial naming divergence."
    else:
        desc_dir = ExplanationDirection.NEUTRAL
        desc_expl = f"Moderate description similarity ({round(fv.description_similarity * 100, 1)}%)."

    factors.append(
        ExplanationFactor(
            factor_name="description_similarity",
            display_label="Description Text Parity",
            contribution_value=desc_val,
            contribution_percentage=desc_pct,
            direction=desc_dir,
            explanation=desc_expl,
            evidence=[
                f"{mat_a.source_cpse}: {mat_a.standard_description}",
                f"{mat_b.source_cpse}: {mat_b.standard_description}",
            ]
        )
    )

    # 2. Attribute Similarity (Weight: 20%)
    attr_val = round(bkd.attribute_contribution, 4)
    attr_pct = round(bkd.attribute_contribution * 100, 1)
    if fv.critical_attribute_conflict_count > 0:
        attr_dir = ExplanationDirection.NEGATIVE
        attr_expl = f"Attribute comparison detected {fv.critical_attribute_conflict_count} critical specification mismatch(es)."
    elif fv.attribute_similarity >= 0.70:
        attr_dir = ExplanationDirection.POSITIVE
        attr_expl = f"Both records share {fv.exact_attribute_match_count} exact technical specifications with high attribute parity ({round(fv.attribute_similarity * 100, 1)}%)."
    elif fv.attribute_similarity < 0.40:
        attr_dir = ExplanationDirection.NEGATIVE
        attr_expl = f"Low attribute overlap ({round(fv.attribute_similarity * 100, 1)}%) with {fv.missing_critical_attribute_count} missing critical attributes."
    else:
        attr_dir = ExplanationDirection.NEUTRAL
        attr_expl = f"Partial attribute overlap ({round(fv.attribute_similarity * 100, 1)}%) across available fields."

    attr_evidence: List[str] = []
    for sig in candidate.matching_signals:
        if "Attribute" in sig.description or "attribute" in sig.signal_type.lower():
            attr_evidence.append(sig.description)
    if not attr_evidence and (mat_a.attributes or mat_b.attributes):
        shared_keys = set(mat_a.attributes.keys()) & set(mat_b.attributes.keys())
        for k in list(shared_keys)[:3]:
            attr_evidence.append(f"{k}: {mat_a.attributes.get(k)} vs {mat_b.attributes.get(k)}")
    if not attr_evidence:
        attr_evidence.append("No common structured attributes detected")

    factors.append(
        ExplanationFactor(
            factor_name="attribute_similarity",
            display_label="Technical Attribute Parity",
            contribution_value=attr_val,
            contribution_percentage=attr_pct,
            direction=attr_dir,
            explanation=attr_expl,
            evidence=attr_evidence
        )
    )

    # 3. Semantic Vector Similarity (Weight: 20%)
    sem_val = round(bkd.semantic_contribution, 4)
    sem_pct = round(bkd.semantic_contribution * 100, 1)
    if fv.semantic_similarity_score >= 0.65:
        sem_dir = ExplanationDirection.POSITIVE
        sem_expl = f"Dense vector cosine similarity is strong ({round(fv.semantic_similarity_score * 100, 1)}%), confirming domain conceptual equivalence."
    elif fv.semantic_similarity_score < 0.35:
        sem_dir = ExplanationDirection.NEGATIVE
        sem_expl = f"Low semantic embedding similarity ({round(fv.semantic_similarity_score * 100, 1)}%) indicates disparate material domains."
    else:
        sem_dir = ExplanationDirection.NEUTRAL
        sem_expl = f"Moderate semantic embedding similarity ({round(fv.semantic_similarity_score * 100, 1)}%)."

    factors.append(
        ExplanationFactor(
            factor_name="semantic_similarity",
            display_label="Semantic Vector Alignment",
            contribution_value=sem_val,
            contribution_percentage=sem_pct,
            direction=sem_dir,
            explanation=sem_expl,
            evidence=[
                f"Cosine Similarity: {round(fv.semantic_similarity_score, 4)}",
                f"Domain A: {mat_a.category} | Material: {mat_a.material_type or 'N/A'}",
                f"Domain B: {mat_b.category} | Material: {mat_b.material_type or 'N/A'}",
            ]
        )
    )

    # 4. Token Jaccard Overlap (Weight: 10%)
    tok_val = round(bkd.token_contribution, 4)
    tok_pct = round(bkd.token_contribution * 100, 1)
    if fv.token_similarity >= 0.55:
        tok_dir = ExplanationDirection.POSITIVE
        tok_expl = f"Substantial normalized token overlap ({round(fv.token_similarity * 100, 1)}%)."
    elif fv.token_similarity < 0.30:
        tok_dir = ExplanationDirection.NEGATIVE
        tok_expl = f"Sparse token overlap ({round(fv.token_similarity * 100, 1)}%)."
    else:
        tok_dir = ExplanationDirection.NEUTRAL
        tok_expl = f"Moderate token overlap ({round(fv.token_similarity * 100, 1)}%)."

    # Compute quick intersection tokens for evidence
    tokens_a = set(mat_a.normalized_tokens or [])
    tokens_b = set(mat_b.normalized_tokens or [])
    common_tokens = list(tokens_a & tokens_b)
    tok_evidence = [f"Common tokens: {', '.join(common_tokens[:6])}"] if common_tokens else ["No shared tokens"]

    factors.append(
        ExplanationFactor(
            factor_name="token_overlap",
            display_label="Token Overlap",
            contribution_value=tok_val,
            contribution_percentage=tok_pct,
            direction=tok_dir,
            explanation=tok_expl,
            evidence=tok_evidence
        )
    )

    # 5. Category Compatibility (Weight: 10%)
    cat_val = round(bkd.category_contribution, 4)
    cat_pct = round(bkd.category_contribution * 100, 1)
    if fv.category_compatibility >= 0.80:
        cat_dir = ExplanationDirection.POSITIVE
        cat_expl = f"Both items reside in the same material classification ({mat_a.category})."
    else:
        cat_dir = ExplanationDirection.NEGATIVE
        cat_expl = f"Category mismatch: '{mat_a.category}' vs '{mat_b.category}'."

    factors.append(
        ExplanationFactor(
            factor_name="category_compatibility",
            display_label="Taxonomy Classification Match",
            contribution_value=cat_val,
            contribution_percentage=cat_pct,
            direction=cat_dir,
            explanation=cat_expl,
            evidence=[
                f"{mat_a.source_cpse} Category: {mat_a.category}",
                f"{mat_b.source_cpse} Category: {mat_b.category}",
            ]
        )
    )

    # 6. Unit of Measure Compatibility (Weight: 5%)
    uom_val = round(bkd.uom_contribution, 4)
    uom_pct = round(bkd.uom_contribution * 100, 1)
    if fv.uom_compatibility >= 0.80:
        uom_dir = ExplanationDirection.POSITIVE
        uom_expl = f"Units of measure are directly compatible or standard ({mat_a.uom} and {mat_b.uom})."
    elif fv.uom_compatibility == 0.0:
        uom_dir = ExplanationDirection.NEGATIVE
        uom_expl = f"Incompatible units of measure ({mat_a.uom} vs {mat_b.uom})."
    else:
        uom_dir = ExplanationDirection.NEUTRAL
        uom_expl = f"UOM alignment requires conversion or review ({mat_a.uom} vs {mat_b.uom})."

    factors.append(
        ExplanationFactor(
            factor_name="uom_compatibility",
            display_label="Unit of Measure (UOM) Match",
            contribution_value=uom_val,
            contribution_percentage=uom_pct,
            direction=uom_dir,
            explanation=uom_expl,
            evidence=[
                f"{mat_a.source_cpse} UOM: {mat_a.uom}",
                f"{mat_b.source_cpse} UOM: {mat_b.uom}",
            ]
        )
    )

    # 7. Manufacturer & Part / Model Match (Weight: 5%)
    mfg_val = round(bkd.mfg_part_contribution, 4)
    mfg_pct = round(bkd.mfg_part_contribution * 100, 1)
    if fv.manufacturer_match >= 0.80 or fv.part_number_match >= 0.80:
        mfg_dir = ExplanationDirection.POSITIVE
        mfg_expl = "Manufacturer or OEM part number alignment verified."
    elif (mat_a.part_number and mat_b.part_number and fv.part_number_match == 0.0):
        mfg_dir = ExplanationDirection.NEGATIVE
        mfg_expl = f"Distinct OEM part numbers stated ({mat_a.part_number} vs {mat_b.part_number})."
    else:
        mfg_dir = ExplanationDirection.NEUTRAL
        mfg_expl = "Manufacturer and part numbers are generic or partially stated."

    factors.append(
        ExplanationFactor(
            factor_name="manufacturer_part_model",
            display_label="Manufacturer & Part Number Match",
            contribution_value=mfg_val,
            contribution_percentage=mfg_pct,
            direction=mfg_dir,
            explanation=mfg_expl,
            evidence=[
                f"Manufacturer: {mat_a.manufacturer or 'N/A'} vs {mat_b.manufacturer or 'N/A'}",
                f"Part Number: {mat_a.part_number or 'N/A'} vs {mat_b.part_number or 'N/A'}",
            ]
        )
    )

    # 8. Critical Completeness Bonus (Weight: 5%)
    bonus_val = round(bkd.completeness_bonus, 4)
    bonus_pct = round(bkd.completeness_bonus * 100, 1)
    if bkd.completeness_bonus > 0.0:
        bonus_dir = ExplanationDirection.POSITIVE
        bonus_expl = "Both records provide complete critical engineering parameters (completeness bonus awarded)."
    else:
        bonus_dir = ExplanationDirection.NEUTRAL
        bonus_expl = f"One or both records lack critical parameters ({fv.missing_critical_attribute_count} missing specifications)."

    factors.append(
        ExplanationFactor(
            factor_name="completeness_bonus",
            display_label="Specification Completeness Bonus",
            contribution_value=bonus_val,
            contribution_percentage=bonus_pct,
            direction=bonus_dir,
            explanation=bonus_expl,
            evidence=[
                f"Missing critical count: {fv.missing_critical_attribute_count}",
                f"Bonus added: +{bonus_pct}%",
            ]
        )
    )

    # 9. Conflict Penalties & Ceiling Cap (Deduction)
    if bkd.conflict_penalty_applied:
        penalty_deduction = round(bkd.raw_composite_score - bkd.final_hybrid_score, 4)
        penalty_pct = round(penalty_deduction * 100, 1)
        pen_evidence = [cs.description for cs in candidate.conflict_signals]
        if not pen_evidence and bkd.conflict_penalty_description:
            pen_evidence = [bkd.conflict_penalty_description]

        factors.append(
            ExplanationFactor(
                factor_name="conflict_penalty",
                display_label="Conflict Penalty & Ceiling Cap",
                contribution_value=-penalty_deduction,
                contribution_percentage=-penalty_pct,
                direction=ExplanationDirection.NEGATIVE,
                explanation=bkd.conflict_penalty_description or "Hard ceiling cap applied due to technical discrepancy.",
                evidence=pen_evidence
            )
        )
    else:
        factors.append(
            ExplanationFactor(
                factor_name="conflict_penalty",
                display_label="Conflict Penalty & Ceiling Cap",
                contribution_value=0.0,
                contribution_percentage=0.0,
                direction=ExplanationDirection.NEUTRAL,
                explanation="No critical technical conflicts detected; full composite score retained.",
                evidence=["Zero critical conflicts detected"]
            )
        )

    return factors


def generate_positive_explanations(candidate: HybridScoredCandidate) -> List[ExplanationFactor]:
    """
    Filters and returns factors that positively contribute toward the duplicate recommendation.
    """
    all_factors = generate_factor_contributions(candidate)
    return [
        f for f in all_factors
        if f.direction == ExplanationDirection.POSITIVE and f.contribution_value > 0.0
    ]


def generate_risk_explanations(candidate: HybridScoredCandidate) -> List[ExplanationFactor]:
    """
    Identifies and returns risk factors that reduce confidence or require scrutiny.
    """
    all_factors = generate_factor_contributions(candidate)
    return [
        f for f in all_factors
        if f.direction == ExplanationDirection.NEGATIVE
    ]


def generate_conflict_explanations(candidate: HybridScoredCandidate) -> List[str]:
    """
    Generates explicit technical conflict statements from detected conflict signals and hard caps.
    """
    conflicts: List[str] = []
    bkd = candidate.hybrid_score_breakdown

    for cs in candidate.conflict_signals:
        conflicts.append(f"[{cs.severity}] {cs.attribute}: {cs.description} (Value A: '{cs.value_a}' vs Value B: '{cs.value_b}')")

    if bkd.conflict_penalty_applied and bkd.conflict_penalty_description:
        if not any(bkd.conflict_penalty_description in c for c in conflicts):
            conflicts.append(f"Hard Cap Penalty: {bkd.conflict_penalty_description}")

    return conflicts


def generate_missing_data_explanations(candidate: HybridScoredCandidate) -> List[str]:
    """
    Identifies attributes present on one material record but missing on the other,
    or key category attributes that are entirely unstated.
    """
    warnings: List[str] = []
    mat_a = candidate.source_material_a
    mat_b = candidate.source_material_b
    attrs_a = mat_a.attributes or {}
    attrs_b = mat_b.attributes or {}

    # Check key attributes present in A but missing in B
    for k, v in attrs_a.items():
        if k not in attrs_b:
            warnings.append(f"Attribute '{k}' ({v}) is specified by {mat_a.source_cpse} but unstated by {mat_b.source_cpse}.")

    # Check key attributes present in B but missing in A
    for k, v in attrs_b.items():
        if k not in attrs_a:
            warnings.append(f"Attribute '{k}' ({v}) is specified by {mat_b.source_cpse} but unstated by {mat_a.source_cpse}.")

    # Check OEM Part number gaps
    if mat_a.part_number and not mat_b.part_number:
        warnings.append(f"OEM Part Number '{mat_a.part_number}' is present on {mat_a.source_cpse} record but missing on {mat_b.source_cpse}.")
    elif mat_b.part_number and not mat_a.part_number:
        warnings.append(f"OEM Part Number '{mat_b.part_number}' is present on {mat_b.source_cpse} record but missing on {mat_a.source_cpse}.")

    # Check Material Grade gaps
    if mat_a.material_type and not mat_b.material_type:
        warnings.append(f"Material metallurgy '{mat_a.material_type}' specified by {mat_a.source_cpse} but missing on {mat_b.source_cpse}.")
    elif mat_b.material_type and not mat_a.material_type:
        warnings.append(f"Material metallurgy '{mat_b.material_type}' specified by {mat_b.source_cpse} but missing on {mat_a.source_cpse}.")

    return warnings


def generate_reviewer_summary(candidate: HybridScoredCandidate) -> str:
    """
    Generates a concise, high-level reviewer summary explaining the verdict.
    """
    score = candidate.hybrid_score
    classification = candidate.hybrid_classification
    bkd = candidate.hybrid_score_breakdown
    fv = candidate.feature_vector
    mat_a = candidate.source_material_a
    mat_b = candidate.source_material_b

    # Case 1: Hard conflict penalty triggered (e.g. Bearing mismatch, Diameter mismatch)
    if bkd.conflict_penalty_applied:
        if fv.critical_attribute_conflict_count > 0:
            return f"Rejected or flagged by scoring because critical engineering specifications conflict ({bkd.conflict_penalty_description or 'spec divergence'})."
        if fv.category_compatibility < 0.5:
            return f"Rejected by scoring because material taxonomies are fundamentally incompatible ({mat_a.category} vs {mat_b.category})."
        return f"Score penalized by hard conflict cap: {bkd.conflict_penalty_description}."

    # Case 2: Auto Match Recommended
    if classification == HybridClassification.AUTO_MATCH_RECOMMENDED or score >= 0.92:
        return f"Recommended for auto-match because description, category, UOM, and critical technical specifications are tightly aligned ({round(score * 100, 1)}% composite confidence)."

    # Case 3: Strong Review Candidate
    if classification == HybridClassification.STRONG_REVIEW_CANDIDATE or (score >= 0.80 and score < 0.92):
        if fv.missing_critical_attribute_count > 0:
            return f"Strong review candidate: descriptions and core specifications align, but {fv.missing_critical_attribute_count} missing specification(s) require human verification."
        return f"Strong review candidate: high semantic and text parity ({round(score * 100, 1)}%), suitable for catalog alias consolidation upon officer sign-off."

    # Case 4: Manual Review Required
    if classification == HybridClassification.MANUAL_REVIEW_REQUIRED or (score >= 0.65 and score < 0.80):
        if fv.confidence_gap > 0.20:
            return f"Requires manual review because descriptions appear similar ({round(fv.description_similarity * 100, 1)}%), but structured technical attributes diverge or are unstated."
        return f"Requires manual review: moderate composite match ({round(score * 100, 1)}%) with incomplete cross-CPSE attribute overlap."

    # Case 5: Weak Match
    if classification == HybridClassification.WEAK_MATCH_REVIEW_OPTIONAL or (score >= 0.50 and score < 0.65):
        return f"Weak candidate: lexical or semantic similarity exists, but technical attributes are incomplete or inconclusive ({round(score * 100, 1)}%)."

    # Case 6: Rejected
    return f"Rejected by scoring: insufficient specification match or low cross-domain similarity ({round(score * 100, 1)}%)."


def generate_audit_explanation(candidate: HybridScoredCandidate) -> AuditExplanation:
    """
    Generates a concise audit-ready explanation record.
    """
    mat_a = candidate.source_material_a
    mat_b = candidate.source_material_b
    factors = generate_factor_contributions(candidate)

    # Extract top positive factors
    positives = [
        f"{f.display_label} (+{f.contribution_percentage}%)"
        for f in factors
        if f.direction == ExplanationDirection.POSITIVE and f.contribution_value > 0
    ][:3]

    # Extract top risk / penalty factors
    risks = [
        f"{f.display_label} ({f.contribution_percentage}%)"
        for f in factors
        if f.direction == ExplanationDirection.NEGATIVE
    ][:3]

    return AuditExplanation(
        candidate_pair_id=candidate.pair_id,
        material_a_summary=f"[{mat_a.source_cpse}] {mat_a.source_material_code} - {mat_a.standard_description}",
        material_b_summary=f"[{mat_b.source_cpse}] {mat_b.source_material_code} - {mat_b.standard_description}",
        hybrid_score=candidate.hybrid_score,
        classification=candidate.hybrid_classification.value if hasattr(candidate.hybrid_classification, "value") else str(candidate.hybrid_classification),
        top_positive_factors=positives if positives else ["No dominant positive factors"],
        top_negative_risk_factors=risks if risks else ["No active risk penalties"],
        recommendation=candidate.hybrid_recommendation,
        method_version="hybrid-rule-v1 + semantic-stub-v1 + explainability-v1",
        timestamp=datetime.now(timezone.utc).isoformat()
    )


def explain_scored_candidate(candidate: HybridScoredCandidate) -> ReviewerExplanation:
    """
    Builds a complete ReviewerExplanation for a single hybrid scored candidate duplicate pair.
    """
    all_factors = generate_factor_contributions(candidate)
    positive_factors = [f for f in all_factors if f.direction == ExplanationDirection.POSITIVE and f.contribution_value > 0.0]
    risk_factors = [f for f in all_factors if f.direction == ExplanationDirection.NEGATIVE]
    conflict_factors = generate_conflict_explanations(candidate)
    missing_data_warnings = generate_missing_data_explanations(candidate)
    reviewer_summary = generate_reviewer_summary(candidate)
    audit_explanation = generate_audit_explanation(candidate)

    return ReviewerExplanation(
        pair_id=candidate.pair_id,
        source_material_a_code=candidate.source_material_a.source_material_code,
        source_material_b_code=candidate.source_material_b.source_material_code,
        source_cpse_a=candidate.source_material_a.source_cpse,
        source_cpse_b=candidate.source_material_b.source_cpse,
        hybrid_score=candidate.hybrid_score,
        hybrid_classification=candidate.hybrid_classification,
        reviewer_summary=reviewer_summary,
        factors=all_factors,
        positive_factors=positive_factors,
        risk_factors=risk_factors,
        conflict_factors=conflict_factors,
        missing_data_warnings=missing_data_warnings,
        audit_explanation=audit_explanation,
        recommendation=candidate.hybrid_recommendation
    )


def explain_scored_candidates(candidates: List[HybridScoredCandidate]) -> List[ReviewerExplanation]:
    """
    Generates reviewer explanations for a list of scored candidates, maintaining rank order.
    """
    return [explain_scored_candidate(c) for c in candidates]
