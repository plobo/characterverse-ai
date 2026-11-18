package com.characterverse.core.analytics

import android.util.Log
import com.characterverse.core.datastore.UserPreferences
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import javax.inject.Inject
import javax.inject.Singleton

/** Consent-gated analytics. Never logs prompts, dialogue, names or media (plan §19). */
@Singleton
class Analytics @Inject constructor(prefs: UserPreferences) {
    private val consent = prefs.analyticsConsent.stateIn(CoroutineScope(SupervisorJob() + Dispatchers.Default), SharingStarted.Eagerly, false)
    fun track(event: String, props: Map<String, String> = emptyMap()) { if (consent.value) Log.i("CVAnalytics", "$event $props") }
    fun error(code: String, area: String) = Log.w("CVDiagnostics", "error $code in $area")
}
