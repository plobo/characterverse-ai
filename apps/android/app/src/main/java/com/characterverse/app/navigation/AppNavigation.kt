package com.characterverse.app.navigation

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.characterverse.app.SessionViewModel
import com.characterverse.feature.animationstudio.SceneEditorScreen
import com.characterverse.feature.charactercreator.CreatorScreen
import com.characterverse.feature.charactermixer.MixerScreen
import com.characterverse.feature.discover.DiscoverScreen
import com.characterverse.feature.discover.TemplateDetailScreen
import com.characterverse.feature.myuniverse.CharacterDetailScreen
import com.characterverse.feature.myuniverse.MyUniverseScreen
import com.characterverse.feature.renderqueue.RenderQueueScreen
import com.characterverse.feature.settings.SettingsScreen
import com.characterverse.feature.storyboard.StoryboardScreen
import com.characterverse.feature.storycreator.StoryCreatorScreen
import com.characterverse.feature.storycreator.StudioHomeScreen
import com.characterverse.feature.storycreator.StudioViewModel

enum class Tab(val route: String, val title: String, val icon: ImageVector) {
    DISCOVER("discover", "Discover", Icons.Default.Explore),
    CREATE("create", "Create", Icons.Default.AutoFixHigh),
    MIXER("mixer?demo=false", "Mixer", Icons.Default.MergeType),
    STUDIO("studio", "Studio", Icons.Default.Movie),
    UNIVERSE("universe", "My Universe", Icons.Default.Public),
}

private val titles = mapOf("template" to "Template", "character" to "Character", "story" to "Story Creator", "storyboard" to "Storyboard",
    "scene" to "Animation Studio", "renders" to "Render Queue", "settings" to "Settings")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScaffold(session: SessionViewModel, startScreen: String? = null) {
    val nav = rememberNavController()
    val entry by nav.currentBackStackEntryAsState()
    val route = entry?.destination?.route.orEmpty()
    val base = route.substringBefore("/").substringBefore("?")
    val tab = Tab.entries.firstOrNull { it.route.substringBefore("?") == base }
    val offline by session.offline.collectAsState()
    val studio: StudioViewModel = hiltViewModel()
    val renders by session.repo.renders.collectAsState()
    val projects by session.repo.projects.collectAsState()
    val characters by session.repo.characters.collectAsState()

    LaunchedEffect(startScreen, projects.isNotEmpty(), characters.isNotEmpty()) {
        val p = projects.firstOrNull()
        when (startScreen) {
            "create" -> session.catalog.manifest.characterTemplates.firstOrNull()?.let { session.creatorSeed.pending.value = it.recipe to null; nav.go(Tab.CREATE.route) }
            "mixer" -> nav.go("mixer?demo=true")
            "studio" -> nav.go(Tab.STUDIO.route)
            "story" -> nav.navigate("story")
            "storyboard" -> p?.let { nav.navigate("storyboard/${it.id}") }
            "scene" -> p?.storyboard?.scenes?.firstOrNull()?.let { nav.navigate("scene/${p.id}/${it.sceneId}") }
            "renders" -> nav.navigate("renders")
            "universe" -> nav.go(Tab.UNIVERSE.route)
            "detail" -> characters.firstOrNull { it.lineage.isEmpty() }?.let { nav.navigate("character/${it.id}") }
            "settings" -> nav.navigate("settings")
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(title = { Text(tab?.title ?: titles[base] ?: "CharacterVerse") },
                navigationIcon = { if (tab == null && route.isNotEmpty()) IconButton({ nav.popBackStack() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } },
                actions = { if (tab == Tab.UNIVERSE) IconButton({ nav.navigate("settings") }) { Icon(Icons.Default.Settings, "Settings") } })
        },
        bottomBar = {
            NavigationBar {
                Tab.entries.forEach { t ->
                    NavigationBarItem(selected = tab == t, onClick = { nav.go(t.route) }, icon = { Icon(t.icon, null) }, label = { Text(t.title) })
                }
            }
        },
    ) { padding ->
        Box(Modifier.padding(padding)) {
            NavHost(nav, startDestination = Tab.DISCOVER.route) {
                composable(Tab.DISCOVER.route) { DiscoverScreen(session, { nav.navigate("template/$it") }, { nav.go(Tab.CREATE.route) }) }
                composable("template/{id}") { e ->
                    TemplateDetailScreen(session, e.arguments?.getString("id").orEmpty()) { session.creatorSeed.pending.value = it to null; nav.go(Tab.CREATE.route) }
                }
                composable(Tab.CREATE.route) { CreatorScreen() }
                composable("mixer?demo={demo}") { e ->
                    MixerScreen({ id -> nav.navigate("character/$id") }, { nav.go(Tab.CREATE.route) }, demo = e.arguments?.getString("demo") == "true")
                }
                composable(Tab.STUDIO.route) {
                    StudioHomeScreen(studio, renders.count { it.isActive }, { nav.navigate("story") }, { nav.navigate("renders") }) { nav.navigate("storyboard/$it") }
                }
                composable("story") { StoryCreatorScreen(studio) { id -> nav.navigate("storyboard/$id") } }
                composable("storyboard/{id}") { e ->
                    val id = e.arguments?.getString("id").orEmpty()
                    StoryboardScreen(studio, id, { sid -> nav.navigate("scene/$id/$sid") }) { nav.navigate("renders") }
                }
                composable("scene/{pid}/{sid}") { e ->
                    SceneEditorScreen(studio, e.arguments?.getString("pid").orEmpty(), e.arguments?.getString("sid").orEmpty(), onDone = { nav.popBackStack() })
                }
                composable("renders") { RenderQueueScreen() }
                composable(Tab.UNIVERSE.route) {
                    MyUniverseScreen({ nav.navigate("character/$it") }, { nav.navigate("storyboard/$it") }, { nav.navigate("renders") }, { nav.go(Tab.CREATE.route) })
                }
                composable("character/{id}") { e ->
                    CharacterDetailScreen(session, e.arguments?.getString("id").orEmpty(), onEdit = { nav.go(Tab.CREATE.route) },
                        onDeleted = { nav.popBackStack() })
                }
                composable("settings") { SettingsScreen({ session.signOut() }) }
            }
            if (offline) Surface(color = com.characterverse.core.design.Tokens.warning, modifier = Modifier.fillMaxWidth()) {
                Text("Offline — showing saved data", Modifier.padding(6.dp), color = Color.Black, style = MaterialTheme.typography.labelMedium)
            }
        }
    }
}

/** Tab navigation keeping one back stack per tab. */
fun NavHostController.go(route: String) = navigate(route) {
    popUpTo(graph.findStartDestination().id) { saveState = true }
    launchSingleTop = true
    restoreState = true
}
