package com.characterverse.domain.usecase

import com.characterverse.domain.model.Catalog
import com.characterverse.domain.model.CharacterRecipe

data class RecipeIssue(val code: String, val field: String, val message: String)

/** Kotlin port of backend `recipe_issues`; parity pinned by shared/fixtures/recipe_validation_cases.json. */
class RecipeValidator(private val catalog: Catalog) {
    private val idPattern = Regex("^[a-z0-9_]+$")
    private val categoryPattern = Regex("^[a-z_]+$")
    private val hexPattern = Regex("^#[0-9A-Fa-f]{6}$")
    private val versionPattern = Regex("^[0-9]+\\.[0-9]+$")

    fun issues(r: CharacterRecipe): List<RecipeIssue> {
        val schema = mutableListOf<RecipeIssue>()
        fun s(field: String, message: String) = schema.add(RecipeIssue("SCHEMA_VIOLATION", field, message))
        if (r.schemaVersion != 1) s("schemaVersion", "Unsupported schema version")
        if (r.name.isEmpty() || r.name.length > 40) s("name", "Name must be 1-40 characters")
        if (!categoryPattern.matches(r.category)) s("category", "Invalid category")
        if (!idPattern.matches(r.baseModelId)) s("baseModelId", "Invalid id")
        if (!idPattern.matches(r.style)) s("style", "Invalid style")
        listOf("height" to r.proportions.height, "shoulderWidth" to r.proportions.shoulderWidth, "headScale" to r.proportions.headScale)
            .filter { it.second !in 0.7..1.3 }.forEach { s("proportions/${it.first}", "Must be between 0.7 and 1.3") }
        listOf("primary" to r.palette.primary, "secondary" to r.palette.secondary, "accent" to r.palette.accent)
            .filter { !hexPattern.matches(it.second) }.forEach { s("palette/${it.first}", "Colour must be #RRGGBB") }
        fun list(values: List<String>, field: String, max: Int, pattern: Regex) {
            if (values.size > max) s(field, "At most $max allowed")
            if (values.toSet().size != values.size) s(field, "Duplicates are not allowed")
            if (values.any { !pattern.matches(it) }) s(field, "Invalid id")
        }
        list(r.modules, "modules", 6, idPattern)
        list(r.powers, "powers", 3, idPattern)
        list(r.personalityTraits, "personalityTraits", 5, categoryPattern)
        if (!idPattern.matches(r.voiceProfileId)) s("voiceProfileId", "Invalid id")
        if (!versionPattern.matches(r.assetManifestVersion)) s("assetManifestVersion", "Invalid version")
        if (schema.isNotEmpty()) return schema

        val out = mutableListOf<RecipeIssue>()
        val m = catalog.manifest
        if (r.category !in m.categories) out += RecipeIssue("UNKNOWN_CATEGORY", "category", "Unknown category")
        if (r.style !in m.styles) out += RecipeIssue("UNKNOWN_STYLE", "style", "Unknown style")
        if (r.assetManifestVersion != m.manifestVersion) out += RecipeIssue("MANIFEST_VERSION_MISMATCH", "assetManifestVersion", "Recipe targets another manifest")
        var rig: String? = null
        val base = catalog.baseModel(r.baseModelId)
        when {
            base == null -> out += RecipeIssue("UNKNOWN_ASSET", "baseModelId", "Unknown base model")
            !catalog.isApproved(base.licenceId) -> out += RecipeIssue("ASSET_NOT_APPROVED", "baseModelId", "Base model licence is not approved")
            else -> {
                rig = base.rig
                if (r.category in m.categories && r.category !in base.categories) {
                    out += RecipeIssue("CATEGORY_NOT_SUPPORTED", "category", "${base.name} does not support ${r.category}")
                }
            }
        }
        val usedSlots = mutableMapOf<String, String>()
        r.modules.forEachIndexed { i, id ->
            val field = "modules/$i"
            val module = catalog.module(id)
            when {
                module == null -> out += RecipeIssue("UNKNOWN_ASSET", field, "Unknown module $id")
                !catalog.isApproved(module.licenceId) -> out += RecipeIssue("ASSET_NOT_APPROVED", field, "${module.name} is not approved")
                else -> {
                    if (rig != null && rig !in module.rigs) out += RecipeIssue("INCOMPATIBLE_MODULE", field, "${module.name} does not fit this body")
                    val other = usedSlots[module.slot]
                    if (other != null) out += RecipeIssue("SLOT_CONFLICT", field, "$id and $other share the ${module.slot} slot")
                    else usedSlots[module.slot] = id
                }
            }
        }
        r.powers.forEachIndexed { i, id ->
            val power = catalog.power(id)
            if (power == null) out += RecipeIssue("UNKNOWN_ASSET", "powers/$i", "Unknown power")
            else if (rig != null && rig !in power.rigs) out += RecipeIssue("UNSUPPORTED_POWER", "powers/$i", "${power.name} is not supported by this body")
        }
        r.personalityTraits.forEachIndexed { i, t ->
            if (t !in m.personalityTraits) out += RecipeIssue("UNKNOWN_TRAIT", "personalityTraits/$i", "Unknown trait")
        }
        val voice = catalog.voice(r.voiceProfileId)
        if (voice == null) out += RecipeIssue("UNKNOWN_ASSET", "voiceProfileId", "Unknown voice profile")
        else if (!catalog.isApproved(voice.licenceId)) out += RecipeIssue("ASSET_NOT_APPROVED", "voiceProfileId", "Voice is not approved")
        return out
    }
}
