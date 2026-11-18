package com.characterverse.feature.onboarding

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PersonAdd
import androidx.compose.material.icons.filled.Verified
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.characterverse.app.SessionViewModel
import com.characterverse.core.design.CvCard
import com.characterverse.core.design.ErrorBanner
import com.characterverse.core.design.Tokens
import com.characterverse.threed.viewer.CharacterThumbnail
import kotlinx.coroutines.launch

@Composable
fun OnboardingScreen(session: SessionViewModel) {
    var accepted by remember { mutableStateOf(false) }
    var showSignIn by remember { mutableStateOf(false) }
    var name by remember { mutableStateOf("") }
    val error by session.error.collectAsState()
    val scope = rememberCoroutineScope()
    val hero = remember { session.catalog.manifest.characterTemplates.firstOrNull()?.let { session.assembler.assemble(it.recipe) }.orEmpty() }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp).systemBarsPadding(), verticalArrangement = Arrangement.spacedBy(18.dp)) {
        Box(Modifier.fillMaxWidth().height(250.dp).clip(RoundedCornerShape(28.dp)).background(Tokens.heroGradient), contentAlignment = Alignment.Center) {
            CharacterThumbnail(hero, Modifier.fillMaxSize().padding(24.dp))
        }
        Text("CharacterVerse AI", style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
        Text("Create, mix and animate your own original 3D characters.", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        CvCard {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Icon(Icons.Default.Verified, null, tint = Tokens.brand); Text("Original characters only", fontWeight = FontWeight.Bold, color = Tokens.brand)
            }
            Text("CharacterVerse is built for your own ideas. Requests to copy existing characters, franchises, logos or real people are blocked, and every built-in asset has a reviewed commercial-use licence.",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(accepted, { accepted = it })
                Text("I agree to the Terms, Privacy Policy and Content Policy", style = MaterialTheme.typography.bodyMedium)
            }
        }
        Button({ scope.launch { session.signIn("guest", null, null) } }, Modifier.fillMaxWidth().height(52.dp), enabled = accepted) {
            Icon(Icons.Default.PersonAdd, null); Spacer(Modifier.width(8.dp)); Text("Continue as guest")
        }
        FilledTonalButton({ showSignIn = true }, Modifier.fillMaxWidth().height(52.dp), enabled = accepted) { Text("Sign in") }
        error?.let { ErrorBanner(it) }
        Text("Guest drafts stay on this device. You can delete your account and data at any time in Settings.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    if (showSignIn) {
        AlertDialog(onDismissRequest = { showSignIn = false }, title = { Text("Sign in") },
            text = {
                Column { Text("Development builds use the local identity provider."); Spacer(Modifier.height(8.dp))
                    OutlinedTextField(name, { name = it }, label = { Text("Display name") }) }
            },
            confirmButton = { TextButton({ showSignIn = false; scope.launch { session.signIn("dev", name.lowercase().replace(' ', '-'), name) } }) { Text("Continue") } },
            dismissButton = { TextButton({ showSignIn = false }) { Text("Cancel") } })
    }
}
