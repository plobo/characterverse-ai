package com.characterverse

import com.characterverse.data.dto.MixLineageDto
import com.characterverse.data.dto.OmittedDto
import com.characterverse.domain.model.CharacterRecipe
import com.characterverse.domain.usecase.FusionResolver
import com.characterverse.domain.usecase.MixDimension
import com.characterverse.domain.usecase.PartAssembler
import com.characterverse.domain.usecase.RecipeValidator
import kotlinx.serialization.Serializable
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs

/** Same golden fixtures as backend/tests and the iOS GoldenParityTests. */
class GoldenParityTest {
    @Serializable data class RecipeCase(val name: String, val recipe: CharacterRecipe, val expectedCodes: List<String>)
    @Serializable data class RecipeCases(val cases: List<RecipeCase>)
    @Serializable data class Source(val id: String, val recipe: CharacterRecipe)
    @Serializable data class Expected(val recipe: CharacterRecipe, val omitted: List<OmittedDto>, val lineage: List<MixLineageDto>, val dominantSourceId: String, val warningCodes: List<String>)
    @Serializable data class MixCase(val name: String, val sources: List<Source>, val weights: Map<String, Double>? = null, val dimensions: List<String>, val expected: Expected)
    @Serializable data class MixCases(val cases: List<MixCase>)
    @Serializable data class Part(val id: String, val shape: String, val position: List<Double>, val size: List<Double>, val color: String)
    @Serializable data class AssemblyCase(val templateId: String, val recipe: CharacterRecipe, val parts: List<Part>)
    @Serializable data class AssemblyCases(val tolerance: Double, val cases: List<AssemblyCase>)

    @Test fun recipeValidationMatchesBackend() {
        val v = RecipeValidator(Fixtures.catalog)
        val cases = Fixtures.json.decodeFromString<RecipeCases>(Fixtures.text("recipe_validation_cases.json")).cases
        assertTrue(cases.size >= 15)
        cases.forEach { c -> assertEquals(c.name, c.expectedCodes.toSet(), v.issues(c.recipe).map { it.code }.toSet()) }
    }

    @Test fun fusionMatchesBackend() {
        val f = FusionResolver(Fixtures.catalog)
        val cases = Fixtures.json.decodeFromString<MixCases>(Fixtures.text("mix_golden.json")).cases
        assertTrue(cases.isNotEmpty())
        cases.forEach { c ->
            val dims = if ("all" in c.dimensions) MixDimension.entries.toSet() else MixDimension.entries.filter { it.id in c.dimensions }.toSet()
            val r = f.resolve(c.sources.map { it.id to it.recipe }, c.weights, dims)
            assertEquals("recipe ${c.name}", c.expected.recipe, r.recipe)
            assertEquals("omitted ${c.name}", c.expected.omitted.map { "${it.id}|${it.kind}|${it.reason}" }, r.omitted.map { "${it.id}|${it.kind}|${it.reason}" })
            assertEquals(c.expected.dominantSourceId, r.dominantSourceId)
            assertEquals("warnings ${c.name}", c.expected.warningCodes, r.warningCodes)
            assertEquals("lineage ${c.name}", c.expected.lineage.map { it.weight }, r.lineage.map { it.weight })
        }
    }

    @Test fun assemblyMatchesBackend() {
        val a = PartAssembler(Fixtures.catalog)
        val golden = Fixtures.json.decodeFromString<AssemblyCases>(Fixtures.text("assembly_golden.json"))
        golden.cases.forEach { c ->
            val parts = a.assemble(c.recipe)
            assertEquals(c.templateId, c.parts.map { it.id }, parts.map { it.id })
            parts.zip(c.parts).forEach { (x, y) ->
                assertEquals(y.shape, x.shape); assertEquals(y.color, x.color)
                (0 until 3).forEach { i ->
                    assertTrue("${c.templateId} ${x.id} pos", abs(x.position[i] - y.position[i]) <= golden.tolerance)
                    assertTrue("${c.templateId} ${x.id} size", abs(x.size[i] - y.size[i]) <= golden.tolerance)
                }
            }
        }
    }

    @Test fun unapprovedLicenceHiddenFromPickers() {
        assertFalse(Fixtures.catalog.approvedModules.any { it.id == "experimental_glow_tail_01" })
    }
}
