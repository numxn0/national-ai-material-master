"""
Data Cleaning and Normalization Engine.
Provides reusable rule-based standardization for CPSE/PSU material descriptions,
technical abbreviations, dimensional specifications, UOMs, and categories.
"""

import re
from typing import Optional, List, Dict

# Standard English & catalog noise stopwords
STOPWORDS = {
    "for", "with", "and", "the", "in", "of", "to", "a", "an", "by", "is", "at",
    "on", "from", "as", "per", "type", "or", "item", "genuine", "original",
    "both", "sides", "side", "all", "each", "approx", "approximate"
}

# Unit of Measure normalization mapping
UOM_NORMALIZATION_MAP: Dict[str, str] = {
    # Length
    "MTR": "M",
    "METER": "M",
    "METERS": "M",
    "METRE": "M",
    "METRES": "M",
    "M": "M",
    "MM": "MM",
    "MILLIMETER": "MM",
    "MILLIMETRE": "MM",
    "MILLIMETERS": "MM",
    "MILLIMETRES": "MM",
    "CM": "CM",
    "CENTIMETER": "CM",
    "CENTIMETRE": "CM",
    "CENTIMETERS": "CM",
    "CENTIMETRES": "CM",
    "INCH": "IN",
    "INCHES": "IN",
    "IN": "IN",
    '"': "IN",
    "FEET": "FT",
    "FOOT": "FT",
    "FT": "FT",
    "'": "FT",
    # Count / Packaging
    "NOS": "EA",
    "NO": "EA",
    "NUMBER": "EA",
    "NUMBERS": "EA",
    "EACH": "EA",
    "EA": "EA",
    "PCS": "EA",
    "PC": "EA",
    "PIECE": "EA",
    "PIECES": "EA",
    "SET": "SET",
    "SETS": "SET",
    "BOX": "BOX",
    "BOXES": "BOX",
    "PKT": "PKT",
    "PACKET": "PKT",
    "PACKETS": "PKT",
    "PACK": "PKT",
    "PACKS": "PKT",
    "PAIR": "PAIR",
    "PAIRS": "PAIR",
    "ROLL": "ROLL",
    "ROLLS": "ROLL",
    # Weight
    "KG": "KG",
    "KGS": "KG",
    "KILOGRAM": "KG",
    "KILOGRAMS": "KG",
    "TON": "MT",
    "TONS": "MT",
    "TONNE": "MT",
    "TONNES": "MT",
    "MT": "MT",
    # Volume
    "LTR": "L",
    "LITRE": "L",
    "LITRES": "L",
    "LITER": "L",
    "LITERS": "L",
    "L": "L",
}

# Category classification mapping
CATEGORY_KEYWORD_MAP: List[tuple[List[str], str]] = [
    (["pipe", "tube", "piping", "tubing", "casing"], "PIPES_AND_TUBES"),
    (["bearing", "ball bearing", "roller bearing", "needle bearing", "pillow block"], "BEARINGS"),
    (["valve", "ball valve", "gate valve", "globe valve", "check valve", "butterfly valve"], "VALVES"),
    (["cable", "wire", "conductor", "cord", "cables"], "ELECTRICAL_CABLES"),
    (["motor", "electric motor", "induction motor", "dc motor", "stepper motor"], "MOTORS"),
    (["pump", "centrifugal pump", "submersible pump"], "PUMPS"),
    (["fastener", "bolt", "nut", "washer", "screw", "stud", "rivet"], "FASTENERS"),
    (["gasket", "seal", "o-ring", "packing", "jointing"], "GASKETS_AND_SEALS"),
    (["switch", "relay", "breaker", "contactor", "mcb", "mccb"], "SWITCHGEAR"),
]


def normalize_whitespace(text: str) -> str:
    """Trim leading/trailing whitespace and collapse internal spaces, tabs, and newlines."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def normalize_punctuation(text: str) -> str:
    """
    Standardize quotes and dashes; remove noisy punctuation while preserving
    critical technical symbols such as '/', '-', '.', and '&'.
    """
    if not text:
        return ""
    # Standardize unicode quotes to standard single/double quotes
    t = re.sub(r"[\u201c\u201d\"]", '"', text)
    t = re.sub(r"[\u2018\u2019']", "'", t)
    # Standardize unicode dashes to standard hyphen
    t = re.sub(r"[–—]", "-", t)
    # Normalize multiple periods (e.g. ".." -> ".")
    t = re.sub(r"\.{2,}", ".", t)
    # Remove unwanted punctuation noise like commas, semicolons, asterisks at word boundaries
    t = re.sub(r"[,;*~`!#$^*()\[\]{}]+", " ", t)
    return normalize_whitespace(t)


def normalize_material_terms(text: str) -> str:
    """
    Standardize common metallurgical and material abbreviations:
    - S.S., SS, ST STL -> STAINLESS STEEL (preserving technical identifiers like SS304/SS316)
    - M.S., MS -> MILD STEEL
    - G.I., GI -> GALVANIZED IRON
    - C.I., CI -> CAST IRON
    - AL, ALU -> ALUMINIUM
    """
    if not text:
        return ""
    t = text

    # Handle S.S., SS, ST STL -> STAINLESS STEEL (preserve SS304, SS316, etc.)
    t = re.sub(r"(?:\bS\.S\.?(?!\w)|\bST\s*STL\b|\bSS\b(?![0-9]))", "STAINLESS STEEL", t, flags=re.IGNORECASE)
    # Handle M.S., MS -> MILD STEEL
    t = re.sub(r"(?:\bM\.S\.?(?!\w)|\bMS\b)", "MILD STEEL", t, flags=re.IGNORECASE)
    # Handle G.I., GI -> GALVANIZED IRON
    t = re.sub(r"(?:\bG\.I\.?(?!\w)|\bGI\b)", "GALVANIZED IRON", t, flags=re.IGNORECASE)
    # Handle C.I., CI -> CAST IRON
    t = re.sub(r"(?:\bC\.I\.?(?!\w)|\bCI\b)", "CAST IRON", t, flags=re.IGNORECASE)
    # Handle AL, ALU -> ALUMINIUM
    t = re.sub(r"\b(AL|ALU)\b", "ALUMINIUM", t, flags=re.IGNORECASE)

    return normalize_whitespace(t)


def normalize_dimension_terms(text: str) -> str:
    """
    Standardize dimensional and technical abbreviations:
    - SCH, SCH- -> SCHEDULE
    - NB -> NOMINAL BORE (also handles 50NB -> 50 NOMINAL BORE)
    - OD -> OUTER DIAMETER
    - ID -> INNER DIAMETER
    - DIA -> DIAMETER
    - THK -> THICKNESS
    - NOS, NO., EACH -> EA
    - MTR, METER, METRE -> M
    """
    if not text:
        return ""
    t = text

    # Split attached numbers to unit/term (e.g. "50NB" -> "50 NOMINAL BORE", "SCH-40" -> "SCHEDULE 40")
    t = re.sub(r"(\d+)\s*NB\b", r"\1 NOMINAL BORE", t, flags=re.IGNORECASE)
    t = re.sub(r"\bSCH\s*[-/]?\s*(\d+)\b", r"SCHEDULE \1", t, flags=re.IGNORECASE)
    t = re.sub(r"\bSCH\b", "SCHEDULE", t, flags=re.IGNORECASE)

    # Standardize dimension acronyms
    t = re.sub(r"\bNB\b", "NOMINAL BORE", t, flags=re.IGNORECASE)
    t = re.sub(r"\bOD\b", "OUTER DIAMETER", t, flags=re.IGNORECASE)
    t = re.sub(r"\bID\b", "INNER DIAMETER", t, flags=re.IGNORECASE)
    t = re.sub(r"\bDIA\b", "DIAMETER", t, flags=re.IGNORECASE)
    t = re.sub(r"\bTHK\b", "THICKNESS", t, flags=re.IGNORECASE)

    # Standardize UOM words embedded in descriptions
    t = re.sub(r"(?:\bNO\.(?!\w)|\b(NOS|EACH)\b)", "EA", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(MTR|METER|METRE)\b", "M", t, flags=re.IGNORECASE)

    return normalize_whitespace(t)


def normalize_description(text: str) -> str:
    """
    Full description normalization pipeline:
    - whitespace normalization
    - punctuation standardization
    - material terms expansion
    - dimension terms expansion
    - uppercase output formatting
    """
    if not text:
        return ""
    t = normalize_punctuation(text)
    t = normalize_material_terms(t)
    t = normalize_dimension_terms(t)
    return normalize_whitespace(t).upper()


def build_standard_description(raw_description: str) -> str:
    """Builds canonical standard golden description from raw text."""
    return normalize_description(raw_description)


def normalize_uom(uom: Optional[str]) -> str:
    """
    Normalizes Units of Measure into canonical standard ISO/BIS representations:
    - MTR, METER, METRE -> M
    - NOS, NUMBER, EACH, EA, PCS -> EA
    - KG, KGS, KILOGRAM -> KG
    - LTR, LITRE, LITER -> L
    - MM, MILLIMETER, MILLIMETRE -> MM
    - CM, CENTIMETER, CENTIMETRE -> CM
    - INCH, IN, " -> IN
    - FEET, FT, ' -> FT
    - SET, SETS -> SET
    - BOX -> BOX
    - PKT, PACKET -> PKT
    """
    if not uom or not str(uom).strip():
        return "EA"
    clean = str(uom).strip().upper()
    if clean in UOM_NORMALIZATION_MAP:
        return UOM_NORMALIZATION_MAP[clean]

    # Strip symbols and test again
    alphanumeric = re.sub(r"[^A-Z]", "", clean)
    if alphanumeric in UOM_NORMALIZATION_MAP:
        return UOM_NORMALIZATION_MAP[alphanumeric]

    return clean if clean else "EA"


def normalize_category(category: Optional[str]) -> str:
    """
    Maps common raw categories into authoritative standardized taxonomy categories:
    - pipe, tube, piping -> PIPES_AND_TUBES
    - bearing, ball bearing, roller bearing -> BEARINGS
    - valve, ball valve, gate valve -> VALVES
    - cable, wire, conductor -> ELECTRICAL_CABLES
    - motor, electric motor -> MOTORS
    - pump -> PUMPS
    - fastener, bolt, nut, washer -> FASTENERS
    """
    if not category or not str(category).strip():
        return "UNASSIGNED"
    cat_lower = str(category).strip().lower()

    for keywords, standard_name in CATEGORY_KEYWORD_MAP:
        for kw in keywords:
            if kw in cat_lower:
                return standard_name

    # If no keyword matched, clean string to upper snake_case
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", str(category).strip()).strip("_").upper()
    return clean if clean else "UNASSIGNED"


def tokenize_description(text: str) -> List[str]:
    """
    Tokenizes normalized description:
    - removes stopwords
    - preserves technical identifiers (e.g., 6205, SS304, PN16, ASTM, A312, 2.5, SQMM, 24V, 0.5HP)
    - returns ordered list of unique lowercase tokens
    """
    if not text:
        return []

    clean_text = normalize_punctuation(text)
    # Split on whitespace and common delimiters
    raw_tokens = re.split(r"[\s,;/:|()\[\]{}]+", clean_text.lower())
    tokens: List[str] = []
    seen = set()

    for t in raw_tokens:
        # Strip leading and trailing punctuation (preserve internal dots or hyphens like 2.5, 0.5hp, 6205-2rs)
        token = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", t)
        if not token:
            continue
        if token in STOPWORDS:
            continue

        # Keep valid technical identifiers and domain words
        if token not in seen:
            tokens.append(token)
            seen.add(token)

    return tokens
