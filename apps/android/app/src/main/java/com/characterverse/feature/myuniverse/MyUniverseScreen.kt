package com.characterverse.feature.myuniverse

import android.text.format.Formatter
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.characterverse.app.CreatorSeed
import com.characterverse.core.design.*
import com.characterverse.core.network.ApiError
import com.characterverse.data.dto.UpdateCharacterDto
import com.characterverse.data.dto.UsageDto
import com.characterverse.data.repository.RemoteRepository
import com.characterverse.domain.model.CharacterCategory
import com.characterverse.domain.model.CharacterRecipe
import com.characterverse.domain.model.CharacterSummary
import com.characterverse.domain.model.humanized
import com.characterverse.domain.repository.DraftRepository
import com.characterverse.domain.usecase.PartAssembler
import com.characterverse.feature.discover.RecipeSummary
import com.characterverse.app.SessionViewModel
import com.characterverse.threed.viewer.CharacterThumbnail
import com.characterverse.threed.viewer.CharacterViewer
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class UniverseViewModel @Inject constructor(
    val repo: RemoteRepository, val drafts: DraftRepository, val assembler: PartAssembler, private val seed: CreatorSeed,
) : ViewModel() {
    val characters = repo.characters
    val projects = repo.projects
    val renders = repo.renders
    val usage = MutableStateFlow<UsageDto?>(null)
    val error = MutableStateFlow<String?>(null)

    init { viewModelScope.launch { usage.value = runCatching { repo.usage() }.getOrNull() } }

    private fun act(block: suspend () -> Unit) = viewModelScope.launch { runCatching { block() }.onFailure { error.value = ApiError.from(it).userMessage } }
    fun favorite(c: CharacterSummary) = act { repo.update(c.id, UpdateCharacterDto(isFavorite = !c.isFavorite)) }
    fun archive(c: CharacterSummary) = act { repo.update(c.id, UpdateCharacterDto(archived = !c.archived)) }
    fun duplicate(c: CharacterSummary) = act { repo.duplicate(c.id) }
    fun delete(c: CharacterSummary) = act { repo.delete(c.id) }
    fun report(c: CharacterSummary) = act { repo.report("character", c.id, "copyright") }
    fun edit(recipe: CharacterRecipe, id: String?) { seed.pending.value = recipe to id }
    fun discardDraft(id: String) = act { drafts.remove(id) }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MyUniverseScreen(onCharacter: (String) -> Unit, onProject: (String) -> Unit, onVideos: () -> Unit, onCreate: () -> Unit, vm: UniverseViewModel = hiltViewModel()) {
    val tabs = listOf("Characters", "Favorites", "Projects", "Videos", "Drafts")
    var tab by remember { mutableIntStateOf(0) }
    var search by remember { mutableStateOf("") }
    var sort by remember { mutableStateOf("updated") }
    var category by remember { mutableStateOf<String?>(null) }
    var showArchived by remember { mutableStateOf(false) }
    var menu by remember { mutableStateOf(false) }
    val characters by vm.characters.collectAsState()
    val projects by vm.projects.collectAsState()
    val renders by vm.renders.collectAsState()
    val drafts by vm.drafts.drafts.collectAsState(emptyList())
    val usage by vm.usage.collectAsState()
    val context = LocalContext.current
    val filtered = characters.filter { (showArchived || !it.archived) && (tab != 1 || it.isFavorite) && (category == null || it.category == category) && it.name.contains(search, true) }
        .let { l -> when (sort) { "name" -> l.sortedBy { it.name }; "created" -> l.sortedByDescending { it.createdAt }; else -> l.sortedByDescending { it.updatedAt } } }

    Column {
        ScrollableTabRow(tab, edgePadding = 8.dp) { tabs.forEachIndexed { i, t -> Tab(tab == i, { tab = i }, text = { Text(t) }) } }
        LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            usage?.let { u ->
                item {
                    Text("${u.characters} characters · ${u.projects} projects · ${u.renders} renders · ${Formatter.formatShortFileSize(context, u.storageBytes)}",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            when (tab) {
                0, 1 -> {
                    item {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            OutlinedTextField(search, { search = it }, Modifier.weight(1f), placeholder = { Text("Search characters") }, singleLine = true,
                                leadingIcon = { Icon(Icons.Default.Search, null) }, shape = RoundedCornerShape(14.dp))
                            Box {
                                IconButton({ menu = true }) { Icon(Icons.Default.FilterList, "Sort and filter") }
                                DropdownMenu(menu, { menu = false }) {
                                    listOf("updated" to "Recently edited", "created" to "Newest", "name" to "Name").forEach { (k, l) ->
                                        DropdownMenuItem({ Text(l) }, { sort = k; menu = false }, leadingIcon = { if (sort == k) Icon(Icons.Default.Check, null) })
                                    }
                                    HorizontalDivider()
                                    DropdownMenuItem({ Text("All categories") }, { category = null; menu = false })
                                    CharacterCategory.entries.forEach { c -> DropdownMenuItem({ Text(c.title) }, { category = c.id; menu = false }) }
                                    HorizontalDivider()
                                    DropdownMenuItem({ Text(if (showArchived) "Hide archived" else "Show archived") }, { showArchived = !showArchived; menu = false })
                                }
                            }
                        }
                    }
                    if (filtered.isEmpty()) item { EmptyState(Icons.Default.PersonOutline, "No characters here", "Create an original character to fill your universe.", "Create", onCreate) }
                    items(filtered, key = { it.id }) { c -> CharacterRow(vm.assembler, c) { onCharacter(c.id) } }
                }
                2 -> {
                    if (projects.isEmpty()) item { EmptyState(Icons.Default.Movie, "No projects", "Projects you create in the Studio appear here.") }
                    items(projects, key = { it.id }) { p -> CvCard(Modifier.clickable { onProject(p.id) }) { Text(p.title, fontWeight = FontWeight.Bold); Text("${p.storyboard?.scenes?.size ?: 0} scenes") } }
                }
                3 -> {
                    val done = renders.filter { it.status == com.characterverse.domain.model.RenderJob.Status.COMPLETED }
                    if (done.isEmpty()) item { EmptyState(Icons.Default.VideoLibrary, "No videos yet", "Finished renders appear here.") }
                    items(done, key = { it.id }) { j -> ListItem({ Text("${j.projectTitle} · ${j.quality} · ${(j.durationMs ?: 0) / 1000}s") }, Modifier.clickable(onClick = onVideos),
                        leadingContent = { Icon(Icons.Default.PlayCircle, null, tint = Tokens.brand) }) }
                }
                else -> {
                    if (drafts.isEmpty()) item { EmptyState(Icons.Default.Description, "No local drafts", "Unsaved creator edits are kept here, even offline.") }
                    items(drafts, key = { it.id }) { d ->
                        ListItem({ Text(d.recipe.name) }, Modifier.clickable { vm.edit(d.recipe, d.serverCharacterId); onCreate() },
                            supportingContent = { Text(android.text.format.DateUtils.getRelativeTimeSpanString(d.updatedAt).toString()) },
                            leadingContent = { CharacterThumbnail(vm.assembler.assemble(d.recipe), Modifier.size(44.dp, 48.dp)) },
                            trailingContent = { IconButton({ vm.discardDraft(d.id) }) { Icon(Icons.Default.Delete, "Discard draft") } })
                    }
                }
            }
        }
    }
}

@Composable
fun CharacterRow(assembler: PartAssembler, c: CharacterSummary, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surface, RoundedCornerShape(16.dp)).clickable(onClick = onClick).padding(10.dp)
        .semantics(mergeDescendants = true) {}, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        CharacterThumbnail(remember(c.id, c.version) { assembler.assemble(c.recipe) },
            Modifier.size(58.dp, 64.dp).background(Tokens.category(c.category).copy(alpha = 0.12f), RoundedCornerShape(12.dp)))
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(c.name, fontWeight = FontWeight.Bold)
                if (c.isFavorite) Icon(Icons.Default.Star, "Favorite", tint = Tokens.accent, modifier = Modifier.size(16.dp))
                if (c.lineage.isNotEmpty()) Icon(Icons.Default.MergeType, "Fusion", tint = Tokens.brand, modifier = Modifier.size(16.dp))
            }
            Text(c.category.humanized(), color = Tokens.category(c.category), style = MaterialTheme.typography.labelMedium)
            Text("v${c.version}${if (c.archived) " · Archived" else ""}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        PaletteDots(c.recipe.palette)
    }
}

@Composable
fun CharacterDetailScreen(session: SessionViewModel, characterId: String, onEdit: () -> Unit, onDeleted: () -> Unit, vm: UniverseViewModel = hiltViewModel()) {
    val characters by vm.characters.collectAsState()
    val c = characters.firstOrNull { it.id == characterId } ?: run { EmptyState(Icons.Default.HelpOutline, "Character not found", "It may have been deleted."); return }
    var confirm by remember { mutableStateOf(false) }
    var reported by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        CharacterViewer(remember(c.version) { vm.assembler.assemble(c.recipe) }, Modifier.fillMaxWidth().height(340.dp), description = "${c.name} 3D preview")
        RecipeSummary(session, c.recipe)
        if (c.lineage.isNotEmpty()) CvCard {
            SectionHeader("Fusion lineage")
            c.lineage.forEach { li -> Row { Text(characters.firstOrNull { it.id == li.sourceCharacterId }?.name ?: "Deleted character", Modifier.weight(1f))
                Text("${(li.contributionWeight * 100).toInt()}% · ${li.mixDimension.replace(",", ", ")}", style = MaterialTheme.typography.bodySmall) } }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button({ vm.edit(c.recipe, c.id); onEdit() }, Modifier.weight(1f)) { Icon(Icons.Default.Edit, null); Text("Edit") }
            FilledTonalButton({ vm.duplicate(c) }, Modifier.weight(1f)) { Icon(Icons.Default.ContentCopy, null); Text("Duplicate") }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton({ vm.favorite(c) }) { Icon(if (c.isFavorite) Icons.Default.Star else Icons.Default.StarBorder, null); Text(if (c.isFavorite) "Unfavorite" else "Favorite") }
            OutlinedButton({ vm.archive(c) }) { Icon(Icons.Default.Archive, null); Text(if (c.archived) "Unarchive" else "Archive") }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton({ vm.report(c); reported = true }) { Icon(Icons.Default.Flag, null); Text("Report") }
            TextButton({ confirm = true }, colors = ButtonDefaults.textButtonColors(contentColor = Tokens.danger)) { Icon(Icons.Default.Delete, null); Text("Delete") }
        }
    }
    if (confirm) AlertDialog({ confirm = false }, { TextButton({ vm.delete(c); confirm = false; onDeleted() }) { Text("Delete") } },
        dismissButton = { TextButton({ confirm = false }) { Text("Cancel") } }, title = { Text("Delete ${c.name}?") })
    if (reported) AlertDialog({ reported = false }, { TextButton({ reported = false }) { Text("OK") } }, text = { Text("Thanks — our team will review this.") })
}
