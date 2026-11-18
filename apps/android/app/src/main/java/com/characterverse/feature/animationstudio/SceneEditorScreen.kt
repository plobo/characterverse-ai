package com.characterverse.feature.animationstudio

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.characterverse.core.design.*
import com.characterverse.domain.model.Storyboard
import com.characterverse.domain.model.humanized
import com.characterverse.feature.charactercreator.Dropdown
import com.characterverse.feature.storyboard.StageCanvas
import com.characterverse.feature.storycreator.StudioViewModel

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SceneEditorScreen(vm: StudioViewModel, projectId: String, sceneId: String, onDone: () -> Unit) {
    val characters by vm.characters.characters.collectAsState()
    val drafts by vm.drafts.collectAsState()
    val projects by vm.projects.collectAsState()
    val busy by vm.busy.collectAsState()
    val error by vm.error.collectAsState()
    val sb = drafts[projectId] ?: projects.firstOrNull { it.id == projectId }?.storyboard ?: return
    val scene = sb.scenes.firstOrNull { it.sceneId == sceneId } ?: return
    var newLine by remember { mutableStateOf("") }
    fun update(change: (Storyboard.Scene) -> Storyboard.Scene) = vm.updateScene(projectId, change(scene))
    val cat = vm.catalog

    Box {
        Column {
            StageCanvas(vm, scene, characters, Modifier.fillMaxWidth().height(220.dp))
            Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 6.dp).semantics { contentDescription = "Timeline, scene ${scene.sequence} of ${sb.scenes.size}" },
                horizontalArrangement = Arrangement.spacedBy(2.dp)) {
                sb.scenes.forEach { s ->
                    Box(Modifier.weight(s.durationMs.toFloat()).height(20.dp).background(if (s.sceneId == sceneId) Tokens.brand else Tokens.brand.copy(alpha = 0.25f), RoundedCornerShape(4.dp)),
                        contentAlignment = Alignment.Center) { Text("${s.sequence}", style = MaterialTheme.typography.labelSmall, color = androidx.compose.ui.graphics.Color.White) }
                }
            }
            LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                error?.let { item { ErrorBanner(it) } }
                item {
                    CvCard {
                        SectionHeader("Scene")
                        OutlinedTextField(scene.title, { v -> update { it.copy(title = v) } }, Modifier.fillMaxWidth(), label = { Text("Title") }, singleLine = true)
                        Text("Duration ${"%.1f".format(scene.durationMs / 1000.0)}s")
                        Slider(scene.durationMs.toFloat(), { v -> update { it.copy(durationMs = (v / 500).toInt() * 500) } }, valueRange = 2000f..15000f,
                            modifier = Modifier.semantics { contentDescription = "Scene duration" })
                        Dropdown("Environment", scene.environmentId, cat.approvedEnvironments.associate { it.id to it.name }) { v -> update { it.copy(environmentId = v) } }
                        Dropdown("Camera", scene.cameraPresetId, cat.manifest.cameraPresets.associate { it.id to it.id.removePrefix("cam_").humanized() }) { v -> update { it.copy(cameraPresetId = v) } }
                        Dropdown("Lighting", scene.lightingPresetId, cat.manifest.lightingPresets.associate { it.id to it.id.removePrefix("light_").humanized() }) { v -> update { it.copy(lightingPresetId = v) } }
                        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            listOf("cut", "fade").forEach { tr -> Chip("Transition: ${tr.humanized()}", scene.transition == tr) { update { it.copy(transition = tr) } } }
                        }
                    }
                }
                scene.characters.forEachIndexed { idx, sc ->
                    item(key = sc.characterId) {
                        val c = characters.firstOrNull { it.id == sc.characterId }
                        val rig = c?.let { cat.rigOf(it.recipe.baseModelId) } ?: "humanoid_v1"
                        fun set(n: Storyboard.SceneCharacter) = update { s -> s.copy(characters = s.characters.mapIndexed { i, x -> if (i == idx) n else x }) }
                        CvCard {
                            SectionHeader(c?.name ?: "Character")
                            Dropdown("Action clip", sc.actionId, cat.clipsFor(rig).associate { it.id to it.id.humanized() }) { set(sc.copy(actionId = it)) }
                            Dropdown("Position", sc.position, listOf("far_left", "left", "center", "right", "far_right").associateWith { it.humanized() }) { set(sc.copy(position = it)) }
                            Text("Scale ${"%.2f".format(sc.scale)}")
                            Slider(sc.scale.toFloat(), { set(sc.copy(scale = Math.round(it * 20) / 20.0)) }, valueRange = 0.5f..1.5f, modifier = Modifier.semantics { contentDescription = "Character scale" })
                        }
                    }
                }
                item {
                    CvCard {
                        SectionHeader("Dialogue & audio")
                        scene.dialogue.forEachIndexed { i, d ->
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Column(Modifier.weight(1f)) {
                                    Text(characters.firstOrNull { it.id == d.characterId }?.name ?: "", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.labelMedium)
                                    OutlinedTextField(d.line, { v -> update { s -> s.copy(dialogue = s.dialogue.mapIndexed { j, x -> if (j == i) x.copy(line = v.take(140)) else x }) } }, Modifier.fillMaxWidth())
                                }
                                IconButton({ update { s -> s.copy(dialogue = s.dialogue.filterIndexed { j, _ -> j != i }) } }) { Icon(Icons.Default.Delete, "Remove line") }
                            }
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            OutlinedTextField(newLine, { newLine = it }, Modifier.weight(1f), placeholder = { Text("Add a line…") })
                            TextButton({
                                val speaker = scene.characters.firstOrNull()?.characterId ?: return@TextButton
                                if (newLine.isNotBlank()) update { it.copy(dialogue = it.dialogue + Storyboard.DialogueLine(speaker, newLine.take(140), minOf(1000, it.durationMs - 500))) }
                                newLine = ""
                            }) { Text("Add") }
                        }
                        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            cat.manifest.soundEffects.forEach { fx ->
                                val on = fx.id in scene.soundEffectIds
                                Chip(fx.id.removePrefix("sfx_").humanized(), on, Tokens.brandSecondary) {
                                    update { s -> s.copy(soundEffectIds = if (on) s.soundEffectIds - fx.id else if (s.soundEffectIds.size < 4) s.soundEffectIds + fx.id else s.soundEffectIds) }
                                }
                            }
                        }
                    }
                }
                item { Button({ vm.save(projectId, onDone) }, Modifier.fillMaxWidth().height(52.dp), enabled = !busy) { Text("Save scene") } }
            }
        }
        if (busy) LoadingOverlay("Validating scene…")
    }
}
