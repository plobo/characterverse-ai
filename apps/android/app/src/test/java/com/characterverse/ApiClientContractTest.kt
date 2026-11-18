package com.characterverse

import com.characterverse.app.AppModule
import com.characterverse.core.network.ApiError
import com.characterverse.core.network.RetryPolicy
import com.characterverse.core.network.withRetry
import com.characterverse.data.api.ApiService
import com.characterverse.data.dto.CreateRenderDto
import kotlinx.coroutines.test.runTest
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

/** HTTP-level contract: headers, error envelopes and bounded retries against a mock server. */
class ApiClientContractTest {
    private lateinit var server: MockWebServer
    private lateinit var api: ApiService

    @Before fun setUp() {
        server = MockWebServer().apply { start() }
        api = Retrofit.Builder().baseUrl(server.url("/")).client(OkHttpClient())
            .addConverterFactory(AppModule.json.asConverterFactory("application/json".toMediaType())).build().create(ApiService::class.java)
    }

    @After fun tearDown() = server.shutdown()

    @Test fun renderSubmitSendsIdempotencyKeyAndDecodes() = runTest {
        server.enqueue(MockResponse().setResponseCode(201).setBody(Fixtures.text("render_job.json")))
        val job = api.submitRender("p1", "android-p1-v2-draft", CreateRenderDto("draft"))
        val req = server.takeRequest()
        assertEquals("/v1/projects/p1/renders", req.path)
        assertEquals("android-p1-v2-draft", req.getHeader("Idempotency-Key"))
        assertTrue(req.body.readUtf8().contains("\"quality\":\"draft\""))
        assertEquals("completed", job.status)
    }

    @Test fun errorEnvelopeMapsToSharedCodes() = runTest {
        server.enqueue(MockResponse().setResponseCode(422).setBody(Fixtures.text("error_recipe_invalid.json")))
        try { api.characters(); fail() } catch (t: Throwable) {
            val e = ApiError.from(t) as ApiError.Server
            assertEquals("RECIPE_INVALID", e.code); assertEquals(422, e.status); assertTrue(!e.isRetryable)
        }
    }

    @Test fun retryableErrorsAreRetriedThenSucceed() = runTest {
        server.enqueue(MockResponse().setResponseCode(429).setBody("""{"error":{"code":"RATE_LIMITED","message":"slow down","details":[],"retryable":true}}"""))
        server.enqueue(MockResponse().setResponseCode(200).setBody(Fixtures.text("usage.json")))
        val usage = withRetry(RetryPolicy(maxAttempts = 3, baseDelayMs = 1)) { api.usage() }
        assertEquals(2, usage.characters); assertEquals(2, server.requestCount)
    }

    @Test fun nonRetryableErrorsFailFast() = runTest {
        server.enqueue(MockResponse().setResponseCode(404).setBody("""{"error":{"code":"NOT_FOUND","message":"gone","details":[],"retryable":false}}"""))
        try { withRetry(RetryPolicy(baseDelayMs = 1)) { api.me() }; fail() } catch (e: ApiError.Server) { assertEquals("NOT_FOUND", e.code) }
        assertEquals(1, server.requestCount)
    }

    @Test fun backoffIsBounded() {
        val p = RetryPolicy()
        assertEquals(500, p.delayFor(1)); assertEquals(1000, p.delayFor(2)); assertEquals(8000, p.delayFor(10))
    }
}
