import Foundation
import Observation

@MainActor
@Observable
final class CharacterCreatorViewModel {
    let env: AppEnvironment
    var recipe: CharacterRecipe { didSet { autosave() } }
    var editingCharacterId: String?
    var draftId: String?
    var description = ""
    var aiPrompt = ""
    var aiWarnings: [String] = []
    var moderationNote: String?
    var busy = false
    var errorMessage: String?
    var savedMessage: String?

    init(env: AppEnvironment, seed: CharacterRecipe? = nil, editing: String? = nil) {
        self.env = env
        recipe = seed ?? Self.blank(env.catalog)
        editingCharacterId = editing
    }

    static func blank(_ catalog: Catalog) -> CharacterRecipe {
        CharacterRecipe(schemaVersion: 1, name: "New Character", category: "hero", baseModelId: "humanoid_base_01",
                        style: "stylized_cinematic", proportions: .init(height: 1, shoulderWidth: 1, headScale: 1),
                        palette: .init(primary: "#6C4DF6", secondary: "#2E3A59", accent: "#FFB547"),
                        modules: [], powers: [], personalityTraits: ["brave"], voiceProfileId: "voice_fictional_warm_01",
                        assetManifestVersion: catalog.manifest.manifestVersion)
    }

    var parts: [ResolvedPart] { env.assembler.assemble(recipe) }
    var issues: [RecipeIssue] { env.validator.issues(recipe) }
    var rig: String { env.catalog.rig(of: recipe.baseModelId) ?? "humanoid_v1" }

    var baseModelsForCategory: [AssetManifest.BaseModel] {
        env.catalog.approvedBaseModels.filter { $0.categories.contains(recipe.category) }
    }

    var slots: [(slot: String, modules: [AssetManifest.Module])] {
        let compatible = env.catalog.approvedModules.filter { $0.rigs.contains(rig) }
        let grouped = Dictionary(grouping: compatible, by: \.slot)
        return grouped.keys.sorted().map { ($0, grouped[$0]!.sorted { $0.priority < $1.priority }) }
    }

    var availablePowers: [AssetManifest.Power] { env.catalog.manifest.powers.filter { $0.rigs.contains(rig) } }

    func setCategory(_ category: String) {
        recipe.category = category
        if !(env.catalog.baseModel(recipe.baseModelId)?.categories.contains(category) ?? false),
           let base = baseModelsForCategory.first {
            setBaseModel(base.id)
        }
    }

    /// Switching body keeps only modules/powers the new rig supports (no skeleton blending).
    func setBaseModel(_ id: String) {
        recipe.baseModelId = id
        let newRig = env.catalog.rig(of: id) ?? rig
        recipe.modules = recipe.modules.filter { env.catalog.module($0)?.rigs.contains(newRig) ?? false }
        recipe.powers = recipe.powers.filter { env.catalog.power($0)?.rigs.contains(newRig) ?? false }
    }

    func selectedModule(in slot: String) -> String? {
        recipe.modules.first { env.catalog.module($0)?.slot == slot }
    }

    func setModule(_ id: String?, slot: String) {
        recipe.modules.removeAll { env.catalog.module($0)?.slot == slot }
        if let id { recipe.modules.append(id) }
    }

    func togglePower(_ id: String) {
        if let i = recipe.powers.firstIndex(of: id) { recipe.powers.remove(at: i) }
        else if recipe.powers.count < 3 { recipe.powers.append(id) }
    }

    func toggleTrait(_ id: String) {
        if let i = recipe.personalityTraits.firstIndex(of: id) { recipe.personalityTraits.remove(at: i) }
        else if recipe.personalityTraits.count < 5 { recipe.personalityTraits.append(id) }
    }

    func generateFromDescription() async {
        guard !aiPrompt.trimmingCharacters(in: .whitespaces).isEmpty else { return }
        busy = true
        defer { busy = false }
        do {
            let res = try await env.remote.generateRecipe(description: aiPrompt, category: nil, name: nil)
            recipe = res.recipe
            description = aiPrompt
            aiWarnings = res.warnings.map(\.message)
            moderationNote = res.moderation.feedback
            errorMessage = nil
            env.analytics.track("recipe_generated")
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func save() async -> CharacterSummary? {
        guard issues.isEmpty else { errorMessage = issues.first?.message; return nil }
        busy = true
        defer { busy = false }
        do {
            let saved: CharacterSummary
            if let id = editingCharacterId {
                saved = try await env.remote.update(id, UpdateCharacterDTO(recipe: recipe, description: description))
            } else {
                saved = try await env.remote.create(recipe, description: description)
            }
            editingCharacterId = saved.id
            if let draftId { env.drafts.remove(id: draftId); self.draftId = nil }
            savedMessage = "Saved to My Universe (v\(saved.version))"
            errorMessage = nil
            env.analytics.track("character_saved")
            return saved
        } catch APIError.offline {
            autosave()
            errorMessage = "You're offline — kept as a local draft."
        } catch {
            errorMessage = error.localizedDescription
        }
        return nil
    }

    private func autosave() {
        draftId = env.drafts.upsert(id: draftId, recipe: recipe, serverCharacterId: editingCharacterId).id
    }
}
