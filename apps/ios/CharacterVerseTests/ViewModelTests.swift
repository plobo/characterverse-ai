import Foundation
import Testing
@testable import CharacterVerse

@MainActor
@Suite("View models & local logic")
struct ViewModelTests {
    func env() -> AppEnvironment { AppEnvironment(baseURL: URL(string: "http://127.0.0.1:9")!, inMemoryDrafts: true) }

    func template(_ env: AppEnvironment, _ id: String) -> CharacterRecipe {
        env.catalog.manifest.characterTemplates.first { $0.id == id }!.recipe
    }

    @Test func switchingBodyDropsIncompatibleParts() {
        let e = env()
        let vm = CharacterCreatorViewModel(env: e, seed: template(e, "tmpl_voltwood_guardian"))
        vm.setCategory("robot")
        #expect(vm.recipe.baseModelId == "mech_base_01")
        #expect(vm.recipe.modules == ["original_armor_shoulders_02", "energy_bracers_03"])  // leaf cape does not fit mech_v1
        #expect(vm.recipe.powers == ["electricity"])                                       // plant growth unsupported by mech_v1
        #expect(vm.issues.isEmpty)
    }

    @Test func oneModulePerSlotAndPowerLimit() {
        let e = env()
        let vm = CharacterCreatorViewModel(env: e)
        vm.setModule("leaf_cape_01", slot: "back")
        vm.setModule("jet_pack_01", slot: "back")
        #expect(vm.recipe.modules == ["jet_pack_01"])
        ["electricity", "ice", "flight", "force_field"].forEach(vm.togglePower)
        #expect(vm.recipe.powers.count == 3)
    }

    @Test func creatorAutosavesDraftOffline() {
        let e = env()
        let vm = CharacterCreatorViewModel(env: e)
        vm.recipe.name = "Offline Ollie"
        #expect(e.drafts.all().first?.recipe?.name == "Offline Ollie")
        vm.recipe.name = "Offline Ollie 2"
        #expect(e.drafts.all().count == 1)
    }

    @Test func offlineSaveKeepsDraft() async {
        let e = env()
        let vm = CharacterCreatorViewModel(env: e)
        vm.recipe.name = "Kept Locally"
        let saved = await vm.save()
        #expect(saved == nil)
        #expect(vm.errorMessage?.contains("offline") == true)
        #expect(e.drafts.all().first?.recipe?.name == "Kept Locally")
    }

    @Test func mixerPreviewUndoAndWarnings() {
        let e = env()
        let vm = CharacterMixerViewModel(env: e)
        let a = CharacterSummary(id: "a", name: "Mossy Pip", description: "", category: "cartoon", recipe: template(e, "tmpl_mossy_pip"),
                                 version: 1, isFavorite: false, archived: false, lineage: [], createdAt: .now, updatedAt: .now)
        var b = a
        b.id = "b"; b.name = "Ember Ridgeback"; b.recipe = template(e, "tmpl_ember_ridgeback")
        vm.characters = [a, b]
        vm.toggle("a"); vm.toggle("b")
        vm.beginWeightChange()
        vm.setWeight("b", 3)
        #expect(vm.result?.recipe.baseModelId == "creature_base_01")
        #expect(vm.warnings.contains { $0.contains("Leaf Cape") })
        vm.undo()
        #expect(vm.result?.recipe.baseModelId == "critter_base_01")
        vm.toggleDimension(.appearance); vm.toggleDimension(.powers); vm.toggleDimension(.personality); vm.toggleDimension(.voice)
        #expect(vm.result == nil && vm.warnings == ["Choose at least one mix dimension"])
    }

    @Test func storyboardRenumbersAfterReorder() throws {
        let sb = try APIClient.decoder.decode(GenerateStoryResponseDTO.self, from: Fixtures.data("story_generate")).storyboard
        var doc = sb
        doc.scenes.reverse()
        doc.renumber()
        #expect(doc.scenes.map(\.sequence) == [1, 2, 3])
        #expect(doc.scenes.first?.sceneId == sb.scenes.last?.sceneId)
    }

    @Test func retryPolicyIsBounded() {
        let p = RetryPolicy()
        #expect(p.delay(forAttempt: 10) <= p.maxDelay * 1.2)
        #expect(APIError.server(status: 429, code: "RATE_LIMITED", message: "", details: [], retryable: true).isRetryable)
        #expect(!APIError.server(status: 422, code: "RECIPE_INVALID", message: "", details: [], retryable: false).isRetryable)
    }

    @Test func assetCacheRetriesThenFails() async {
        let dir = FileManager.default.temporaryDirectory.appending(path: UUID().uuidString)
        let cache = AssetCache(directory: dir)
        await #expect(throws: (any Error).self) {
            _ = try await cache.file(for: URL(string: "http://127.0.0.1:9/nothing.mp4")!, key: "x", ext: "mp4",
                                     retry: RetryPolicy(maxAttempts: 2, baseDelay: 0.01, maxDelay: 0.02))
        }
        #expect(await cache.cachedFile(key: "x", ext: "mp4") == nil)
    }
}
