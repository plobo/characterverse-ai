import Foundation
import Testing
@testable import CharacterVerse

/// Decodes real responses recorded from the backend (shared/fixtures/api) into the iOS DTOs.
@Suite("API contract decoding")
struct APIDecodingTests {
    func decode<T: Decodable>(_ type: T.Type, _ name: String) throws -> T {
        try APIClient.decoder.decode(T.self, from: Fixtures.data(name))
    }

    @Test func session() throws { #expect(try decode(SessionResponseDTO.self, "session").user.displayName == "Sam") }
    @Test func character() throws {
        let c = try decode(CharacterDTO.self, "character").domain
        #expect(c.recipe.name == "Voltwood Guardian" && c.version == 1)
    }
    @Test func characterList() throws { #expect(try decode(ItemsDTO<CharacterDTO>.self, "character_list").items.count == 2) }
    @Test func generateRecipe() throws { #expect(try decode(GenerateRecipeResponseDTO.self, "generate_recipe").recipe.category == "robot") }
    @Test func mixPreview() throws { #expect(try decode(MixPreviewDTO.self, "mix_preview").suggestions.count == 3) }
    @Test func story() throws { #expect(try decode(GenerateStoryResponseDTO.self, "story_generate").storyboard.scenes.count == 3) }
    @Test func project() throws { #expect(try decode(ProjectDTO.self, "project").storyboard?.durationSeconds == 15) }
    @Test func renderJob() throws {
        let job = try decode(RenderJobDTO.self, "render_job").domain
        #expect(job.status == .completed && job.stageLabel == "Ready")
    }
    @Test func renderList() throws { #expect(try decode(ItemsDTO<RenderJobDTO>.self, "render_list").items.count == 1) }
    @Test func downloadURL() throws { #expect(try decode(DownloadURLDTO.self, "download_url").mimeType == "video/mp4") }
    @Test func usage() throws { #expect(try decode(UsageDTO.self, "usage").characters == 2) }

    @Test func errorEnvelope() throws {
        let env = try decode(APIErrorEnvelope.self, "error_recipe_invalid")
        #expect(env.error.code == "RECIPE_INVALID" && env.error.details.first?.code == "INCOMPATIBLE_MODULE" && !env.error.retryable)
    }

    @Test func storyboardRoundTripsUnchanged() throws {
        let original = try decode(GenerateStoryResponseDTO.self, "story_generate").storyboard
        let again = try JSONDecoder().decode(Storyboard.self, from: JSONEncoder().encode(original))
        #expect(again == original)
    }
}
