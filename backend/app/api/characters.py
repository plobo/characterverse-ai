from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    audit,
    current_user,
    feedback_for,
    get_container,
    get_owned,
    get_session,
    moderate,
    rate_limit,
)
from app.core.container import Container
from app.core.db import utcnow
from app.core.errors import AppError
from app.domain.models import Character, CharacterLineage, CharacterVersion, User
from app.schemas.api import (
    CharacterList,
    CharacterOut,
    CharacterVersionList,
    CharacterVersionOut,
    CreateCharacterRequest,
    GenerateRecipeRequest,
    GenerateRecipeResponse,
    LineageOut,
    PreviewOut,
    PreviewRequest,
    UpdateCharacterRequest,
    dump,
)
from app.services.previews import ensure_preview, recipe_hash
from app.services.recipes import normalized_recipe, recipe_issues, validate_recipe

router = APIRouter(prefix="/v1", tags=["characters"])


def character_out(session: Session, c: Character) -> CharacterOut:
    lineage = session.scalars(select(CharacterLineage).where(CharacterLineage.character_id == c.id)).all()
    return CharacterOut(
        id=str(c.id),
        name=c.name,
        description=c.description,
        category=c.category,
        style=c.style,
        recipe=c.recipe_json,
        version=c.version,
        visibility=c.visibility,
        is_favorite=c.is_favorite,
        archived=c.archived,
        created_at=c.created_at,
        updated_at=c.updated_at,
        lineage=[
            LineageOut(
                source_character_id=str(li.source_character_id),
                contribution_weight=li.contribution_weight,
                mix_dimension=li.mix_dimension,
            )
            for li in lineage
        ],
    )


def checked_recipe(container: Container, session: Session, user: User, recipe: dict) -> dict:
    validate_recipe(recipe, container.catalog, container.settings.shared_dir)
    moderate(container, session, user, recipe["name"], "name")
    return normalized_recipe(recipe)


def save_new_character(session: Session, user: User, recipe: dict, description: str) -> Character:
    c = Character(
        owner_user_id=user.id,
        name=recipe["name"],
        description=description,
        category=recipe["category"],
        style=recipe["style"],
        recipe_json=recipe,
        recipe_hash=recipe_hash(recipe),
        version=1,
    )
    session.add(c)
    session.flush()
    session.add(CharacterVersion(character_id=c.id, version=1, recipe_json=recipe))
    return c


@router.get("/characters", response_model=CharacterList)
def list_characters(
    search: str | None = Query(default=None, max_length=80),
    category: str | None = None,
    sort: str = Query(default="updated", pattern="^(updated|created|name)$"),
    include_archived: bool = Query(default=False, alias="includeArchived"),
    favorites: bool = False,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> CharacterList:
    q = select(Character).where(Character.owner_user_id == user.id, Character.deleted_at.is_(None))
    if not include_archived:
        q = q.where(Character.archived.is_(False))
    if category:
        q = q.where(Character.category == category)
    if favorites:
        q = q.where(Character.is_favorite.is_(True))
    if search:
        q = q.where(Character.name.ilike(f"%{search}%"))
    order = {
        "updated": Character.updated_at.desc(),
        "created": Character.created_at.desc(),
        "name": Character.name.asc(),
    }[sort]
    return CharacterList(items=[character_out(session, c) for c in session.scalars(q.order_by(order))])


@router.post("/characters", response_model=CharacterOut, status_code=201)
def create_character(
    body: CreateCharacterRequest,
    user: User = Depends(current_user),
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
) -> CharacterOut:
    recipe = checked_recipe(container, session, user, dump(body.recipe))
    if body.description:
        moderate(container, session, user, body.description, "character_prompt")
    c = save_new_character(session, user, recipe, body.description)
    audit(session, user, "character.created", "character", c.id)
    session.commit()
    return character_out(session, c)


@router.post("/characters/generate-recipe", response_model=GenerateRecipeResponse)
def generate_recipe(
    body: GenerateRecipeRequest,
    user: User = Depends(current_user),
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
) -> GenerateRecipeResponse:
    """Prompt -> moderation -> structured recipe (LLM) -> schema + registry validation -> compatibility resolver."""
    rate_limit(container, user, "generate")
    mod = moderate(container, session, user, f"{body.name or ''} {body.description}", "character_prompt")
    cat = container.catalog
    if body.category and body.category not in cat.categories:
        raise AppError("VALIDATION_FAILED", "Unknown category")
    vocab = {
        "personalityTraits": cat.personality_traits,
        "manifestVersion": cat.manifest_version,
        "voiceProfiles": [v.id for v in cat.of_type("voice_profile")],
    }
    hints = {"category": body.category, "name": body.name}
    if body.category:
        from app.services.ai.mock_text import BASE_BY_CATEGORY

        hints["baseModelId"] = BASE_BY_CATEGORY[body.category]
    recipe = container.text_provider.character_recipe(body.description, hints, vocab)
    recipe, warnings = resolve_compatibility(container, recipe)
    validate_recipe(recipe, cat, container.settings.shared_dir)
    audit(session, user, "recipe.generated", "recipe", None, provider=container.text_provider.info.name)
    session.commit()
    info = container.text_provider.info
    return GenerateRecipeResponse(
        recipe=recipe,
        warnings=warnings,
        moderation=feedback_for(mod),
        provider={"name": info.name, "version": info.version, "local": info.local},
    )


def resolve_compatibility(container: Container, recipe: dict) -> tuple[dict, list[dict]]:
    """Drop parts an LLM proposed that the chosen rig cannot use, instead of failing the whole generation."""
    cat = container.catalog
    rig = cat.rig_of(recipe["baseModelId"])
    warnings: list[dict] = []
    modules, slots = [], set()
    for m in recipe["modules"]:
        asset = cat.get(m, "module")
        if not asset or not asset.approved or rig not in asset.data["rigs"] or asset.data["slot"] in slots:
            warnings.append({"code": "MODULE_DROPPED", "message": f"{m} is not compatible and was left out"})
            continue
        if len(modules) >= 6:
            warnings.append({"code": "MODULE_DROPPED", "message": f"{m} exceeds the module limit"})
            continue
        modules.append(m)
        slots.add(asset.data["slot"])
    powers = []
    for p in recipe["powers"]:
        asset = cat.get(p, "power_effect")
        if not asset or not asset.approved or rig not in asset.data["rigs"] or len(powers) >= 3:
            warnings.append({"code": "POWER_DROPPED", "message": f"{p} is not supported here and was left out"})
            continue
        powers.append(p)
    base = cat.get(recipe["baseModelId"], "base_model")
    if base and recipe["category"] not in base.data["categories"]:
        recipe["category"] = base.data["categories"][0]
    return {**recipe, "modules": modules, "powers": powers}, warnings


@router.post("/previews", response_model=PreviewOut)
def preview_recipe(
    body: PreviewRequest,
    user: User = Depends(current_user),
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
) -> PreviewOut:
    """Assemble a preview GLB + thumbnail for an unsaved recipe (cached by recipe hash)."""
    recipe = normalized_recipe(validate_recipe(dump(body.recipe), container.catalog, container.settings.shared_dir))
    return PreviewOut(**ensure_preview(container, session, recipe, user.id))


@router.get("/characters/{character_id}", response_model=CharacterOut)
def get_character(
    character_id: str, user: User = Depends(current_user), session: Session = Depends(get_session)
) -> CharacterOut:
    return character_out(session, get_owned(session, Character, character_id, user))


@router.patch("/characters/{character_id}", response_model=CharacterOut)
def update_character(
    character_id: str,
    body: UpdateCharacterRequest,
    user: User = Depends(current_user),
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
) -> CharacterOut:
    c = get_owned(session, Character, character_id, user)
    if body.expected_version is not None and body.expected_version != c.version:
        raise AppError("IDEMPOTENCY_CONFLICT", "Character was changed elsewhere; reload and try again")
    if body.recipe is not None:
        recipe = checked_recipe(container, session, user, dump(body.recipe))
        if recipe != c.recipe_json:
            c.version += 1
            c.recipe_json, c.recipe_hash = recipe, recipe_hash(recipe)
            c.name, c.category, c.style = recipe["name"], recipe["category"], recipe["style"]
            session.add(CharacterVersion(character_id=c.id, version=c.version, recipe_json=recipe))
    if body.description is not None:
        if body.description:
            moderate(container, session, user, body.description, "character_prompt")
        c.description = body.description
    if body.archived is not None:
        c.archived = body.archived
    if body.is_favorite is not None:
        c.is_favorite = body.is_favorite
    c.updated_at = utcnow()
    audit(session, user, "character.updated", "character", c.id, version=c.version)
    session.commit()
    return character_out(session, c)


@router.delete("/characters/{character_id}", status_code=204)
def delete_character(
    character_id: str, user: User = Depends(current_user), session: Session = Depends(get_session)
) -> Response:
    c = get_owned(session, Character, character_id, user)
    c.deleted_at = utcnow()
    audit(session, user, "character.deleted", "character", c.id)
    session.commit()
    return Response(status_code=204)


@router.post("/characters/{character_id}/duplicate", response_model=CharacterOut, status_code=201)
def duplicate_character(
    character_id: str, user: User = Depends(current_user), session: Session = Depends(get_session)
) -> CharacterOut:
    src = get_owned(session, Character, character_id, user)
    name = f"{src.name} Copy"[:40]
    copy = save_new_character(session, user, {**src.recipe_json, "name": name}, src.description)
    audit(session, user, "character.duplicated", "character", copy.id, source=str(src.id))
    session.commit()
    return character_out(session, copy)


@router.get("/characters/{character_id}/versions", response_model=CharacterVersionList)
def character_versions(
    character_id: str, user: User = Depends(current_user), session: Session = Depends(get_session)
) -> CharacterVersionList:
    c = get_owned(session, Character, character_id, user)
    rows = session.scalars(
        select(CharacterVersion).where(CharacterVersion.character_id == c.id).order_by(CharacterVersion.version.desc())
    )
    return CharacterVersionList(
        items=[CharacterVersionOut(version=r.version, recipe=r.recipe_json, created_at=r.created_at) for r in rows]
    )


@router.post("/characters/{character_id}/preview", response_model=PreviewOut)
def preview_character(
    character_id: str,
    user: User = Depends(current_user),
    container: Container = Depends(get_container),
    session: Session = Depends(get_session),
) -> PreviewOut:
    c = get_owned(session, Character, character_id, user)
    if recipe_issues(c.recipe_json, container.catalog, container.settings.shared_dir):
        raise AppError("RECIPE_INVALID", "This character uses assets that are no longer available")
    return PreviewOut(**ensure_preview(container, session, c.recipe_json, user.id))
