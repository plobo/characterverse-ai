package com.characterverse.app

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.characterverse.core.network.ApiError
import com.characterverse.data.repository.RemoteRepository
import com.characterverse.domain.model.Catalog
import com.characterverse.domain.model.CharacterRecipe
import com.characterverse.domain.usecase.PartAssembler
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

enum class Phase { LAUNCHING, SIGNED_OUT, SIGNED_IN }

/** Hand-off of a recipe into the Creator tab (template customise, edit, draft restore). */
@Singleton
class CreatorSeed @Inject constructor() {
    val pending = MutableStateFlow<Pair<CharacterRecipe, String?>?>(null)
}

@HiltViewModel
class SessionViewModel @Inject constructor(
    val repo: RemoteRepository,
    val catalog: Catalog,
    val assembler: PartAssembler,
    val creatorSeed: CreatorSeed,
) : ViewModel() {
    private val _phase = MutableStateFlow(Phase.LAUNCHING)
    val phase: StateFlow<Phase> = _phase
    val error = MutableStateFlow<String?>(null)
    val offline = MutableStateFlow(false)
    val user = repo.user

    init {
        viewModelScope.launch {
            _phase.value = if (repo.restore()) Phase.SIGNED_IN.also { refresh() } else Phase.SIGNED_OUT
        }
    }

    fun refresh() = viewModelScope.launch {
        runCatching { repo.refresh() }.onFailure { offline.value = ApiError.from(it) is ApiError.Offline }.onSuccess { offline.value = false }
        runCatching { repo.refreshProjects() }
        runCatching { repo.refreshRenders() }
    }

    suspend fun signIn(provider: String, token: String?, name: String?) {
        runCatching { repo.signIn(provider, token, name) }
            .onSuccess { _phase.value = Phase.SIGNED_IN; error.value = null; repo.refreshAll() }
            .onFailure { error.value = ApiError.from(it).userMessage }
    }

    fun signOut() = viewModelScope.launch { repo.signOut(); _phase.value = Phase.SIGNED_OUT }
    fun markSignedOut() { _phase.value = Phase.SIGNED_OUT }
}
