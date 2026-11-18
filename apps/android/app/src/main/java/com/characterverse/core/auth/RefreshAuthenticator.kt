package com.characterverse.core.auth

import com.characterverse.data.dto.RefreshRequestDto
import com.characterverse.data.dto.SessionResponseDto
import kotlinx.serialization.json.Json
import okhttp3.Authenticator
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.Route

/** Credential storage seen by the HTTP layer (implemented by [TokenStore]; in-memory in tests). */
interface SessionTokens {
    fun accessBlocking(): String?
    fun refreshBlocking(): String?
    fun saveBlocking(access: String, refresh: String)
    fun clearBlocking()
}

/**
 * On 401, exchanges the long-lived refresh token for a new session once and replays the request, so short-lived
 * access tokens never strand a (guest) account. Runs on OkHttp's dispatcher threads, never the main thread.
 */
class RefreshAuthenticator(private val tokens: SessionTokens, baseUrl: String) : Authenticator {
    private val refreshUrl = baseUrl.trimEnd('/') + "/v1/auth/refresh"
    private val json = Json { ignoreUnknownKeys = true }
    private val plain = OkHttpClient()

    override fun authenticate(route: Route?, response: Response): Request? {
        if (response.request.url.encodedPath.startsWith("/v1/auth/")) return null
        if (response.priorResponse != null) return null // already retried once
        synchronized(this) {
            val sent = response.request.header("Authorization")?.removePrefix("Bearer ")
            val current = tokens.accessBlocking()
            if (current != null && current != sent) return response.request.withToken(current) // refreshed by another call
            val refresh = tokens.refreshBlocking() ?: return null
            val body = json.encodeToString(RefreshRequestDto.serializer(), RefreshRequestDto(refresh)).toRequestBody("application/json".toMediaType())
            val session = runCatching {
                plain.newCall(Request.Builder().url(refreshUrl).post(body).build()).execute().use { r ->
                    if (!r.isSuccessful) null else json.decodeFromString(SessionResponseDto.serializer(), r.body!!.string())
                }
            }.getOrNull()
            if (session == null) { tokens.clearBlocking(); return null }
            tokens.saveBlocking(session.accessToken, session.refreshToken)
            return response.request.withToken(session.accessToken)
        }
    }

    private fun Request.withToken(token: String) = newBuilder().header("Authorization", "Bearer $token").build()
}
