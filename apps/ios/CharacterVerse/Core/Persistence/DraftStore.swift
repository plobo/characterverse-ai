import Foundation
import SwiftData

/// Local character drafts (offline-first). Saved on every edit in the Creator; synced on explicit save.
@Model
final class CharacterDraft {
    @Attribute(.unique) var id: String
    var recipeJSON: Data
    var serverCharacterId: String?
    var updatedAt: Date

    init(id: String = UUID().uuidString, recipe: CharacterRecipe, serverCharacterId: String? = nil) {
        self.id = id
        self.recipeJSON = (try? JSONEncoder().encode(recipe)) ?? Data()
        self.serverCharacterId = serverCharacterId
        self.updatedAt = .now
    }

    var recipe: CharacterRecipe? { try? JSONDecoder().decode(CharacterRecipe.self, from: recipeJSON) }
}

@MainActor
final class DraftStore {
    let container: ModelContainer
    private var context: ModelContext { container.mainContext }

    init(inMemory: Bool = false) {
        if let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first {
            try? FileManager.default.createDirectory(at: support, withIntermediateDirectories: true)
        }
        let config = ModelConfiguration(isStoredInMemoryOnly: inMemory)
        container = (try? ModelContainer(for: CharacterDraft.self, configurations: config))
            ?? (try! ModelContainer(for: CharacterDraft.self, configurations: ModelConfiguration(isStoredInMemoryOnly: true)))
    }

    func all() -> [CharacterDraft] {
        (try? context.fetch(FetchDescriptor<CharacterDraft>(sortBy: [SortDescriptor(\.updatedAt, order: .reverse)]))) ?? []
    }

    @discardableResult
    func upsert(id: String?, recipe: CharacterRecipe, serverCharacterId: String? = nil) -> CharacterDraft {
        if let id, let existing = all().first(where: { $0.id == id }) {
            existing.recipeJSON = (try? JSONEncoder().encode(recipe)) ?? existing.recipeJSON
            existing.serverCharacterId = serverCharacterId ?? existing.serverCharacterId
            existing.updatedAt = .now
            try? context.save()
            return existing
        }
        let draft = CharacterDraft(id: id ?? UUID().uuidString, recipe: recipe, serverCharacterId: serverCharacterId)
        context.insert(draft)
        try? context.save()
        return draft
    }

    func remove(id: String) {
        for d in all() where d.id == id { context.delete(d) }
        try? context.save()
    }

    func removeAll() {
        all().forEach(context.delete)
        try? context.save()
    }
}
