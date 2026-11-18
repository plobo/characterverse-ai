package com.characterverse.feature.charactermixer

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.characterverse.core.analytics.Analytics
import com.characterverse.core.network.ApiError
import com.characterverse.data.dto.MixRequestDto
import com.characterverse.data.dto.SuggestionDto
import com.characterverse.domain.model.Catalog
import com.characterverse.domain.model.CharacterSummary
import com.characterverse.domain.model.MixResult
import com.characterverse.domain.model.humanized
import com.characterverse.domain.repository.CharacterRepository
import com.characterverse.domain.repository.MixRepository
import com.characterverse.domain.usecase.FusionException
import com.characterverse.domain.usecase.FusionResolver
import com.characterverse.domain.usecase.MixDimension
import com.characterverse.domain.usecase.PartAssembler
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

data class MixerInputs(
    val selected: List<String> = emptyList(),
    val dimensions: Set<MixDimension> = MixDimension.entries.toSet(),
    val weights: Map<String, Double> = emptyMap(),
    val name: String = "",
)

data class MixerState(
    val inputs: MixerInputs = MixerInputs(),
    val characters: List<CharacterSummary> = emptyList(),
    val result: MixResult? = null,
    val warnings: List<String> = emptyList(),
    val suggestions: List<SuggestionDto> = emptyList(),
    val canUndo: Boolean = false,
    val busy: Boolean = false,
    val error: String? = null,
)

/** Pure state reducer so the mixer is unit-testable without Android. */
class MixerLogic(private val catalog: Catalog, private val fusion: FusionResolver) {
    fun compute(inputs: MixerInputs, characters: List<CharacterSummary>): Pair<MixResult?, List<String>> {
        val sources = inputs.selected.mapNotNull { id -> characters.firstOrNull { it.id == id }?.let { id to it.recipe } }
        if (sources.size < 2) return null to emptyList()
        return try {
            val r = fusion.resolve(sources, inputs.weights, inputs.dimensions, inputs.name.ifBlank { null })
            r to warnings(r)
        } catch (e: FusionException) { null to listOf(e.message.orEmpty()) }
    }

    fun warnings(r: MixResult): List<String> {
        val out = mutableListOf<String>()
        if ("RIG_MISMATCH" in r.warningCodes) out += "Different body types — using ${catalog.baseModel(r.recipe.baseModelId)?.name} and keeping only compatible parts."
        val why = mapOf("slot_taken" to "slot already used", "incompatible_rig" to "doesn't fit this body", "unsupported_by_rig" to "not supported by this body",
            "limit_reached" to "limit reached", "not_approved" to "not licensed")
        r.omitted.forEach { o -> out += "${catalog.module(o.id)?.name ?: catalog.power(o.id)?.name ?: o.id.humanized()} left out (${why[o.reason] ?: o.reason})" }
        return out
    }

    fun toggle(i: MixerInputs, id: String) = if (id in i.selected) i.copy(selected = i.selected - id, weights = i.weights - id)
        else if (i.selected.size < 3) i.copy(selected = i.selected + id, weights = i.weights + (id to (i.weights[id] ?: 1.0))) else i
}

@HiltViewModel
class MixerViewModel @Inject constructor(
    val catalog: Catalog,
    fusion: FusionResolver,
    val assembler: PartAssembler,
    characters: CharacterRepository,
    private val mixes: MixRepository,
    private val analytics: Analytics,
) : ViewModel() {
    private val logic = MixerLogic(catalog, fusion)
    private val history = ArrayDeque<MixerInputs>()
    private val _state = MutableStateFlow(MixerState())
    val state: StateFlow<MixerState> = _state

    init {
        viewModelScope.launch { characters.characters.collect { list -> update(chars = list.filterNot { it.archived }) } }
    }

    private fun update(inputs: MixerInputs = _state.value.inputs, chars: List<CharacterSummary> = _state.value.characters, push: Boolean = false) {
        if (push) { history.addLast(_state.value.inputs); if (history.size > 30) history.removeFirst() }
        val (result, warnings) = logic.compute(inputs, chars)
        _state.update { it.copy(inputs = inputs, characters = chars, result = result, warnings = warnings, canUndo = history.isNotEmpty()) }
    }

    fun toggle(id: String) = update(logic.toggle(_state.value.inputs, id), push = true)
    fun toggleDimension(d: MixDimension) = _state.value.inputs.let { i ->
        update(i.copy(dimensions = if (d in i.dimensions) i.dimensions - d else i.dimensions + d), push = true)
    }
    fun beginWeightChange() { history.addLast(_state.value.inputs) }
    fun setWeight(id: String, w: Double) = update(_state.value.inputs.let { it.copy(weights = it.weights + (id to w)) })
    fun setName(n: String) = update(_state.value.inputs.copy(name = n))
    fun undo() { history.removeLastOrNull()?.let { update(it) } }

    private fun request() = _state.value.inputs.let { MixRequestDto(it.selected, it.dimensions.map { d -> d.id }.sorted(), it.weights, it.name.ifBlank { null }) }

    fun fetchSuggestions() = viewModelScope.launch {
        if (_state.value.inputs.selected.size < 2) return@launch
        _state.update { it.copy(busy = true) }
        runCatching { mixes.preview(request()) }
            .onSuccess { p -> _state.update { it.copy(busy = false, suggestions = p.suggestions) } }
            .onFailure { e -> _state.update { it.copy(busy = false, error = ApiError.from(e).userMessage) } }
    }

    fun nextSuggestion() {
        val s = _state.value.suggestions.ifEmpty { return }
        val idx = s.indexOfFirst { it.name == _state.value.inputs.name }
        update(_state.value.inputs.copy(name = s[(idx + 1) % s.size].name), push = true)
    }

    fun save(onSaved: (String) -> Unit) = viewModelScope.launch {
        _state.update { it.copy(busy = true) }
        runCatching { mixes.save(request()) }
            .onSuccess { m -> _state.update { it.copy(busy = false, error = null) }; analytics.track("mix_saved"); m.character?.let { onSaved(it.id) } }
            .onFailure { e -> _state.update { it.copy(busy = false, error = ApiError.from(e).userMessage) } }
    }

    /** Debug/screenshot helper: preselect two originals with uneven weights. */
    fun demoSelect() {
        if (_state.value.inputs.selected.isNotEmpty()) return
        val ids = _state.value.characters.filter { it.lineage.isEmpty() }.take(2).map { it.id }
        if (ids.size < 2) return
        update(MixerInputs(selected = ids, weights = mapOf(ids[0] to 1.6, ids[1] to 1.0)))
        fetchSuggestions()
    }
}
