package com.characterverse

import com.characterverse.data.dto.*
import com.characterverse.domain.model.RenderJob
import com.characterverse.domain.model.Storyboard
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Decodes real backend responses (shared/fixtures/api) into the Android DTOs. */
class ApiDecodingTest {
    private inline fun <reified T> decode(name: String): T = Fixtures.json.decodeFromString(Fixtures.text("$name.json"))

    @Test fun session() = assertEquals("Sam", decode<SessionResponseDto>("session").user.displayName)
    @Test fun character() { val c = decode<CharacterDto>("character").toDomain(); assertEquals("Voltwood Guardian", c.recipe.name); assertEquals(1, c.version) }
    @Test fun characterList() = assertEquals(2, decode<ItemsDto<CharacterDto>>("character_list").items.size)
    @Test fun generateRecipe() = assertEquals("robot", decode<GenerateRecipeResponseDto>("generate_recipe").recipe.category)
    @Test fun mixPreview() = assertEquals(3, decode<MixPreviewDto>("mix_preview").suggestions.size)
    @Test fun story() = assertEquals(3, decode<GenerateStoryResponseDto>("story_generate").storyboard.scenes.size)
    @Test fun project() = assertEquals(15, decode<ProjectDto>("project").storyboard?.durationSeconds)
    @Test fun renderJob() { val j = decode<RenderJobDto>("render_job").toDomain(); assertEquals(RenderJob.Status.COMPLETED, j.status); assertEquals("Ready", j.stageLabel) }
    @Test fun renderList() = assertEquals(1, decode<ItemsDto<RenderJobDto>>("render_list").items.size)
    @Test fun downloadUrl() = assertEquals("video/mp4", decode<DownloadUrlDto>("download_url").mimeType)
    @Test fun usage() = assertEquals(2, decode<UsageDto>("usage").characters)

    @Test fun errorEnvelope() {
        val e = decode<ErrorEnvelopeDto>("error_recipe_invalid").error
        assertEquals("RECIPE_INVALID", e.code); assertEquals("INCOMPATIBLE_MODULE", e.details.first().code); assertFalse(e.retryable)
    }

    @Test fun storyboardRoundTripAndRenumber() {
        val sb = decode<GenerateStoryResponseDto>("story_generate").storyboard
        assertEquals(sb, Fixtures.json.decodeFromString<Storyboard>(com.characterverse.app.AppModule.json.encodeToString(Storyboard.serializer(), sb)))
        val reversed = sb.copy(scenes = sb.scenes.reversed()).renumbered()
        assertEquals(listOf(1, 2, 3), reversed.scenes.map { it.sequence })
        assertTrue(reversed.scenes.first().sceneId == sb.scenes.last().sceneId)
    }
}
