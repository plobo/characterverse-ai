package com.characterverse.core.auth

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import com.characterverse.core.datastore.dataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.inject.Inject
import javax.inject.Singleton

/** Session token encrypted with an AES-GCM key held in the Android Keystore; ciphertext lives in DataStore. */
@Singleton
class TokenStore @Inject constructor(@ApplicationContext private val context: Context) : SessionTokens {
    private val keyAlias = "cv_session_key"
    private val prefKey = stringPreferencesKey("session_token")
    private val refreshKey = stringPreferencesKey("refresh_token")
    @Volatile private var cached: String? = null
    @Volatile private var cachedRefresh: String? = null

    private fun key(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getEntry(keyAlias, null) as? KeyStore.SecretKeyEntry)?.let { return it.secretKey }
        val gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        gen.init(KeyGenParameterSpec.Builder(keyAlias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        return gen.generateKey()
    }

    private fun encrypt(value: String): String {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key()) }
        return Base64.encodeToString(cipher.iv + cipher.doFinal(value.toByteArray()), Base64.NO_WRAP)
    }

    private fun decrypt(blob: String): String? = runCatching {
        val bytes = Base64.decode(blob, Base64.NO_WRAP)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, bytes, 0, 12)) }
        String(cipher.doFinal(bytes, 12, bytes.size - 12))
    }.getOrNull()

    suspend fun save(token: String, refresh: String) {
        val a = encrypt(token); val r = encrypt(refresh)
        context.dataStore.edit { it[prefKey] = a; it[refreshKey] = r }
        cached = token; cachedRefresh = refresh
    }

    suspend fun token(): String? = cached ?: context.dataStore.data.first()[prefKey]?.let(::decrypt).also { cached = it }
    suspend fun refreshToken(): String? = cachedRefresh ?: context.dataStore.data.first()[refreshKey]?.let(::decrypt).also { cachedRefresh = it }

    // Blocking variants are only called from OkHttp dispatcher threads (interceptor / authenticator), never the UI thread.
    fun tokenBlocking(): String? = cached ?: runBlocking { token() }
    override fun accessBlocking() = tokenBlocking()
    override fun refreshBlocking(): String? = cachedRefresh ?: runBlocking { refreshToken() }
    override fun saveBlocking(access: String, refresh: String) = runBlocking { save(access, refresh) }
    override fun clearBlocking() = runBlocking { clear() }

    suspend fun clear() {
        cached = null; cachedRefresh = null
        context.dataStore.edit { it.remove(prefKey); it.remove(refreshKey) }
    }
}
