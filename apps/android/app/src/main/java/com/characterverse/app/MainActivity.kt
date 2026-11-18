package com.characterverse.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Surface
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import com.characterverse.BuildConfig
import com.characterverse.app.navigation.MainScaffold
import com.characterverse.core.design.CharacterVerseTheme
import com.characterverse.feature.onboarding.OnboardingScreen
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    private val session: SessionViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        // Debug-only extras for UI tests and README screenshots: --es cvDevSignIn demo --es cvScreen mixer
        val devSubject = if (BuildConfig.DEBUG) intent.getStringExtra("cvDevSignIn") else null
        val screen = if (BuildConfig.DEBUG) intent.getStringExtra("cvScreen") else null
        setContent {
            CharacterVerseTheme {
                Surface(Modifier.fillMaxSize()) {
                    val phase by session.phase.collectAsState()
                    LaunchedEffect(phase) { if (phase == Phase.SIGNED_OUT && devSubject != null) session.signIn("dev", devSubject, "Demo Creator") }
                    when (phase) {
                        Phase.LAUNCHING -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                        Phase.SIGNED_OUT -> OnboardingScreen(session)
                        Phase.SIGNED_IN -> MainScaffold(session, screen)
                    }
                }
            }
        }
    }
}
