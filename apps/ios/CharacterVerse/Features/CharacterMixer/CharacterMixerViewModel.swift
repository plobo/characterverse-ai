import Foundation
import Observation

@MainActor
@Observable
final class CharacterMixerViewModel {
    struct Snapshot: Equatable { var selected: [String]; var dimensions: Set<MixDimension>; var weights: [String: Double]; var name: String }

    let env: AppEnvironment
    var selected: [String] = [] { didSet { recompute() } }
    var dimensions: Set<MixDimension> = Set(MixDimension.allCases) { didSet { recompute() } }
    var weights: [String: Double] = [:] { didSet { recompute() } }
    var customName = "" { didSet { recompute() } }
    var suggestions: [SuggestionDTO] = []
    private(set) var result: MixResult?
    private(set) var localError: String?
    private var history: [Snapshot] = []
    var busy = false
    var errorMessage: String?
    var savedCharacter: CharacterSummary?
    var characters: [CharacterSummary] = [] { didSet { recompute() } }

    init(env: AppEnvironment) { self.env = env }

    var canUndo: Bool { !history.isEmpty }

    func toggle(_ id: String) {
        pushHistory()
        if let i = selected.firstIndex(of: id) { selected.remove(at: i); weights[id] = nil }
        else if selected.count < 3 { selected.append(id); weights[id] = weights[id] ?? 1 }
    }

    func toggleDimension(_ d: MixDimension) {
        pushHistory()
        if dimensions.contains(d) { dimensions.remove(d) } else { dimensions.insert(d) }
    }

    func setWeight(_ id: String, _ value: Double) { weights[id] = value }
    func beginWeightChange() { pushHistory() }

    func undo() {
        guard let last = history.popLast() else { return }
        selected = last.selected; dimensions = last.dimensions; weights = last.weights; customName = last.name
    }

    private func pushHistory() {
        history.append(Snapshot(selected: selected, dimensions: dimensions, weights: weights, name: customName))
        if history.count > 30 { history.removeFirst() }
    }

    /// Instant, offline preview using the shared deterministic resolver (identical to the server's result).
    func recompute() {
        let sources = selected.compactMap { id in characters.first { $0.id == id }.map { (id: id, recipe: $0.recipe) } }
        guard sources.count >= 2 else { result = nil; localError = nil; return }
        do {
            result = try env.fusion.resolve(sources: sources, weights: weights, dimensions: dimensions,
                                            name: customName.isEmpty ? nil : customName)
            localError = nil
        } catch let e as FusionError {
            result = nil
            localError = e.message
        } catch {}
    }

    var warnings: [String] {
        guard let r = result else { return localError.map { [$0] } ?? [] }
        var out: [String] = []
        if r.warningCodes.contains("RIG_MISMATCH") {
            let base = env.catalog.baseModel(r.recipe.baseModelId)?.name ?? r.recipe.baseModelId
            out.append("Different body types — using \(base) and keeping only compatible parts.")
        }
        for o in r.omitted {
            let name = env.catalog.module(o.id)?.name ?? env.catalog.power(o.id)?.name ?? o.id.humanized
            let why = ["slot_taken": "slot already used", "incompatible_rig": "doesn't fit this body",
                       "unsupported_by_rig": "not supported by this body", "limit_reached": "limit reached",
                       "not_approved": "not licensed"][o.reason] ?? o.reason
            out.append("\(name) left out (\(why))")
        }
        return out
    }

    private var request: MixRequestDTO {
        MixRequestDTO(sourceCharacterIds: selected, dimensions: dimensions.map(\.rawValue).sorted(), weights: weights,
                      name: customName.isEmpty ? nil : customName)
    }

    func fetchSuggestions() async {
        guard selected.count >= 2 else { return }
        busy = true
        defer { busy = false }
        do {
            suggestions = try await env.remote.preview(request).suggestions
        } catch { errorMessage = error.localizedDescription }
    }

    func applyNextSuggestion() {
        guard !suggestions.isEmpty else { return }
        pushHistory()
        let current = suggestions.firstIndex { $0.name == customName } ?? -1
        customName = suggestions[(current + 1) % suggestions.count].name
    }

    func save() async -> CharacterSummary? {
        busy = true
        defer { busy = false }
        do {
            let mix = try await env.remote.save(request)
            savedCharacter = mix.character?.domain
            errorMessage = nil
            env.analytics.track("mix_saved", ["sources": "\(selected.count)"])
            return savedCharacter
        } catch {
            errorMessage = error.localizedDescription
            return nil
        }
    }
}
