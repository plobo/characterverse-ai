package com.characterverse.domain.model

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

@Serializable
data class AssetManifest(
    val manifestVersion: String,
    val licences: List<Licence>,
    val categories: List<String>,
    val styles: List<String>,
    val rigs: List<String>,
    val baseModels: List<BaseModel>,
    val modules: List<Module>,
    val powers: List<Power>,
    val personalityTraits: List<String>,
    val voiceProfiles: List<Voice>,
    val animationClips: List<Clip>,
    val environments: List<Environment>,
    val cameraPresets: List<Preset>,
    val lightingPresets: List<Preset>,
    val soundEffects: List<Preset>,
    val musicCues: List<Music>,
    val storyTemplates: List<StoryTemplate>,
    val characterTemplates: List<CharacterTemplate>,
) {
    @Serializable data class Licence(val id: String, val name: String, val commercialUse: Boolean, val reviewStatus: String)
    @Serializable data class BaseModel(val id: String, val name: String, val rig: String, val categories: List<String>, val licenceId: String)
    @Serializable data class Module(val id: String, val name: String, val slot: String, val rigs: List<String>, val priority: Int, val licenceId: String)
    @Serializable data class Power(val id: String, val name: String, val rigs: List<String>, val effectColor: String)
    @Serializable data class Voice(val id: String, val name: String, val provider: String, val baseHz: Double, val licenceId: String)
    @Serializable data class Clip(val id: String, val rigs: List<String>, val motion: String, val licenceId: String)
    @Serializable data class Environment(val id: String, val name: String, val skyTop: String, val skyBottom: String, val ground: String, val licenceId: String)
    @Serializable data class Preset(val id: String, val licenceId: String)
    @Serializable data class Music(val id: String, val bpm: Int, val scale: String, val licenceId: String)
    @Serializable data class StoryTemplate(val id: String, val name: String, val genre: String, val tone: String)
    @Serializable data class CharacterTemplate(val id: String, val featured: Boolean, val recipe: CharacterRecipe)
}

@Serializable
data class ProceduralParts(val partsVersion: String, val baseModels: Map<String, BaseModel>, val modules: Map<String, Module>) {
    @Serializable
    data class Part(val id: String, val shape: String, val group: String? = null, val position: List<Double>, val size: List<Double>, val color: String)

    @Serializable
    data class BaseModel(val skin: String, val headCenter: List<Double>, val anchors: Map<String, List<Double>>, val parts: List<Part>)

    @Serializable
    data class Module(val group: String, val mirrorX: Boolean, val parts: List<Part>)
}

/** Licence-gated catalogue lookups, mirroring backend `Catalog.approved`. */
class Catalog(val manifest: AssetManifest, val parts: ProceduralParts) {
    private val approvedLicences = manifest.licences.filter { it.reviewStatus == "approved" && it.commercialUse }.map { it.id }.toSet()

    fun isApproved(licenceId: String) = licenceId in approvedLicences
    fun baseModel(id: String) = manifest.baseModels.firstOrNull { it.id == id }
    fun module(id: String) = manifest.modules.firstOrNull { it.id == id }
    fun power(id: String) = manifest.powers.firstOrNull { it.id == id }
    fun voice(id: String) = manifest.voiceProfiles.firstOrNull { it.id == id }
    fun clip(id: String) = manifest.animationClips.firstOrNull { it.id == id }
    fun environment(id: String) = manifest.environments.firstOrNull { it.id == id }
    fun rigOf(baseModelId: String) = baseModel(baseModelId)?.rig

    val approvedBaseModels get() = manifest.baseModels.filter { isApproved(it.licenceId) }
    val approvedModules get() = manifest.modules.filter { isApproved(it.licenceId) }
    val approvedEnvironments get() = manifest.environments.filter { isApproved(it.licenceId) }
    val approvedVoices get() = manifest.voiceProfiles.filter { isApproved(it.licenceId) }
    fun clipsFor(rig: String) = manifest.animationClips.filter { rig in it.rigs && isApproved(it.licenceId) }

    companion object {
        val json = Json { ignoreUnknownKeys = true }
        fun fromJson(manifestJson: String, partsJson: String) =
            Catalog(json.decodeFromString(manifestJson), json.decodeFromString(partsJson))
    }
}
