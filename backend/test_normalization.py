"""
Verification script for Data Cleaning and Normalization Engine.
Tests all specified test cases from Prompt 5.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.normalization import (
    normalize_whitespace,
    normalize_punctuation,
    normalize_description,
    normalize_uom,
    normalize_category,
    normalize_material_terms,
    normalize_dimension_terms,
    tokenize_description,
    build_standard_description,
)

def test_normalization():
    print("--- 1. Testing Abbreviation & Material Term Expansion ---")
    case1 = "SS PIPE 50 NB SCH 40 ASTM A312"
    norm1 = build_standard_description(case1)
    print(f"  Raw:  {case1}")
    print(f"  Norm: {norm1}")
    assert "STAINLESS STEEL" in norm1, f"Expected 'STAINLESS STEEL' in {norm1}"
    assert "NOMINAL BORE" in norm1, f"Expected 'NOMINAL BORE' in {norm1}"
    assert "SCHEDULE 40" in norm1, f"Expected 'SCHEDULE 40' in {norm1}"
    assert "ASTM A312" in norm1, f"Expected 'ASTM A312' in {norm1}"

    case2 = "S.S. PIPE 50NB SCH-40"
    norm2 = build_standard_description(case2)
    print(f"  Raw:  {case2}")
    print(f"  Norm: {norm2}")
    assert "STAINLESS STEEL" in norm2, f"Expected 'STAINLESS STEEL' in {norm2}"
    assert "50 NOMINAL BORE" in norm2, f"Expected '50 NOMINAL BORE' in {norm2}"
    assert "SCHEDULE 40" in norm2, f"Expected 'SCHEDULE 40' in {norm2}"

    print("\n--- 2. Testing Technical Identifiers Preservation ---")
    case3 = "BEARING 6205 ZZ"
    toks3 = tokenize_description(case3)
    print(f"  Raw:   {case3}")
    print(f"  Toks:  {toks3}")
    assert "bearing" in toks3
    assert "6205" in toks3
    assert "zz" in toks3

    case4 = "PVC CABLE 3 CORE 2.5 SQMM"
    toks4 = tokenize_description(case4)
    print(f"  Raw:   {case4}")
    print(f"  Toks:  {toks4}")
    assert "pvc" in toks4
    assert "cable" in toks4
    assert "2.5" in toks4
    assert "sqmm" in toks4

    case5 = "BALL VALVE 50MM SS304 PN16"
    norm5 = build_standard_description(case5)
    toks5 = tokenize_description(case5)
    print(f"  Raw:   {case5}")
    print(f"  Norm:  {norm5}")
    print(f"  Toks:  {toks5}")
    assert "SS304" in norm5, f"Expected 'SS304' to remain intact in {norm5}"
    assert "PN16" in norm5, f"Expected 'PN16' in {norm5}"
    assert "ss304" in toks5
    assert "pn16" in toks5

    print("\n--- 3. Testing Dimension & Metallurgy Terms ---")
    test_terms = "OD 60.3MM ID 52MM THK 4MM DIA 50MM M.S. PLATE G.I. PIPE C.I. BEND AL SHEET"
    norm_terms = build_standard_description(test_terms)
    print(f"  Raw:  {test_terms}")
    print(f"  Norm: {norm_terms}")
    assert "OUTER DIAMETER" in norm_terms
    assert "INNER DIAMETER" in norm_terms
    assert "THICKNESS" in norm_terms
    assert "DIAMETER" in norm_terms
    assert "MILD STEEL" in norm_terms
    assert "GALVANIZED IRON" in norm_terms
    assert "CAST IRON" in norm_terms
    assert "ALUMINIUM" in norm_terms

    print("\n--- 4. Testing UOM Normalization ---")
    uom_tests = {
        "MTR": "M",
        "METER": "M",
        "METRE": "M",
        "NOS": "EA",
        "NUMBER": "EA",
        "EACH": "EA",
        "KGS": "KG",
        "KILOGRAM": "KG",
        "LTR": "L",
        "LITRE": "L",
        "MM": "MM",
        "CM": "CM",
        "INCH": "IN",
        "FT": "FT",
        "SET": "SET",
        "BOX": "BOX",
        "PKT": "PKT",
    }
    for raw_uom, expected_uom in uom_tests.items():
        res = normalize_uom(raw_uom)
        assert res == expected_uom, f"UOM '{raw_uom}' expected '{expected_uom}', got '{res}'"
        print(f"  {raw_uom:8} -> {res}")

    print("\n--- 5. Testing Category Normalization ---")
    cat_tests = {
        "pipe": "PIPES_AND_TUBES",
        "tube": "PIPES_AND_TUBES",
        "piping": "PIPES_AND_TUBES",
        "bearing": "BEARINGS",
        "ball bearing": "BEARINGS",
        "roller bearing": "BEARINGS",
        "valve": "VALVES",
        "ball valve": "VALVES",
        "gate valve": "VALVES",
        "cable": "ELECTRICAL_CABLES",
        "wire": "ELECTRICAL_CABLES",
        "conductor": "ELECTRICAL_CABLES",
        "motor": "MOTORS",
        "electric motor": "MOTORS",
        "pump": "PUMPS",
        "fastener": "FASTENERS",
        "bolt": "FASTENERS",
    }
    for raw_cat, expected_cat in cat_tests.items():
        res = normalize_category(raw_cat)
        assert res == expected_cat, f"Category '{raw_cat}' expected '{expected_cat}', got '{res}'"
        print(f"  {raw_cat:18} -> {res}")

    print("\nALL NORMALIZATION UNIT TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_normalization()
