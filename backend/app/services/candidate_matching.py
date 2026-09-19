"""
Candidate Duplicate Detection Service using RapidFuzz and Domain Rules.
Performs candidate generation, fuzzy string matching, attribute-aware comparison,
blocking filters, and human-in-the-loop explanation generation.
"""

import math
import re
from typing import Dict, Any, List, Tuple, Optional, Set
from rapidfuzz import fuzz

from app.schemas.material import SourceMaterialResponse
from app.schemas.matching import (
    CandidateClassification,
    MatchingSignal,
    ConflictSignal,
    CandidateScoreBreakdown,
    CandidateMatchResult,
    CandidateMatchResponse,
)

# Mutually exclusive specific domains that must NOT be compared
INCOMPATIBLE_DOMAINS: Set[frozenset] = {
    frozenset(["BEARINGS", "ELECTRICAL_CABLES"]),
    frozenset(["BEARINGS", "PIPES_AND_TUBES"]),
    frozenset(["BEARINGS", "VALVES"]),
    frozenset(["BEARINGS", "FASTENERS"]),
    frozenset(["BEARINGS", "MOTORS"]),
    frozenset(["VALVES", "ELECTRICAL_CABLES"]),
    frozenset(["VALVES", "MOTORS"]),
    frozenset(["VALVES", "FASTENERS"]),
    frozenset(["PIPES_AND_TUBES", "ELECTRICAL_CABLES"]),
    frozenset(["PIPES_AND_TUBES", "MOTORS"]),
    frozenset(["PIPES_AND_TUBES", "FASTENERS"]),
    frozenset(["ELECTRICAL_CABLES", "FASTENERS"]),
    frozenset(["MOTORS", "FASTENERS"]),
    frozenset(["MOTORS", "GASKETS_AND_SEALS"]),
    frozenset(["FASTENERS", "GASKETS_AND_SEALS"]),
}

# Generic or parent category synonyms that can map to specific domains
CATEGORY_FAMILY_MAP: Dict[str, Set[str]] = {
    "MECHANICAL_SPARES": {"BEARINGS", "VALVES", "PIPES_AND_TUBES", "FASTENERS", "PUMPS", "GASKETS_AND_SEALS"},
    "ELECTRICAL_ROTATING_SPARES": {"BEARINGS", "MOTORS", "ELECTRICAL_SPARES"},
    "ELECTRICAL_SPARES": {"ELECTRICAL_CABLES", "MOTORS", "ELECTRICAL_ROTATING_SPARES"},
    "ELECTRICAL": {"ELECTRICAL_CABLES", "MOTORS", "ELECTRICAL_SPARES"},
    "CABLES_AND_CONDUCTORS": {"ELECTRICAL_CABLES"},
    "STANDARD_HARDWARE": {"FASTENERS"},
    "PIPING_AND_VALVES": {"VALVES", "PIPES_AND_TUBES", "GASKETS_AND_SEALS"},
    "PIPING": {"PIPES_AND_TUBES", "VALVES", "GASKETS_AND_SEALS"},
    "GASKETS_AND_SEALS": {"PIPING_AND_VALVES", "PIPING", "MECHANICAL_SPARES"},
}


def _clean_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip().upper()


def _is_category_incompatible(cat_a: str, cat_b: str) -> bool:
    """Checks if two distinct categories are mutually exclusive."""
    c_a = _clean_str(cat_a)
    c_b = _clean_str(cat_b)

    if not c_a or not c_b or c_a == "UNASSIGNED" or c_b == "UNASSIGNED":
        return False
    if c_a == c_b:
        return False

    # Check parent/child compatibility
    if c_a in CATEGORY_FAMILY_MAP and c_b in CATEGORY_FAMILY_MAP[c_a]:
        return False
    if c_b in CATEGORY_FAMILY_MAP and c_a in CATEGORY_FAMILY_MAP[c_b]:
        return False

    pair = frozenset([c_a, c_b])
    return pair in INCOMPATIBLE_DOMAINS


def calculate_category_compatibility(material_a: Any, material_b: Any) -> Tuple[float, Optional[str]]:
    """
    Computes category compatibility score [0.0 - 1.0].
    Returns (score, reason_note).
    """
    cat_a = _clean_str(getattr(material_a, "category", ""))
    cat_b = _clean_str(getattr(material_b, "category", ""))

    if not cat_a or not cat_b or cat_a == "UNASSIGNED" or cat_b == "UNASSIGNED":
        return 0.85, "One or both categories unassigned - cross-comparison allowed"

    if cat_a == cat_b:
        return 1.0, f"Exact category match: {cat_a}"

    if _is_category_incompatible(cat_a, cat_b):
        return 0.0, f"Incompatible taxonomy domains: {cat_a} vs {cat_b}"

    # Check broad category compatibility
    if (cat_a in CATEGORY_FAMILY_MAP and cat_b in CATEGORY_FAMILY_MAP[cat_a]) or \
       (cat_b in CATEGORY_FAMILY_MAP and cat_a in CATEGORY_FAMILY_MAP[cat_b]):
        return 0.90, f"Compatible category hierarchy: {cat_a} ~ {cat_b}"

    return 0.50, f"Different categories ({cat_a} vs {cat_b}), non-exclusive"


def calculate_uom_compatibility(uom_a: Optional[str], uom_b: Optional[str]) -> Tuple[float, Optional[str]]:
    """
    Computes UOM compatibility [0.0 - 1.0].
    Normalized UOMs: EA, M, KG, L, SET, ROLL, SQM, etc.
    """
    u_a = _clean_str(uom_a)
    u_b = _clean_str(uom_b)

    if not u_a or not u_b:
        return 0.70, "UOM missing on one side - neutral rating"

    if u_a == u_b:
        return 1.0, f"Identical normalized UOM: {u_a}"

    # Compatible count units
    count_units = {"EA", "NOS", "NO", "SET", "PIECE", "PC"}
    if u_a in count_units and u_b in count_units:
        return 0.95, f"Compatible count units: {u_a} ~ {u_b}"

    # Hardware weight vs count cross-reference (common in PSUs like CIL vs SAIL for bolts)
    if {u_a, u_b} == {"EA", "KG"} or {u_a, u_b} == {"NOS", "KGS"}:
        return 0.75, f"Cross-domain bulk UOM variance: {u_a} vs {u_b} (count vs bulk weight)"

    length_units = {"M", "MTR", "MM", "KM"}
    if u_a in length_units and u_b in length_units:
        return 0.90, f"Compatible length units: {u_a} ~ {u_b}"

    return 0.20, f"Conflicting UOM classes: {u_a} vs {u_b}"


def calculate_text_similarity(material_a: Any, material_b: Any) -> Tuple[float, Dict[str, float]]:
    """
    Computes text similarity using RapidFuzz token_sort_ratio and token_set_ratio.
    Weighted combination emphasizing token set overlap for reordered strings.
    """
    std_a = (getattr(material_a, "standard_description", "") or getattr(material_a, "raw_description", "")).strip()
    std_b = (getattr(material_b, "standard_description", "") or getattr(material_b, "raw_description", "")).strip()

    raw_a = (getattr(material_a, "raw_description", "") or "").strip()
    raw_b = (getattr(material_b, "raw_description", "") or "").strip()

    if not std_a or not std_b:
        return 0.0, {"token_sort_ratio": 0.0, "token_set_ratio": 0.0}

    # Calculate ratios on standardized descriptions
    sort_ratio = fuzz.token_sort_ratio(std_a, std_b) / 100.0
    set_ratio = fuzz.token_set_ratio(std_a, std_b) / 100.0

    # Also compute on raw descriptions
    raw_sort = fuzz.token_sort_ratio(raw_a, raw_b) / 100.0 if raw_a and raw_b else 0.0
    raw_set = fuzz.token_set_ratio(raw_a, raw_b) / 100.0 if raw_a and raw_b else 0.0

    score_std = 0.55 * sort_ratio + 0.45 * set_ratio
    score_raw = 0.55 * raw_sort + 0.45 * raw_set

    best_score = max(score_std, score_raw)
    details = {
        "token_sort_ratio": round(sort_ratio * 100, 1),
        "token_set_ratio": round(set_ratio * 100, 1),
        "raw_token_set_ratio": round(raw_set * 100, 1),
    }
    return round(best_score, 4), details


def calculate_token_similarity(tokens_a: List[str], tokens_b: List[str]) -> Tuple[float, List[str]]:
    """
    Calculates Jaccard overlap of normalized tokens.
    Returns (overlap_score, shared_tokens_list).
    """
    if not tokens_a or not tokens_b:
        return 0.0, []

    set_a = {t.lower() for t in tokens_a if t and len(t) > 1}
    set_b = {t.lower() for t in tokens_b if t and len(t) > 1}

    intersection = set_a & set_b
    union = set_a | set_b

    if not union:
        return 0.0, []

    score = len(intersection) / len(union)
    return round(score, 4), sorted(list(intersection))


def _are_pressures_compatible(val_a: Any, val_b: Any) -> bool:
    """Normalizes and tests pressure classes (e.g., CLASS 300 == CL300 == 300#)."""
    s_a = re.sub(r"[^A-Z0-9]", "", _clean_str(val_a))
    s_b = re.sub(r"[^A-Z0-9]", "", _clean_str(val_b))

    if s_a == s_b:
        return True

    # 300# == CLASS300 == CL300
    for num in ["150", "300", "600", "800", "900", "1500", "2500"]:
        if num in s_a and num in s_b:
            return True

    # PN16 == PN 16
    for pn in ["PN6", "PN10", "PN16", "PN25", "PN40", "PN64", "PN100"]:
        if pn in s_a and pn in s_b:
            return True

    return False


def _are_voltages_compatible(val_a: Any, val_b: Any) -> bool:
    """Tests voltage equivalence (e.g., 1.1KV == 1100V)."""
    s_a = _clean_str(val_a).replace(" ", "")
    s_b = _clean_str(val_b).replace(" ", "")

    if s_a == s_b:
        return True

    if ("1.1KV" in s_a or "1100V" in s_a) and ("1.1KV" in s_b or "1100V" in s_b):
        return True

    if ("3.3KV" in s_a or "3300V" in s_a) and ("3.3KV" in s_b or "3300V" in s_b):
        return True

    if ("6.6KV" in s_a or "6600V" in s_a) and ("6.6KV" in s_b or "6600V" in s_b):
        return True

    if ("11KV" in s_a or "11000V" in s_a) and ("11KV" in s_b or "11000V" in s_b):
        return True

    return False


def _are_diameters_compatible(val_a: Any, val_b: Any) -> bool:
    """Tests diameter equivalence including inch-to-mm conversions (4 INCH == 100 MM)."""
    try:
        f_a = float(val_a)
        f_b = float(val_b)
        # Check within 2% or 4mm tolerance (accounts for 4 inch = 101.6mm ~ 100mm NB)
        return abs(f_a - f_b) <= max(4.0, 0.04 * max(f_a, f_b))
    except (ValueError, TypeError):
        pass

    s_a = _clean_str(val_a)
    s_b = _clean_str(val_b)

    # 4 INCH == 100MM
    if ("4 INCH" in s_a or "4\"" in s_a or "100MM" in s_a or "DN100" in s_a or "100 NB" in s_a) and \
       ("4 INCH" in s_b or "4\"" in s_b or "100MM" in s_b or "DN100" in s_b or "100 NB" in s_b):
        return True

    # 2 INCH == 50MM
    if ("2 INCH" in s_a or "2\"" in s_a or "50MM" in s_a or "DN50" in s_a or "50 NB" in s_a) and \
       ("2 INCH" in s_b or "2\"" in s_b or "50MM" in s_b or "DN50" in s_b or "50 NB" in s_b):
        return True

    # 3 INCH == 80MM
    if ("3 INCH" in s_a or "3\"" in s_a or "80MM" in s_a or "DN80" in s_a or "80 NB" in s_a) and \
       ("3 INCH" in s_b or "3\"" in s_b or "80MM" in s_b or "DN80" in s_b or "80 NB" in s_b):
        return True

    return s_a == s_b


def calculate_attribute_similarity(
    attrs_a: Dict[str, Any],
    attrs_b: Dict[str, Any]
) -> Tuple[float, List[MatchingSignal], List[ConflictSignal]]:
    """
    Compares extracted attribute dictionaries.
    Identifies positive matches and flags critical conflict signals.
    """
    matching_signals: List[MatchingSignal] = []
    conflict_signals: List[ConflictSignal] = []

    if not attrs_a or not attrs_b:
        return 0.50, matching_signals, conflict_signals

    match_points = 0.0
    total_comparable = 0.0

    # 1. Critical Attribute Check: Bearing Number
    if "bearing_number" in attrs_a and "bearing_number" in attrs_b:
        total_comparable += 3.0
        val_a = _clean_str(attrs_a["bearing_number"])
        val_b = _clean_str(attrs_b["bearing_number"])
        if val_a == val_b:
            match_points += 3.0
            matching_signals.append(MatchingSignal(
                signal_type="ATTRIBUTE_MATCH",
                description=f"Exact bearing series number match: {val_a}",
                score=1.0,
                weight=0.25
            ))
        else:
            conflict_signals.append(ConflictSignal(
                attribute="bearing_number",
                value_a=val_a,
                value_b=val_b,
                severity="CRITICAL",
                description=f"Bearing series mismatch ({val_a} vs {val_b})"
            ))

    # 2. Critical Attribute Check: Schedule (Pipes)
    if "schedule" in attrs_a and "schedule" in attrs_b:
        total_comparable += 2.0
        s_a = _clean_str(attrs_a["schedule"])
        s_b = _clean_str(attrs_b["schedule"])
        if s_a == s_b:
            match_points += 2.0
            matching_signals.append(MatchingSignal(
                signal_type="ATTRIBUTE_MATCH",
                description=f"Identical pipe schedule: {s_a}",
                score=1.0,
                weight=0.20
            ))
        else:
            conflict_signals.append(ConflictSignal(
                attribute="schedule",
                value_a=s_a,
                value_b=s_b,
                severity="CRITICAL",
                description=f"Pipe schedule mismatch ({s_a} vs {s_b})"
            ))

    # 3. Critical Attribute Check: Diameter / Nominal Bore
    dia_a = attrs_a.get("diameter_mm") or attrs_a.get("nominal_bore") or attrs_a.get("nominal_diameter")
    dia_b = attrs_b.get("diameter_mm") or attrs_b.get("nominal_bore") or attrs_b.get("nominal_diameter")
    if dia_a is not None and dia_b is not None:
        total_comparable += 2.5
        if _are_diameters_compatible(dia_a, dia_b):
            match_points += 2.5
            matching_signals.append(MatchingSignal(
                signal_type="ATTRIBUTE_MATCH",
                description=f"Nominal diameter equivalence: {dia_a} ~ {dia_b}",
                score=1.0,
                weight=0.20
            ))
        else:
            conflict_signals.append(ConflictSignal(
                attribute="nominal_diameter",
                value_a=dia_a,
                value_b=dia_b,
                severity="CRITICAL",
                description=f"Diameter / nominal bore divergence ({dia_a} vs {dia_b})"
            ))

    # 4. Critical Attribute Check: Pressure Rating
    if "pressure_rating" in attrs_a and "pressure_rating" in attrs_b:
        total_comparable += 2.0
        p_a = attrs_a["pressure_rating"]
        p_b = attrs_b["pressure_rating"]
        if _are_pressures_compatible(p_a, p_b):
            match_points += 2.0
            matching_signals.append(MatchingSignal(
                signal_type="ATTRIBUTE_MATCH",
                description=f"Pressure class compatibility: {p_a} ~ {p_b}",
                score=1.0,
                weight=0.20
            ))
        else:
            conflict_signals.append(ConflictSignal(
                attribute="pressure_rating",
                value_a=p_a,
                value_b=p_b,
                severity="CRITICAL",
                description=f"Incompatible pressure ratings ({p_a} vs {p_b})"
            ))

    # 5. Critical Attribute Check: Voltage Grade
    v_a = attrs_a.get("voltage") or attrs_a.get("voltage_grade")
    v_b = attrs_b.get("voltage") or attrs_b.get("voltage_grade")
    if v_a is not None and v_b is not None:
        total_comparable += 2.0
        if _are_voltages_compatible(v_a, v_b):
            match_points += 2.0
            matching_signals.append(MatchingSignal(
                signal_type="ATTRIBUTE_MATCH",
                description=f"Voltage rating equivalence: {v_a} ~ {v_b}",
                score=1.0,
                weight=0.20
            ))
        else:
            conflict_signals.append(ConflictSignal(
                attribute="voltage",
                value_a=v_a,
                value_b=v_b,
                severity="CRITICAL",
                description=f"Voltage mismatch ({v_a} vs {v_b})"
            ))

    # 6. Critical Attribute Check: Cable Cores
    if "number_of_cores" in attrs_a and "number_of_cores" in attrs_b:
        total_comparable += 2.0
        c_a = attrs_a["number_of_cores"]
        c_b = attrs_b["number_of_cores"]
        if c_a == c_b:
            match_points += 2.0
            matching_signals.append(MatchingSignal(
                signal_type="ATTRIBUTE_MATCH",
                description=f"Identical core count: {c_a} Core",
                score=1.0,
                weight=0.15
            ))
        else:
            conflict_signals.append(ConflictSignal(
                attribute="number_of_cores",
                value_a=c_a,
                value_b=c_b,
                severity="CRITICAL",
                description=f"Conductor core count divergence ({c_a} vs {c_b})"
            ))

    # 7. Critical Attribute Check: Cable Cross-Section Area
    if "cross_section_sqmm" in attrs_a and "cross_section_sqmm" in attrs_b:
        total_comparable += 2.0
        cs_a = float(attrs_a["cross_section_sqmm"])
        cs_b = float(attrs_b["cross_section_sqmm"])
        if abs(cs_a - cs_b) < 0.1:
            match_points += 2.0
            matching_signals.append(MatchingSignal(
                signal_type="ATTRIBUTE_MATCH",
                description=f"Conductor area match: {cs_a} SQMM",
                score=1.0,
                weight=0.20
            ))
        else:
            conflict_signals.append(ConflictSignal(
                attribute="cross_section_sqmm",
                value_a=cs_a,
                value_b=cs_b,
                severity="CRITICAL",
                description=f"Cable size mismatch ({cs_a} vs {cs_b} sqmm)"
            ))

    # 8. Material Metallurgy Parity (SS304, Copper, WCB, Grade 8.8, etc.)
    mat_a = attrs_a.get("material") or attrs_a.get("material_grade") or attrs_a.get("body_material") or attrs_a.get("conductor_material")
    mat_b = attrs_b.get("material") or attrs_b.get("material_grade") or attrs_b.get("body_material") or attrs_b.get("conductor_material")
    if mat_a and mat_b:
        total_comparable += 1.5
        m_a = _clean_str(mat_a).replace("GRADE", "GR").replace("CLASS", "CL").replace(" ", "")
        m_b = _clean_str(mat_b).replace("GRADE", "GR").replace("CLASS", "CL").replace(" ", "")
        if m_a == m_b or m_a in m_b or m_b in m_a or ("WCB" in m_a and "WCB" in m_b):
            match_points += 1.5
            matching_signals.append(MatchingSignal(
                signal_type="ATTRIBUTE_MATCH",
                description=f"Metallurgy / grade equivalence: {mat_a} ~ {mat_b}",
                score=1.0,
                weight=0.15
            ))
        else:
            conflict_signals.append(ConflictSignal(
                attribute="material_grade",
                value_a=mat_a,
                value_b=mat_b,
                severity="MODERATE",
                description=f"Material grade variance ({mat_a} vs {mat_b})"
            ))

    # 9. Fastener Metric Size (M12X50, etc.)
    size_a = attrs_a.get("size") or attrs_a.get("thread_size")
    size_b = attrs_b.get("size") or attrs_b.get("thread_size")
    if size_a and size_b:
        total_comparable += 2.0
        s_a = _clean_str(size_a).replace(" ", "")
        s_b = _clean_str(size_b).replace(" ", "")
        if s_a == s_b:
            match_points += 2.0
            matching_signals.append(MatchingSignal(
                signal_type="ATTRIBUTE_MATCH",
                description=f"Fastener size match: {size_a}",
                score=1.0,
                weight=0.20
            ))
        else:
            conflict_signals.append(ConflictSignal(
                attribute="size",
                value_a=size_a,
                value_b=size_b,
                severity="CRITICAL",
                description=f"Fastener size mismatch ({size_a} vs {size_b})"
            ))

    # 9. Seal Type / Enclosure Check
    if "seal_type" in attrs_a and "seal_type" in attrs_b:
        total_comparable += 1.0
        st_a = _clean_str(attrs_a["seal_type"])
        st_b = _clean_str(attrs_b["seal_type"])
        if st_a == st_b:
            match_points += 1.0
            matching_signals.append(MatchingSignal(
                signal_type="ATTRIBUTE_MATCH",
                description=f"Bearing seal match: {st_a}",
                score=1.0,
                weight=0.10
            ))
        else:
            conflict_signals.append(ConflictSignal(
                attribute="seal_type",
                value_a=st_a,
                value_b=st_b,
                severity="LOW",
                description=f"Seal variation ({st_a} vs {st_b})"
            ))

    # 10. Part Number Parity
    if "part_number" in attrs_a and "part_number" in attrs_b:
        total_comparable += 2.0
        pn_a = _clean_str(attrs_a["part_number"])
        pn_b = _clean_str(attrs_b["part_number"])
        if pn_a == pn_b:
            match_points += 2.0
            matching_signals.append(MatchingSignal(
                signal_type="ATTRIBUTE_MATCH",
                description=f"Exact OEM part number match: {pn_a}",
                score=1.0,
                weight=0.20
            ))
        else:
            conflict_signals.append(ConflictSignal(
                attribute="part_number",
                value_a=pn_a,
                value_b=pn_b,
                severity="CRITICAL",
                description=f"OEM part number conflict ({pn_a} vs {pn_b})"
            ))

    if total_comparable == 0:
        return 0.50, matching_signals, conflict_signals

    score = match_points / total_comparable
    return round(score, 4), matching_signals, conflict_signals


def calculate_mfg_part_compatibility(material_a: Any, material_b: Any) -> Tuple[float, Optional[str]]:
    """
    Evaluates manufacturer and part number alignment [0.0 - 1.0].
    """
    mfg_a = _clean_str(getattr(material_a, "manufacturer", None))
    mfg_b = _clean_str(getattr(material_b, "manufacturer", None))

    pn_a = _clean_str(getattr(material_a, "part_number", None))
    pn_b = _clean_str(getattr(material_b, "part_number", None))

    # Exact part number match takes highest precedence
    if pn_a and pn_b and pn_a == pn_b:
        return 1.0, f"Identical part number: {pn_a}"

    if mfg_a and mfg_b:
        if mfg_a == mfg_b:
            return 1.0, f"Same OEM manufacturer: {mfg_a}"
        else:
            return 0.10, f"Different manufacturers: {mfg_a} vs {mfg_b}"

    if (mfg_a and not mfg_b) or (mfg_b and not mfg_a):
        return 0.50, "One side specifies OEM manufacturer"

    return 0.70, "No OEM manufacturer restrictions specified"


def calculate_candidate_score(
    material_a: SourceMaterialResponse,
    material_b: SourceMaterialResponse
) -> Tuple[float, CandidateScoreBreakdown, List[MatchingSignal], List[ConflictSignal], str]:
    """
    Computes composite similarity score and generates structured explanation:
    - 30% description similarity (RapidFuzz)
    - 25% attribute similarity
    - 15% normalized token overlap
    - 15% category compatibility
    - 10% UOM compatibility
    - 5% manufacturer/part number compatibility
    """
    # 1. Blocking: Incompatible Categories
    cat_score, cat_note = calculate_category_compatibility(material_a, material_b)
    if cat_score == 0.0:
        breakdown = CandidateScoreBreakdown(
            description_similarity=0.0,
            attribute_similarity=0.0,
            token_overlap=0.0,
            category_compatibility=0.0,
            uom_compatibility=0.0,
            mfg_part_compatibility=0.0,
            final_score=0.0,
        )
        conflicts = [ConflictSignal(
            attribute="category",
            value_a=getattr(material_a, "category", ""),
            value_b=getattr(material_b, "category", ""),
            severity="CRITICAL",
            description=cat_note or "Mutually exclusive categories"
        )]
        return 0.0, breakdown, [], conflicts, f"Blocked by category exclusion: {cat_note}"

    # 2. Text Similarity (30%)
    desc_score, text_details = calculate_text_similarity(material_a, material_b)

    # 3. Attribute Similarity (25%)
    attrs_a = getattr(material_a, "attributes", {}) or {}
    attrs_b = getattr(material_b, "attributes", {}) or {}
    attr_score, matching_signals, conflict_signals = calculate_attribute_similarity(attrs_a, attrs_b)

    # 4. Token Overlap (15%)
    tokens_a = getattr(material_a, "normalized_tokens", []) or []
    tokens_b = getattr(material_b, "normalized_tokens", []) or []
    token_score, shared_tokens = calculate_token_similarity(tokens_a, tokens_b)

    # 5. UOM Compatibility (10%)
    uom_a = getattr(material_a, "uom", None)
    uom_b = getattr(material_b, "uom", None)
    uom_score, uom_note = calculate_uom_compatibility(uom_a, uom_b)

    # 6. Manufacturer / Part Number Compatibility (5%)
    mfg_score, mfg_note = calculate_mfg_part_compatibility(material_a, material_b)

    # Positive Matching Signals
    if desc_score >= 0.70:
        matching_signals.append(MatchingSignal(
            signal_type="DESCRIPTION_SIMILARITY",
            description=f"High textual similarity ({int(desc_score * 100)}% token ratio)",
            score=desc_score,
            weight=0.30
        ))
    if token_score >= 0.40 and shared_tokens:
        matching_signals.append(MatchingSignal(
            signal_type="TOKEN_OVERLAP",
            description=f"Shared normalized engineering terms: {', '.join(shared_tokens[:5])}",
            score=token_score,
            weight=0.15
        ))
    if cat_score >= 0.90:
        matching_signals.append(MatchingSignal(
            signal_type="CATEGORY_COMPATIBLE",
            description=cat_note or "Taxonomy domains align",
            score=cat_score,
            weight=0.15
        ))
    if uom_score >= 0.90:
        matching_signals.append(MatchingSignal(
            signal_type="UOM_COMPATIBLE",
            description=uom_note or "Units of measure are equivalent",
            score=uom_score,
            weight=0.10
        ))
    if mfg_score >= 0.90 and mfg_note:
        matching_signals.append(MatchingSignal(
            signal_type="MANUFACTURER_MATCH",
            description=mfg_note,
            score=mfg_score,
            weight=0.05
        ))

    # Weighted composite sum
    raw_final = (
        (0.30 * desc_score) +
        (0.25 * attr_score) +
        (0.15 * token_score) +
        (0.15 * cat_score) +
        (0.10 * uom_score) +
        (0.05 * mfg_score)
    )

    # Check for Critical Attribute Conflicts
    critical_conflicts = [c for c in conflict_signals if c.severity == "CRITICAL"]
    if critical_conflicts:
        # Severe penalty: cap score below review threshold or drastically reduce
        final_score = min(0.45, raw_final * 0.40)
        reasons = "; ".join(c.description for c in critical_conflicts[:2])
        recommendation = f"Rejected by blocking: {reasons}"
    elif raw_final >= 0.90:
        final_score = raw_final
        recommendation = "Likely duplicate: descriptions, category, UOM, and engineering parameters match."
    elif raw_final >= 0.75:
        final_score = raw_final
        if conflict_signals:
            diffs = ", ".join(c.attribute for c in conflict_signals[:2])
            recommendation = f"Needs review: descriptions are highly similar, but check variance in: {diffs}."
        else:
            recommendation = "Possible duplicate: strong parameter alignment, verify slight catalog phrasing differences."
    elif raw_final >= 0.65:
        final_score = raw_final
        recommendation = "Low-confidence candidate: moderate text overlap, requires manual engineering inspection."
    else:
        final_score = raw_final
        recommendation = "Low similarity: distinct items or insufficient attribute evidence."

    final_score = round(min(1.0, max(0.0, final_score)), 4)

    breakdown = CandidateScoreBreakdown(
        description_similarity=round(desc_score, 4),
        attribute_similarity=round(attr_score, 4),
        token_overlap=round(token_score, 4),
        category_compatibility=round(cat_score, 4),
        uom_compatibility=round(uom_score, 4),
        mfg_part_compatibility=round(mfg_score, 4),
        final_score=final_score,
    )

    return final_score, breakdown, matching_signals, conflict_signals, recommendation


def classify_candidate(score: float) -> CandidateClassification:
    """Classifies match candidate into confidence tier based on score."""
    if score >= 0.90:
        return CandidateClassification.HIGH_CONFIDENCE_DUPLICATE
    elif score >= 0.75:
        return CandidateClassification.POSSIBLE_DUPLICATE
    elif score >= 0.65:
        return CandidateClassification.LOW_CONFIDENCE_REVIEW
    return CandidateClassification.NOT_INCLUDED


def generate_candidate_pairs(
    materials: List[SourceMaterialResponse]
) -> List[Tuple[SourceMaterialResponse, SourceMaterialResponse]]:
    """
    Generates candidate pairs from input materials applying initial blocking rules.
    Skips self-pairs and reverse duplicates (A-B vs B-A).
    """
    pairs: List[Tuple[SourceMaterialResponse, SourceMaterialResponse]] = []
    n = len(materials)

    for i in range(n):
        mat_a = materials[i]
        cat_a = getattr(mat_a, "category", "")
        for j in range(i + 1, n):
            mat_b = materials[j]
            cat_b = getattr(mat_b, "category", "")

            # Apply early category blocking
            if _is_category_incompatible(cat_a, cat_b):
                continue

            pairs.append((mat_a, mat_b))

    return pairs


def find_duplicate_candidates(
    materials: List[SourceMaterialResponse],
    min_score: float = 0.65,
    enrich_embeddings: bool = True,
) -> CandidateMatchResponse:
    """
    Master candidate duplicate detection pipeline.
    Takes a list of normalized source material records, evaluates candidate pairs,
    and returns sorted candidate matches meeting min_score.
    Optionally enriches candidate output with preview-only semantic embedding similarity scores.
    """
    total_records = len(materials)
    pairs = generate_candidate_pairs(materials)
    compared_pairs = len(pairs)

    candidates: List[CandidateMatchResult] = []

    for idx, (mat_a, mat_b) in enumerate(pairs, start=1):
        score, breakdown, matching_signals, conflict_signals, recommendation = calculate_candidate_score(
            mat_a, mat_b
        )

        classification = classify_candidate(score)

        if score >= min_score and classification != CandidateClassification.NOT_INCLUDED:
            pair_id = f"PAIR-{mat_a.source_material_code}-{mat_b.source_material_code}"
            candidate_item = CandidateMatchResult(
                pair_id=pair_id,
                source_material_a=mat_a,
                source_material_b=mat_b,
                score=score,
                classification=classification,
                score_breakdown=breakdown,
                matching_signals=matching_signals,
                conflict_signals=conflict_signals,
                recommendation=recommendation,
            )
            candidates.append(candidate_item)

    # Sort descending by primary RapidFuzz score
    candidates.sort(key=lambda c: c.score, reverse=True)

    # Optional enrichment with preview-only semantic embedding similarity scores
    if enrich_embeddings and candidates:
        from app.services.embedding_service import enrich_candidates_with_semantic_score
        candidates = enrich_candidates_with_semantic_score(candidates)

    return CandidateMatchResponse(
        total_records=total_records,
        compared_pairs=compared_pairs,
        candidate_count=len(candidates),
        candidates=candidates,
    )
