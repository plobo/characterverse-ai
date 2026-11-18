package com.characterverse.feature.settings

import android.content.Intent
import android.net.Uri
import android.text.format.Formatter
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.characterverse.core.datastore.UserPreferences
import com.characterverse.core.design.*
import com.characterverse.core.network.ApiError
import com.characterverse.data.repository.RemoteRepository
import com.characterverse.domain.model.Catalog
import com.characterverse.domain.repository.DraftRepository
import com.characterverse.feature.renderqueue.shareFile
import com.characterverse.threed.cache.AssetCache
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import java.io.File
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(
    val repo: RemoteRepository, val prefs: UserPreferences, val cache: AssetCache, val catalog: Catalog, private val drafts: DraftRepository,
) : ViewModel() {
    val error = MutableStateFlow<String?>(null)
    fun set(block: suspend UserPreferences.() -> Unit) = viewModelScope.launch { prefs.block() }
    fun export(dir: File, onReady: (File) -> Unit) = viewModelScope.launch {
        runCatching { File(dir, "characterverse-export.json").apply { writeText(repo.exportData()) } }.onSuccess(onReady).onFailure { error.value = ApiError.from(it).userMessage }
    }
    fun deleteAccount(onDone: () -> Unit) = viewModelScope.launch {
        runCatching { repo.deleteAccount(); drafts.clear(); cache.clear() }.onSuccess { onDone() }.onFailure { error.value = ApiError.from(it).userMessage }
    }
}

@Composable
fun SettingsScreen(onSignOut: () -> Unit, vm: SettingsViewModel = hiltViewModel()) {
    val user by vm.repo.user.collectAsState()
    val analytics by vm.prefs.analyticsConsent.collectAsState(false)
    val family by vm.prefs.familyMode.collectAsState(true)
    val notify by vm.prefs.notifications.collectAsState(true)
    val error by vm.error.collectAsState()
    var confirm by remember { mutableStateOf(false) }
    var cacheBytes by remember { mutableLongStateOf(vm.cache.totalBytes()) }
    val context = LocalContext.current
    fun open(url: String) = context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        CvCard {
            SectionHeader("Account")
            Text("${user?.displayName ?: "—"} · ${if (user?.isGuest == true) "Guest" else "Signed in"}")
            OutlinedButton(onSignOut) { Text("Sign out") }
        }
        CvCard {
            SectionHeader("Privacy", "Analytics never include your prompts, dialogue, character names or videos.")
            ToggleRow("Share anonymous usage analytics", analytics) { vm.set { setAnalytics(it) } }
        }
        CvCard {
            SectionHeader("Content preferences")
            ToggleRow("Family-friendly story suggestions", family) { vm.set { setFamilyMode(it) } }
            ToggleRow("Render notifications", notify) { vm.set { setNotifications(it) } }
        }
        CvCard {
            SectionHeader("Your data", "Deleting removes characters, projects, videos and uploads immediately.")
            OutlinedButton({ vm.export(context.cacheDir) { shareFile(context, it) } }) { Icon(Icons.Default.Download, null); Text("Export my data") }
            Text("Cached media: ${Formatter.formatShortFileSize(context, cacheBytes)}")
            TextButton({ vm.cache.clear(); cacheBytes = 0 }) { Text("Clear cached media") }
            Button({ confirm = true }, colors = ButtonDefaults.buttonColors(containerColor = Tokens.danger)) { Icon(Icons.Default.DeleteForever, null); Text("Delete account and data") }
        }
        error?.let { ErrorBanner(it) }
        CvCard {
            SectionHeader("Help & legal")
            TextButton({ open("https://characterverse.example/policy") }) { Text("Content policy — original characters only") }
            TextButton({ open("https://characterverse.example/terms") }) { Text("Terms of service") }
            TextButton({ open("https://characterverse.example/privacy") }) { Text("Privacy notice") }
            TextButton({ open("https://characterverse.example/report") }) { Text("Report content or request a takedown") }
            Text("Asset manifest ${vm.catalog.manifest.manifestVersion}", style = MaterialTheme.typography.bodySmall)
        }
    }
    if (confirm) AlertDialog({ confirm = false }, { TextButton({ confirm = false; vm.deleteAccount(onSignOut) }) { Text("Delete everything") } },
        dismissButton = { TextButton({ confirm = false }) { Text("Cancel") } }, title = { Text("Delete your account?") }, text = { Text("This cannot be undone.") })
}

@Composable
private fun ToggleRow(label: String, value: Boolean, onChange: (Boolean) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) { Text(label, Modifier.weight(1f)); Switch(value, onChange) }
}
