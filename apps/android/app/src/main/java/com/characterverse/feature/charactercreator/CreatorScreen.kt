package com.characterverse.feature.charactercreator

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.characterverse.core.design.*
import com.characterverse.domain.model.CharacterCategory
import com.characterverse.domain.model.CharacterRecipe
import com.characterverse.domain.model.humanized
import com.characterverse.threed.viewer.CharacterViewer

private val swatches = listOf("#6C4DF6", "#2F6FDE", "#245A75", "#1FA5A1", "#3FA34D", "#7FB069", "#F4D35E", "#FFB547", "#F28C28",
    "#E4572E", "#D7263D", "#F27CB2", "#8E4EC6", "#4B3F72", "#29335C", "#22223B", "#B8C0CC", "#F4F4F8")

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun CreatorScreen(vm: CreatorViewModel = hiltViewModel()) {
    val s by vm.state.collectAsState()
    val r = s.recipe
    val issues = vm.issues(r)
    Box {
        Column {
            CharacterViewer(vm.assembler.assemble(r), Modifier.fillMaxWidth().height(260.dp), description = "${r.name} 3D preview")
            LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                item {
                    CvCard {
                        SectionHeader("AI description", "AI picks from approved, licence-cleared parts only")
                        OutlinedTextField(s.aiPrompt, vm::setPrompt, Modifier.fillMaxWidth(), placeholder = { Text("Describe an original character…") }, minLines = 2)
                        FilledTonalButton(vm::generate, enabled = s.aiPrompt.isNotBlank() && !s.busy) { Icon(Icons.Default.AutoAwesome, null); Spacer(Modifier.width(6.dp)); Text("Generate recipe with AI") }
                        s.aiWarnings.forEach { Text(it, color = Tokens.warning, style = MaterialTheme.typography.bodySmall) }
                    }
                }
                item {
                    CvCard {
                        SectionHeader("Identity")
                        OutlinedTextField(r.name, { v -> vm.edit { it.copy(name = v) } }, Modifier.fillMaxWidth(), label = { Text("Name") }, singleLine = true)
                        Text("Category", style = MaterialTheme.typography.labelLarge)
                        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            CharacterCategory.entries.forEach { c -> Chip(c.title, r.category == c.id, Tokens.category(c.id)) { vm.setCategory(c.id) } }
                        }
                        Text("Base body", style = MaterialTheme.typography.labelLarge)
                        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            vm.baseModelsFor(r.category).forEach { b -> Chip(b.name, r.baseModelId == b.id) { vm.setBaseModel(b.id) } }
                        }
                        Dropdown("Style", r.style, vm.catalog.manifest.styles.associateWith { it.humanized() }) { v -> vm.edit { it.copy(style = v) } }
                        Dropdown("Voice", r.voiceProfileId, vm.catalog.approvedVoices.associate { it.id to it.name }) { v -> vm.edit { it.copy(voiceProfileId = v) } }
                    }
                }
                item {
                    CvCard {
                        SectionHeader("Body & face")
                        Proportion("Height", r.proportions.height) { v -> vm.edit { it.copy(proportions = it.proportions.copy(height = v)) } }
                        Proportion("Shoulder width", r.proportions.shoulderWidth) { v -> vm.edit { it.copy(proportions = it.proportions.copy(shoulderWidth = v)) } }
                        Proportion("Head size", r.proportions.headScale) { v -> vm.edit { it.copy(proportions = it.proportions.copy(headScale = v)) } }
                    }
                }
                item {
                    CvCard {
                        SectionHeader("Colours & materials")
                        SwatchRow("Primary", r.palette.primary) { v -> vm.edit { it.copy(palette = it.palette.copy(primary = v)) } }
                        SwatchRow("Secondary", r.palette.secondary) { v -> vm.edit { it.copy(palette = it.palette.copy(secondary = v)) } }
                        SwatchRow("Accent", r.palette.accent) { v -> vm.edit { it.copy(palette = it.palette.copy(accent = v)) } }
                    }
                }
                item {
                    CvCard {
                        SectionHeader("Outfit & accessories", "Only parts that fit this body are shown. One per slot.")
                        vm.slots().forEach { (slot, modules) ->
                            val current = r.modules.firstOrNull { vm.catalog.module(it)?.slot == slot }
                            Dropdown(slot.humanized(), current ?: "", mapOf("" to "None") + modules.associate { it.id to it.name }) { v -> vm.setModule(v.ifEmpty { null }, slot) }
                        }
                    }
                }
                item {
                    CvCard {
                        SectionHeader("Powers & effects (up to 3)")
                        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) { vm.availablePowers().forEach { p -> Chip(p.name, p.id in r.powers) { vm.togglePower(p.id) } } }
                        SectionHeader("Personality (up to 5)")
                        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            vm.catalog.manifest.personalityTraits.forEach { t -> Chip(t.humanized(), t in r.personalityTraits, Tokens.brandSecondary) { vm.toggleTrait(t) } }
                        }
                    }
                }
                if (issues.isNotEmpty()) item {
                    CvCard { SectionHeader("Fix before saving"); issues.forEach { Text("• ${it.message}", color = Tokens.danger) } }
                }
                item {
                    s.error?.let { ErrorBanner(it) }
                    s.saved?.let { Text(it, color = Tokens.success, fontWeight = FontWeight.Bold) }
                    Spacer(Modifier.height(8.dp))
                    Button({ vm.save() }, Modifier.fillMaxWidth().height(52.dp), enabled = issues.isEmpty() && !s.busy) {
                        Icon(Icons.Default.Save, null); Spacer(Modifier.width(8.dp)); Text(if (s.editingId == null) "Save to My Universe" else "Save new version")
                    }
                }
            }
        }
        if (s.busy) LoadingOverlay("Working…")
    }
}

@Composable
private fun Proportion(label: String, value: Double, onChange: (Double) -> Unit) {
    Column {
        Row { Text(label, Modifier.weight(1f)); Text("%.2f".format(value), color = MaterialTheme.colorScheme.onSurfaceVariant) }
        Slider(value.toFloat(), { onChange(Math.round(it * 100) / 100.0) }, valueRange = 0.7f..1.3f, modifier = Modifier.semantics { contentDescription = label })
    }
}

@Composable
private fun SwatchRow(label: String, value: String, onPick: (String) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(label, style = MaterialTheme.typography.labelLarge)
        LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            items(swatches) { c ->
                Box(Modifier.size(32.dp).background(hex(c), CircleShape).border(if (c.equals(value, true)) 3.dp else 1.dp,
                    if (c.equals(value, true)) Tokens.brand else hex("#DDDDDD"), CircleShape).clickable { onPick(c) }
                    .semantics { contentDescription = "$label colour $c" })
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun Dropdown(label: String, selected: String, options: Map<String, String>, onSelect: (String) -> Unit) {
    var open by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(open, { open = it }) {
        OutlinedTextField(options[selected] ?: selected, {}, readOnly = true, label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(open) },
            modifier = Modifier.fillMaxWidth().menuAnchor(MenuAnchorType.PrimaryNotEditable))
        ExposedDropdownMenu(open, { open = false }) {
            options.forEach { (id, name) -> DropdownMenuItem({ Text(name) }, { onSelect(id); open = false }) }
        }
    }
}
