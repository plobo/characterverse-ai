"""Typed REST contracts. OpenAPI generated from these is the source of truth (shared/api-contracts/openapi.json)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, WithJsonSchema
from pydantic.alias_generators import to_camel


def _utc(d: datetime) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%S.") + f"{d.microsecond // 1000:03d}Z"


# All timestamps are UTC, RFC 3339 with millisecond precision, e.g. 2026-11-17T22:41:05.123Z
UtcDateTime = Annotated[
    datetime, PlainSerializer(_utc, return_type=str), WithJsonSchema({"type": "string", "format": "date-time"})
]


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


# ------------------------------------------------------------------ recipe & storyboard documents
class Proportions(ApiModel):
    height: float
    shoulder_width: float
    head_scale: float


class Palette(ApiModel):
    primary: str
    secondary: str
    accent: str


class CharacterRecipe(ApiModel):
    schema_version: int
    name: str
    category: str
    base_model_id: str
    style: str
    proportions: Proportions
    palette: Palette
    modules: list[str]
    powers: list[str]
    personality_traits: list[str]
    voice_profile_id: str
    asset_manifest_version: str


class StoryCharacter(ApiModel):
    character_id: str
    display_name: str
    role: str


class SceneCharacter(ApiModel):
    character_id: str
    position: str
    scale: float
    action_id: str


class DialogueLine(ApiModel):
    character_id: str
    line: str
    start_ms: int


class StoryScene(ApiModel):
    scene_id: str
    sequence: int
    title: str
    description: str | None = None
    duration_ms: int
    environment_id: str
    camera_preset_id: str
    lighting_preset_id: str
    characters: list[SceneCharacter]
    dialogue: list[DialogueLine]
    sound_effect_ids: list[str]
    transition: str


class Storyboard(ApiModel):
    schema_version: int
    title: str
    logline: str
    synopsis: str
    duration_seconds: int
    aspect_ratio: str
    language: str
    characters: list[StoryCharacter]
    music_cue_id: str | None
    scenes: list[StoryScene]


def dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(by_alias=True, exclude_none=False)


# ------------------------------------------------------------------ common
class ErrorDetail(ApiModel):
    code: str
    field: str | None = None
    message: str


class ErrorInfo(ApiModel):
    code: str
    message: str
    details: list[ErrorDetail]
    retryable: bool


class ErrorResponse(ApiModel):
    error: ErrorInfo


class SignedUrl(ApiModel):
    url: str
    expires_at: int


class ModerationFeedback(ApiModel):
    decision: Literal["allow", "flag", "block"]
    reason_code: str | None = None
    feedback: str | None = None


class ProviderMeta(ApiModel):
    name: str
    version: str
    local: bool


# ------------------------------------------------------------------ auth / users
class SessionRequest(ApiModel):
    provider: Literal["dev", "guest", "oidc"]
    token: str | None = Field(default=None, max_length=4096)
    display_name: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=320)


class UserOut(ApiModel):
    id: str
    display_name: str
    email: str | None
    is_guest: bool
    preferences: dict[str, Any]
    created_at: UtcDateTime


class SessionResponse(ApiModel):
    access_token: str
    token_type: str = "Bearer"
    expires_at: int
    user: UserOut


class UpdateMeRequest(ApiModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    preferences: dict[str, Any] | None = None


class UsageOut(ApiModel):
    characters: int
    projects: int
    renders: int
    storage_bytes: int


# ------------------------------------------------------------------ assets
class LicenceOut(ApiModel):
    id: str
    name: str
    licence_url: str
    commercial_use: bool
    attribution_required: bool
    review_status: str
    reviewed_at: str | None
    reviewer: str | None


class AssetOut(ApiModel):
    id: str
    type: str
    name: str
    version: str
    licence_id: str
    commercial_use_approved: bool
    sha256: str
    metadata: dict[str, Any]


class AssetDetailOut(AssetOut):
    licence: LicenceOut


class AssetList(ApiModel):
    items: list[AssetOut]


class CatalogManifestOut(ApiModel):
    manifest_version: str
    manifest: dict[str, Any]
    parts: dict[str, Any]


# ------------------------------------------------------------------ characters
class LineageOut(ApiModel):
    source_character_id: str
    contribution_weight: float
    mix_dimension: str


class CharacterOut(ApiModel):
    id: str
    name: str
    description: str
    category: str
    style: str
    recipe: CharacterRecipe
    version: int
    visibility: str
    is_favorite: bool
    archived: bool
    lineage: list[LineageOut]
    created_at: UtcDateTime
    updated_at: UtcDateTime


class CharacterList(ApiModel):
    items: list[CharacterOut]


class CreateCharacterRequest(ApiModel):
    recipe: CharacterRecipe
    description: str = Field(default="", max_length=1000)


class UpdateCharacterRequest(ApiModel):
    recipe: CharacterRecipe | None = None
    description: str | None = Field(default=None, max_length=1000)
    archived: bool | None = None
    is_favorite: bool | None = None
    expected_version: int | None = None


class CharacterVersionOut(ApiModel):
    version: int
    recipe: CharacterRecipe
    created_at: UtcDateTime


class CharacterVersionList(ApiModel):
    items: list[CharacterVersionOut]


class GenerateRecipeRequest(ApiModel):
    description: str = Field(min_length=1, max_length=1000)
    category: str | None = None
    name: str | None = Field(default=None, max_length=40)


class RecipeWarning(ApiModel):
    code: str
    message: str


class GenerateRecipeResponse(ApiModel):
    recipe: CharacterRecipe
    warnings: list[RecipeWarning]
    moderation: ModerationFeedback
    provider: ProviderMeta


class PreviewRequest(ApiModel):
    recipe: CharacterRecipe


class PreviewOut(ApiModel):
    recipe_hash: str
    cached: bool
    glb_url: str
    thumbnail_url: str
    expires_at: int


# ------------------------------------------------------------------ mixer
class MixRequest(ApiModel):
    source_character_ids: list[str] = Field(min_length=2, max_length=3)
    dimensions: list[Literal["appearance", "powers", "personality", "voice", "all"]] = Field(min_length=1)
    weights: dict[str, float] | None = None
    name: str | None = Field(default=None, max_length=40)
    intent: str | None = Field(default=None, max_length=300)


class MixLineage(ApiModel):
    source_character_id: str
    weight: float
    dimensions: list[str]


class OmittedTrait(ApiModel):
    id: str
    kind: str
    reason: str


class FusionSuggestion(ApiModel):
    name: str
    tagline: str


class MixPreviewOut(ApiModel):
    recipe: CharacterRecipe
    lineage: list[MixLineage]
    omitted: list[OmittedTrait]
    warnings: list[RecipeWarning]
    dominant_source_id: str
    suggestions: list[FusionSuggestion]


class MixOut(ApiModel):
    id: str
    character: CharacterOut | None
    result: MixPreviewOut
    created_at: UtcDateTime


# ------------------------------------------------------------------ stories / projects
class GenerateStoryRequest(ApiModel):
    prompt: str = Field(default="", max_length=600)
    character_ids: list[str] = Field(min_length=1, max_length=4)
    template_id: str | None = None
    title: str | None = Field(default=None, max_length=80)
    genre: str | None = Field(default=None, max_length=30)
    tone: str | None = Field(default=None, max_length=30)
    audience: str | None = Field(default=None, max_length=30)
    duration_seconds: Literal[15, 30, 60] = 30
    aspect_ratio: Literal["16:9", "9:16"] = "16:9"
    language: str = Field(default="en", max_length=8)


class GenerateStoryResponse(ApiModel):
    storyboard: Storyboard
    moderation: ModerationFeedback
    provider: ProviderMeta
    cached: bool


class CreateProjectRequest(ApiModel):
    title: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=1000)
    storyboard: Storyboard | None = None


class UpdateProjectRequest(ApiModel):
    title: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=1000)
    status: Literal["draft", "ready", "archived"] | None = None


class StoryboardRequest(ApiModel):
    storyboard: Storyboard


class ScenePatch(ApiModel):
    title: str | None = None
    description: str | None = None
    duration_ms: int | None = None
    environment_id: str | None = None
    camera_preset_id: str | None = None
    lighting_preset_id: str | None = None
    characters: list[SceneCharacter] | None = None
    dialogue: list[DialogueLine] | None = None
    sound_effect_ids: list[str] | None = None
    transition: str | None = None


class ProjectOut(ApiModel):
    id: str
    title: str
    description: str
    status: str
    version: int
    storyboard: Storyboard | None
    created_at: UtcDateTime
    updated_at: UtcDateTime


class ProjectList(ApiModel):
    items: list[ProjectOut]


# ------------------------------------------------------------------ renders
class CreateRenderRequest(ApiModel):
    quality: Literal["draft", "final"] = "draft"
    aspect_ratio: Literal["16:9", "9:16"] | None = None


class RenderJobOut(ApiModel):
    id: str
    project_id: str
    project_title: str | None
    status: Literal["queued", "processing", "completed", "failed", "cancelled"]
    progress_stage: str
    progress_percent: int
    quality: str
    aspect_ratio: str
    width: int
    height: int
    error_code: str | None
    attempts: int
    cancel_requested: bool
    duration_ms: int | None
    created_at: UtcDateTime
    started_at: UtcDateTime | None
    completed_at: UtcDateTime | None


class RenderJobList(ApiModel):
    items: list[RenderJobOut]


class DownloadUrlOut(ApiModel):
    url: str
    thumbnail_url: str | None
    expires_at: int
    mime_type: str
    file_size: int


# ------------------------------------------------------------------ uploads / moderation
class PresignRequest(ApiModel):
    file_name: str = Field(min_length=1, max_length=200)
    mime_type: Literal["image/png", "image/jpeg", "audio/wav", "audio/mpeg"]
    file_size: int = Field(gt=0)
    purpose: Literal["reference_image", "custom_audio"]
    rights_confirmed: bool


class PresignOut(ApiModel):
    asset_id: str
    upload_url: str
    method: str
    headers: dict[str, str]
    expires_at: int


class ModerationCheckRequest(ApiModel):
    text: str = Field(max_length=4000)
    content_type: Literal["character_prompt", "story_prompt", "dialogue", "name", "other"] = "other"


class ReportRequest(ApiModel):
    content_type: Literal["character", "project", "render", "other"]
    content_id: str = Field(min_length=1, max_length=80)
    reason: Literal["copyright", "trademark", "offensive", "impersonation", "other"]
    details: str = Field(default="", max_length=2000)


class ReportOut(ApiModel):
    id: str
    status: str
    created_at: UtcDateTime
