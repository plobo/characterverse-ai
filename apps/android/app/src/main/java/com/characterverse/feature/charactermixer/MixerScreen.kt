package com.characterverse.feature.charactermixer

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Undo
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.characterverse.core.design.*
import com.characterverse.domain.model.humanized
import com.characterverse.domain.usecase.MixDimension
import com.characterverse.threed.viewer.CharacterThumbnail
import com.characterverse.threed.viewer.CharacterViewer

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun MixerScreen(onSaved: (String) -> Unit, onCreate: () -> Unit, demo: Boolean = false, vm: MixerViewModel = hiltViewModel()) {
    val s by vm.state.collectAsState()
    LaunchedEffect(demo, s.characters.size) { if (demo) vm.demoSelect() }
    Box {
        LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            item {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.weight(1f)) { SectionHeader("1. Pick 2–3 characters", "Only characters you own can be mixed") }
                    IconButton(vm::undo, enabled = s.canUndo) { Icon(Icons.AutoMirrored.Filled.Undo, "Undo") }
                }
            }
            if (s.characters.size < 2) item { EmptyState(Icons.Default.Group, "Need two characters", "Create or save at least two characters to start mixing.", "Create a character", onCreate) }
            item {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    items(s.characters, key = { it.id }) { c ->
                        val selected = c.id in s.inputs.selected
                        Column(Modifier.width(112.dp).background(MaterialTheme.colorScheme.surface, RoundedCornerShape(14.dp))
                            .border(3.dp, if (selected) Tokens.brand else Color.Transparent, RoundedCornerShape(14.dp))
                            .clickable { vm.toggle(c.id) }.padding(8.dp).semantics(mergeDescendants = true) { this.selected = selected },
                            horizontalAlignment = Alignment.CenterHorizontally) {
                            CharacterThumbnail(remember(c.id, c.version) { vm.assembler.assemble(c.recipe) }, Modifier.size(96.dp, 104.dp))
                            Text(c.name, style = MaterialTheme.typography.labelMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        }
                    }
                }
            }
            item { SectionHeader("2. What to mix") }
            item { FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) { MixDimension.entries.forEach { d -> Chip(d.title, d in s.inputs.dimensions) { vm.toggleDimension(d) } } } }
            if (s.inputs.selected.size >= 2) {
                item { SectionHeader("3. Trait contribution") }
                items(s.inputs.selected) { id ->
                    val c = s.characters.firstOrNull { it.id == id } ?: return@items
                    val total = s.inputs.selected.sumOf { s.inputs.weights[it] ?: 1.0 }
                    val share = ((s.inputs.weights[id] ?: 1.0) / total * 100).toInt()
                    Column {
                        Row { Text(c.name, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f)); Text("$share%") }
                        Slider((s.inputs.weights[id] ?: 1.0).toFloat(), { vm.setWeight(id, it.toDouble()) }, valueRange = 0f..3f,
                            onValueChangeFinished = {}, modifier = Modifier.semantics { contentDescription = "${c.name} contribution"; stateDescription = "$share percent" })
                    }
                }
            }
            s.result?.let { r ->
                item {
                    CvCard {
                        Row(verticalAlignment = Alignment.CenterVertically) { Text("Fusion preview", fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f)); PaletteDots(r.recipe.palette) }
                        CharacterViewer(vm.assembler.assemble(r.recipe), Modifier.fillMaxWidth().height(260.dp), description = "${r.recipe.name} fusion preview")
                        OutlinedTextField(s.inputs.name, vm::setName, Modifier.fillMaxWidth(), placeholder = { Text(r.recipe.name) }, label = { Text("Name") }, singleLine = true)
                        if (s.suggestions.isNotEmpty()) FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            s.suggestions.forEach { sug -> Chip(sug.name, s.inputs.name == sug.name, Tokens.brandSecondary) { vm.setName(sug.name) } }
                        }
                        Text("Powers: ${r.recipe.powers.joinToString { it.humanized() }}  ·  Traits: ${r.recipe.personalityTraits.joinToString()}",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            FilledTonalButton({ if (s.suggestions.isEmpty()) vm.fetchSuggestions() else vm.nextSuggestion() }, Modifier.weight(1f)) {
                                Icon(Icons.Default.AutoAwesome, null); Spacer(Modifier.width(6.dp)); Text(if (s.suggestions.isEmpty()) "AI suggestions" else "Regenerate")
                            }
                            Button({ vm.save(onSaved) }, Modifier.weight(1f)) { Icon(Icons.Default.AddCircle, null); Spacer(Modifier.width(6.dp)); Text("Save") }
                        }
                    }
                }
            }
            items(s.warnings) { w -> Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) { Icon(Icons.Default.Warning, null, tint = Tokens.warning, modifier = Modifier.size(18.dp)); Text(w, style = MaterialTheme.typography.bodySmall, color = Tokens.warning) } }
            s.error?.let { item { ErrorBanner(it) } }
        }
        if (s.busy) LoadingOverlay("Mixing…")
    }
}
