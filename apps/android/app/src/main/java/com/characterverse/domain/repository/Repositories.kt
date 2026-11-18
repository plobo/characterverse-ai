package com.characterverse.domain.repository

import com.characterverse.data.dto.*
import com.characterverse.domain.model.CharacterRecipe
import com.characterverse.domain.model.CharacterSummary
import com.characterverse.domain.model.Project
import com.characterverse.domain.model.RenderJob
import com.characterverse.domain.model.Storyboard
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow

interface AccountRepository {
    val user: StateFlow<UserDto?>
    suspend fun restore(): Boolean
    suspend fun signIn(provider: String, token: String?, displayName: String?): UserDto
    suspend fun signOut()
    suspend fun usage(): UsageDto
    suspend fun exportData(): String
    suspend fun deleteAccount()
    suspend fun report(contentType: String, contentId: String, reason: String)
}

interface CharacterRepository {
    val characters: StateFlow<List<CharacterSummary>>
    suspend fun refresh()
    suspend fun create(recipe: CharacterRecipe, description: String): CharacterSummary
    suspend fun update(id: String, change: UpdateCharacterDto): CharacterSummary
    suspend fun delete(id: String)
    suspend fun duplicate(id: String): CharacterSummary
    suspend fun generateRecipe(description: String, category: String? = null): GenerateRecipeResponseDto
}

interface MixRepository {
    suspend fun preview(request: MixRequestDto): MixPreviewDto
    suspend fun save(request: MixRequestDto): MixDto
}

interface ProjectRepository {
    val projects: StateFlow<List<Project>>
    suspend fun refreshProjects()
    suspend fun generateStory(request: GenerateStoryRequestDto): GenerateStoryResponseDto
    suspend fun create(title: String, storyboard: Storyboard?): Project
    suspend fun saveStoryboard(projectId: String, storyboard: Storyboard): Project
    suspend fun deleteProject(id: String)
}

interface RenderRepository {
    val renders: StateFlow<List<RenderJob>>
    suspend fun refreshRenders()
    suspend fun submit(projectId: String, quality: String, idempotencyKey: String): RenderJob
    suspend fun cancel(id: String): RenderJob
    suspend fun retry(id: String): RenderJob
    suspend fun downloadUrl(id: String): DownloadUrlDto
}

data class Draft(val id: String, val recipe: CharacterRecipe, val serverCharacterId: String?, val updatedAt: Long)

interface DraftRepository {
    val drafts: Flow<List<Draft>>
    suspend fun upsert(id: String?, recipe: CharacterRecipe, serverCharacterId: String?): String
    suspend fun remove(id: String)
    suspend fun clear()
}
