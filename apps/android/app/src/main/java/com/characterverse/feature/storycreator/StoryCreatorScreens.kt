package com.characterverse.feature.storycreator

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.characterverse.core.design.*
import com.characterverse.data.dto.GenerateStoryRequestDto
import com.characterverse.feature.charactercreator.Dropdown
import com.characterverse.threed.viewer.CharacterThumbnail

@Composable
fun StudioHomeScreen(vm: StudioViewModel, activeRenders: Int, onNew: () -> Unit, onQueue: () -> Unit, onProject: (String) -> Unit) {
    val projects by vm.projects.collectAsState()
    LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Button(onNew, Modifier.weight(1f).height(52.dp)) { Icon(Icons.Default.AddToQueue, null); Spacer(Modifier.width(6.dp)); Text("New short") }
                FilledTonalButton(onQueue, Modifier.weight(1f).height(52.dp)) {
                    Icon(Icons.Default.Layers, null); Spacer(Modifier.width(6.dp)); Text(if (activeRenders > 0) "Queue ($activeRenders)" else "Render queue")
                }
            }
        }
        item { SectionHeader("Projects") }
        if (projects.isEmpty()) item { EmptyState(Icons.Default.Movie, "No projects yet", "Generate a story with your characters to start a storyboard.") }
        items(projects, key = { it.id }) { p ->
            CvCard(Modifier.clickable { onProject(p.id) }) {
                Text(p.title, fontWeight = FontWeight.Bold)
                Text("${p.storyboard?.scenes?.size ?: 0} scenes · ${p.storyboard?.durationSeconds ?: 0}s · ${p.status}", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun StoryCreatorScreen(vm: StudioViewModel, onOpenStoryboard: (String) -> Unit) {
    val characters by vm.characters.characters.collectAsState()
    val story by vm.story.collectAsState()
    val busy by vm.busy.collectAsState()
    val error by vm.error.collectAsState()
    var prompt by remember { mutableStateOf("find the glowing map in the crystal forest") }
    var genre by remember { mutableStateOf("adventure") }
    var tone by remember { mutableStateOf("playful") }
    var audience by remember { mutableStateOf("family") }
    var duration by remember { mutableIntStateOf(30) }
    var aspect by remember { mutableStateOf("16:9") }
    var language by remember { mutableStateOf("en") }
    val cast = remember { mutableStateListOf<String>() }
    LaunchedEffect(characters) { if (cast.isEmpty()) cast.addAll(characters.filter { !it.archived && it.lineage.isEmpty() }.take(2).map { it.id }) }

    Box {
        LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            item {
                CvCard {
                    SectionHeader("Story idea")
                    OutlinedTextField(prompt, { prompt = it }, Modifier.fillMaxWidth(), minLines = 2, label = { Text("What happens?") })
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        vm.catalog.manifest.storyTemplates.forEach { t -> AssistChip({ genre = t.genre; tone = t.tone; prompt = t.name.lowercase() }, { Text(t.name) }) }
                    }
                }
            }
            item {
                CvCard {
                    SectionHeader("Style")
                    Dropdown("Genre", genre, listOf("adventure", "comedy", "fantasy", "mystery", "sci-fi").associateWith { it.replaceFirstChar(Char::uppercase) }) { genre = it }
                    Dropdown("Tone", tone, listOf("playful", "uplifting", "heartwarming", "mysterious", "calm").associateWith { it.replaceFirstChar(Char::uppercase) }) { tone = it }
                    Dropdown("Audience", audience, listOf("family", "kids", "teens", "everyone").associateWith { it.replaceFirstChar(Char::uppercase) }) { audience = it }
                    Dropdown("Language", language, mapOf("en" to "English", "fr" to "Français", "es" to "Español")) { language = it }
                    Text("Duration", style = MaterialTheme.typography.labelLarge)
                    SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                        listOf(15, 30, 60).forEachIndexed { i, d -> SegmentedButton(duration == d, { duration = d }, SegmentedButtonDefaults.itemShape(i, 3)) { Text("$d s") } }
                    }
                    SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                        listOf("16:9", "9:16").forEachIndexed { i, a -> SegmentedButton(aspect == a, { aspect = a }, SegmentedButtonDefaults.itemShape(i, 2)) { Text(if (a == "16:9") "Landscape" else "Vertical") } }
                    }
                }
            }
            item { SectionHeader("Cast (1–4)") }
            items(characters.filter { !it.archived }, key = { it.id }) { c ->
                Row(Modifier.fillMaxWidth().clickable { if (c.id in cast) cast.remove(c.id) else if (cast.size < 4) cast.add(c.id) }, verticalAlignment = Alignment.CenterVertically) {
                    CharacterThumbnail(remember(c.id) { vm.assembler.assemble(c.recipe) }, Modifier.size(44.dp, 48.dp))
                    Text(c.name, Modifier.weight(1f).padding(start = 8.dp))
                    Checkbox(c.id in cast, null)
                }
            }
            error?.let { item { ErrorBanner(it) } }
            story?.let { r ->
                item {
                    CvCard {
                        SectionHeader("Outline")
                        Text(r.storyboard.title, fontWeight = FontWeight.Bold)
                        Text(r.storyboard.logline)
                        r.storyboard.scenes.forEach { s ->
                            Text("${s.sequence}. ${s.title}", fontWeight = FontWeight.SemiBold)
                            s.dialogue.forEach { Text("“${it.line}”", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                        }
                        Text(r.moderation.feedback ?: "Originality check passed", color = if (r.moderation.feedback == null) Tokens.success else Tokens.warning,
                            style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            item {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    FilledTonalButton({ vm.generate(GenerateStoryRequestDto(prompt, cast.toList(), genre = genre, tone = tone, audience = audience,
                        durationSeconds = duration, aspectRatio = aspect, language = language)) }, Modifier.fillMaxWidth().height(52.dp), enabled = cast.isNotEmpty() && !busy) {
                        Icon(Icons.Default.AutoAwesome, null); Spacer(Modifier.width(6.dp)); Text(if (story == null) "Generate story" else "Regenerate")
                    }
                    if (story != null) Button({ vm.createProject(onOpenStoryboard) }, Modifier.fillMaxWidth().height(52.dp)) { Text("Open storyboard") }
                }
            }
        }
        if (busy) LoadingOverlay("Writing your story…")
    }
}
