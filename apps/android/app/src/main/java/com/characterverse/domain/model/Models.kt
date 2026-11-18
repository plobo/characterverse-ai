package com.characterverse.domain.model

import kotlinx.serialization.Serializable

/** Versioned character recipe (shared/json-schemas/character_recipe.v1.schema.json). */
@Serializable
data class CharacterRecipe(
    val schemaVersion: Int,
    val name: String,
    val category: String,
    val baseModelId: String,
    val style: String,
    val proportions: Proportions,
    val palette: Palette,
    val modules: List<String>,
    val powers: List<String>,
    val personalityTraits: List<String>,
    val voiceProfileId: String,
    val assetManifestVersion: String,
) {
    @Serializable
    data class Proportions(val height: Double, val shoulderWidth: Double, val headScale: Double)

    @Serializable
    data class Palette(val primary: String, val secondary: String, val accent: String)
}

enum class CharacterCategory(val id: String) {
    HERO("hero"), VILLAIN("villain"), CARTOON("cartoon"), FANTASY("fantasy"), ROBOT("robot"), ALIEN("alien"), CREATURE("creature");

    val title get() = id.replaceFirstChar { it.uppercase() }
}

data class CharacterSummary(
    val id: String,
    val name: String,
    val description: String,
    val category: String,
    val recipe: CharacterRecipe,
    val version: Int,
    val isFavorite: Boolean,
    val archived: Boolean,
    val lineage: List<Lineage>,
    val createdAt: String,
    val updatedAt: String,
) {
    data class Lineage(val sourceCharacterId: String, val contributionWeight: Double, val mixDimension: String)
}

/** Versioned storyboard document (shared/json-schemas/storyboard.v1.schema.json). */
@Serializable
data class Storyboard(
    val schemaVersion: Int,
    val title: String,
    val logline: String,
    val synopsis: String,
    val durationSeconds: Int,
    val aspectRatio: String,
    val language: String,
    val characters: List<CastMember>,
    val musicCueId: String?,
    val scenes: List<Scene>,
) {
    @Serializable data class CastMember(val characterId: String, val displayName: String, val role: String)
    @Serializable data class SceneCharacter(val characterId: String, val position: String, val scale: Double, val actionId: String)
    @Serializable data class DialogueLine(val characterId: String, val line: String, val startMs: Int)

    @Serializable
    data class Scene(
        val sceneId: String,
        val sequence: Int,
        val title: String,
        val description: String? = null,
        val durationMs: Int,
        val environmentId: String,
        val cameraPresetId: String,
        val lightingPresetId: String,
        val characters: List<SceneCharacter>,
        val dialogue: List<DialogueLine>,
        val soundEffectIds: List<String>,
        val transition: String,
    )

    val totalDurationMs get() = scenes.sumOf { it.durationMs }

    /** Renumbers scenes 1..n after reorder/add/delete. */
    fun renumbered() = copy(scenes = scenes.mapIndexed { i, s -> s.copy(sequence = i + 1) })
}

data class Project(
    val id: String, val title: String, val description: String, val status: String, val version: Int,
    val storyboard: Storyboard?, val updatedAt: String,
)

data class RenderJob(
    val id: String, val projectId: String, val projectTitle: String?, val status: Status, val progressStage: String,
    val progressPercent: Int, val quality: String, val aspectRatio: String, val errorCode: String?, val attempts: Int,
    val cancelRequested: Boolean, val durationMs: Int?, val createdAt: String,
) {
    enum class Status { QUEUED, PROCESSING, COMPLETED, FAILED, CANCELLED }

    val isActive get() = status == Status.QUEUED || status == Status.PROCESSING

    /** Never invents a completion time (plan §4.2). Same labels as iOS. */
    val stageLabel get() = when (progressStage) {
        "queued" -> "Waiting in queue"
        "preparing" -> "Preparing scene"
        "rendering_scenes" -> "Rendering scenes"
        "composing" -> "Composing audio & video"
        "uploading" -> "Uploading"
        "completed" -> "Ready"
        "cancelled" -> "Cancelled"
        else -> "Failed"
    }
}

data class MixResult(
    val recipe: CharacterRecipe,
    val lineage: List<LineageEntry>,
    val omitted: List<Omitted>,
    val warningCodes: List<String>,
    val dominantSourceId: String,
) {
    data class Omitted(val id: String, val kind: String, val reason: String)
    data class LineageEntry(val sourceCharacterId: String, val weight: Double, val dimensions: List<String>)
}

fun String.humanized() = replace('_', ' ').split(' ').joinToString(" ") { w -> w.replaceFirstChar { it.uppercase() } }
