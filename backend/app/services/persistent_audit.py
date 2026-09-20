import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AuditChainState, AuditEvent

GENESIS_HASH = "0" * 64
PRIMARY_CHAIN_KEY = "primary"
METHOD_VERSION = "persistent-audit-ledger-v1"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stable(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, dict):
        return {str(key): _stable(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple, set)):
        return [_stable(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    return value


def canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(_stable(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_event_payload(
    *,
    audit_id: str,
    sequence_number: int,
    timestamp: datetime,
    actor: str,
    actor_role: str,
    action: str,
    entity_type: str,
    entity_id: str,
    old_value: Optional[Dict[str, Any]],
    new_value: Optional[Dict[str, Any]],
    reason: Optional[str],
    method_version: str,
    previous_hash: str,
) -> Dict[str, Any]:
    return {
        "audit_id": audit_id,
        "sequence_number": sequence_number,
        "timestamp": _stable(timestamp),
        "actor": actor,
        "actor_role": actor_role,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "old_value": old_value,
        "new_value": new_value,
        "reason": reason,
        "method_version": method_version,
        "previous_hash": previous_hash,
    }


def compute_event_hash(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _get_or_create_chain_state(db: Session, chain_key: str = PRIMARY_CHAIN_KEY) -> AuditChainState:
    stmt = select(AuditChainState).where(AuditChainState.chain_key == chain_key)
    bind = db.get_bind()
    if bind.dialect.name != "sqlite":
        stmt = stmt.with_for_update()
    state = db.execute(stmt).scalar_one_or_none()
    if state:
        return state

    state = AuditChainState(
        chain_key=chain_key,
        last_sequence_number=0,
        last_hash=GENESIS_HASH,
        last_event_id=None,
        updated_at=_utc_now(),
    )
    db.add(state)
    db.flush()
    return state


def append_audit_event(
    db: Session,
    *,
    actor: str,
    actor_role: str,
    action: str,
    entity_type: str,
    entity_id: str,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None,
    method_version: str = METHOD_VERSION,
    chain_key: str = PRIMARY_CHAIN_KEY,
) -> AuditEvent:
    """
    Append one event to the durable audit chain.

    The caller owns the surrounding transaction. PostgreSQL callers lock the chain-state
    row with SELECT FOR UPDATE. SQLite local development relies on the active write
    transaction to serialize updates.
    """
    state = _get_or_create_chain_state(db, chain_key=chain_key)
    sequence_number = state.last_sequence_number + 1
    previous_hash = state.last_hash
    audit_id = f"AUD-PROD-{sequence_number:012d}"
    timestamp = _utc_now()
    event_id = uuid.uuid4()
    payload = canonical_event_payload(
        audit_id=audit_id,
        sequence_number=sequence_number,
        timestamp=timestamp,
        actor=actor,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        reason=reason,
        method_version=method_version,
        previous_hash=previous_hash,
    )
    hash_signature = compute_event_hash(payload)
    event = AuditEvent(
        id=event_id,
        audit_id=audit_id,
        sequence_number=sequence_number,
        timestamp=timestamp,
        actor=actor,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=_stable(old_value) if old_value is not None else None,
        new_value=_stable(new_value) if new_value is not None else None,
        reason=reason,
        method_version=method_version,
        previous_hash=previous_hash,
        hash_signature=hash_signature,
        verification_status="VERIFIED",
        created_at=timestamp,
    )
    db.add(event)
    state.last_sequence_number = sequence_number
    state.last_hash = hash_signature
    state.last_event_id = str(event_id)
    state.updated_at = timestamp
    db.flush()
    return event


def list_audit_events(
    db: Session,
    *,
    page: int = 1,
    limit: int = 50,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    action: Optional[str] = None,
    actor: Optional[str] = None,
    from_timestamp: Optional[datetime] = None,
    to_timestamp: Optional[datetime] = None,
) -> Tuple[int, List[AuditEvent]]:
    conditions = []
    if entity_type:
        conditions.append(AuditEvent.entity_type == entity_type)
    if entity_id:
        conditions.append(AuditEvent.entity_id == entity_id)
    if action:
        conditions.append(AuditEvent.action == action)
    if actor:
        conditions.append(AuditEvent.actor == actor)
    if from_timestamp:
        conditions.append(AuditEvent.timestamp >= from_timestamp)
    if to_timestamp:
        conditions.append(AuditEvent.timestamp <= to_timestamp)

    total = db.scalar(select(func.count()).select_from(AuditEvent).where(*conditions)) or 0
    events = db.execute(
        select(AuditEvent)
        .where(*conditions)
        .order_by(AuditEvent.sequence_number.asc(), AuditEvent.timestamp.asc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).scalars().all()
    return total, events


def event_payload(event: AuditEvent) -> Dict[str, Any]:
    return {
        "id": event.id,
        "audit_id": event.audit_id,
        "sequence_number": event.sequence_number,
        "timestamp": event.timestamp,
        "actor": event.actor,
        "actor_role": event.actor_role,
        "action": event.action,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "old_value": event.old_value,
        "new_value": event.new_value,
        "reason": event.reason,
        "method_version": event.method_version,
        "previous_hash": event.previous_hash,
        "hash_signature": event.hash_signature,
        "verification_status": event.verification_status,
        "created_at": event.created_at,
    }


def _event_hash_payload(event: AuditEvent) -> Dict[str, Any]:
    return canonical_event_payload(
        audit_id=event.audit_id,
        sequence_number=event.sequence_number,
        timestamp=event.timestamp,
        actor=event.actor,
        actor_role=event.actor_role,
        action=event.action,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        old_value=event.old_value,
        new_value=event.new_value,
        reason=event.reason,
        method_version=event.method_version,
        previous_hash=event.previous_hash,
    )


def verify_persistent_audit_chain(db: Session, chain_key: str = PRIMARY_CHAIN_KEY) -> Dict[str, Any]:
    events = db.execute(
        select(AuditEvent).order_by(AuditEvent.sequence_number.asc(), AuditEvent.timestamp.asc())
    ).scalars().all()
    state = db.get(AuditChainState, chain_key)

    previous_hash = GENESIS_HASH
    expected_sequence = 1
    verified = 0
    latest_hash = GENESIS_HASH

    for event in events:
        if event.sequence_number != expected_sequence:
            return {
                "status": "CHAIN_BROKEN",
                "total_events": len(events),
                "verified_events": verified,
                "chain_tip_hash": latest_hash,
                "first_broken_sequence": event.sequence_number,
                "first_broken_event_id": event.audit_id,
                "reason": f"Sequence continuity failed: expected {expected_sequence}, got {event.sequence_number}.",
            }
        if event.previous_hash != previous_hash:
            return {
                "status": "CHAIN_BROKEN",
                "total_events": len(events),
                "verified_events": verified,
                "chain_tip_hash": latest_hash,
                "first_broken_sequence": event.sequence_number,
                "first_broken_event_id": event.audit_id,
                "reason": "Previous hash does not match prior event hash.",
            }
        expected_hash = compute_event_hash(_event_hash_payload(event))
        if event.hash_signature != expected_hash:
            return {
                "status": "CHAIN_BROKEN",
                "total_events": len(events),
                "verified_events": verified,
                "chain_tip_hash": latest_hash,
                "first_broken_sequence": event.sequence_number,
                "first_broken_event_id": event.audit_id,
                "reason": "Hash signature recomputation mismatch.",
            }
        previous_hash = event.hash_signature
        latest_hash = event.hash_signature
        expected_sequence += 1
        verified += 1

    expected_last_sequence = len(events)
    if state:
        if state.last_sequence_number != expected_last_sequence:
            return {
                "status": "CHAIN_BROKEN",
                "total_events": len(events),
                "verified_events": verified,
                "chain_tip_hash": latest_hash,
                "first_broken_sequence": None,
                "first_broken_event_id": None,
                "reason": f"Chain-state sequence tip {state.last_sequence_number} does not match event count {expected_last_sequence}.",
            }
        if state.last_hash != latest_hash:
            return {
                "status": "CHAIN_BROKEN",
                "total_events": len(events),
                "verified_events": verified,
                "chain_tip_hash": latest_hash,
                "first_broken_sequence": state.last_sequence_number,
                "first_broken_event_id": state.last_event_id,
                "reason": "Chain-state hash tip does not match latest event hash.",
            }
    elif events:
        return {
            "status": "CHAIN_BROKEN",
            "total_events": len(events),
            "verified_events": verified,
            "chain_tip_hash": latest_hash,
            "first_broken_sequence": None,
            "first_broken_event_id": None,
            "reason": "Audit events exist but chain-state row is missing.",
        }

    return {
        "status": "CHAIN_INTACT",
        "total_events": len(events),
        "verified_events": verified,
        "chain_tip_hash": latest_hash,
        "first_broken_sequence": None,
        "first_broken_event_id": None,
        "reason": "Persistent audit chain verified successfully.",
    }
