package com.characterverse

import com.characterverse.app.AppModule
import com.characterverse.core.auth.RefreshAuthenticator
import com.characterverse.core.auth.SessionTokens
import com.characterverse.data.api.ApiService
import kotlinx.coroutines.test.runTest
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

class SessionRefreshTest {
    class MemoryTokens(var access: String?, var refresh: String?) : SessionTokens {
        override fun accessBlocking() = access
        override fun refreshBlocking() = refresh
        override fun saveBlocking(access: String, refresh: String) { this.access = access; this.refresh = refresh }
        override fun clearBlocking() { access = null; refresh = null }
    }

    private fun api(server: MockWebServer, tokens: SessionTokens): ApiService {
        val client = OkHttpClient.Builder()
            .addInterceptor { c -> c.proceed(c.request().newBuilder().apply { tokens.accessBlocking()?.let { header("Authorization", "Bearer $it") } }.build()) }
            .authenticator(RefreshAuthenticator(tokens, server.url("/").toString()))
            .build()
        return Retrofit.Builder().baseUrl(server.url("/")).client(client)
            .addConverterFactory(AppModule.json.asConverterFactory("application/json".toMediaType())).build().create(ApiService::class.java)
    }

    private val expired = """{"error":{"code":"AUTH_INVALID","message":"Session expired","details":[],"retryable":false}}"""
    private val user = """{"id":"u1","displayName":"Guest Creator","email":null,"isGuest":true,"createdAt":"2026-11-17T22:41:05.123Z"}"""

    @Test fun expiredSessionIsRefreshedAndRetried() = runTest {
        val server = MockWebServer().apply { start() }
        server.enqueue(MockResponse().setResponseCode(401).setBody(expired))
        server.enqueue(MockResponse().setBody("""{"accessToken":"new-a","tokenType":"Bearer","expiresAt":1,"refreshToken":"new-r","refreshExpiresAt":2,"user":$user}"""))
        server.enqueue(MockResponse().setBody(user))
        val tokens = MemoryTokens("old-a", "old-r")
        assertEquals("u1", api(server, tokens).me().id)
        assertEquals(listOf("/v1/me", "/v1/auth/refresh", "/v1/me"), (1..3).map { server.takeRequest().path })
        assertEquals("new-a", tokens.access); assertEquals("new-r", tokens.refresh)
        server.shutdown()
    }

    @Test fun failedRefreshGivesUpWithoutLooping() = runTest {
        val server = MockWebServer().apply { start() }
        server.enqueue(MockResponse().setResponseCode(401).setBody(expired))
        server.enqueue(MockResponse().setResponseCode(401).setBody(expired))
        val tokens = MemoryTokens("old-a", "bad-r")
        runCatching { api(server, tokens).me() }
        assertEquals(2, server.requestCount)
        assertNull(tokens.access)
        server.shutdown()
    }
}
