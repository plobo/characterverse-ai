package com.characterverse.feature.storycreator

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.characterverse.core.network.ApiError
import com.characterverse.data.dto.GenerateStoryRequestDto
import com.characterverse.data.dto.GenerateStoryResponseDto
import com.characterverse.domain.model.Catalog
import com.characterverse.domain.model.Storyboard
import com.characterverse.domain.repository.CharacterRepository
import com.characterverse.domain.repository.ProjectRepository
import com.characterverse.domain.repository.RenderRepository
import com.characterverse.domain.usecase.PartAssembler
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import java.util.UUID
import javax.inject.Inject

/** Story creation, storyboard editing and render submission (shared by the Studio screens). */
@HiltViewModel
class StudioViewModel @Inject constructor(
    val catalog: Catalog,
    val assembler: PartAssembler,
    val characters: CharacterRepository,
    private val projectsRepo: ProjectRepository,
    private val renders: RenderRepository,
) : ViewModel() {
    val projects = projectsRepo.projects
    val busy = MutableStateFlow(false)
    val error = MutableStateFlow<String?>(null)
    val story = MutableStateFlow<GenerateStoryResponseDto?>(null)
    val drafts = MutableStateFlow<Map<String, Storyboard>>(emptyMap())

    private fun run(block: suspend () -> Unit) = viewModelScope.launch {
        busy.value = true
        try { block(); error.value = null } catch (e: Exception) {
            val err = ApiError.from(e)
            error.value = (err as? ApiError.Server)?.let { s -> (listOf(s.userMessage) + s.details.take(3).map { "• ${it.message}" }).joinToString("\n") } ?: err.userMessage
        } finally { busy.value = false }
    }

    fun generate(req: GenerateStoryRequestDto) = run { story.value = projectsRepo.generateStory(req) }

    fun createProject(onCreated: (String) -> Unit) = run {
        val sb = story.value?.storyboard ?: return@run
        onCreated(projectsRepo.create(sb.title, sb).id)
    }

    fun storyboard(projectId: String): Storyboard? = drafts.value[projectId] ?: projects.value.firstOrNull { it.id == projectId }?.storyboard
    fun isDirty(projectId: String) = projectId in drafts.value

    fun editStoryboard(projectId: String, change: (Storyboard) -> Storyboard) {
        val current = storyboard(projectId) ?: return
        drafts.value = drafts.value + (projectId to change(current).renumbered())
    }

    fun moveScene(projectId: String, from: Int, to: Int) = editStoryboard(projectId) { sb ->
        if (to !in sb.scenes.indices) sb else sb.copy(scenes = sb.scenes.toMutableList().apply { add(to, removeAt(from)) })
    }
    fun duplicateScene(projectId: String, index: Int) = editStoryboard(projectId) { sb ->
        if (sb.scenes.size >= 8) sb else sb.copy(scenes = sb.scenes.toMutableList().apply { add(index + 1, sb.scenes[index].copy(sceneId = newSceneId())) })
    }
    fun deleteScene(projectId: String, index: Int) = editStoryboard(projectId) { sb -> if (sb.scenes.size <= 1) sb else sb.copy(scenes = sb.scenes.filterIndexed { i, _ -> i != index }) }
    fun addScene(projectId: String) = editStoryboard(projectId) { sb ->
        if (sb.scenes.size >= 8) sb else sb.copy(scenes = sb.scenes + sb.scenes.last().copy(sceneId = newSceneId(), title = "New scene", description = null, durationMs = 3000, dialogue = emptyList()))
    }
    fun updateScene(projectId: String, scene: Storyboard.Scene) = editStoryboard(projectId) { sb -> sb.copy(scenes = sb.scenes.map { if (it.sceneId == scene.sceneId) scene else it }) }

    private fun newSceneId() = "scene_" + UUID.randomUUID().toString().take(6)

    fun save(projectId: String, onDone: () -> Unit = {}) = run {
        val sb = drafts.value[projectId] ?: return@run onDone()
        projectsRepo.saveStoryboard(projectId, sb)
        drafts.value = drafts.value - projectId
        onDone()
    }

    fun discard(projectId: String) { drafts.value = drafts.value - projectId }

    fun render(projectId: String, quality: String, onSubmitted: () -> Unit) = run {
        drafts.value[projectId]?.let { projectsRepo.saveStoryboard(projectId, it); drafts.value = drafts.value - projectId }
        val version = projects.value.firstOrNull { it.id == projectId }?.version ?: 0
        renders.submit(projectId, quality, "android-$projectId-v$version-$quality")
        onSubmitted()
    }

    fun deleteProject(id: String) = run { projectsRepo.deleteProject(id) }
}
