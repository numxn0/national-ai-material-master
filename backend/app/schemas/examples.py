"""
Typed example placeholder records for the National AI Material Master prototype.
Adheres strictly to the Canonical Material Schema specification.
"""

from datetime import datetime
from uuid import UUID
from .material import SourceMaterialResponse, NationalMaterialResponse
from .mapping import MaterialMappingResponse, MatchMethod, MatchStatus, ApprovalStatus
from .ingestion import IngestionBatchResponse, IngestionStatus
from .audit import AuditLogResponse, AuditAction

# 1. Example Source Material: Stainless Steel Pipe from IOCL
EXAMPLE_SOURCE_MATERIAL = SourceMaterialResponse(
    id=UUID("7a942b2e-9d21-4f4c-83b6-194ce0291ba1"),
    source_cpse="IOCL",
    source_system="SAP_ECC_PRD",
    source_material_code="IOCL-P-304-50NB",
    raw_description="PIPE S.S. 50 NB SCH 40 ASTM A312 GR TP 304 SEAMLESS 6M",
    cleaned_description="pipe ss 50 nb sch 40 astm a312 gr tp 304 seamless 6m",
    standard_description="Pipe, Stainless Steel, Seamless, 50 NB (2 Inch), Schedule 40, ASTM A312 TP304, Plain Ends, L=6M",
    category="PIPING_AND_FITTINGS",
    sub_category="PIPES",
    material_type="SEAMLESS_PIPE",
    material_grade="ASTM A312 TP304",
    manufacturer="JINDAL_SAW",
    part_number="JND-304-50-SCH40",
    model_number=None,
    uom="MTR",
    attributes={
        "nominal_bore_nb": 50,
        "nominal_bore_inch": 2.0,
        "outer_diameter_mm": 60.3,
        "schedule": "SCH 40",
        "wall_thickness_mm": 3.91,
        "material_grade": "ASTM A312 TP304",
        "manufacturing_process": "SEAMLESS",
        "length_meters": 6.0,
        "ends": "PLAIN_END",
        "governing_standard": "ASTM A312",
        "uom": "MTR"
    },
    normalized_tokens=[
        "pipe", "stainless", "steel", "seamless", "50", "nb", "schedule", "40", "astm", "a312", "tp304", "6m"
    ],
    ingestion_batch_id=UUID("c3e1b7f0-0d3a-4a25-9b2f-7c1a8d5e9f02"),
    match_status=MatchStatus.MATCH_FOUND,
    approval_status=ApprovalStatus.APPROVED,
    created_at=datetime.fromisoformat("2026-09-19T06:30:00+00:00"),
    updated_at=datetime.fromisoformat("2026-09-19T06:35:12+00:00")
)

# 2. Example National Material Master: Canonical SS Pipe SKU
EXAMPLE_NATIONAL_MATERIAL = NationalMaterialResponse(
    id=UUID("2d9f481c-8e3b-4172-8f69-d2b38271e950"),
    national_material_code="NAMM-PIP-SS-0042",
    standard_description="PIPE, STAINLESS STEEL, SEAMLESS, 50 NB (2 INCH), SCH 40, ASTM A312 TP304, PLAIN ENDS",
    category="PIPING_AND_FITTINGS",
    sub_category="PIPES",
    material_type="SEAMLESS_PIPE",
    material_grade="ASTM A312 TP304",
    standard_uom="MTR",
    canonical_attributes={
        "nominal_bore_nb": 50,
        "nominal_bore_inch": 2.0,
        "outer_diameter_mm": 60.3,
        "schedule": "SCH 40",
        "wall_thickness_mm": 3.91,
        "material_grade": "ASTM A312 TP304",
        "manufacturing_process": "SEAMLESS",
        "governing_standard": "ASTM A312 / ASME SA312",
        "standard_uom": "MTR"
    },
    classification_path="ENG.PIPING.PIPES.STAINLESS_STEEL.SEAMLESS",
    status="ACTIVE",
    created_by="SYSTEM_AI_ENGINE",
    approved_by="officer.verma@nic.in",
    created_at=datetime.fromisoformat("2026-09-19T06:35:12+00:00"),
    updated_at=datetime.fromisoformat("2026-09-19T06:35:12+00:00")
)

# 3. Example Material Mapping: Linking IOCL Pipe to National SKU
EXAMPLE_MATERIAL_MAPPING = MaterialMappingResponse(
    id=UUID("f5b67281-2c9e-4e94-b153-27a13c90e811"),
    source_material_id=UUID("7a942b2e-9d21-4f4c-83b6-194ce0291ba1"),
    national_material_id=UUID("2d9f481c-8e3b-4172-8f69-d2b38271e950"),
    confidence_score=0.9650,
    match_method=MatchMethod.XGBOOST_HYBRID,
    match_explanation={
        "token_sort_ratio": 94.2,
        "vector_cosine_similarity": 0.978,
        "exact_attribute_matches": ["nominal_bore_nb", "schedule", "material_grade", "uom"],
        "shap_top_drivers": [
            {"feature": "grade_ASTM_A312_TP304", "weight": 0.38},
            {"feature": "dimension_50NB_SCH40", "weight": 0.35},
            {"feature": "process_SEAMLESS", "weight": 0.18}
        ]
    },
    approval_status=ApprovalStatus.APPROVED,
    reviewer_id="officer.sharma@railways.gov.in",
    reviewed_at=datetime.fromisoformat("2026-09-19T07:10:00+00:00"),
    created_at=datetime.fromisoformat("2026-09-19T06:35:12+00:00")
)

# 4. Example Ingestion Batch: Bulk CSV Catalog Upload from Indian Railways
EXAMPLE_INGESTION_BATCH = IngestionBatchResponse(
    id=UUID("c3e1b7f0-0d3a-4a25-9b2f-7c1a8d5e9f02"),
    batch_name="BATCH-2026-09-RAILWAYS-NR-01",
    source_cpse="INDIAN_RAILWAYS",
    source_system="IREPS_NORTHERN_RAILWAY",
    file_name="northern_railways_mechanical_spares_q3_2026.csv",
    total_records=2500,
    processed_records=2488,
    failed_records=12,
    status=IngestionStatus.COMPLETED,
    uploaded_by="officer.sharma@railways.gov.in",
    file_hash_sha256="4a35d91c78e90f23d15b4f621cae938914b184029143891e48ab9345cdef7812",
    error_summary={
        "missing_mandatory_fields": 8,
        "unrecognized_uom": 4
    },
    created_at=datetime.fromisoformat("2026-09-19T06:28:00+00:00"),
    completed_at=datetime.fromisoformat("2026-09-19T06:34:45+00:00")
)

# 5. Example Audit Log: Tamper-Evident SHA-256 Chained Entry
EXAMPLE_AUDIT_LOG = AuditLogResponse(
    id=UUID("9b7410ac-4712-4cf4-912b-7e61a4f009e5"),
    actor_id="officer.sharma@railways.gov.in",
    actor_role="NODAL_OFFICER_L1",
    action=AuditAction.MAPPING_REVIEWED,
    entity_type="material_mapping",
    entity_id="f5b67281-2c9e-4e94-b153-27a13c90e811",
    old_value={"approval_status": "PENDING_L1"},
    new_value={"approval_status": "APPROVED", "reviewed_at": "2026-09-19T07:10:00+00:00"},
    reason="Confirmed 100% metallurgical and dimensional equivalence with National Standard SKU",
    ip_address="10.42.18.91",
    hash_signature="e83d81b491ec6f29ab48108e4cfd58709e631980839e1a8efbc7520e5e01b3aa",
    created_at=datetime.fromisoformat("2026-09-19T07:10:01+00:00")
)
