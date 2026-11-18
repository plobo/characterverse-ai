import Foundation

/// Versioned character recipe document (shared/json-schemas/character_recipe.v1.schema.json).
/// The same JSON is produced and consumed by the backend and the Android app.
struct CharacterRecipe: Codable, Hashable, Sendable {
    struct Proportions: Codable, Hashable, Sendable {
        var height: Double
        var shoulderWidth: Double
        var headScale: Double
    }

    struct Palette: Codable, Hashable, Sendable {
        var primary: String
        var secondary: String
        var accent: String
    }

    var schemaVersion: Int
    var name: String
    var category: String
    var baseModelId: String
    var style: String
    var proportions: Proportions
    var palette: Palette
    var modules: [String]
    var powers: [String]
    var personalityTraits: [String]
    var voiceProfileId: String
    var assetManifestVersion: String
}

enum CharacterCategory: String, CaseIterable, Identifiable, Sendable {
    case hero, villain, cartoon, fantasy, robot, alien, creature
    var id: String { rawValue }
    var title: String { rawValue.capitalized }
    var symbol: String {
        switch self {
        case .hero: "shield.lefthalf.filled"
        case .villain: "theatermasks"
        case .cartoon: "face.smiling"
        case .fantasy: "wand.and.stars"
        case .robot: "gearshape.2"
        case .alien: "sparkles"
        case .creature: "pawprint"
        }
    }
}

struct CharacterSummary: Identifiable, Hashable, Sendable {
    struct Lineage: Hashable, Sendable {
        var sourceCharacterId: String
        var contributionWeight: Double
        var mixDimension: String
    }

    var id: String
    var name: String
    var description: String
    var category: String
    var recipe: CharacterRecipe
    var version: Int
    var isFavorite: Bool
    var archived: Bool
    var lineage: [Lineage]
    var createdAt: Date
    var updatedAt: Date
}
