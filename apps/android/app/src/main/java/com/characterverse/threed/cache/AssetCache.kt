package com.characterverse.threed.cache

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import com.characterverse.core.network.RetryPolicy
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

/** Disk cache for media (rendered videos). Downloads go to a .part file and are renamed atomically. */
@Singleton
class AssetCache @Inject constructor(@ApplicationContext context: Context) {
    val dir = File(context.cacheDir, "cv-assets").apply { mkdirs() }
    private val client = OkHttpClient()

    fun cached(key: String, ext: String): File? = File(dir, "$key.$ext").takeIf { it.exists() }

    suspend fun download(url: String, key: String, ext: String, policy: RetryPolicy = RetryPolicy()): File = withContext(Dispatchers.IO) {
        cached(key, ext)?.let { return@withContext it }
        val target = File(dir, "$key.$ext")
        val part = File(dir, "$key.$ext.part")
        var attempt = 1
        while (true) {
            try {
                client.newCall(Request.Builder().url(url).build()).execute().use { res ->
                    if (!res.isSuccessful) throw IOException("HTTP ${res.code}")
                    part.outputStream().use { out -> res.body!!.byteStream().copyTo(out) }
                }
                if (!part.renameTo(target)) throw IOException("rename failed")
                return@withContext target
            } catch (e: IOException) {
                part.delete()
                if (attempt >= policy.maxAttempts) throw e
                delay(policy.delayFor(attempt))
                attempt++
            }
        }
        @Suppress("UNREACHABLE_CODE") target
    }

    fun totalBytes() = dir.listFiles()?.sumOf { it.length() } ?: 0L
    fun clear() { dir.listFiles()?.forEach { it.delete() } }
}

/** Deferrable background download of a finished render (WorkManager survives process death). */
class RenderDownloadWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val url = inputData.getString(KEY_URL) ?: return Result.failure()
        val jobId = inputData.getString(KEY_JOB) ?: return Result.failure()
        return try {
            val file = AssetCache(applicationContext).download(url, "render-$jobId", "mp4")
            Result.success(workDataOf(KEY_PATH to file.absolutePath))
        } catch (e: IOException) {
            if (runAttemptCount < 3) Result.retry() else Result.failure()
        }
    }

    companion object {
        const val KEY_URL = "url"
        const val KEY_JOB = "jobId"
        const val KEY_PATH = "path"
    }
}
