from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import require_roles
from app.db.models import TaxonomyNode
from app.db.session import get_db
from app.services.auth import AuthenticatedUser
from app.services.ps_completion import create_taxonomy_node, taxonomy_payload, validate_against_taxonomy
from app.services.persistent_audit import append_audit_event

router = APIRouter(prefix="/taxonomy", tags=["Taxonomy Governance"])


@router.get("/nodes")
async def list_taxonomy_nodes(db: Session = Depends(get_db)):
    nodes = db.execute(
        select(TaxonomyNode)
        .options(selectinload(TaxonomyNode.attributes))
        .order_by(TaxonomyNode.category.asc(), TaxonomyNode.version.desc())
    ).scalars().all()
    return {"status": "success", "count": len(nodes), "items": [taxonomy_payload(node) for node in nodes]}


@router.post("/nodes")
async def create_node(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN")),
):
    node = create_taxonomy_node(db, payload, current_user)
    return {"status": "success", "item": taxonomy_payload(node)}


@router.patch("/nodes/{node_id}")
async def update_node(
    node_id: UUID,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN")),
):
    node = db.execute(
        select(TaxonomyNode).options(selectinload(TaxonomyNode.attributes)).where(TaxonomyNode.id == node_id)
    ).scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Taxonomy node not found.")
    before = taxonomy_payload(node)
    if "display_name" in payload:
        node.display_name = payload["display_name"]
    if "allowed_units" in payload:
        node.allowed_units = payload["allowed_units"]
    if "lifecycle_status" in payload:
        node.lifecycle_status = payload["lifecycle_status"]
    node.version = int(payload.get("version") or node.version + 1)
    append_audit_event(
        db,
        actor=current_user.display_name,
        actor_role="ADMIN",
        action="TAXONOMY_NODE_UPDATED",
        entity_type="taxonomy_node",
        entity_id=str(node.id),
        old_value=before,
        new_value=taxonomy_payload(node),
        reason="Governed taxonomy node updated.",
    )
    db.commit()
    db.refresh(node)
    return {"status": "success", "item": taxonomy_payload(node)}


@router.post("/nodes/{node_id}/deprecate")
async def deprecate_node(
    node_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN")),
):
    node = db.get(TaxonomyNode, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Taxonomy node not found.")
    before = {"lifecycle_status": node.lifecycle_status}
    node.lifecycle_status = "DEPRECATED"
    append_audit_event(
        db,
        actor=current_user.display_name,
        actor_role="ADMIN",
        action="TAXONOMY_NODE_DEPRECATED",
        entity_type="taxonomy_node",
        entity_id=str(node.id),
        old_value=before,
        new_value={"lifecycle_status": node.lifecycle_status},
        reason="Governed taxonomy node deprecated.",
    )
    db.commit()
    return {"status": "success", "id": str(node.id), "lifecycle_status": node.lifecycle_status}


@router.post("/validate")
async def validate_material_against_taxonomy(payload: dict = Body(...), db: Session = Depends(get_db)):
    return {
        "status": "success",
        "validation": validate_against_taxonomy(
            db,
            category=payload.get("category") or "UNASSIGNED",
            uom=payload.get("uom") or "EA",
            attributes=payload.get("attributes") or {},
        ),
    }
