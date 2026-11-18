package com.characterverse.feature.storyboard

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.characterverse.core.design.*
import com.characterverse.domain.model.CharacterSummary
import com.characterverse.domain.model.Storyboard
import com.characterverse.domain.model.humanized
import com.characterverse.feature.storycreator.StudioViewModel
import com.characterverse.threed.viewer.drawCharacter
import com.characterverse.threed.viewer.rememberReduceMotion
import kotlin.math.sin

val slotX = mapOf("far_left" to 0.12f, "left" to 0.3f, "center" to 0.5f, "right" to 0.7f, "far_right" to 0.88f)

@Composable
fun StoryboardScreen(vm: StudioViewModel, projectId: String, onScene: (String) -> Unit, onRenders: () -> Unit) {
    val projects by vm.projects.collectAsState()
    val drafts by vm.drafts.collectAsState()
    val characters by vm.characters.characters.collectAsState()
    val busy by vm.busy.collectAsState()
    val error by vm.error.collectAsState()
    val sb = drafts[projectId] ?: projects.firstOrNull { it.id == projectId }?.storyboard
    var quality by remember { mutableStateOf("draft") }
    if (sb == null) { EmptyState(Icons.Default.Movie, "No storyboard", "Generate a story first."); return }
    Box {
        LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                Text(sb.logline, style = MaterialTheme.typography.bodyMedium)
                val over = sb.totalDurationMs > sb.durationSeconds * 1000
                Text("${sb.scenes.size} scenes · ${"%.1f".format(sb.totalDurationMs / 1000.0)}s of ${sb.durationSeconds}s · ${sb.aspectRatio}",
                    style = MaterialTheme.typography.bodySmall, color = if (over) Tokens.danger else MaterialTheme.colorScheme.onSurfaceVariant)
            }
            itemsIndexed(sb.scenes, key = { _, s -> s.sceneId }) { i, scene ->
                CvCard(Modifier.clickable { onScene(scene.sceneId) }) {
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        StageCanvas(vm, scene, characters, Modifier.size(120.dp, 78.dp).clip(RoundedCornerShape(10.dp)), animate = false)
                        Column(Modifier.weight(1f)) {
                            Text("${scene.sequence}. ${scene.title}", fontWeight = FontWeight.Bold)
                            Text("${vm.catalog.environment(scene.environmentId)?.name} · ${scene.cameraPresetId.removePrefix("cam_").humanized()} · ${"%.1f".format(scene.durationMs / 1000.0)}s",
                                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            scene.dialogue.firstOrNull()?.let { d -> Text("${sb.characters.firstOrNull { it.characterId == d.characterId }?.displayName}: “${d.line}”", style = MaterialTheme.typography.bodySmall, maxLines = 2) }
                            Text(scene.characters.joinToString(" · ") { it.actionId.humanized() }, style = MaterialTheme.typography.labelSmall, color = Tokens.brand)
                        }
                    }
                    Row {
                        IconButton({ vm.moveScene(projectId, i, i - 1) }, enabled = i > 0) { Icon(Icons.Default.ArrowUpward, "Move up") }
                        IconButton({ vm.moveScene(projectId, i, i + 1) }, enabled = i < sb.scenes.size - 1) { Icon(Icons.Default.ArrowDownward, "Move down") }
                        IconButton({ vm.duplicateScene(projectId, i) }) { Icon(Icons.Default.ContentCopy, "Duplicate scene") }
                        IconButton({ vm.deleteScene(projectId, i) }, enabled = sb.scenes.size > 1) { Icon(Icons.Default.Delete, "Delete scene") }
                    }
                }
            }
            item { OutlinedButton({ vm.addScene(projectId) }, Modifier.fillMaxWidth()) { Icon(Icons.Default.Add, null); Text("Add scene") } }
            error?.let { item { ErrorBanner(it) } }
            item {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    if (vm.isDirty(projectId)) FilledTonalButton({ vm.save(projectId) }, Modifier.fillMaxWidth()) { Text("Save storyboard") }
                    SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                        listOf("draft" to "Draft 480p", "final" to "Final 720p").forEachIndexed { i, (q, l) ->
                            SegmentedButton(quality == q, { quality = q }, SegmentedButtonDefaults.itemShape(i, 2)) { Text(l) }
                        }
                    }
                    Button({ vm.render(projectId, quality, onRenders) }, Modifier.fillMaxWidth().height(52.dp), enabled = !busy) {
                        Icon(Icons.Default.PlayCircle, null); Spacer(Modifier.width(6.dp)); Text("Render video")
                    }
                    Text("Rendering runs on our servers. Time depends on scene complexity and queue depth.", style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        if (busy) LoadingOverlay("Saving…")
    }
}

/** Stage preview: environment backdrop + characters at their slots with clip motion (respects reduce motion). */
@Composable
fun StageCanvas(vm: StudioViewModel, scene: Storyboard.Scene, characters: List<CharacterSummary>, modifier: Modifier, animate: Boolean = true) {
    val env = vm.catalog.environment(scene.environmentId)
    val reduce = rememberReduceMotion()
    val t = if (animate && !reduce) rememberInfiniteTransition(label = "stage").animateFloat(0f, 6.283f, infiniteRepeatable(tween(2400, easing = LinearEasing)), label = "t").value else 0f
    val partsById = remember(characters, scene.characters) { scene.characters.associate { sc -> sc.characterId to characters.firstOrNull { it.id == sc.characterId }?.let { vm.assembler.assemble(it.recipe) } } }
    val tint = hex(mapOf("light_sunset" to "#FFD1A6", "light_night_neon" to "#C7B8FF")[scene.lightingPresetId] ?: "#FFFFFF")
    val zoom = mapOf("cam_wide" to 0.8f, "cam_medium" to 1f, "cam_closeup" to 1.45f, "cam_low_hero" to 1.15f, "cam_orbit" to 0.95f)[scene.cameraPresetId] ?: 1f
    Canvas(modifier.semantics { contentDescription = "Scene preview in ${env?.name} with ${scene.characters.size} characters" }) {
        drawRect(Brush.verticalGradient(listOf(hex(env?.skyTop ?: "#4A90D9"), hex(env?.skyBottom ?: "#BFE3FF"))))
        drawRect(hex(env?.ground ?: "#8FA3B8"), Offset(0f, size.height * 0.72f), Size(size.width, size.height * 0.28f))
        scene.characters.forEach { sc ->
            val parts = partsById[sc.characterId] ?: return@forEach
            val motion = vm.catalog.clip(sc.actionId)?.motion
            val dy = when (motion) { "hop" -> 0.3f * maxOf(0f, sin(t)); "float", "soar" -> 0.25f + 0.05f * sin(t); else -> 0.03f * sin(t) }
            val dx = when (motion) { "stride", "dash" -> 0.2f * sin(t / 2); "shake" -> 0.03f * sin(t * 4); else -> 0f }
            val unit = size.height * 0.36f * zoom * sc.scale.toFloat()
            val feet = Offset(size.width * (slotX[sc.position] ?: 0.5f) + dx * unit, size.height * 0.86f - dy * unit)
            drawCharacter(parts, if (motion == "spin") t else 0f, feet, unit, tint, flat = motion != "spin")
        }
    }
}
