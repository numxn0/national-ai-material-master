"""
Approval Workflow Service for Dual-Tier Governance and National Material Code Proposals.
Manages deterministic national material master code generation, approval level assignment,
procurement impact metrics, mapping previews, and multi-tier L1/L2 review simulations.
Strictly non-persisted demonstration logic adhering to Prompt 11 requirements.
"""

import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from app.schemas.material import SourceMaterialResponse
from app.schemas.matching import CandidateMatchResult
from app.schemas.hybrid_scoring import (
    HybridClassification,
    HybridScoredCandidate,
)
from app.schemas.approval_workflow import (
    ApprovalStage,
    ApprovalWorkflowStatus,
    ApprovalDecision,
    ProcurementImpact,
    MappingPreview,
    ApprovalCase,
    ApprovalQueueResponse,
    ApprovalActionRequest,
    ApprovalActionResponse,
)
from app.services.candidate_matching import find_duplicate_candidates
from app.services.ingestion_preview import parse_csv_content
from app.services.hybrid_scoring import score_candidates_hybrid
from app.services.explainability import generate_reviewer_summary


def _clean_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip().upper()


def generate_national_material_code(
    category: str,
    standard_description: str,
    attributes: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generates a deterministic canonical National Material Master (NAMM) code.
    Follows standardized domain templates:
    - Bearings: NAMM-BRG-{SERIES}-{SEALS} (e.g., NAMM-BRG-6205-2RS)
    - Pipes: NAMM-PIP-{MATERIAL}-{NOMINAL_BORE}-{SCHEDULE} (e.g., NAMM-PIP-SS-050-S40)
    - Valves: NAMM-VLV-{TYPE}-{SIZE}-{RATING} (e.g., NAMM-VLV-BALL-050-PN16)
    - Cables: NAMM-CBL-{CONDUCTOR}-{CORES}C-{SIZE} (e.g., NAMM-CBL-AL-3C-185SQ)
    - Motors: NAMM-MTR-{POWER}KW-{RPM}RPM (e.g., NAMM-MTR-15KW-1440RPM)
    - Fallback: NAMM-DRAFT-{CATEGORY}-{HASH}
    """
    cat = _clean_str(category)
    desc = _clean_str(standard_description)
    attrs = attributes or {}

    # 1. BEARINGS
    if "BEAR" in cat:
        bearing_num = attrs.get("bearing_number") or ""
        if not bearing_num:
            m = re.search(r"\b([0-9]{4,5})\b", desc)
            if m:
                bearing_num = m.group(1)
            else:
                bearing_num = "STD"

        # Check seals / shielding
        seal = ""
        seal_attr = attrs.get("seal_type") or ""
        if seal_attr:
            seal = seal_attr.upper().replace("-", "")
        elif "2RS" in desc or "RS" in desc:
            seal = "2RS"
        elif "2Z" in desc or "ZZ" in desc:
            seal = "ZZ"

        if seal:
            return f"NAMM-BRG-{bearing_num}-{seal}"
        return f"NAMM-BRG-{bearing_num}"

    # 2. PIPES AND TUBES
    if "PIPE" in cat or "TUBE" in cat:
        # Material
        mat = "CS"
        mat_attr = _clean_str(attrs.get("material_grade"))
        if "SS" in mat_attr or "304" in mat_attr or "316" in mat_attr or "STAINLESS" in desc:
            mat = "SS"
        elif "CS" in mat_attr or "A106" in mat_attr or "CARBON" in desc:
            mat = "CS"

        # Size / NB
        size_code = "050"
        nb = attrs.get("nominal_bore") or attrs.get("diameter_mm") or attrs.get("nominal_diameter")
        if nb:
            try:
                num = int(float(re.sub(r"[^\d.]", "", str(nb))))
                size_code = f"{num:03d}"
            except (ValueError, TypeError):
                size_code = "050"
        elif "50" in desc or "2 INCH" in desc or "2\"" in desc:
            size_code = "050"
        elif "100" in desc or "4 INCH" in desc or "4\"" in desc:
            size_code = "100"

        # Schedule
        sch_code = "S40"
        sch = attrs.get("schedule") or ""
        if sch:
            sch_clean = re.sub(r"[^\d]", "", str(sch))
            if sch_clean:
                sch_code = f"S{sch_clean}"
        elif "SCH 80" in desc or "SCH80" in desc:
            sch_code = "S80"
        elif "SCH 40" in desc or "SCH40" in desc:
            sch_code = "S40"

        return f"NAMM-PIP-{mat}-{size_code}-{sch_code}"

    # 3. VALVES
    if "VALVE" in cat:
        # Type
        v_type = "BALL"
        for candidate_type in ["BALL", "GATE", "GLOBE", "CHECK", "BUTTERFLY"]:
            if candidate_type in desc:
                v_type = candidate_type
                break

        # Size
        size_code = "050"
        size_attr = attrs.get("nominal_size") or attrs.get("nominal_bore") or attrs.get("size")
        if size_attr:
            try:
                num = int(float(re.sub(r"[^\d.]", "", str(size_attr))))
                size_code = f"{num:03d}"
            except (ValueError, TypeError):
                size_code = "050"
        elif "100" in desc or "DN100" in desc or "4 INCH" in desc:
            size_code = "100"
        elif "50" in desc or "DN50" in desc or "2 INCH" in desc:
            size_code = "050"

        # Rating
        rating_code = "PN16"
        rating_attr = attrs.get("pressure_rating") or attrs.get("class_rating")
        if rating_attr:
            rating_clean = re.sub(r"\s+", "", str(rating_attr).upper())
            rating_code = rating_clean
        elif "CL150" in desc or "CLASS 150" in desc or "150#" in desc:
            rating_code = "CL150"
        elif "CL300" in desc or "CLASS 300" in desc or "300#" in desc:
            rating_code = "CL300"
        elif "PN16" in desc:
            rating_code = "PN16"
        elif "PN40" in desc:
            rating_code = "PN40"

        return f"NAMM-VLV-{v_type}-{size_code}-{rating_code}"

    # 4. ELECTRICAL CABLES
    if "CABLE" in cat or "ELECTRICAL" in cat:
        cond = "AL"
        if "COPPER" in desc or " CU " in desc or "CU" == _clean_str(attrs.get("conductor_material")):
            cond = "CU"
        elif "ALUMINIUM" in desc or " AL " in desc or "AL" == _clean_str(attrs.get("conductor_material")):
            cond = "AL"

        cores = "3C"
        core_attr = attrs.get("core_count")
        if core_attr:
            cores = f"{core_attr}C"
        elif "3.5C" in desc or "3.5 CORE" in desc:
            cores = "3.5C"
        elif "4 CORE" in desc or "4C" in desc:
            cores = "4C"
        elif "3 CORE" in desc or "3C" in desc:
            cores = "3C"

        size_sq = "185SQ"
        csa = attrs.get("cross_section_sqmm")
        if csa:
            size_sq = f"{csa}SQ"
        else:
            m = re.search(r"(\d+(?:\.\d+)?)\s*(?:SQMM|SQ\s*MM)", desc)
            if m:
                val = m.group(1).replace(".", "P")
                size_sq = f"{val}SQ"

        return f"NAMM-CBL-{cond}-{cores}-{size_sq}"

    # 5. MOTORS
    if "MOTOR" in cat:
        power = "15KW"
        p_attr = attrs.get("power_kw") or attrs.get("rating_kw")
        if p_attr:
            power = f"{p_attr}KW"
        else:
            m = re.search(r"(\d+(?:\.\d+)?)\s*KW", desc)
            if m:
                power = f"{m.group(1)}KW"

        rpm = "1440RPM"
        rpm_attr = attrs.get("rpm") or attrs.get("speed_rpm")
        if rpm_attr:
            rpm = f"{rpm_attr}RPM"
        else:
            m = re.search(r"(\d{3,4})\s*RPM", desc)
            if m:
                rpm = f"{m.group(1)}RPM"

        return f"NAMM-MTR-{power}-{rpm}"

    # 6. Fallback Deterministic Slug
    cat_slug = re.sub(r"[^A-Z0-9]", "", cat)[:4] or "GEN"
    h = hashlib.md5(desc.encode("utf-8")).hexdigest()[:6].upper()
    return f"NAMM-DRAFT-{cat_slug}-{h}"


def assign_approval_level(hybrid_classification: str, confidence_score: float) -> str:
    """
    Assigns the required governance approval tier based on AI confidence.
    Rules:
    - AUTO_MATCH_RECOMMENDED (score >= 0.88): "L1_ONLY" (Expedited Technical Nodal Officer)
    - STRONG_REVIEW_CANDIDATE (0.75 - 0.88): "L1_AND_L2" (Dual-Tier Nodal + Ministry Authority)
    - MANUAL_REVIEW_REQUIRED (0.60 - 0.75): "L1_AND_L2" (Dual-Tier with detailed inspection)
    - WEAK_MATCH_REVIEW_OPTIONAL (0.45 - 0.60): "L2_SPECIALIST" (Domain Specialist / Plant SME)
    - REJECTED_BY_SCORING (< 0.45): "REJECTED_ONLY" (Auto-marked distinct)
    """
    cls = _clean_str(hybrid_classification)
    if "AUTO_MATCH" in cls:
        return "L1_ONLY"
    elif "STRONG_REVIEW" in cls:
        return "L1_AND_L2"
    elif "MANUAL_REVIEW" in cls:
        return "L1_AND_L2"
    elif "WEAK_MATCH" in cls:
        return "L2_SPECIALIST"
    elif "REJECT" in cls:
        return "REJECTED_ONLY"
    else:
        if confidence_score >= 0.88:
            return "L1_ONLY"
        elif confidence_score >= 0.60:
            return "L1_AND_L2"
        elif confidence_score >= 0.45:
            return "L2_SPECIALIST"
        return "REJECTED_ONLY"


def estimate_procurement_impact(
    category: str,
    hybrid_score: float,
    cpses: List[str]
) -> ProcurementImpact:
    """
    Calculates estimated fiscal and operational savings from standardizing duplicate items.
    Demonstration estimation based on benchmark category expenditure models.
    """
    cat = _clean_str(category)
    unique_cpses = sorted(list(set(c for c in cpses if c)))

    # Annual spend benchmark by domain category (INR)
    if "BEAR" in cat:
        base_spend = 2400000.0  # ₹24 Lakhs
    elif "VALVE" in cat:
        base_spend = 4800000.0  # ₹48 Lakhs
    elif "PIPE" in cat or "TUBE" in cat:
        base_spend = 3200000.0  # ₹32 Lakhs
    elif "CABLE" in cat or "ELECTRICAL" in cat:
        base_spend = 6500000.0  # ₹65 Lakhs
    elif "MOTOR" in cat:
        base_spend = 5500000.0  # ₹55 Lakhs
    elif "FASTENER" in cat:
        base_spend = 1200000.0  # ₹12 Lakhs
    else:
        base_spend = 2000000.0  # ₹20 Lakhs

    # Savings percentage scales with confidence
    if hybrid_score >= 0.85:
        savings_pct = 0.14  # 14%
        risk_level = "LOW"
    elif hybrid_score >= 0.65:
        savings_pct = 0.12  # 12%
        risk_level = "MEDIUM"
    else:
        savings_pct = 0.09  # 9%
        risk_level = "HIGH"

    estimated_savings = round(base_spend * savings_pct, 2)

    return ProcurementImpact(
        duplicate_count=max(len(unique_cpses), 2),
        estimated_annual_spend_overlap=base_spend,
        standardization_savings_percent=round(savings_pct * 100, 1),
        estimated_savings_inr=estimated_savings,
        affected_cpses=unique_cpses,
        procurement_risk_level=risk_level,
        is_demo_estimate=True,
    )


def generate_mapping_preview(
    source_a: SourceMaterialResponse,
    source_b: SourceMaterialResponse,
    proposed_code: str,
    proposed_description: str,
    hybrid_score: float = 0.85
) -> MappingPreview:
    """
    Constructs the canonical-to-source mapping schema preview.
    """
    cpses = [source_a.source_cpse, source_b.source_cpse]
    unique_cpses = list(dict.fromkeys(c for c in cpses if c))
    codes = [source_a.source_material_code, source_b.source_material_code]
    unique_codes = list(dict.fromkeys(codes))

    mapping_type = "UNIFIED_CANONICAL" if hybrid_score >= 0.85 else "CATALOG_ALIAS"

    return MappingPreview(
        source_material_codes=unique_codes,
        source_cpses=unique_cpses,
        target_national_code=proposed_code,
        target_description=proposed_description,
        mapping_type=mapping_type,
    )


def create_approval_case(candidate: HybridScoredCandidate) -> ApprovalCase:
    """
    Transforms a hybrid scored candidate duplicate pair into a governance ApprovalCase.
    """
    mat_a = candidate.source_material_a
    mat_b = candidate.source_material_b
    cat = mat_a.category or mat_b.category or "GENERAL"

    # Merge extracted technical attributes
    merged_attrs = dict(mat_b.attributes or {})
    merged_attrs.update(mat_a.attributes or {})

    proposed_code = generate_national_material_code(
        category=cat,
        standard_description=mat_a.standard_description,
        attributes=merged_attrs
    )
    proposed_desc = mat_a.standard_description

    req_level = assign_approval_level(
        candidate.hybrid_classification.value if hasattr(candidate.hybrid_classification, "value") else str(candidate.hybrid_classification),
        candidate.hybrid_score
    )

    # Initial stage assignment
    if candidate.hybrid_classification == HybridClassification.REJECTED_BY_SCORING:
        initial_stage = ApprovalStage.REJECTED
        initial_status = ApprovalWorkflowStatus.REJECTED_DISTINCT
    else:
        initial_stage = ApprovalStage.PENDING_L1
        initial_status = ApprovalWorkflowStatus.PENDING

    # Explanation summary
    explanation_summary = generate_reviewer_summary(candidate)

    # Procurement impact and mapping preview
    cpses = [mat_a.source_cpse, mat_b.source_cpse]
    impact = estimate_procurement_impact(cat, candidate.hybrid_score, cpses)
    mapping_preview = generate_mapping_preview(
        mat_a, mat_b, proposed_code, proposed_desc, candidate.hybrid_score
    )

    clean_pair_id = candidate.pair_id.replace("PAIR-", "")
    case_id = f"CASE-{clean_pair_id}"

    return ApprovalCase(
        approval_case_id=case_id,
        candidate_pair_id=candidate.pair_id,
        source_material_a=mat_a,
        source_material_b=mat_b,
        proposed_national_material_code=proposed_code,
        proposed_standard_description=proposed_desc,
        hybrid_score=candidate.hybrid_score,
        hybrid_classification=candidate.hybrid_classification,
        explanation_summary=explanation_summary,
        required_approval_level=req_level,
        current_stage=initial_stage,
        approval_status=initial_status,
        l1_reviewer=None,
        l1_decision=None,
        l1_reviewed_at=None,
        l1_notes=None,
        l2_reviewer=None,
        l2_decision=None,
        l2_reviewed_at=None,
        l2_notes=None,
        procurement_impact=impact,
        mapping_preview=mapping_preview,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def simulate_l1_review(
    case: ApprovalCase,
    decision: str,
    reviewer: str = "Nodal Officer Sharma",
    notes: Optional[str] = None
) -> ApprovalCase:
    """
    Simulates Level-1 (Technical Nodal Officer) verification in memory.
    Updates stage to PENDING_L2 (or COMPLETED if L1_ONLY), or REJECTED / NEEDS_INFO.
    """
    dec = _clean_str(decision)
    now_iso = datetime.now(timezone.utc).isoformat()

    updated = case.model_copy(deep=True)
    updated.l1_reviewer = reviewer
    updated.l1_decision = dec
    updated.l1_reviewed_at = now_iso
    updated.l1_notes = notes or f"Technical parameter verification completed by {reviewer}."

    if dec == "APPROVE":
        if updated.required_approval_level == "L1_ONLY":
            updated.current_stage = ApprovalStage.COMPLETED
            updated.approval_status = ApprovalWorkflowStatus.APPROVED_AS_UNIFIED_SKU
        else:
            updated.current_stage = ApprovalStage.PENDING_L2
            updated.approval_status = ApprovalWorkflowStatus.PENDING
    elif dec == "REJECT":
        updated.current_stage = ApprovalStage.REJECTED
        updated.approval_status = ApprovalWorkflowStatus.REJECTED_DISTINCT
    elif "INFO" in dec or dec == "NEEDS_MORE_INFO":
        updated.current_stage = ApprovalStage.NEEDS_INFO
        updated.approval_status = ApprovalWorkflowStatus.NEEDS_MORE_INFO

    return updated


def simulate_l2_review(
    case: ApprovalCase,
    decision: str,
    reviewer: str = "Director General Verma",
    notes: Optional[str] = None
) -> ApprovalCase:
    """
    Simulates Level-2 (Ministry Oversight Authority) ratification in memory.
    Concludes workflow as COMPLETED (APPROVED_AS_UNIFIED_SKU) or REJECTED / NEEDS_INFO.
    """
    dec = _clean_str(decision)
    now_iso = datetime.now(timezone.utc).isoformat()

    updated = case.model_copy(deep=True)
    updated.l2_reviewer = reviewer
    updated.l2_decision = dec
    updated.l2_reviewed_at = now_iso
    updated.l2_notes = notes or f"Inter-CPSE procurement harmonization ratified by {reviewer}."

    if dec == "APPROVE":
        updated.current_stage = ApprovalStage.COMPLETED
        updated.approval_status = ApprovalWorkflowStatus.APPROVED_AS_UNIFIED_SKU
    elif dec == "REJECT":
        updated.current_stage = ApprovalStage.REJECTED
        updated.approval_status = ApprovalWorkflowStatus.REJECTED_DISTINCT
    elif "INFO" in dec or dec == "NEEDS_MORE_INFO":
        updated.current_stage = ApprovalStage.NEEDS_INFO
        updated.approval_status = ApprovalWorkflowStatus.NEEDS_MORE_INFO

    return updated


def build_demo_approval_queue(min_candidate_score: float = 0.45) -> ApprovalQueueResponse:
    """
    Generates a rich, realistic demonstration approval queue by running sample materials
    through candidate generation, hybrid scoring, and case structuring.
    Includes cases in PENDING_L1, PENDING_L2, and COMPLETED stages for full UI demonstration.
    """
    sample_file = None
    for p in [
        Path("sample-data/sample_materials_raw.csv"),
        Path("../sample-data/sample_materials_raw.csv"),
        Path("../../sample-data/sample_materials_raw.csv"),
    ]:
        if p.exists():
            sample_file = p
            break

    cases: List[ApprovalCase] = []
    if sample_file:
        try:
            with open(sample_file, "r", encoding="utf-8") as f:
                content = f.read()

            preview_res = parse_csv_content(csv_text_or_bytes=content, file_name="sample_materials_raw.csv")
            cand_resp = find_duplicate_candidates(
                preview_res.valid_records,
                min_score=min_candidate_score,
                enrich_embeddings=True
            )
            scored = score_candidates_hybrid(cand_resp.candidates)

            # Build approval cases
            for idx, candidate in enumerate(scored):
                c = create_approval_case(candidate)

                # For demonstration depth, simulate diverse review states:
                # Case 1 (e.g. top bearing pair): simulate L1 approved -> now PENDING_L2
                if idx == 1 and c.required_approval_level == "L1_AND_L2":
                    c = simulate_l1_review(
                        c,
                        decision="APPROVE",
                        reviewer="Technical Nodal Officer Sharma (BHEL)",
                        notes="Dimensional tolerance and bearing clearance C3 verified against OEM technical catalogue."
                    )
                # Case 2 (e.g. auto match): simulate L1 approved -> COMPLETED
                elif idx == 0 and c.required_approval_level == "L1_ONLY":
                    # Leave in PENDING_L1 so reviewer can test interactive action directly
                    pass

                cases.append(c)
        except Exception:
            pass

    pending_l1 = sum(1 for c in cases if c.current_stage == ApprovalStage.PENDING_L1)
    pending_l2 = sum(1 for c in cases if c.current_stage == ApprovalStage.PENDING_L2)
    completed = sum(1 for c in cases if c.current_stage in [ApprovalStage.COMPLETED, ApprovalStage.REJECTED])

    return ApprovalQueueResponse(
        total_cases=len(cases),
        pending_l1_count=pending_l1,
        pending_l2_count=pending_l2,
        completed_count=completed,
        cases=cases,
        version="approval-workflow-v1.0",
        note="Demo-only approval queue: data generated dynamically from sample pipeline without database persistence."
    )
