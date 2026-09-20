from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.schemas import (
    DraftFromCandidateResponse,
    NationalMaterialDetailResponse,
    NationalMaterialDraftResponse,
    SourceMappingResponse,
)
from app.services.national_material_registry import (
    create_draft_from_candidate,
    get_national_by_code,
    get_source_mappings,
    mapping_payloads,
)
from app.services.auth import AuthenticatedUser

router = APIRouter(tags=["National Material Registry"])


@router.post("/national-materials/draft-from-candidate/{candidate_id}", response_model=DraftFromCandidateResponse)
async def draft_from_candidate(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "CPSE_USER")),
):
    try:
        national, mappings, idempotent_replay = create_draft_from_candidate(db, candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if national is None:
        raise HTTPException(status_code=404, detail=f"Match candidate '{candidate_id}' not found.")

    return DraftFromCandidateResponse(
        idempotent_replay=idempotent_replay,
        national_material=NationalMaterialDraftResponse.model_validate(national),
        mappings=[SourceMappingResponse(**payload) for payload in mapping_payloads(mappings, national)],
    )


@router.get("/national-materials/{national_material_code}", response_model=NationalMaterialDetailResponse)
async def get_national_material(national_material_code: str, db: Session = Depends(get_db)):
    national = get_national_by_code(db, national_material_code)
    if not national:
        raise HTTPException(status_code=404, detail=f"National material code '{national_material_code}' not found.")

    return NationalMaterialDetailResponse(
        national_material=NationalMaterialDraftResponse.model_validate(national),
        mappings=[SourceMappingResponse(**payload) for payload in mapping_payloads(list(national.mappings), national)],
    )


@router.get("/mappings/source/{source_material_id}", response_model=list[SourceMappingResponse])
async def get_mappings_for_source(
    source_material_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles("ADMIN", "CPSE_USER")),
):
    found, mappings = get_source_mappings(db, source_material_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"Source material '{source_material_id}' not found.")
    return [SourceMappingResponse(**payload) for payload in mapping_payloads(mappings)]
