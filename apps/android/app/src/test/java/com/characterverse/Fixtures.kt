package com.characterverse

import com.characterverse.domain.model.Catalog
import kotlinx.serialization.json.Json

object Fixtures {
    val json = Json { ignoreUnknownKeys = true }
    fun text(name: String): String = requireNotNull(javaClass.classLoader!!.getResource(name)) { "missing fixture $name" }.readText()
    val catalog by lazy { Catalog.fromJson(text("asset_manifest_v1.json"), text("procedural_parts_v1.json")) }
}
