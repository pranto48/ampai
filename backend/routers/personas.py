"""Personas router: CRUD for chat personas."""

from __future__ import annotations

from core.deps import UserContext, require_authenticated_user
from core.models import PersonaCreateRequest, PersonaUpdateRequest
from database import create_persona, delete_persona, list_personas, update_persona
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/api/personas", tags=["personas"])


@router.get("")
def api_list_personas(user: UserContext = Depends(require_authenticated_user)):
    personas = list_personas(user.username, include_global=True)
    return {"personas": personas}


@router.post("")
def api_create_persona(
    request: PersonaCreateRequest,
    user: UserContext = Depends(require_authenticated_user),
):
    owner_username = (
        None
        if (getattr(request, "is_global", False) and user.role == "admin")
        else user.username
    )
    persona = create_persona(
        username=owner_username,
        name=request.name,
        system_prompt=request.system_prompt,
        tags=request.tags or "",
        is_default=bool(request.is_default),
    )
    if not persona:
        raise HTTPException(status_code=500, detail="Failed to create persona")
    return persona


@router.patch("/{persona_id}")
def api_update_persona(
    persona_id: int,
    request: PersonaUpdateRequest,
    user: UserContext = Depends(require_authenticated_user),
):
    updated = update_persona(
        persona_id=persona_id,
        actor_username=user.username,
        is_admin=(user.role == "admin"),
        updates=request.model_dump(exclude_none=True),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Persona not found or not editable")
    return updated


@router.delete("/{persona_id}")
def api_delete_persona(
    persona_id: int, user: UserContext = Depends(require_authenticated_user)
):
    deleted = delete_persona(
        persona_id=persona_id,
        actor_username=user.username,
        is_admin=(user.role == "admin"),
    )
    if not deleted:
        raise HTTPException(
            status_code=404, detail="Persona not found or not deletable"
        )
    return {"status": "success"}
