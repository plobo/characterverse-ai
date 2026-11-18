package com.characterverse.core.network

import com.characterverse.data.dto.ErrorDetailDto
import com.characterverse.data.dto.ErrorEnvelopeDto
import kotlinx.serialization.json.Json
import retrofit2.HttpException
import java.io.IOException
import kotlin.math.min
import kotlin.math.pow

/** Shared error codes + retry semantics (shared/api-contracts/error_codes.json). */
sealed class ApiError(message: String) : Exception(message) {
    class Server(val status: Int, val code: String, message: String, val details: List<ErrorDetailDto>, val retryable: Boolean) : ApiError(message)
    object Offline : ApiError("You're offline. Drafts are saved on this device.") { private fun readResolve(): Any = Offline }
    class Unexpected(message: String) : ApiError(message)

    val isRetryable get() = when (this) { is Server -> retryable; Offline -> true; else -> false }
    val userMessage: String get() = when (this) {
        is Server -> if (code == "AUTH_INVALID" || code == "AUTH_REQUIRED") "Please sign in again." else message ?: code
        else -> message ?: "Something went wrong"
    }

    companion object {
        private val json = Json { ignoreUnknownKeys = true }

        fun from(t: Throwable): ApiError = when (t) {
            is ApiError -> t
            is HttpException -> {
                val raw = t.response()?.errorBody()?.string().orEmpty()
                runCatching { json.decodeFromString<ErrorEnvelopeDto>(raw).error }.getOrNull()
                    ?.let { Server(t.code(), it.code, it.message, it.details, it.retryable) }
                    ?: Server(t.code(), "INTERNAL", "Unexpected error", emptyList(), t.code() >= 500)
            }
            is IOException -> Offline
            else -> Unexpected(t.message ?: t.javaClass.simpleName)
        }
    }
}

/** Bounded exponential backoff with jitter (same policy as iOS). */
data class RetryPolicy(val maxAttempts: Int = 3, val baseDelayMs: Long = 500, val maxDelayMs: Long = 8000) {
    fun delayFor(attempt: Int, jitter: Double = 1.0): Long = (min(maxDelayMs.toDouble(), baseDelayMs * 2.0.pow(attempt - 1)) * jitter).toLong()
}

suspend fun <T> withRetry(policy: RetryPolicy = RetryPolicy(), block: suspend () -> T): T {
    var attempt = 1
    while (true) {
        try {
            return block()
        } catch (t: Throwable) {
            val err = ApiError.from(t)
            if (!err.isRetryable || attempt >= policy.maxAttempts) throw err
            kotlinx.coroutines.delay(policy.delayFor(attempt, 0.8 + Math.random() * 0.4))
            attempt++
        }
    }
}

/** Maps any failure to [ApiError]; used by repositories for non-idempotent calls (no automatic retry). */
suspend fun <T> apiCall(block: suspend () -> T): T = try { block() } catch (t: Throwable) {
    if (t is kotlinx.coroutines.CancellationException) throw t
    throw ApiError.from(t)
}
