package com.characterverse.feature.discover

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.characterverse.app.SessionViewModel
import com.characterverse.core.design.*
import com.characterverse.domain.model.AssetManifest
import com.characterverse.domain.model.CharacterCategory
import com.characterverse.domain.model.CharacterRecipe
import com.characterverse.domain.model.humanized
import com.characterverse.threed.viewer.CharacterThumbnail
import com.characterverse.threed.viewer.CharacterViewer

fun categoryIcon(c: CharacterCategory): ImageVector = when (c) {
    CharacterCategory.HERO -> Icons.Default.Shield
    CharacterCategory.VILLAIN -> Icons.Default.TheaterComedy
    CharacterCategory.CARTOON -> Icons.Default.EmojiEmotions
    CharacterCategory.FANTASY -> Icons.Default.AutoAwesome
    CharacterCategory.ROBOT -> Icons.Default.PrecisionManufacturing
    CharacterCategory.ALIEN -> Icons.Default.Public
    CharacterCategory.CREATURE -> Icons.Default.Pets
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DiscoverScreen(session: SessionViewModel, onTemplate: (String) -> Unit, onCreate: () -> Unit) {
    var search by remember { mutableStateOf("") }
    var category by remember { mutableStateOf<String?>(null) }
    var tutorial by remember { mutableStateOf(true) }
    val user by session.user.collectAsState()
    val templates = session.catalog.manifest.characterTemplates.filter {
        (category == null || it.recipe.category == category) && (search.isBlank() || it.recipe.name.contains(search, true) || it.recipe.powers.any { p -> p.contains(search.lowercase()) })
    }
    LazyVerticalGrid(GridCells.Fixed(2), Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item(span = { GridItemSpan(2) }) {
            OutlinedTextField(search, { search = it }, Modifier.fillMaxWidth(), placeholder = { Text("Search templates or powers") },
                leadingIcon = { Icon(Icons.Default.Search, null) }, singleLine = true, shape = RoundedCornerShape(14.dp))
        }
        if (tutorial) item(span = { GridItemSpan(2) }) {
            Box(Modifier.fillMaxWidth().background(Tokens.heroGradient, RoundedCornerShape(22.dp)).padding(18.dp)) {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Welcome, ${user?.displayName ?: "creator"}!", color = Color.White, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Text("1. Create a character  2. Mix two into a hybrid  3. Generate a story  4. Render a short video", color = Color.White)
                    TextButton(onCreate, colors = ButtonDefaults.textButtonColors(contentColor = Color.White)) { Text("Create my first character", fontWeight = FontWeight.Bold) }
                }
                IconButton({ tutorial = false }, Modifier.align(Alignment.TopEnd)) { Icon(Icons.Default.Close, "Dismiss tutorial", tint = Color.White) }
            }
        }
        item(span = { GridItemSpan(2) }) { SectionHeader("Categories", "Start from an original template") }
        item(span = { GridItemSpan(2) }) {
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                CharacterCategory.entries.forEach { c ->
                    val selected = category == c.id
                    val color = Tokens.category(c.id)
                    Column(Modifier.width(86.dp).background(if (selected) color else color.copy(alpha = 0.12f), RoundedCornerShape(14.dp))
                        .clickable { category = if (selected) null else c.id }.padding(vertical = 14.dp)
                        .semantics { contentDescription = "${c.title} category" },
                        horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(categoryIcon(c), null, tint = if (selected) Color.White else color)
                        Text(c.title, color = if (selected) Color.White else color, style = MaterialTheme.typography.labelLarge)
                    }
                }
            }
        }
        item(span = { GridItemSpan(2) }) { SectionHeader(if (category == null) "Featured originals" else "${category!!.humanized()} templates") }
        if (templates.isEmpty()) item(span = { GridItemSpan(2) }) { EmptyState(Icons.Default.Search, "No matches", "Try another search or category.") }
        items(templates, key = { it.id }) { t -> TemplateCard(session, t) { onTemplate(t.id) } }
    }
}

@Composable
fun TemplateCard(session: SessionViewModel, t: AssetManifest.CharacterTemplate, onClick: () -> Unit) {
    val parts = remember(t.id) { session.assembler.assemble(t.recipe) }
    Column(Modifier.background(MaterialTheme.colorScheme.surface, RoundedCornerShape(22.dp)).clickable(onClick = onClick).padding(10.dp)
        .semantics(mergeDescendants = true) { contentDescription = "${t.recipe.name}, ${t.recipe.category} template" },
        verticalArrangement = Arrangement.spacedBy(8.dp)) {
        CharacterThumbnail(parts, Modifier.fillMaxWidth().height(150.dp).background(Tokens.category(t.recipe.category).copy(alpha = 0.12f), RoundedCornerShape(14.dp)))
        Text(t.recipe.name, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(t.recipe.category.humanized(), color = Tokens.category(t.recipe.category), style = MaterialTheme.typography.labelMedium, modifier = Modifier.weight(1f))
            PaletteDots(t.recipe.palette)
        }
    }
}

@Composable
fun TemplateDetailScreen(session: SessionViewModel, templateId: String, onCustomize: (CharacterRecipe) -> Unit) {
    val t = session.catalog.manifest.characterTemplates.firstOrNull { it.id == templateId } ?: return
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        CharacterViewer(remember { session.assembler.assemble(t.recipe) }, Modifier.fillMaxWidth().height(340.dp).background(Color.Transparent, RoundedCornerShape(22.dp)),
            description = "${t.recipe.name} 3D preview")
        RecipeSummary(session, t.recipe)
        Button({ onCustomize(t.recipe) }, Modifier.fillMaxWidth().height(52.dp)) { Icon(Icons.Default.Tune, null); Spacer(Modifier.width(8.dp)); Text("Customize this template") }
        Text("Original CharacterVerse template · licence lic_cv_original_v1 (commercial use approved)", style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun RecipeSummary(session: SessionViewModel, recipe: CharacterRecipe) {
    val cat = session.catalog
    CvCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(recipe.category.humanized(), color = Tokens.category(recipe.category), fontWeight = FontWeight.Bold,
                modifier = Modifier.background(Tokens.category(recipe.category).copy(alpha = 0.15f), RoundedCornerShape(50)).padding(horizontal = 10.dp, vertical = 4.dp))
            Spacer(Modifier.width(8.dp))
            Text(recipe.style.humanized(), style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
            PaletteDots(recipe.palette)
        }
        SummaryRow("Body", cat.baseModel(recipe.baseModelId)?.name ?: recipe.baseModelId)
        SummaryRow("Outfit & accessories", recipe.modules.joinToString { cat.module(it)?.name ?: it })
        SummaryRow("Powers", recipe.powers.joinToString { it.humanized() })
        SummaryRow("Personality", recipe.personalityTraits.joinToString { it.humanized() })
        SummaryRow("Voice", cat.voice(recipe.voiceProfileId)?.name ?: recipe.voiceProfileId)
    }
}

@Composable
private fun SummaryRow(title: String, value: String) {
    Column(Modifier.semantics(mergeDescendants = true) {}) {
        Text(title, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value.ifEmpty { "None" }, style = MaterialTheme.typography.bodyMedium)
    }
}
