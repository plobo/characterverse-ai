from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.characters import character_out, checked_recipe, save_new_character
from app.api.deps import audit, current_user, get_container, get_owned, get_session, moderate, rate_limit
from app.core.container import Container
from app.domain.models import Character, CharacterLineage, Mix, User
from app.schemas.api import MixOut, MixPreviewOut, MixRequest
from app.services.mixer import resolve_mix
from app.services.recipes import validate_recipe

router = APIRouter(prefix="/v1", tags=["mixer"])


def _preview(body: MixRequest, user: User, container: Container, session: Session) -> dict:
    rate_limit(container, user, "generate")
    if body.intent:
        moderate(container, session, user, body.intent, "character_prompt")
    sources = [get_owned(session, Character, cid, user) for cid in body.source_character_ids]  # ownership
    result = resolve_mix(
        [{"id": str(c.id), "recipe": c.recipe_json} for c in sources],
        body.weights,
        list(body.dimensions),
        container.catalog,
        body.name,
    )
    validate_recipe(result["recipe"], container.catalog, container.settings.shared_dir)
    traits = [t for c in sources for t in c.recipe_json["personalityTraits"]]
    result["suggestions"] = container.text_provider.fusion_suggestions([c.name for c in sources], traits)
    return result


@router.post("/mixes/preview", response_model=MixPreviewOut)
def preview_mix(
    body: MixRequest,
    user: User = Depends(current_user),
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
) -> MixPreviewOut:
    """Deterministic fusion preview. Nothing is saved."""
    return MixPreviewOut(**_preview(body, user, container, session))


@router.post("/mixes", response_model=MixOut, status_code=201)
def create_mix(
    body: MixRequest,
    user: User = Depends(current_user),
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
) -> MixOut:
    """Save the fusion as a new character with source lineage."""
    result = _preview(body, user, container, session)
    recipe = checked_recipe(container, session, user, result["recipe"])
    character = save_new_character(session, user, recipe, f"Fusion of {len(body.source_character_ids)} characters")
    for li in result["lineage"]:
        session.add(
            CharacterLineage(
                character_id=character.id,
                source_character_id=uuid.UUID(li["sourceCharacterId"]),
                contribution_weight=li["weight"],
                mix_dimension=",".join(li["dimensions"]),
            )
        )
    mix = Mix(
        owner_user_id=user.id,
        result_character_id=character.id,
        request_json=body.model_dump(by_alias=True),
        result_json=result,
    )
    session.add(mix)
    session.flush()
    audit(session, user, "mix.created", "mix", mix.id, character=str(character.id))
    session.commit()
    return MixOut(id=str(mix.id), character=character_out(session, character), result=result, created_at=mix.created_at)


@router.get("/mixes/{mix_id}", response_model=MixOut)
def get_mix(mix_id: str, user: User = Depends(current_user), session: Session = Depends(get_session)) -> MixOut:
    mix = get_owned(session, Mix, mix_id, user)
    character = session.get(Character, mix.result_character_id) if mix.result_character_id else None
    alive = character is not None and character.deleted_at is None
    return MixOut(
        id=str(mix.id),
        character=character_out(session, character) if alive else None,
        result=mix.result_json,
        created_at=mix.created_at,
    )
