package com.characterverse.data.dto

import com.characterverse.domain.model.CharacterRecipe
import com.characterverse.domain.model.CharacterSummary
import com.characterverse.domain.model.Project
import com.characterverse.domain.model.RenderJob
import com.characterverse.domain.model.Storyboard
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

// Wire DTOs (shared/api-contracts/openapi.json), separate from domain models.

@Serializable data class UserDto(val id: String, val displayName: String, val email: String? = null, val isGuest: Boolean, val createdAt: String)
@Serializable data class SessionRequestDto(val provider: String, val token: String? = null, val displayName: String? = null)
@Serializable
data class SessionResponseDto(
    val accessToken: String, val tokenType: String, val expiresAt: Long, val refreshToken: String, val refreshExpiresAt: Long, val user: UserDto,
)
@Serializable data class RefreshRequestDto(val refreshToken: String)
@Serializable data class UsageDto(val characters: Int, val projects: Int, val renders: Int, val storageBytes: Long)

@Serializable data class LineageDto(val sourceCharacterId: String, val contributionWeight: Double, val mixDimension: String)

@Serializable
data class CharacterDto(
    val id: String, val name: String, val description: String, val category: String, val style: String, val recipe: CharacterRecipe,
    val version: Int, val visibility: String, val isFavorite: Boolean, val archived: Boolean, val lineage: List<LineageDto>,
    val createdAt: String, val updatedAt: String,
) {
    fun toDomain() = CharacterSummary(id, name, description, category, recipe, version, isFavorite, archived,
        lineage.map { CharacterSummary.Lineage(it.sourceCharacterId, it.contributionWeight, it.mixDimension) }, createdAt, updatedAt)
}

@Serializable data class ItemsDto<T>(val items: List<T>)
@Serializable data class CreateCharacterDto(val recipe: CharacterRecipe, val description: String = "")
@Serializable
data class UpdateCharacterDto(
    val recipe: CharacterRecipe? = null, val description: String? = null, val archived: Boolean? = null,
    val isFavorite: Boolean? = null, val expectedVersion: Int? = null,
)
@Serializable data class GenerateRecipeRequestDto(val description: String, val category: String? = null, val name: String? = null)
@Serializable data class WarningDto(val code: String, val message: String)
@Serializable data class ModerationDto(val decision: String, val reasonCode: String? = null, val feedback: String? = null)
@Serializable data class ProviderDto(val name: String, val version: String, val local: Boolean)
@Serializable data class GenerateRecipeResponseDto(val recipe: CharacterRecipe, val warnings: List<WarningDto>, val moderation: ModerationDto, val provider: ProviderDto)

@Serializable data class MixRequestDto(val sourceCharacterIds: List<String>, val dimensions: List<String>, val weights: Map<String, Double>? = null, val name: String? = null)
@Serializable data class OmittedDto(val id: String, val kind: String, val reason: String)
@Serializable data class MixLineageDto(val sourceCharacterId: String, val weight: Double, val dimensions: List<String>)
@Serializable data class SuggestionDto(val name: String, val tagline: String)
@Serializable
data class MixPreviewDto(
    val recipe: CharacterRecipe, val lineage: List<MixLineageDto>, val omitted: List<OmittedDto>, val warnings: List<WarningDto>,
    val dominantSourceId: String, val suggestions: List<SuggestionDto>,
)
@Serializable data class MixDto(val id: String, val character: CharacterDto? = null, val result: MixPreviewDto, val createdAt: String)

@Serializable
data class GenerateStoryRequestDto(
    val prompt: String, val characterIds: List<String>, val templateId: String? = null, val title: String? = null, val genre: String? = null,
    val tone: String? = null, val audience: String? = null, val durationSeconds: Int = 30, val aspectRatio: String = "16:9", val language: String = "en",
)
@Serializable data class GenerateStoryResponseDto(val storyboard: Storyboard, val moderation: ModerationDto, val provider: ProviderDto, val cached: Boolean)

@Serializable
data class ProjectDto(
    val id: String, val title: String, val description: String, val status: String, val version: Int, val storyboard: Storyboard? = null,
    val createdAt: String, val updatedAt: String,
) {
    fun toDomain() = Project(id, title, description, status, version, storyboard, updatedAt)
}
@Serializable data class CreateProjectDto(val title: String, val description: String = "", val storyboard: Storyboard? = null)
@Serializable data class StoryboardRequestDto(val storyboard: Storyboard)
@Serializable data class CreateRenderDto(val quality: String, val aspectRatio: String? = null)

@Serializable
data class RenderJobDto(
    val id: String, val projectId: String, val projectTitle: String? = null, val status: String, val progressStage: String, val progressPercent: Int,
    val quality: String, val aspectRatio: String, val width: Int, val height: Int, val errorCode: String? = null, val attempts: Int,
    val cancelRequested: Boolean, val durationMs: Int? = null, val createdAt: String, val startedAt: String? = null, val completedAt: String? = null,
) {
    fun toDomain() = RenderJob(id, projectId, projectTitle,
        runCatching { RenderJob.Status.valueOf(status.uppercase()) }.getOrDefault(RenderJob.Status.FAILED),
        progressStage, progressPercent, quality, aspectRatio, errorCode, attempts, cancelRequested, durationMs, createdAt)
}
@Serializable data class DownloadUrlDto(val url: String, val thumbnailUrl: String? = null, val expiresAt: Long, val mimeType: String, val fileSize: Long)
@Serializable data class ModerationCheckDto(val text: String, val contentType: String)
@Serializable data class ReportDto(val contentType: String, val contentId: String, val reason: String, val details: String = "")
@Serializable data class ReportResponseDto(val id: String, val status: String, val createdAt: String)

@Serializable data class ErrorDetailDto(val code: String, val field: String? = null, val message: String)
@Serializable data class ErrorBodyDto(val code: String, val message: String, val details: List<ErrorDetailDto>, val retryable: Boolean)
@Serializable data class ErrorEnvelopeDto(val error: ErrorBodyDto)

typealias ExportDto = Map<String, JsonElement>
