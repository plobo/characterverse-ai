package com.characterverse

import com.characterverse.domain.model.CharacterSummary
import com.characterverse.domain.usecase.FusionResolver
import com.characterverse.domain.usecase.MixDimension
import com.characterverse.feature.charactermixer.MixerInputs
import com.characterverse.feature.charactermixer.MixerLogic
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MixerAndCreatorLogicTest {
    private val cat = Fixtures.catalog
    private val logic = MixerLogic(cat, FusionResolver(cat))
    private fun summary(id: String, template: String) = cat.manifest.characterTemplates.first { it.id == template }.recipe.let {
        CharacterSummary(id, it.name, "", it.category, it, 1, false, false, emptyList(), "", "")
    }
    private val chars = listOf(summary("a", "tmpl_mossy_pip"), summary("b", "tmpl_ember_ridgeback"))

    @Test fun weightsChangeDominantBodyAndReportConflicts() {
        var inputs = logic.toggle(logic.toggle(MixerInputs(), "a"), "b")
        assertEquals("critter_base_01", logic.compute(inputs, chars).first?.recipe?.baseModelId)
        inputs = inputs.copy(weights = inputs.weights + ("b" to 3.0))
        val (result, warnings) = logic.compute(inputs, chars)
        assertEquals("creature_base_01", result?.recipe?.baseModelId)
        assertTrue(warnings.any { "Leaf Cape" in it })
    }

    @Test fun maxThreeSourcesAndDimensionRequired() {
        var i = MixerInputs()
        listOf("a", "b", "c", "d").forEach { i = logic.toggle(i, it) }
        assertEquals(3, i.selected.size)
        val (r, w) = logic.compute(MixerInputs(listOf("a", "b"), emptySet()), chars)
        assertNull(r); assertEquals(listOf("Choose at least one mix dimension"), w)
    }

    @Test fun nonMixedDimensionsComeFromDominant() {
        val r = logic.compute(MixerInputs(listOf("a", "b"), setOf(MixDimension.POWERS)), chars).first!!
        assertEquals(chars[0].recipe.palette, r.recipe.palette)
        assertEquals(listOf("plant_growth", "fire_breath", "sonic_roar"), r.recipe.powers)
    }

    @Test fun switchingBodyDropsIncompatibleParts() {
        val voltwood = cat.manifest.characterTemplates.first { it.id == "tmpl_voltwood_guardian" }.recipe
        val newRig = cat.rigOf("mech_base_01")!!
        val switched = voltwood.copy(baseModelId = "mech_base_01", category = "robot",
            modules = voltwood.modules.filter { cat.module(it)!!.rigs.contains(newRig) }, powers = voltwood.powers.filter { cat.power(it)!!.rigs.contains(newRig) })
        assertEquals(listOf("original_armor_shoulders_02", "energy_bracers_03"), switched.modules)
        assertEquals(emptyList<Any>(), com.characterverse.domain.usecase.RecipeValidator(cat).issues(switched))
    }
}
