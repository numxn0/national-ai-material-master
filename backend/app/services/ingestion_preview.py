"""
CSV Material Ingestion Preview Service.
Parses, cleans, validates, and transforms CPSE/PSU material catalogs into canonical
SourceMaterial-shaped preview records without database persistence.
"""

import csv
import io
import re
import uuid
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

from app.schemas.material import SourceMaterialResponse
from app.schemas.mapping import MatchStatus, ApprovalStatus
from app.schemas.ingestion import (
    CSVPreviewSummary,
    CSVPreviewRowError,
    CSVPreviewResponse,
)

# Canonical field target synonyms mapping
CANONICAL_FIELD_SYNONYMS: Dict[str, List[str]] = {
    "source_material_code": [
        "source_material_code", "original_item_code", "material_code", "material_no",
        "item_code", "mat_code", "item_no", "sku", "code", "part_code", "material_id", "item_id"
    ],
    "raw_description": [
        "raw_description", "description", "item_description", "material_description",
        "item_desc", "mat_desc", "details", "item_details", "specification", "specs", "name", "material_title"
    ],
    "uom": [
        "uom", "raw_uom", "unit", "unit_of_measure", "uom_code", "measurement_unit", "base_uom"
    ],
    "category": [
        "category", "raw_category", "group", "material_group", "item_group", "major_group", "class", "commodity"
    ],
    "sub_category": [
        "sub_category", "subcategory", "sub_group", "subgroup", "minor_group", "subclass"
    ],
    "material_type": [
        "material_type", "type", "item_type", "form_factor"
    ],
    "material_grade": [
        "material_grade", "grade", "metallurgy", "spec_grade", "standard_grade"
    ],
    "manufacturer": [
        "manufacturer", "make", "oem", "brand", "vendor", "mfg"
    ],
    "part_number": [
        "part_number", "part_no", "pn", "catalog_no", "model_pn", "drawing_no"
    ],
    "model_number": [
        "model_number", "model_no", "model", "series"
    ],
    "source_cpse": [
        "source_cpse", "source_organization", "source_psu", "organization", "psu", "org", "company"
    ],
    "source_system": [
        "source_system", "system", "erp", "legacy_system", "source_erp"
    ]
}

from app.services.normalization import (
    normalize_whitespace,
    normalize_punctuation,
    normalize_description,
    normalize_uom,
    normalize_category,
    tokenize_description,
    build_standard_description,
)
from app.services.attribute_extraction import extract_attributes

# Aliases for backward compatibility
clean_raw_description = normalize_punctuation
generate_normalized_tokens = tokenize_description


def normalize_column_name(col: str) -> str:
    """Normalize column header for fuzzy synonym matching."""
    return re.sub(r"[^a-z0-9]", "_", col.strip().lower()).strip("_")


def detect_columns(csv_headers: List[str]) -> Dict[str, str]:
    """
    Detects which CSV headers map to which canonical target fields.
    Returns: { raw_header: canonical_field_name }
    """
    mapped_columns: Dict[str, str] = {}
    assigned_targets = set()

    for raw_header in csv_headers:
        cleaned_h = normalize_column_name(raw_header)
        matched_target = None

        for canonical_target, synonyms in CANONICAL_FIELD_SYNONYMS.items():
            if canonical_target in assigned_targets:
                continue
            normalized_synonyms = [normalize_column_name(s) for s in synonyms]
            if cleaned_h in normalized_synonyms:
                matched_target = canonical_target
                break

        if matched_target:
            mapped_columns[raw_header] = matched_target
            assigned_targets.add(matched_target)

    return mapped_columns


def parse_csv_content(
    csv_text_or_bytes: Any,
    default_cpse: Optional[str] = None,
    default_system: Optional[str] = None,
    file_name: str = "materials.csv"
) -> CSVPreviewResponse:
    """
    Parses CSV content and generates structured preview records conforming to
    SourceMaterialResponse schema along with ingestion summary and error logs.
    """
    # 1. Decode bytes if needed
    if isinstance(csv_text_or_bytes, bytes):
        for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
            try:
                content = csv_text_or_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            content = csv_text_or_bytes.decode("utf-8", errors="replace")
    else:
        content = str(csv_text_or_bytes)

    # 2. Read with CSV DictReader
    f = io.StringIO(content.strip())
    reader = csv.reader(f)
    try:
        raw_headers = next(reader)
    except StopIteration:
        return CSVPreviewResponse(
            success=False,
            message="CSV file is empty",
            summary=CSVPreviewSummary(
                file_name=file_name,
                total_rows=0,
                valid_records_count=0,
                invalid_records_count=0,
                detected_columns_count=0,
                mapped_columns_count=0,
            ),
            detected_columns=[],
            mapped_columns={},
            valid_records=[],
            invalid_rows=[
                CSVPreviewRowError(
                    row_number=1,
                    reason="CSV file contains no rows or headers"
                )
            ]
        )

    # Reset and read as dict
    f.seek(0)
    dict_reader = csv.DictReader(f)
    detected_headers = [h.strip() for h in raw_headers if h and h.strip()]
    column_mapping = detect_columns(detected_headers)

    valid_records: List[SourceMaterialResponse] = []
    invalid_rows: List[CSVPreviewRowError] = []

    detected_cpse_val = default_cpse
    detected_system_val = default_system or "CSV_INGESTION"

    for idx, row in enumerate(dict_reader, start=2):
        # Skip completely empty rows
        if not any(v and str(v).strip() for v in row.values()):
            invalid_rows.append(
                CSVPreviewRowError(
                    row_number=idx,
                    raw_data=row,
                    reason="Empty row"
                )
            )
            continue

        # Extract values according to mapped columns
        extracted: Dict[str, Any] = {}
        unmapped_attributes: Dict[str, Any] = {}

        for raw_col, val in row.items():
            if not raw_col:
                continue
            str_val = str(val).strip() if val is not None else ""
            if raw_col in column_mapping:
                canonical_field = column_mapping[raw_col]
                extracted[canonical_field] = str_val
            else:
                if str_val:
                    unmapped_attributes[raw_col.strip()] = str_val

        # Mandatory validation checks
        raw_desc = extracted.get("raw_description", "")
        source_code = extracted.get("source_material_code", "")

        if not raw_desc:
            invalid_rows.append(
                CSVPreviewRowError(
                    row_number=idx,
                    item_code=source_code or None,
                    raw_data=row,
                    reason="Missing mandatory material description"
                )
            )
            continue

        if not source_code:
            invalid_rows.append(
                CSVPreviewRowError(
                    row_number=idx,
                    item_code=None,
                    raw_data=row,
                    reason="Missing mandatory source material code"
                )
            )
            continue

        # Cleaning & Normalization using normalization service
        cleaned_desc = normalize_punctuation(raw_desc).lower()
        standard_title = build_standard_description(raw_desc)
        norm_uom = normalize_uom(extracted.get("uom"))
        norm_category = normalize_category(extracted.get("category"))
        tokens = tokenize_description(standard_title)

        # Rule-based attribute extraction
        parsed_attrs, inferred_cat, _, _, _ = extract_attributes(
            raw_description=raw_desc,
            category=norm_category,
            uom=norm_uom
        )
        broad_cat_set = {"UNASSIGNED", "MECHANICAL_SPARES", "ELECTRICAL_SPARES", "ELECTRICAL_ROTATING_SPARES", "STANDARD_HARDWARE", "GENERAL_SPARES"}
        if (norm_category in broad_cat_set and inferred_cat != "UNASSIGNED") or (norm_category == "PIPES_AND_TUBES" and inferred_cat == "VALVES"):
            norm_category = inferred_cat

        # Merge unmapped attributes with extracted attributes
        merged_attributes = {**unmapped_attributes, **parsed_attrs}

        # CPSE and system resolution
        row_cpse = extracted.get("source_cpse") or default_cpse or "UNSPECIFIED_CPSE"
        row_system = extracted.get("source_system") or default_system or "CSV_INGESTION"

        if not detected_cpse_val and row_cpse != "UNSPECIFIED_CPSE":
            detected_cpse_val = row_cpse

        # Construct typed SourceMaterialResponse
        now = datetime.utcnow()
        record = SourceMaterialResponse(
            id=uuid.uuid4(),
            source_cpse=row_cpse,
            source_system=row_system,
            source_material_code=source_code,
            raw_description=raw_desc,
            cleaned_description=cleaned_desc,
            standard_description=standard_title,
            category=norm_category,
            sub_category=extracted.get("sub_category") or "GENERAL",
            material_type=extracted.get("material_type"),
            material_grade=extracted.get("material_grade") or parsed_attrs.get("material_grade"),
            manufacturer=extracted.get("manufacturer") or parsed_attrs.get("manufacturer"),
            part_number=extracted.get("part_number") or parsed_attrs.get("part_number"),
            model_number=extracted.get("model_number") or parsed_attrs.get("model_number"),
            uom=norm_uom,
            attributes=merged_attributes,
            normalized_tokens=tokens,
            ingestion_batch_id=None,
            match_status=MatchStatus.UNPROCESSED,
            approval_status=ApprovalStatus.PENDING_INGESTION,
            created_at=now,
            updated_at=now
        )
        valid_records.append(record)

    total_rows = len(valid_records) + len(invalid_rows)

    summary = CSVPreviewSummary(
        file_name=file_name,
        total_rows=total_rows,
        valid_records_count=len(valid_records),
        invalid_records_count=len(invalid_rows),
        detected_columns_count=len(detected_headers),
        mapped_columns_count=len(column_mapping),
        source_cpse_detected=detected_cpse_val,
        source_system_detected=detected_system_val
    )

    return CSVPreviewResponse(
        success=True,
        message=f"Preview ready: {len(valid_records)} valid records processed, {len(invalid_rows)} invalid rows flagged.",
        summary=summary,
        detected_columns=detected_headers,
        mapped_columns=column_mapping,
        valid_records=valid_records,
        invalid_rows=invalid_rows
    )
