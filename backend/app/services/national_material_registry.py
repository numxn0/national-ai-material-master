import hashlib
import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import MatchCandidate, MaterialMapping, NationalMaterial, SourceMaterial
from app.services.normalization import build_standard_description
from app.services.persistent_audit import append_audit_event


def _value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _slug(value: Optional[str], fallback: str, max_len: int = 18) -> str:
    text = re.sub(r"[^A-Z0-9]+", "-", _value(value).upper()).strip("-")
    text = text or fallback
    return text[:max_len].strip("-") or fallback


def _prefer_agreed(a: Any, b: Any) -> Tuple[Any, Optional[Dict[str, Any]]]:
    if a in (None, "", [], {}):
        return b, None
    if b in (None, "", [], {}):
        return a, None
    if str(a).strip().upper() == str(b).strip().upper():
        return a, None
    return a, {"left": a, "right": b}


def _canonical_properties(a: SourceMaterial, b: SourceMaterial) -> Dict[str, Any]:
    category, cat_conflict = _prefer_agreed(a.category, b.category)
    sub_category, sub_conflict = _prefer_agreed(a.sub_category, b.sub_category)
    uom, uom_conflict = _prefer_agreed(a.uom, b.uom)
    material_type, type_conflict = _prefer_agreed(a.material_type, b.material_type)
    material_grade, grade_conflict = _prefer_agreed(a.material_grade, b.material_grade)

    attrs_a = a.attributes or {}
    attrs_b = b.attributes or {}
    keys = sorted(set(attrs_a) | set(attrs_b))
    attrs: Dict[str, Any] = {}
    conflicts: Dict[str, Dict[str, Any]] = {}
    for key in keys:
        chosen, conflict = _prefer_agreed(attrs_a.get(key), attrs_b.get(key))
        attrs[key] = chosen
        if conflict:
            conflicts[key] = conflict

    field_conflicts = {}
    for name, conflict in {
        "category": cat_conflict,
        "sub_category": sub_conflict,
        "uom": uom_conflict,
        "material_type": type_conflict,
        "material_grade": grade_conflict,
    }.items():
        if conflict:
            field_conflicts[name] = conflict

    chosen_description = a.standard_description or b.standard_description or a.raw_description or b.raw_description
    standard_description = build_standard_description(chosen_description)
    canonical_attributes = {
        "attributes": attrs,
        "conflicts": {
            "fields": field_conflicts,
            "attributes": conflicts,
        },
    }

    return {
        "standard_description": standard_description,
        "category": category or "UNASSIGNED",
        "sub_category": sub_category or "GENERAL",
        "material_type": material_type or "GENERAL",
        "material_grade": material_grade,
        "standard_uom": uom or "EA",
        "canonical_attributes": canonical_attributes,
        "classification_path": f"{category or 'UNASSIGNED'}/{sub_category or 'GENERAL'}",
    }


def _national_code(props: Dict[str, Any]) -> str:
    fingerprint_payload = {
        "standard_description": props["standard_description"],
        "category": props["category"],
        "sub_category": props["sub_category"],
        "standard_uom": props["standard_uom"],
        "attributes": props["canonical_attributes"].get("attributes", {}),
    }
    encoded = json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:10].upper()
    category = _slug(props["category"], "GENERAL")
    sub_category = _slug(props["sub_category"], "GENERAL")
    code = f"NAMM-{category}-{sub_category}-{fingerprint}"
    return code[:160]


def _mapping_response(mapping: MaterialMapping, national: Optional[NationalMaterial] = None) -> Dict[str, Any]:
    nm = national or mapping.national_material
    return {
        "id": mapping.id,
        "source_material_id": mapping.source_material_id,
        "national_material_id": mapping.national_material_id,
        "national_material_code": nm.national_material_code,
        "national_material_status": nm.status,
        "confidence_score": mapping.confidence_score,
        "match_method": mapping.match_method,
        "match_explanation": mapping.match_explanation or {},
        "approval_status": mapping.approval_status,
        "reviewer_id": mapping.reviewer_id,
        "reviewed_at": mapping.reviewed_at,
        "created_at": mapping.created_at,
    }


def create_draft_from_candidate(db: Session, candidate_id: uuid.UUID) -> Tuple[Optional[NationalMaterial], List[MaterialMapping], bool]:
    candidate = db.execute(
        select(MatchCandidate)
        .options(selectinload(MatchCandidate.source_material_a), selectinload(MatchCandidate.source_material_b))
        .where(MatchCandidate.id == candidate_id)
    ).scalar_one_or_none()
    if not candidate:
        return None, [], False

    existing = db.execute(
        select(NationalMaterial)
        .options(selectinload(NationalMaterial.mappings))
        .where(NationalMaterial.originating_match_candidate_id == candidate.id)
    ).scalar_one_or_none()
    if existing:
        return existing, list(existing.mappings), True

    if not candidate.source_material_a or not candidate.source_material_b:
        raise ValueError("Match candidate must have both source materials before drafting a national material.")

    props = _canonical_properties(candidate.source_material_a, candidate.source_material_b)
    code = _national_code(props)

    national = NationalMaterial(
        originating_match_candidate_id=candidate.id,
        national_material_code=code,
        standard_description=props["standard_description"],
        category=props["category"],
        sub_category=props["sub_category"],
        material_type=props["material_type"],
        material_grade=props["material_grade"],
        standard_uom=props["standard_uom"],
        canonical_attributes=props["canonical_attributes"],
        classification_path=props["classification_path"],
        status="DRAFT",
        created_by="NATIONAL_CODE_RECOMMENDER",
        metadata_json={
            "originating_match_candidate_id": str(candidate.id),
            "pair_id": candidate.pair_id,
            "generation_method": "NAMM-{CATEGORY}-{SUBCATEGORY}-{STABLE_FINGERPRINT}",
            "fingerprint_inputs": {
                "category": props["category"],
                "sub_category": props["sub_category"],
                "standard_description": props["standard_description"],
                "standard_uom": props["standard_uom"],
            },
        },
    )
    db.add(national)
    db.flush()

    mappings = []
    for source_id in [candidate.source_material_a_id, candidate.source_material_b_id]:
        mapping = MaterialMapping(
            source_material_id=source_id,
            national_material_id=national.id,
            confidence_score=candidate.hybrid_score if candidate.hybrid_score is not None else candidate.candidate_score,
            match_method="RULE_BASED_CANDIDATE_RECOMMENDATION",
            match_explanation={
                "candidate_id": str(candidate.id),
                "pair_id": candidate.pair_id,
                "classification": candidate.classification,
                "hybrid_score": candidate.hybrid_score,
                "candidate_score": candidate.candidate_score,
                "explanation": candidate.explanation or {},
                "score_details": candidate.score_details or {},
            },
            approval_status="PENDING_L1",
            metadata_json={"originating_match_candidate_id": str(candidate.id)},
        )
        db.add(mapping)
        mappings.append(mapping)

    db.flush()
    append_audit_event(
        db,
        actor="NATIONAL_CODE_RECOMMENDER",
        actor_role="SYSTEM_PROCESS",
        action="NATIONAL_MATERIAL_DRAFT_CREATED",
        entity_type="national_material",
        entity_id=str(national.id),
        old_value=None,
        new_value={
            "national_material_id": national.id,
            "national_material_code": national.national_material_code,
            "status": national.status,
            "originating_match_candidate_id": candidate.id,
            "mapping_ids": [mapping.id for mapping in mappings],
            "source_material_ids": [mapping.source_material_id for mapping in mappings],
        },
        reason="DRAFT national material and source mappings created from persisted match candidate.",
    )
    db.commit()
    db.refresh(national)
    for mapping in mappings:
        db.refresh(mapping)
    return national, mappings, False


def get_national_by_code(db: Session, national_material_code: str) -> Optional[NationalMaterial]:
    return db.execute(
        select(NationalMaterial)
        .options(selectinload(NationalMaterial.mappings).selectinload(MaterialMapping.national_material))
        .where(NationalMaterial.national_material_code == national_material_code)
    ).scalar_one_or_none()


def get_source_mappings(db: Session, source_material_id: uuid.UUID) -> Tuple[bool, List[MaterialMapping]]:
    source = db.get(SourceMaterial, source_material_id)
    if not source:
        return False, []
    mappings = db.execute(
        select(MaterialMapping)
        .options(selectinload(MaterialMapping.national_material))
        .where(MaterialMapping.source_material_id == source_material_id)
        .order_by(MaterialMapping.created_at.desc())
    ).scalars().all()
    return True, mappings


def mapping_payloads(mappings: List[MaterialMapping], national: Optional[NationalMaterial] = None) -> List[Dict[str, Any]]:
    return [_mapping_response(mapping, national) for mapping in mappings]
