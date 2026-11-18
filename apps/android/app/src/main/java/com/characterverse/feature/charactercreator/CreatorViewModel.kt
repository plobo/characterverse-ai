package com.characterverse.feature.charactercreator

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.characterverse.app.CreatorSeed
import com.characterverse.core.analytics.Analytics
import com.characterverse.core.network.ApiError
import com.characterverse.data.dto.UpdateCharacterDto
import com.characterverse.domain.model.Catalog
import com.characterverse.domain.model.CharacterRecipe
import com.characterverse.domain.model.CharacterSummary
import com.characterverse.domain.repository.CharacterRepository
import com.characterverse.domain.repository.DraftRepository
import com.characterverse.domain.usecase.PartAssembler
import com.characterverse.domain.usecase.RecipeIssue
import com.characterverse.domain.usecase.RecipeValidator
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class CreatorState(
    val recipe: CharacterRecipe,
    val editingId: String? = null,
    val draftId: String? = null,
    val aiPrompt: String = "",
    val aiWarnings: List<String> = emptyList(),
    val busy: Boolean = false,
    val error: String? = null,
    val saved: String? = null,
)

@HiltViewModel
class CreatorViewModel @Inject constructor(
    val catalog: Catalog,
    private val validator: RecipeValidator,
    val assembler: PartAssembler,
    private val characters: CharacterRepository,
    private val drafts: DraftRepository,
    private val seed: CreatorSeed,
    private val analytics: Analytics,
) : ViewModel() {
    private val _state = MutableStateFlow(CreatorState(blank(catalog)))
    val state: StateFlow<CreatorState> = _state.asStateFlow()

    init {
        viewModelScope.launch { seed.pending.collect { p -> if (p != null) { _state.value = CreatorState(p.first, editingId = p.second); seed.pending.value = null } } }
    }

    companion object {
        fun blank(c: Catalog) = CharacterRecipe(1, "New Character", "hero", "humanoid_base_01", "stylized_cinematic",
            CharacterRecipe.Proportions(1.0, 1.0, 1.0), CharacterRecipe.Palette("#6C4DF6", "#2E3A59", "#FFB547"),
            emptyList(), emptyList(), listOf("brave"), "voice_fictional_warm_01", c.manifest.manifestVersion)
    }

    val rig get() = catalog.rigOf(_state.value.recipe.baseModelId) ?: "humanoid_v1"
    fun issues(r: CharacterRecipe = _state.value.recipe): List<RecipeIssue> = validator.issues(r)
    fun baseModelsFor(category: String) = catalog.approvedBaseModels.filter { category in it.categories }
    fun slots() = catalog.approvedModules.filter { rig in it.rigs }.groupBy { it.slot }.toSortedMap().mapValues { e -> e.value.sortedBy { it.priority } }
    fun availablePowers() = catalog.manifest.powers.filter { rig in it.rigs }

    fun edit(change: (CharacterRecipe) -> CharacterRecipe) {
        _state.update { it.copy(recipe = change(it.recipe), saved = null) }
        autosave()
    }

    fun setCategory(category: String) = edit { r ->
        val next = r.copy(category = category)
        if (catalog.baseModel(r.baseModelId)?.categories?.contains(category) == true) next
        else baseModelsFor(category).firstOrNull()?.let { withBase(next, it.id) } ?: next
    }

    fun setBaseModel(id: String) = edit { withBase(it, id) }

    /** Switching body keeps only modules/powers the new rig supports (no skeleton blending). */
    fun withBase(r: CharacterRecipe, id: String): CharacterRecipe {
        val newRig = catalog.rigOf(id) ?: return r
        return r.copy(baseModelId = id, modules = r.modules.filter { catalog.module(it)?.rigs?.contains(newRig) == true },
            powers = r.powers.filter { catalog.power(it)?.rigs?.contains(newRig) == true })
    }

    fun setModule(id: String?, slot: String) = edit { r ->
        r.copy(modules = r.modules.filter { catalog.module(it)?.slot != slot } + listOfNotNull(id))
    }

    fun togglePower(id: String) = edit { r ->
        r.copy(powers = if (id in r.powers) r.powers - id else if (r.powers.size < 3) r.powers + id else r.powers)
    }

    fun toggleTrait(id: String) = edit { r ->
        r.copy(personalityTraits = if (id in r.personalityTraits) r.personalityTraits - id else if (r.personalityTraits.size < 5) r.personalityTraits + id else r.personalityTraits)
    }

    fun setPrompt(p: String) = _state.update { it.copy(aiPrompt = p) }

    fun generate() = viewModelScope.launch {
        val prompt = _state.value.aiPrompt.trim().ifEmpty { return@launch }
        _state.update { it.copy(busy = true) }
        runCatching { characters.generateRecipe(prompt) }
            .onSuccess { res -> _state.update { it.copy(recipe = res.recipe, aiWarnings = res.warnings.map { w -> w.message }, busy = false, error = null) }; autosave(); analytics.track("recipe_generated") }
            .onFailure { e -> _state.update { it.copy(busy = false, error = ApiError.from(e).userMessage) } }
    }

    fun save(onSaved: (CharacterSummary) -> Unit = {}) = viewModelScope.launch {
        val s = _state.value
        val problems = issues(s.recipe)
        if (problems.isNotEmpty()) { _state.update { it.copy(error = problems.first().message) }; return@launch }
        _state.update { it.copy(busy = true) }
        runCatching {
            if (s.editingId != null) characters.update(s.editingId, UpdateCharacterDto(recipe = s.recipe)) else characters.create(s.recipe, s.aiPrompt)
        }.onSuccess { saved ->
            s.draftId?.let { drafts.remove(it) }
            _state.update { it.copy(busy = false, editingId = saved.id, draftId = null, saved = "Saved to My Universe (v${saved.version})", error = null) }
            analytics.track("character_saved")
            onSaved(saved)
        }.onFailure { e ->
            val err = ApiError.from(e)
            _state.update { it.copy(busy = false, error = if (err is ApiError.Offline) "You're offline — kept as a local draft." else err.userMessage) }
        }
    }

    private fun autosave() = viewModelScope.launch {
        val s = _state.value
        val id = drafts.upsert(s.draftId, s.recipe, s.editingId)
        if (s.draftId == null) _state.update { it.copy(draftId = id) }
    }
}
