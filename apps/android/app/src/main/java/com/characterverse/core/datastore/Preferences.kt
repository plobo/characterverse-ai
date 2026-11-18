package com.characterverse.core.datastore

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

val Context.dataStore by preferencesDataStore(name = "characterverse")

@Singleton
class UserPreferences @Inject constructor(@ApplicationContext private val context: Context) {
    private val analyticsKey = booleanPreferencesKey("analytics_consent")
    private val tutorialKey = booleanPreferencesKey("tutorial_dismissed")
    private val familyKey = booleanPreferencesKey("family_mode")
    private val notifyKey = booleanPreferencesKey("render_notifications")

    val analyticsConsent: Flow<Boolean> = context.dataStore.data.map { it[analyticsKey] ?: false }
    val tutorialDismissed: Flow<Boolean> = context.dataStore.data.map { it[tutorialKey] ?: false }
    val familyMode: Flow<Boolean> = context.dataStore.data.map { it[familyKey] ?: true }
    val notifications: Flow<Boolean> = context.dataStore.data.map { it[notifyKey] ?: true }

    suspend fun setAnalytics(v: Boolean) = context.dataStore.edit { it[analyticsKey] = v }
    suspend fun setTutorialDismissed(v: Boolean) = context.dataStore.edit { it[tutorialKey] = v }
    suspend fun setFamilyMode(v: Boolean) = context.dataStore.edit { it[familyKey] = v }
    suspend fun setNotifications(v: Boolean) = context.dataStore.edit { it[notifyKey] = v }
}
