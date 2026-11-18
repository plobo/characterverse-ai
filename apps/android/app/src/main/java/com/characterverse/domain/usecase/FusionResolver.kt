package com.characterverse.domain.usecase

import com.characterverse.domain.model.Catalog
import com.characterverse.domain.model.CharacterRecipe
import com.characterverse.domain.model.MixResult
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min

enum class MixDimension(val id: String) {
    APPEARANCE("appearance"), POWERS("powers"), PERSONALITY("personality"), VOICE("voice");

    val title get() = id.replaceFirstChar { it.uppercase() }
}

class FusionException(message: String) : IllegalArgumentException(message)

/** Kotlin port of backend `app/services/mixer.py`; parity pinned by shared/fixtures/mix_golden.json. */
class FusionResolver(private val catalog: Catalog) {
    companion object {
        const val MAX_MODULES = 6
        const val MAX_POWERS = 3
        const val MAX_TRAITS = 5
        fun roundHalfUp(x: Double) = floor(x + 0.5).toInt()
        fun round2(x: Double) = floor(x * 100 + 0.5) / 100

        fun blendHex(colors: List<String>, weights: List<Double>): String {
            val ch = (0 until 3).map { c ->
                var total = 0.0
                for (i in colors.indices) total += weights[i] * colors[i].substring(1 + c * 2, 3 + c * 2).toInt(16)
                min(255, max(0, roundHalfUp(total)))
            }
            return "#%02X%02X%02X".format(ch[0], ch[1], ch[2])
        }

        fun defaultName(namesByRank: List<String>, sourceNames: List<String>): String {
            val first = namesByRank[0].split(" ").first()
            val second = if (namesByRank.size > 1) namesByRank[1].split(" ").last() else "Fusion"
            var name = if (first != second) "$first $second" else "$first Fusion"
            if (name in sourceNames) name += " Fusion"
            return name.take(40).trim()
        }
    }

    fun resolve(sources: List<Pair<String, CharacterRecipe>>, weights: Map<String, Double>?, dimensions: Set<MixDimension>, name: String? = null): MixResult {
        if (sources.size !in 2..3) throw FusionException("Select two or three characters to mix")
        if (dimensions.isEmpty()) throw FusionException("Choose at least one mix dimension")
        val ids = sources.map { it.first }
        if (ids.toSet().size != ids.size) throw FusionException("Each source character can only be used once")
        val dims = MixDimension.entries.filter { it in dimensions }
        val raw = ids.map { weights?.get(it) ?: 1.0 }
        var total = 0.0
        for (w in raw) total += w
        if (raw.any { it < 0 } || total <= 0) throw FusionException("Weights must be non-negative and not all zero")
        val w = raw.map { it / total }
        val order = sources.indices.sortedWith(compareBy<Int>({ -w[it] }, { it }))
        val recipes = sources.map { it.second }
        val dom = recipes[order[0]]
        val rig = catalog.rigOf(dom.baseModelId)
        val omitted = mutableListOf<MixResult.Omitted>()
        val warnings = mutableListOf<String>()
        if (recipes.map { catalog.rigOf(it.baseModelId) }.toSet().size > 1) warnings += "RIG_MISMATCH"

        var proportions = dom.proportions
        var palette = CharacterRecipe.Palette(dom.palette.primary.uppercase(), dom.palette.secondary.uppercase(), dom.palette.accent.uppercase())
        var modulePool = dom.modules
        if (MixDimension.APPEARANCE in dims) {
            fun blend(get: (CharacterRecipe.Proportions) -> Double): Double {
                var sum = 0.0
                for (i in recipes.indices) sum += w[i] * get(recipes[i].proportions)
                return min(1.3, max(0.7, round2(sum)))
            }
            proportions = CharacterRecipe.Proportions(blend { it.height }, blend { it.shoulderWidth }, blend { it.headScale })
            palette = CharacterRecipe.Palette(
                blendHex(recipes.map { it.palette.primary }, w),
                blendHex(recipes.map { it.palette.secondary }, w),
                blendHex(recipes.map { it.palette.accent }, w),
            )
            modulePool = order.flatMap { recipes[it].modules }
        }
        fun wasOmitted(id: String) = omitted.any { it.id == id }

        val modules = mutableListOf<String>()
        val slots = mutableSetOf<String>()
        for (id in modulePool) {
            if (id in modules || wasOmitted(id)) continue
            val module = catalog.module(id)
            val reason = when {
                module == null || !catalog.isApproved(module.licenceId) -> "not_approved"
                rig != null && rig !in module.rigs -> "incompatible_rig"
                module.slot in slots -> "slot_taken"
                modules.size >= MAX_MODULES -> "limit_reached"
                else -> null
            }
            if (reason != null) { omitted += MixResult.Omitted(id, "module", reason); continue }
            modules += id
            slots += module!!.slot
        }

        val powerPool = if (MixDimension.POWERS in dims) order.flatMap { recipes[it].powers } else dom.powers
        val powers = mutableListOf<String>()
        for (id in powerPool) {
            if (id in powers || wasOmitted(id)) continue
            val power = catalog.power(id)
            val reason = when {
                power == null -> "not_approved"
                rig != null && rig !in power.rigs -> "unsupported_by_rig"
                powers.size >= MAX_POWERS -> "limit_reached"
                else -> null
            }
            if (reason != null) { omitted += MixResult.Omitted(id, "power", reason); continue }
            powers += id
        }

        val traitPool = if (MixDimension.PERSONALITY in dims) order.flatMap { recipes[it].personalityTraits } else dom.personalityTraits
        val traits = mutableListOf<String>()
        for (t in traitPool) {
            if (t in traits || wasOmitted(t)) continue
            if (traits.size >= MAX_TRAITS) { omitted += MixResult.Omitted(t, "trait", "limit_reached"); continue }
            traits += t
        }
        val voice = if (MixDimension.VOICE in dims) recipes[order[1]].voiceProfileId else dom.voiceProfileId
        if (omitted.isNotEmpty()) warnings += "TRAITS_OMITTED"

        val finalName = (name ?: defaultName(order.map { recipes[it].name }, recipes.map { it.name })).take(40)
        val recipe = CharacterRecipe(1, finalName, dom.category, dom.baseModelId, dom.style, proportions, palette, modules, powers, traits,
            voice, catalog.manifest.manifestVersion)
        val lineage = ids.indices.map { MixResult.LineageEntry(ids[it], Math.round(w[it] * 10000) / 10000.0, dims.map { d -> d.id }) }
        return MixResult(recipe, lineage, omitted, warnings, ids[order[0]])
    }
}
