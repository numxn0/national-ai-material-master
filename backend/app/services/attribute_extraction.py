"""
Rule-Based Attribute Extraction Engine.
Extracts structured technical specifications from normalized CPSE/PSU material descriptions
for high-precision semantic and parametric matching.
"""

import re
from typing import Dict, Any, List, Optional, Tuple

from app.services.normalization import (
    build_standard_description,
    normalize_category,
    normalize_uom,
)

# Common bearing dimensions lookup table (bore x OD x width in mm)
BEARING_DIMENSIONS_TABLE: Dict[str, Dict[str, float]] = {
    "6203": {"bore_diameter_mm": 17.0, "outer_diameter_mm": 40.0, "width_mm": 12.0},
    "6204": {"bore_diameter_mm": 20.0, "outer_diameter_mm": 47.0, "width_mm": 14.0},
    "6205": {"bore_diameter_mm": 25.0, "outer_diameter_mm": 52.0, "width_mm": 15.0},
    "6206": {"bore_diameter_mm": 30.0, "outer_diameter_mm": 62.0, "width_mm": 16.0},
    "6305": {"bore_diameter_mm": 25.0, "outer_diameter_mm": 62.0, "width_mm": 17.0},
    "6005": {"bore_diameter_mm": 25.0, "outer_diameter_mm": 47.0, "width_mm": 12.0},
    "6306": {"bore_diameter_mm": 30.0, "outer_diameter_mm": 72.0, "width_mm": 19.0},
    "6208": {"bore_diameter_mm": 40.0, "outer_diameter_mm": 80.0, "width_mm": 18.0},
}

# Critical attributes by category for completeness and confidence evaluation
CRITICAL_ATTRIBUTES_MAP: Dict[str, List[str]] = {
    "PIPES_AND_TUBES": ["material", "nominal_bore", "schedule"],
    "BEARINGS": ["bearing_number", "bearing_type"],
    "VALVES": ["valve_type", "nominal_diameter", "pressure_rating"],
    "ELECTRICAL_CABLES": ["conductor_material", "number_of_cores", "cross_section_sqmm"],
    "MOTORS": ["voltage", "power_rating"],
    "FASTENERS": ["material_grade", "size"],
}


def infer_material_category(text: str) -> str:
    """Infers canonical taxonomy category from material text keywords."""
    t = text.upper()
    if any(k in t for k in ["BEARING", "BALL BEARING", "ROLLER BEARING", "6205", "6305", "6204", "6206"]):
        return "BEARINGS"
    if any(k in t for k in ["VALVE", "BALL VALVE", "GATE VALVE", "GLOBE VALVE", "CHECK VALVE", "NRV"]):
        return "VALVES"
    if any(k in t for k in ["CABLE", "WIRE", "CONDUCTOR", "XLPE", "SQMM", "SQ.MM", "3 CORE", "4 CORE"]):
        return "ELECTRICAL_CABLES"
    if any(k in t for k in ["MOTOR", "INDUCTION MOTOR", "DC MOTOR", "1440 RPM", "1500 RPM"]):
        return "MOTORS"
    if any(k in t for k in ["PIPE", "TUBE", "PIPING", "SEAMLESS", "ERW"]):
        return "PIPES_AND_TUBES"
    if any(k in t for k in ["PUMP", "CENTRIFUGAL"]):
        return "PUMPS"
    if any(k in t for k in ["BOLT", "NUT", "WASHER", "FASTENER", "SCREW", "STUD"]):
        return "FASTENERS"

    return normalize_category(text)


def extract_common_attributes(text: str) -> Dict[str, Any]:
    """Extracts common cross-domain technical attributes (manufacturer, standards, grades)."""
    attrs: Dict[str, Any] = {}
    t = text.upper()

    # 1. Manufacturer detection
    mfg_patterns = [
        (r"\bSKF\b", "SKF"),
        (r"\bFAG\b", "FAG"),
        (r"\bTIMKEN\b", "TIMKEN"),
        (r"\bNTN\b", "NTN"),
        (r"\bNBC\b", "NBC"),
        (r"\b(L&T|LARSEN\s*&\s*TOUBRO|L&T\s*VALVES)\b", "L&T VALVES"),
        (r"\bPOLYCAB\b", "POLYCAB"),
        (r"\bHAVELLS\b", "HAVELLS"),
        (r"\bKEI\b", "KEI"),
        (r"\bFINOLEX\b", "FINOLEX"),
        (r"\b(CROMPTON|CROMPTON\s*GREAVES|CG\s*POWER)\b", "CROMPTON GREAVES"),
        (r"\bSIEMENS\b", "SIEMENS"),
        (r"\bABB\b", "ABB"),
        (r"\bBHEL\b", "BHEL"),
        (r"\b(JINDAL|JINDAL\s*SAW)\b", "JINDAL SAW"),
        (r"\bTATA(?:\s*STEEL)?\b", "TATA STEEL"),
    ]
    for pattern, mfg in mfg_patterns:
        if re.search(pattern, t):
            attrs["manufacturer"] = mfg
            break

    # 2. Material Grade detection
    grade_match = re.search(
        r"\b(SS\s*304[LH]?|SS\s*316[LH]?|SS304[LH]?|SS316[LH]?|AISI\s*304|AISI\s*316|"
        r"ASTM\s+A312(?:\s+TP304[LH]?)?|ASTM\s+A216\s+WCB|A216\s+WCB|A312|ASTM\s+A106|"
        r"GRADE\s+8\.8|GR\s+8\.8|CLASS\s+8\.8|IS\s+1367|100CR6|SAE\s*52100)\b",
        t
    )
    if grade_match:
        attrs["material_grade"] = grade_match.group(0).strip()

    # 3. Standard detection
    std_match = re.search(
        r"\b(ASTM\s+[A-Z0-9]+|IS\s+\d{3,5}(?:\s+PART\s+\d+)?|BS\s+\d{3,5}|"
        r"ISO\s+\d{2,5}|DIN\s+\d{3,5}|IEC\s+\d{3,5}|API\s+\d[A-Z]?)\b",
        t
    )
    if std_match:
        attrs["standard"] = std_match.group(0).strip()

    # 4. Pressure Rating
    pres_match = re.search(
        r"\b(PN\s*10|PN\s*16|PN\s*25|PN\s*40|PN\s*64|PN\s*100|"
        r"CLASS\s*150|CLASS\s*300|CLASS\s*600|CLASS\s*800|150#|300#|600#|800#)\b",
        t
    )
    if pres_match:
        attrs["pressure_rating"] = pres_match.group(0).replace(" ", "")

    # 5. Fastener Metric Size (e.g. M12X50, M12 X 50 MM)
    fastener_match = re.search(r"\b(M\d{1,2})\s*[X\*\-]\s*(\d{1,3})(?:\s*MM)?\b", t)
    if fastener_match:
        thread = fastener_match.group(1)
        length = float(fastener_match.group(2))
        attrs["size"] = f"{thread}X{int(length)}"
        attrs["thread_size"] = thread
        attrs["length_mm"] = length

    # 5. Voltage
    volt_match = re.search(r"\b(\d+(?:\.\d+)?\s*(?:KV|VOLT|VOLTS|V))\b", t)
    if volt_match and not re.search(r"\bV-BELT\b", t):
        attrs["voltage"] = volt_match.group(0).strip()

    # 6. Power Rating
    power_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(HP|KW)\b", t)
    if power_match:
        val, unit = power_match.groups()
        attrs["power_rating"] = f"{val} {unit}"
        if unit == "HP":
            attrs["power_hp"] = float(val)
            attrs["power_kw"] = round(float(val) * 0.7457, 3)
        elif unit == "KW":
            attrs["power_kw"] = float(val)
            attrs["power_hp"] = round(float(val) / 0.7457, 2)

    return attrs


def extract_pipe_attributes(text: str) -> Dict[str, Any]:
    """Extracts pipe-specific parameters from text."""
    attrs: Dict[str, Any] = {}
    t = text.upper()

    # Material classification
    if "STAINLESS STEEL" in t or re.search(r"\bSS\b", t):
        attrs["material"] = "STAINLESS_STEEL"
    elif "CARBON STEEL" in t or re.search(r"\bCS\b", t):
        attrs["material"] = "CARBON_STEEL"
    elif "MILD STEEL" in t or re.search(r"\bMS\b", t):
        attrs["material"] = "MILD_STEEL"
    elif "GALVANIZED" in t or re.search(r"\bGI\b", t):
        attrs["material"] = "GALVANIZED_IRON"

    # Nominal Bore
    nb_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:NB|NOMINAL\s*BORE)\b", t)
    if nb_match:
        attrs["nominal_bore"] = f"{nb_match.group(1)} NB"
        attrs["diameter_mm"] = float(nb_match.group(1))
    else:
        # Check inches e.g. 2 INCH, 2"
        inch_match = re.search(r'\b(\d+(?:\.\d+)?)\s*(?:INCH|IN|")\s*(?:PIPE)?\b', t)
        if inch_match:
            attrs["nominal_bore_inch"] = float(inch_match.group(1))

    # Diameter MM explicit
    mm_match = re.search(r"\b(\d+(?:\.\d+)?)\s*MM\b", t)
    if mm_match and "diameter_mm" not in attrs:
        attrs["diameter_mm"] = float(mm_match.group(1))

    # Schedule
    sch_match = re.search(r"\b(?:SCHEDULE|SCH)\s*[-/]?\s*(\d+[A-Z]?|STD|XS|XXS)\b", t)
    if sch_match:
        attrs["schedule"] = f"SCH {sch_match.group(1)}"

    # Pipe manufacturing type
    if "SEAMLESS" in t:
        attrs["pipe_type"] = "SEAMLESS"
    elif "WELDED" in t or "ERW" in t:
        attrs["pipe_type"] = "WELDED"

    # Length in meters
    len_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:MTR|METER|M)\b", t)
    if len_match:
        attrs["length_m"] = float(len_match.group(1))

    return attrs


def extract_bearing_attributes(text: str) -> Dict[str, Any]:
    """Extracts bearing-specific parameters and dimensions from lookup table."""
    attrs: Dict[str, Any] = {}
    t = text.upper()

    # Bearing Number (e.g. 6205, 6305, 6204)
    num_match = re.search(r"\b(6\d{3}|2\d{4}|3\d{4})\b", t)
    if num_match:
        b_num = num_match.group(1)
        attrs["bearing_number"] = b_num
        # Dimensions lookup
        if b_num in BEARING_DIMENSIONS_TABLE:
            dims = BEARING_DIMENSIONS_TABLE[b_num]
            attrs["bore_diameter_mm"] = dims["bore_diameter_mm"]
            attrs["outer_diameter_mm"] = dims["outer_diameter_mm"]
            attrs["width_mm"] = dims["width_mm"]

    # Bearing type
    if "DEEP GROOVE" in t or "BALL" in t or "DGBB" in t:
        attrs["bearing_type"] = "DEEP_GROOVE_BALL_BEARING"
    elif "ROLLER" in t:
        attrs["bearing_type"] = "ROLLER_BEARING"
    else:
        attrs["bearing_type"] = "BALL_BEARING"

    # Seal type
    if re.search(r"\b(ZZ|2Z)\b", t) or "METAL SHIELD" in t:
        attrs["seal_type"] = "ZZ_DOUBLE_METAL_SHIELD"
    elif re.search(r"\b(2RS|2RS1|2RSR)\b", t) or "RUBBER SEAL" in t:
        attrs["seal_type"] = "2RS_DOUBLE_RUBBER_SEAL"
    elif re.search(r"\b(RS|RS1)\b", t):
        attrs["seal_type"] = "RS_SINGLE_RUBBER_SEAL"
    elif re.search(r"\b(Z)\b", t):
        attrs["seal_type"] = "Z_SINGLE_METAL_SHIELD"
    elif "OPEN" in t:
        attrs["seal_type"] = "OPEN"

    # Internal clearance
    clear_match = re.search(r"\b(C2|C3|C4|C5)\b", t)
    if clear_match:
        attrs["clearance"] = clear_match.group(1)

    return attrs


def extract_valve_attributes(text: str) -> Dict[str, Any]:
    """Extracts valve-specific parameters from text."""
    attrs: Dict[str, Any] = {}
    t = text.upper()

    # Valve Type
    if "BALL VALVE" in t or "BALL" in t:
        attrs["valve_type"] = "BALL_VALVE"
    elif "GATE VALVE" in t or "GATE" in t:
        attrs["valve_type"] = "GATE_VALVE"
    elif "GLOBE VALVE" in t or "GLOBE" in t:
        attrs["valve_type"] = "GLOBE_VALVE"
    elif "CHECK VALVE" in t or "NRV" in t:
        attrs["valve_type"] = "CHECK_VALVE"
    elif "BUTTERFLY" in t:
        attrs["valve_type"] = "BUTTERFLY_VALVE"

    # Nominal Diameter
    dn_match = re.search(r"\b(?:DN\s*|DN)(\d+)\b", t)
    if dn_match:
        attrs["nominal_diameter"] = f"DN{dn_match.group(1)}"
        attrs["diameter_mm"] = float(dn_match.group(1))
    else:
        mm_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:MM|NB)\b", t)
        if mm_match:
            attrs["nominal_diameter"] = f"{mm_match.group(1)}MM"
            attrs["diameter_mm"] = float(mm_match.group(1))
        else:
            inch_match = re.search(r'\b(\d+(?:\.\d+)?)\s*(?:INCH|IN|")\b', t)
            if inch_match:
                inch_val = float(inch_match.group(1))
                attrs["nominal_diameter"] = f"{inch_match.group(1)} INCH"
                # Map standard inch nominal sizes to mm NB (e.g. 4" = 100mm, 2" = 50mm)
                inch_to_mm_map = {0.5: 15.0, 0.75: 20.0, 1.0: 25.0, 1.5: 40.0, 2.0: 50.0, 3.0: 80.0, 4.0: 100.0, 6.0: 150.0, 8.0: 200.0, 10.0: 250.0, 12.0: 300.0}
                attrs["diameter_mm"] = inch_to_mm_map.get(inch_val, round(inch_val * 25.4, 1))

    # Body Material
    if "SS304" in t or "SS 304" in t or "STAINLESS STEEL" in t:
        attrs["body_material"] = "SS304"
    elif "SS316" in t or "SS 316" in t:
        attrs["body_material"] = "SS316"
    elif "WCB" in t or "CAST STEEL" in t:
        attrs["body_material"] = "ASTM A216 WCB"
    elif "CAST IRON" in t or "CI" in t:
        attrs["body_material"] = "CAST_IRON"

    # End connection
    if "FLANGED" in t or "FLANGE" in t:
        attrs["end_connection"] = "FLANGED"
    elif "SCREWED" in t or "THREADED" in t:
        attrs["end_connection"] = "SCREWED"
    elif "SOCKET WELD" in t:
        attrs["end_connection"] = "SOCKET_WELD"

    return attrs


def extract_cable_attributes(text: str) -> Dict[str, Any]:
    """Extracts electrical cable specifications from text."""
    attrs: Dict[str, Any] = {}
    t = text.upper()

    # Number of cores
    core_match = re.search(r"\b(\d+(?:\.5)?)\s*(?:CORE|CORES)\b", t)
    if core_match:
        attrs["number_of_cores"] = float(core_match.group(1)) if "." in core_match.group(1) else int(core_match.group(1))
    else:
        c_short = re.search(r"\b(\d+)C\b", t)
        if c_short:
            attrs["number_of_cores"] = int(c_short.group(1))

    # Cross section in sqmm
    sqmm_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:SQMM|SQ\.MM|SQ\s*MM|MM2)\b", t)
    if sqmm_match:
        attrs["cross_section_sqmm"] = float(sqmm_match.group(1))

    # Conductor material
    if "COPPER" in t or re.search(r"\bCU\b", t):
        attrs["conductor_material"] = "COPPER"
    elif "ALUMINIUM" in t or "ALUMINUM" in t or re.search(r"\bAL\b", t):
        attrs["conductor_material"] = "ALUMINIUM"

    # Insulation type
    if "XLPE" in t:
        attrs["insulation_type"] = "XLPE"
    elif "PVC" in t:
        attrs["insulation_type"] = "PVC"

    # Voltage grade
    volt_match = re.search(r"\b(\d+(?:\.\d+)?\s*KV|1100\s*V|660\s*V)\b", t)
    if volt_match:
        attrs["voltage_grade"] = volt_match.group(0).replace(" ", "")

    # Cable type / armouring
    if "ARMOURED" in t or "ARMD" in t:
        attrs["cable_type"] = "ARMOURED"
    elif "UNARMOURED" in t:
        attrs["cable_type"] = "UNARMOURED"

    return attrs


def extract_motor_attributes(text: str) -> Dict[str, Any]:
    """Extracts electric motor specifications from text."""
    attrs: Dict[str, Any] = {}
    t = text.upper()

    # Motor type
    if "DC" in t or "DIRECT CURRENT" in t:
        attrs["motor_type"] = "DC_MOTOR"
        attrs["current_type"] = "DC"
    elif "INDUCTION" in t:
        attrs["motor_type"] = "INDUCTION_MOTOR"
        attrs["current_type"] = "AC"
    elif "AC" in t or "ALTERNATING CURRENT" in t:
        attrs["motor_type"] = "AC_MOTOR"
        attrs["current_type"] = "AC"
    else:
        attrs["motor_type"] = "ELECTRIC_MOTOR"

    # Speed RPM
    rpm_match = re.search(r"\b(\d{3,4})\s*RPM\b", t)
    if rpm_match:
        attrs["speed_rpm"] = int(rpm_match.group(1))

    # Frame Size
    frame_match = re.search(r"\b(?:FRAME|FRAME\s*SIZE)\s*([A-Z0-9-]+)\b", t)
    if frame_match:
        attrs["frame_size"] = frame_match.group(1)
    else:
        iec_match = re.search(r"\b(IEC\s*[0-9]+[A-Z]?)\b", t)
        if iec_match:
            attrs["frame_size"] = iec_match.group(1)

    return attrs


def calculate_extraction_confidence(
    attributes: Dict[str, Any],
    category: str
) -> Tuple[float, List[str], str]:
    """
    Calculates extraction completeness confidence score [0.0 - 1.0],
    identifies missing critical parameters, and gives a qualitative level.
    """
    critical_keys = CRITICAL_ATTRIBUTES_MAP.get(category, ["material_grade"])
    missing_critical = [k for k in critical_keys if k not in attributes]

    total_critical = len(critical_keys)
    found_critical = total_critical - len(missing_critical)

    # Base confidence calculation
    if total_critical > 0:
        base_score = found_critical / total_critical
    else:
        base_score = 0.5

    # Bonus for extra rich attributes (up to +0.20)
    extra_count = len(attributes) - found_critical
    bonus = min(0.20, extra_count * 0.05)
    final_score = min(1.0, round(base_score * 0.80 + bonus, 2))

    if final_score >= 0.75:
        level = "HIGH"
    elif final_score >= 0.50:
        level = "MEDIUM"
    else:
        level = "LOW"

    return final_score, missing_critical, level


def extract_attributes(
    raw_description: str,
    category: Optional[str] = None,
    uom: Optional[str] = None
) -> Tuple[Dict[str, Any], str, float, List[str], List[str]]:
    """
    Master attribute extraction entry point.
    Normalizes text, infers category, extracts domain-specific parameters,
    and returns (attributes_dict, category, confidence_score, missing_critical, notes).
    """
    if not raw_description or not raw_description.strip():
        return {}, "UNASSIGNED", 0.0, [], ["Empty description provided"]

    notes: List[str] = []
    std_desc = build_standard_description(raw_description)

    # Infer or normalize category
    inferred = infer_material_category(raw_description)
    if category and str(category).strip() and str(category).strip().upper() not in {"UNASSIGNED", "GENERAL", "SPARES"}:
        norm_cat = normalize_category(category)
        broad_umbrellas = {
            "MECHANICAL_SPARES",
            "ELECTRICAL_SPARES",
            "ELECTRICAL_ROTATING_SPARES",
            "STANDARD_HARDWARE",
            "PIPING_AND_VALVES",
            "PIPES_AND_TUBES",
            "GENERAL_SPARES",
        }
        if norm_cat in broad_umbrellas and inferred in {
            "BEARINGS",
            "VALVES",
            "PIPES_AND_TUBES",
            "ELECTRICAL_CABLES",
            "MOTORS",
            "FASTENERS",
        } and (norm_cat != "PIPES_AND_TUBES" or inferred == "VALVES"):
            active_category = inferred
            notes.append(f"Refined broad category '{norm_cat}' to domain '{inferred}'")
        else:
            active_category = norm_cat
    else:
        active_category = inferred
        notes.append(f"Inferred category: {active_category}")

    # Extract common attributes
    extracted = extract_common_attributes(std_desc)

    # Extract domain-specific attributes based on active category
    if active_category == "PIPES_AND_TUBES":
        pipe_attrs = extract_pipe_attributes(std_desc)
        extracted.update(pipe_attrs)
    elif active_category == "BEARINGS":
        bearing_attrs = extract_bearing_attributes(std_desc)
        extracted.update(bearing_attrs)
        if "bearing_number" in extracted and extracted["bearing_number"] in BEARING_DIMENSIONS_TABLE:
            notes.append(f"Enriched dimensions from bearing catalog for series {extracted['bearing_number']}")
    elif active_category == "VALVES":
        valve_attrs = extract_valve_attributes(std_desc)
        extracted.update(valve_attrs)
    elif active_category == "ELECTRICAL_CABLES":
        cable_attrs = extract_cable_attributes(std_desc)
        extracted.update(cable_attrs)
    elif active_category == "MOTORS":
        motor_attrs = extract_motor_attributes(std_desc)
        extracted.update(motor_attrs)

    # Set normalized UOM if available
    if uom:
        extracted["uom"] = normalize_uom(uom)

    # Confidence calculation
    conf_score, missing_critical, level = calculate_extraction_confidence(extracted, active_category)
    if missing_critical:
        notes.append(f"Missing critical parameters: {', '.join(missing_critical)}")

    return extracted, active_category, conf_score, missing_critical, notes
