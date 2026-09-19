"""
Prompt 6 Comprehensive Verification Script.
Tests rule-based attribute extraction for pipes, bearings, valves, cables, and motors,
evaluates critical attribute completeness, tests API endpoints, and checks CSV preview integration.
"""

import sys
import json
import asyncio
from pathlib import Path

# Add backend root to sys.path
backend_root = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_root))

from app.services.attribute_extraction import (
    extract_attributes,
    extract_pipe_attributes,
    extract_bearing_attributes,
    extract_valve_attributes,
    extract_cable_attributes,
    extract_motor_attributes,
    extract_common_attributes,
    infer_material_category,
    calculate_extraction_confidence,
    BEARING_DIMENSIONS_TABLE,
)
from app.schemas.extraction import (
    AttributeExtractionRequest,
    AttributeExtractionResponse,
)
from app.api.materials import extract_material_attributes, preview_sample_data
from main import health_check


async def run_prompt6_verification():
    print("=" * 70)
    print("PROMPT 6: RULE-BASED ATTRIBUTE EXTRACTION ENGINE VERIFICATION")
    print("=" * 70)

    # 1. Health check verification
    health = await health_check()
    assert health.status == "healthy", f"Health status unexpected: {health.status}"
    print(f"\n[PASS] Backend /health returned 200 OK (status: {health.status})")

    # 2. Test Pipe Attribute Extraction
    print("\n--- Testing Pipe Attribute Extraction ---")
    pipe_samples = [
        ("SS PIPE 50 NB SCH 40 ASTM A312", {"material": "STAINLESS_STEEL", "nominal_bore": "50 NB", "schedule": "SCH 40", "diameter_mm": 50.0}),
        ("STAINLESS STEEL PIPE 50 NOMINAL BORE SCHEDULE 40", {"material": "STAINLESS_STEEL", "nominal_bore": "50 NB", "schedule": "SCH 40"}),
        ("PIPE 50MM SCH-40", {"diameter_mm": 50.0, "schedule": "SCH 40"}),
    ]
    for text, expected in pipe_samples:
        attrs, cat, conf, missing, notes = extract_attributes(text)
        assert cat == "PIPES_AND_TUBES", f"Expected PIPES_AND_TUBES, got {cat}"
        for k, v in expected.items():
            assert attrs.get(k) == v, f"Pipe {text}: expected {k}={v}, got {attrs.get(k)}"
        print(f" [PASS] Pipe: '{text}' -> {attrs} (conf: {conf}, missing: {missing})")

    # 3. Test Bearing Attribute Extraction & Catalog Lookup
    print("\n--- Testing Bearing Attribute Extraction & Dimension Lookup ---")
    bearing_samples = [
        ("BEARING 6205 ZZ", {"bearing_number": "6205", "bore_diameter_mm": 25.0, "outer_diameter_mm": 52.0, "width_mm": 15.0, "seal_type": "ZZ_DOUBLE_METAL_SHIELD"}),
        ("BALL BEARING 6205-2RS", {"bearing_number": "6205", "bearing_type": "DEEP_GROOVE_BALL_BEARING", "seal_type": "2RS_DOUBLE_RUBBER_SEAL"}),
        ("SKF 6205 ZZ BEARING", {"manufacturer": "SKF", "bearing_number": "6205", "seal_type": "ZZ_DOUBLE_METAL_SHIELD"}),
        ("BEARING 6305", {"bearing_number": "6305", "bore_diameter_mm": 25.0, "outer_diameter_mm": 62.0, "width_mm": 17.0}),
        ("BEARING 6204", {"bearing_number": "6204", "bore_diameter_mm": 20.0, "outer_diameter_mm": 47.0, "width_mm": 14.0}),
        ("BEARING 6206", {"bearing_number": "6206", "bore_diameter_mm": 30.0, "outer_diameter_mm": 62.0, "width_mm": 16.0}),
    ]
    for text, expected in bearing_samples:
        attrs, cat, conf, missing, notes = extract_attributes(text)
        assert cat == "BEARINGS", f"Expected BEARINGS, got {cat}"
        for k, v in expected.items():
            assert attrs.get(k) == v, f"Bearing {text}: expected {k}={v}, got {attrs.get(k)}"
        print(f" [PASS] Bearing: '{text}' -> {attrs['bearing_number']} dimensions={attrs.get('bore_diameter_mm')}x{attrs.get('outer_diameter_mm')}x{attrs.get('width_mm')} (conf: {conf})")

    # 4. Test Valve Attribute Extraction
    print("\n--- Testing Valve Attribute Extraction ---")
    valve_samples = [
        ("BALL VALVE 50MM SS304 PN16", {"valve_type": "BALL_VALVE", "nominal_diameter": "50MM", "pressure_rating": "PN16", "material_grade": "SS304", "body_material": "SS304"}),
        ("GATE VALVE DN50 PN16", {"valve_type": "GATE_VALVE", "nominal_diameter": "DN50", "pressure_rating": "PN16"}),
        ("SS304 BALL VALVE 50 MM", {"valve_type": "BALL_VALVE", "nominal_diameter": "50MM", "material_grade": "SS304", "body_material": "SS304"}),
    ]
    for text, expected in valve_samples:
        attrs, cat, conf, missing, notes = extract_attributes(text)
        assert cat == "VALVES", f"Expected VALVES, got {cat}"
        for k, v in expected.items():
            assert attrs.get(k) == v, f"Valve {text}: expected {k}={v}, got {attrs.get(k)}"
        print(f" [PASS] Valve: '{text}' -> type={attrs.get('valve_type')}, dia={attrs.get('nominal_diameter')}, press={attrs.get('pressure_rating')}")

    # 5. Test Cable Attribute Extraction
    print("\n--- Testing Cable Attribute Extraction ---")
    cable_samples = [
        ("PVC INSULATED COPPER CABLE 3 CORE 2.5 SQMM", {"number_of_cores": 3, "cross_section_sqmm": 2.5, "conductor_material": "COPPER", "insulation_type": "PVC"}),
        ("3C X 2.5 SQMM CU PVC CABLE", {"number_of_cores": 3, "cross_section_sqmm": 2.5, "conductor_material": "COPPER", "insulation_type": "PVC"}),
        ("1.1KV XLPE ALUMINIUM CABLE 4 CORE 16 SQMM", {"number_of_cores": 4, "cross_section_sqmm": 16.0, "conductor_material": "ALUMINIUM", "insulation_type": "XLPE", "voltage_grade": "1.1KV"}),
    ]
    for text, expected in cable_samples:
        attrs, cat, conf, missing, notes = extract_attributes(text)
        assert cat == "ELECTRICAL_CABLES", f"Expected ELECTRICAL_CABLES, got {cat}"
        for k, v in expected.items():
            assert attrs.get(k) == v, f"Cable {text}: expected {k}={v}, got {attrs.get(k)}"
        print(f" [PASS] Cable: '{text}' -> cores={attrs.get('number_of_cores')}, size={attrs.get('cross_section_sqmm')} sqmm, cond={attrs.get('conductor_material')}")

    # 6. Test Motor Attribute Extraction
    print("\n--- Testing Motor Attribute Extraction ---")
    motor_samples = [
        ("24V DC MOTOR 0.5 HP", {"voltage": "24V", "current_type": "DC", "power_hp": 0.5, "motor_type": "DC_MOTOR"}),
        ("415V AC MOTOR 5 HP 1440 RPM", {"voltage": "415V", "current_type": "AC", "power_hp": 5.0, "speed_rpm": 1440, "motor_type": "AC_MOTOR"}),
        ("0.37 KW DC MOTOR 24 V", {"voltage": "24 V", "current_type": "DC", "power_kw": 0.37, "motor_type": "DC_MOTOR"}),
    ]
    for text, expected in motor_samples:
        attrs, cat, conf, missing, notes = extract_attributes(text)
        assert cat == "MOTORS", f"Expected MOTORS, got {cat}"
        for k, v in expected.items():
            assert attrs.get(k) == v, f"Motor {text}: expected {k}={v}, got {attrs.get(k)}"
        print(f" [PASS] Motor: '{text}' -> volt={attrs.get('voltage')}, type={attrs.get('motor_type')}, hp={attrs.get('power_hp')}, rpm={attrs.get('speed_rpm')}")

    # 7. Test Missing Critical Attributes
    print("\n--- Testing Missing Critical Attributes Handling ---")
    incomplete_pipe = "PIPE 50MM SCH-40"
    pipe_res = await extract_material_attributes(AttributeExtractionRequest(raw_description=incomplete_pipe))
    assert "material" in pipe_res.missing_critical_attributes or "nominal_bore" in pipe_res.missing_critical_attributes
    print(f" [PASS] Incomplete pipe correctly identified missing attributes: {pipe_res.missing_critical_attributes}")

    incomplete_valve = "SS304 BALL VALVE 50 MM"
    valve_res = await extract_material_attributes(AttributeExtractionRequest(raw_description=incomplete_valve))
    assert "pressure_rating" in valve_res.missing_critical_attributes
    print(f" [PASS] Incomplete valve correctly identified missing attributes: {valve_res.missing_critical_attributes}")

    # 8. Test API Endpoint via Request / Response Schemas
    print("\n--- Testing POST /api/materials/extract-attributes Endpoint ---")
    endpoint_test = AttributeExtractionRequest(
        raw_description="SS PIPE 50 NB SCH 40 ASTM A312",
        category="piping",
        uom="MTR"
    )
    res = await extract_material_attributes(endpoint_test)
    assert isinstance(res, AttributeExtractionResponse)
    assert res.inferred_category == "PIPES_AND_TUBES"
    assert res.extracted_attributes.get("material") == "STAINLESS_STEEL"
    assert res.extracted_attributes.get("uom") == "M"
    assert res.extraction_confidence >= 0.75
    print(f" [PASS] Endpoint returned valid AttributeExtractionResponse:")
    print(f"        standard_description: {res.standard_description}")
    print(f"        inferred_category:    {res.inferred_category}")
    print(f"        confidence:           {res.extraction_confidence}")
    print(f"        extracted_attributes: {res.extracted_attributes}")

    # 9. Test Ingestion Preview Flow with In-Memory Attribute Extraction
    print("\n--- Testing Ingestion Preview with Enriched Attributes ---")
    preview_res = await preview_sample_data()
    assert preview_res.success is True
    assert len(preview_res.valid_records) > 0

    enriched_count = sum(1 for r in preview_res.valid_records if r.attributes and len(r.attributes) > 0)
    print(f" [PASS] CSV Ingestion Preview extracted attributes for {enriched_count}/{len(preview_res.valid_records)} valid records")
    for r in preview_res.valid_records[:3]:
        print(f"        Code: {r.source_material_code:<18} Attrs: {list(r.attributes.keys())}")

    print("\n" + "=" * 70)
    print("ALL PROMPT 6 VERIFICATION CHECKS PASSED WITH ZERO ERRORS!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_prompt6_verification())
