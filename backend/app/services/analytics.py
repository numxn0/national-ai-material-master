from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    ApprovalCase,
    AuditChainState,
    AuditEvent,
    IngestionBatch,
    IngestionRowError,
    MatchCandidate,
    MaterialMapping,
    NationalMaterial,
    ProcurementHistory,
    SourceMaterial,
)


def _count(db: Session, model, *conditions) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0


def _counter_from_rows(rows: Iterable[tuple]) -> Dict[str, int]:
    return {str(key or "UNSPECIFIED"): int(value or 0) for key, value in rows}


def _audit_summary(event: AuditEvent) -> str:
    action = event.action.replace("_", " ").title()
    return f"{action} on {event.entity_type} {event.entity_id}"


def build_analytics_summary(db: Session, *, days: int = 30) -> Dict:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    total_source_materials = _count(db, SourceMaterial)
    total_ingestion_batches = _count(db, IngestionBatch)
    batches_completed = _count(db, IngestionBatch, IngestionBatch.status == "COMPLETED")
    batches_with_errors = _count(db, IngestionBatch, IngestionBatch.failed_records > 0)
    total_match_candidates = _count(db, MatchCandidate)
    duplicate_candidate_count = _count(db, MatchCandidate, MatchCandidate.classification != "REJECTED_BY_SCORING")

    candidate_counts_by_classification = _counter_from_rows(
        db.execute(
            select(MatchCandidate.classification, func.count())
            .group_by(MatchCandidate.classification)
            .order_by(MatchCandidate.classification.asc())
        ).all()
    )
    candidate_counts_by_status = _counter_from_rows(
        db.execute(
            select(MatchCandidate.status, func.count())
            .group_by(MatchCandidate.status)
            .order_by(MatchCandidate.status.asc())
        ).all()
    )

    pending_l1_count = _count(db, ApprovalCase, ApprovalCase.current_stage == "PENDING_L1")
    pending_l2_count = _count(db, ApprovalCase, ApprovalCase.current_stage == "PENDING_L2")
    needs_more_info_count = _count(db, ApprovalCase, ApprovalCase.current_stage == "NEEDS_MORE_INFO")
    approved_mapping_count = _count(db, MaterialMapping, MaterialMapping.approval_status == "APPROVED")
    rejected_mapping_count = _count(db, MaterialMapping, MaterialMapping.approval_status == "REJECTED")
    national_material_draft_count = _count(db, NationalMaterial, NationalMaterial.status == "DRAFT")
    national_material_active_count = _count(db, NationalMaterial, NationalMaterial.status == "ACTIVE")
    national_material_rejected_count = _count(db, NationalMaterial, NationalMaterial.status == "REJECTED")
    audit_event_count = _count(db, AuditEvent)

    approved_cases = db.execute(
        select(ApprovalCase.procurement_impact).where(ApprovalCase.approval_status == "APPROVED")
    ).scalars().all()
    estimated_approved_savings_inr = round(
        sum(float((impact or {}).get("estimated_savings_inr") or 0.0) for impact in approved_cases),
        2,
    )
    actual_procurement_spend_inr = round(float(db.scalar(select(func.coalesce(func.sum(ProcurementHistory.total_amount), 0.0))) or 0.0), 2)
    actual_procurement_quantity = round(float(db.scalar(select(func.coalesce(func.sum(ProcurementHistory.quantity), 0.0))) or 0.0), 4)
    procurement_vendor_count = db.scalar(
        select(func.count(func.distinct(ProcurementHistory.vendor))).where(ProcurementHistory.vendor.is_not(None))
    ) or 0
    approved_national_code_spend_inr = round(
        float(
            db.scalar(
                select(func.coalesce(func.sum(ProcurementHistory.total_amount), 0.0)).where(
                    ProcurementHistory.national_material_id.is_not(None)
                )
            )
            or 0.0
        ),
        2,
    )

    chain = db.get(AuditChainState, "primary")
    audit_chain = {
        "chain_key": chain.chain_key if chain else "primary",
        "last_sequence_number": chain.last_sequence_number if chain else 0,
        "last_hash": chain.last_hash if chain else "0" * 64,
        "last_event_id": chain.last_event_id if chain else None,
        "updated_at": chain.updated_at if chain else None,
    }

    materials = db.execute(select(SourceMaterial)).scalars().all()
    material_by_id = {material.id: material for material in materials}
    cpse_material_count = Counter(material.source_cpse for material in materials)
    category_material_count = Counter(material.category for material in materials)

    cpse_batch_count = _counter_from_rows(
        db.execute(
            select(IngestionBatch.source_cpse, func.count(distinct(IngestionBatch.id)))
            .group_by(IngestionBatch.source_cpse)
        ).all()
    )

    cpse_candidate_count: Counter = Counter()
    category_candidate_count: Counter = Counter()
    candidates = db.execute(select(MatchCandidate)).scalars().all()
    for candidate in candidates:
        seen_cpses = set()
        seen_categories = set()
        for source_id in [candidate.source_material_a_id, candidate.source_material_b_id]:
            material = material_by_id.get(source_id)
            if material:
                seen_cpses.add(material.source_cpse)
                seen_categories.add(material.category)
        for cpse in seen_cpses:
            cpse_candidate_count[cpse] += 1
        for category in seen_categories:
            category_candidate_count[category] += 1

    cpse_approved_mapping_count: Counter = Counter()
    approved_mappings = db.execute(
        select(MaterialMapping).where(MaterialMapping.approval_status == "APPROVED")
    ).scalars().all()
    for mapping in approved_mappings:
        material = material_by_id.get(mapping.source_material_id)
        if material:
            cpse_approved_mapping_count[material.source_cpse] += 1

    cpse_names = sorted(set(cpse_material_count) | set(cpse_batch_count) | set(cpse_candidate_count) | set(cpse_approved_mapping_count))
    cpse_breakdown = [
        {
            "cpse_name": cpse,
            "material_count": int(cpse_material_count[cpse]),
            "batch_count": int(cpse_batch_count.get(cpse, 0)),
            "candidate_involvement_count": int(cpse_candidate_count[cpse]),
            "approved_mapping_count": int(cpse_approved_mapping_count[cpse]),
        }
        for cpse in cpse_names
    ]

    active_national_by_category = _counter_from_rows(
        db.execute(
            select(NationalMaterial.category, func.count())
            .where(NationalMaterial.status == "ACTIVE")
            .group_by(NationalMaterial.category)
        ).all()
    )
    categories = sorted(set(category_material_count) | set(category_candidate_count) | set(active_national_by_category))
    category_breakdown = [
        {
            "category": category,
            "material_count": int(category_material_count[category]),
            "candidate_involvement_count": int(category_candidate_count[category]),
            "active_national_material_count": int(active_national_by_category.get(category, 0)),
        }
        for category in categories
    ]

    recent_events_desc = db.execute(
        select(AuditEvent).order_by(AuditEvent.timestamp.desc(), AuditEvent.sequence_number.desc()).limit(10)
    ).scalars().all()
    recent_events = list(reversed(recent_events_desc))
    recent_activity = [
        {
            "timestamp": event.timestamp,
            "action": event.action,
            "actor": event.actor,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "summary": _audit_summary(event),
        }
        for event in recent_events
    ]

    batches = db.execute(select(IngestionBatch).where(IngestionBatch.created_at >= start)).scalars().all()
    rejected_by_batch = _counter_from_rows(
        db.execute(
            select(IngestionRowError.ingestion_batch_id, func.count())
            .where(IngestionRowError.created_at >= start)
            .group_by(IngestionRowError.ingestion_batch_id)
        ).all()
    )
    timeline = defaultdict(lambda: {"batches_created": 0, "source_materials_processed": 0, "rejected_rows": 0})
    for batch in batches:
        bucket = batch.created_at.date().isoformat()
        timeline[bucket]["batches_created"] += 1
        timeline[bucket]["source_materials_processed"] += int(batch.processed_records or 0)
        timeline[bucket]["rejected_rows"] += int(rejected_by_batch.get(str(batch.id), rejected_by_batch.get(batch.id, 0)) or batch.failed_records or 0)

    ingestion_timeline = [
        {
            "date": date,
            "batches_created": values["batches_created"],
            "source_materials_processed": values["source_materials_processed"],
            "rejected_rows": values["rejected_rows"],
        }
        for date, values in sorted(timeline.items())
    ]

    return {
        "total_source_materials": total_source_materials,
        "total_ingestion_batches": total_ingestion_batches,
        "batches_completed": batches_completed,
        "batches_with_errors": batches_with_errors,
        "total_match_candidates": total_match_candidates,
        "duplicate_candidate_count": duplicate_candidate_count,
        "candidate_counts_by_classification": candidate_counts_by_classification,
        "candidate_counts_by_status": candidate_counts_by_status,
        "pending_l1_count": pending_l1_count,
        "pending_l2_count": pending_l2_count,
        "needs_more_info_count": needs_more_info_count,
        "approved_mapping_count": approved_mapping_count,
        "rejected_mapping_count": rejected_mapping_count,
        "national_material_draft_count": national_material_draft_count,
        "national_material_active_count": national_material_active_count,
        "national_material_rejected_count": national_material_rejected_count,
        "estimated_approved_savings_inr": estimated_approved_savings_inr,
        "actual_procurement_spend_inr": actual_procurement_spend_inr,
        "actual_procurement_quantity": actual_procurement_quantity,
        "procurement_vendor_count": int(procurement_vendor_count),
        "approved_national_code_spend_inr": approved_national_code_spend_inr,
        "procurement_metric_source": "ACTUAL_PROCUREMENT_HISTORY" if actual_procurement_spend_inr > 0 else "NO_PROCUREMENT_HISTORY",
        "audit_event_count": audit_event_count,
        "audit_chain": audit_chain,
        "cpse_breakdown": cpse_breakdown,
        "category_breakdown": category_breakdown,
        "recent_activity": recent_activity,
        "ingestion_timeline": ingestion_timeline,
        "days": days,
        "generated_at": now,
    }
