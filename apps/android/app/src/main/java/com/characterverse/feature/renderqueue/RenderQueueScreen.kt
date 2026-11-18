package com.characterverse.feature.renderqueue

import android.content.Context
import android.content.Intent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.core.content.FileProvider
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import com.characterverse.core.design.*
import com.characterverse.core.network.ApiError
import com.characterverse.domain.model.RenderJob
import com.characterverse.domain.model.humanized
import com.characterverse.domain.repository.RenderRepository
import com.characterverse.threed.cache.AssetCache
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.io.File
import javax.inject.Inject

@HiltViewModel
class RenderQueueViewModel @Inject constructor(private val repo: RenderRepository, private val cache: AssetCache) : ViewModel() {
    val renders = repo.renders
    val playing = MutableStateFlow<String?>(null)
    val error = MutableStateFlow<String?>(null)

    init {
        // Poll while jobs are active (plan §10: polling first; SSE only if insufficient).
        viewModelScope.launch {
            while (isActive) {
                runCatching { repo.refreshRenders() }
                delay(if (renders.value.any { it.isActive }) 2000 else 10000)
            }
        }
    }

    private fun act(block: suspend () -> Unit) = viewModelScope.launch { runCatching { block() }.onFailure { error.value = ApiError.from(it).userMessage } }
    fun cancel(job: RenderJob) = act { repo.cancel(job.id) }
    fun retry(job: RenderJob) = act { repo.retry(job.id) }
    fun preview(job: RenderJob) = act { playing.value = repo.downloadUrl(job.id).url }

    /** User-initiated export: download to cache (resumable/retried), then hand to the Android Sharesheet. */
    fun share(context: Context, job: RenderJob) = act {
        val file = cache.download(repo.downloadUrl(job.id).url, "render-${job.id}", "mp4")
        shareFile(context, file)
    }
}

fun shareFile(context: Context, file: File) {
    val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", file)
    val intent = Intent(Intent.ACTION_SEND).setType("video/mp4").putExtra(Intent.EXTRA_STREAM, uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    context.startActivity(Intent.createChooser(intent, "Share video").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
}

@Composable
fun RenderQueueScreen(vm: RenderQueueViewModel = hiltViewModel()) {
    val jobs by vm.renders.collectAsState()
    val playing by vm.playing.collectAsState()
    val error by vm.error.collectAsState()
    val context = LocalContext.current
    val groups = listOf("Processing" to jobs.filter { it.isActive }, "Completed" to jobs.filter { it.status == RenderJob.Status.COMPLETED },
        "Failed & cancelled" to jobs.filter { it.status == RenderJob.Status.FAILED || it.status == RenderJob.Status.CANCELLED })
    LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        error?.let { item { ErrorBanner(it) } }
        if (jobs.isEmpty()) item { EmptyState(Icons.Default.Layers, "No renders yet", "Render a storyboard from the Studio to see it here.") }
        groups.filter { it.second.isNotEmpty() }.forEach { (title, list) ->
            item { SectionHeader(title) }
            items(list, key = { it.id }) { job -> JobCard(job, { vm.preview(job) }, { vm.share(context, job) }, { vm.cancel(job) }, { vm.retry(job) }) }
        }
    }
    playing?.let { url ->
        Dialog({ vm.playing.value = null }) {
            val player = remember(url) { ExoPlayer.Builder(context).build().apply { setMediaItem(MediaItem.fromUri(url)); prepare(); playWhenReady = true } }
            DisposableEffect(player) { onDispose { player.release() } }
            AndroidView({ PlayerView(it).apply { this.player = player } }, Modifier.fillMaxWidth().aspectRatio(16f / 9f))
        }
    }
}

@Composable
private fun JobCard(job: RenderJob, onPreview: () -> Unit, onShare: () -> Unit, onCancel: () -> Unit, onRetry: () -> Unit) {
    val (color, icon) = when (job.status) {
        RenderJob.Status.COMPLETED -> Tokens.success to Icons.Default.CheckCircle
        RenderJob.Status.FAILED -> Tokens.danger to Icons.Default.Error
        RenderJob.Status.CANCELLED -> Color.Gray to Icons.Default.Block
        RenderJob.Status.QUEUED -> Tokens.warning to Icons.Default.Schedule
        RenderJob.Status.PROCESSING -> Tokens.brand to Icons.Default.Settings
    }
    CvCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(job.projectTitle ?: "Project", fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
            Text("${job.quality.humanized()} · ${job.aspectRatio}", style = MaterialTheme.typography.bodySmall)
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Icon(icon, job.status.name.lowercase(), tint = color)
            Text(job.stageLabel)
            if (job.attempts > 1) Text("attempt ${job.attempts}", style = MaterialTheme.typography.bodySmall)
        }
        if (job.isActive) LinearProgressIndicator({ job.progressPercent / 100f }, Modifier.fillMaxWidth().semantics { contentDescription = "Render progress"; stateDescription = job.stageLabel })
        if (job.status == RenderJob.Status.FAILED) job.errorCode?.let { Text("Error: ${it.humanized()}", color = Tokens.danger, style = MaterialTheme.typography.bodySmall) }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            when (job.status) {
                RenderJob.Status.COMPLETED -> {
                    OutlinedButton(onPreview) { Icon(Icons.Default.PlayArrow, null); Text("Preview") }
                    OutlinedButton(onShare) { Icon(Icons.Default.Share, null); Text("Share") }
                }
                RenderJob.Status.FAILED, RenderJob.Status.CANCELLED -> OutlinedButton(onRetry) { Icon(Icons.Default.Refresh, null); Text("Retry") }
                else -> OutlinedButton(onCancel, enabled = !job.cancelRequested) { Icon(Icons.Default.Close, null); Text(if (job.cancelRequested) "Cancelling…" else "Cancel") }
            }
        }
    }
}
