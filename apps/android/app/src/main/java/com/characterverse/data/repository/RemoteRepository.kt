package com.characterverse.data.repository

import com.characterverse.core.auth.TokenStore
import com.characterverse.core.database.AppDatabase
import com.characterverse.core.database.CachedCharacterEntity
import com.characterverse.core.database.DraftEntity
import com.characterverse.core.network.apiCall
import com.characterverse.core.network.withRetry
import com.characterverse.data.api.ApiService
import com.characterverse.data.dto.*
import com.characterverse.domain.model.CharacterRecipe
import com.characterverse.domain.model.CharacterSummary
import com.characterverse.domain.model.Project
import com.characterverse.domain.model.RenderJob
import com.characterverse.domain.model.Storyboard
import com.characterverse.domain.repository.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.update
import kotlinx.serialization.json.Json
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

/** Single source of truth for server data, exposed as StateFlows to ViewModels. */
@Singleton
class RemoteRepository @Inject constructor(
    private val api: ApiService,
    private val tokens: TokenStore,
    private val db: AppDatabase,
) : AccountRepository, CharacterRepository, MixRepository, ProjectRepository, RenderRepository {
    private val json = Json { ignoreUnknownKeys = true }
    private val _user = MutableStateFlow<UserDto?>(null)
    private val _characters = MutableStateFlow<List<CharacterSummary>>(emptyList())
    private val _projects = MutableStateFlow<List<Project>>(emptyList())
    private val _renders = MutableStateFlow<List<RenderJob>>(emptyList())
    override val user: StateFlow<UserDto?> = _user
    override val characters: StateFlow<List<CharacterSummary>> = _characters
    override val projects: StateFlow<List<Project>> = _projects
    override val renders: StateFlow<List<RenderJob>> = _renders

    // account
    override suspend fun restore(): Boolean {
        if (tokens.token() == null) return false
        return runCatching { _user.value = withRetry { api.me() }; true }.getOrElse {
            val err = com.characterverse.core.network.ApiError.from(it)
            // Only an auth failure (after the authenticator's refresh attempt) ends the session; offline or server
            // errors keep it, so a guest account is never abandoned.
            if (err is com.characterverse.core.network.ApiError.Server && (err.code == "AUTH_INVALID" || err.code == "AUTH_REQUIRED")) {
                tokens.clear(); false
            } else { loadCachedCharacters(); true }
        }
    }

    override suspend fun signIn(provider: String, token: String?, displayName: String?): UserDto {
        val res = apiCall { api.session(SessionRequestDto(provider, token, displayName)) }
        tokens.save(res.accessToken, res.refreshToken)
        _user.value = res.user
        return res.user
    }

    override suspend fun signOut() {
        tokens.clear()
        _user.value = null
        _characters.value = emptyList(); _projects.value = emptyList(); _renders.value = emptyList()
        db.characterCache().clear()
    }

    override suspend fun usage() = withRetry { api.usage() }
    override suspend fun exportData(): String = kotlinx.serialization.json.JsonObject(withRetry { api.export() }).toString()
    override suspend fun deleteAccount() { apiCall { api.deleteMe() }; db.drafts().clear(); signOut() }
    override suspend fun report(contentType: String, contentId: String, reason: String) { apiCall { api.report(ReportDto(contentType, contentId, reason)) } }

    // characters
    override suspend fun refresh() {
        val list = withRetry { api.characters() }.items
        _characters.value = list.map { it.toDomain() }
        db.characterCache().clear()
        db.characterCache().putAll(list.map { CachedCharacterEntity(it.id, json.encodeToString(CharacterDto.serializer(), it), it.updatedAt) })
    }

    private suspend fun loadCachedCharacters() {
        _characters.value = db.characterCache().all().map { json.decodeFromString(CharacterDto.serializer(), it.json).toDomain() }
            .sortedByDescending { it.updatedAt }
    }

    private fun upsert(c: CharacterSummary) = _characters.update { list -> listOf(c) + list.filterNot { it.id == c.id } }

    override suspend fun create(recipe: CharacterRecipe, description: String) =
        apiCall { api.createCharacter(CreateCharacterDto(recipe, description)) }.toDomain().also(::upsert)
    override suspend fun update(id: String, change: UpdateCharacterDto) =
        apiCall { api.updateCharacter(id, change) }.toDomain().also(::upsert)
    override suspend fun delete(id: String) { apiCall { api.deleteCharacter(id) }; _characters.update { l -> l.filterNot { it.id == id } } }
    override suspend fun duplicate(id: String) = apiCall { api.duplicateCharacter(id) }.toDomain().also(::upsert)
    override suspend fun generateRecipe(description: String, category: String?) = apiCall { api.generateRecipe(GenerateRecipeRequestDto(description, category)) }

    // mixer
    override suspend fun preview(request: MixRequestDto) = apiCall { api.mixPreview(request) }
    override suspend fun save(request: MixRequestDto) = apiCall { api.saveMix(request) }.also { m -> m.character?.let { upsert(it.toDomain()) } }

    // projects
    override suspend fun refreshProjects() { _projects.value = withRetry { api.projects() }.items.map { it.toDomain() } }
    override suspend fun generateStory(request: GenerateStoryRequestDto) = apiCall { api.generateStory(request) }
    override suspend fun create(title: String, storyboard: Storyboard?) =
        apiCall { api.createProject(CreateProjectDto(title, storyboard = storyboard)) }.toDomain().also { p -> _projects.update { listOf(p) + it } }
    override suspend fun saveStoryboard(projectId: String, storyboard: Storyboard) =
        apiCall { api.saveStoryboard(projectId, StoryboardRequestDto(storyboard)) }.toDomain()
            .also { p -> _projects.update { l -> l.map { if (it.id == p.id) p else it } } }

    override suspend fun deleteProject(id: String) { apiCall { api.deleteProject(id) }; _projects.update { l -> l.filterNot { it.id == id } } }

    // renders
    override suspend fun refreshRenders() { _renders.value = withRetry { api.renders() }.items.map { it.toDomain() } }
    private fun upsertJob(j: RenderJob) = _renders.update { l -> if (l.any { it.id == j.id }) l.map { if (it.id == j.id) j else it } else listOf(j) + l }
    override suspend fun submit(projectId: String, quality: String, idempotencyKey: String) =
        withRetry { api.submitRender(projectId, idempotencyKey, CreateRenderDto(quality)) }.toDomain().also(::upsertJob)
    override suspend fun cancel(id: String) = apiCall { api.cancelRender(id) }.toDomain().also(::upsertJob)
    override suspend fun retry(id: String) = apiCall { api.retryRender(id) }.toDomain().also(::upsertJob)
    override suspend fun downloadUrl(id: String) = withRetry { api.downloadUrl(id) }

    suspend fun refreshAll() {
        runCatching { refresh() }.onFailure { loadCachedCharacters() }
        runCatching { refreshProjects() }
        runCatching { refreshRenders() }
    }
}

@Singleton
class RoomDraftRepository @Inject constructor(private val db: AppDatabase) : DraftRepository {
    private val json = Json { ignoreUnknownKeys = true }
    override val drafts = db.drafts().observeAll().map { list ->
        list.mapNotNull { e -> runCatching { Draft(e.id, json.decodeFromString(CharacterRecipe.serializer(), e.recipeJson), e.serverCharacterId, e.updatedAt) }.getOrNull() }
    }
    override suspend fun upsert(id: String?, recipe: CharacterRecipe, serverCharacterId: String?): String {
        val draftId = id ?: UUID.randomUUID().toString()
        db.drafts().upsert(DraftEntity(draftId, json.encodeToString(CharacterRecipe.serializer(), recipe), serverCharacterId, System.currentTimeMillis()))
        return draftId
    }
    override suspend fun remove(id: String) = db.drafts().delete(id)
    override suspend fun clear() = db.drafts().clear()
}
