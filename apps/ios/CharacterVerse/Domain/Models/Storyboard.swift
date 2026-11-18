import Foundation

/// Versioned storyboard document (shared/json-schemas/storyboard.v1.schema.json).
struct Storyboard: Codable, Hashable, Sendable {
    struct CastMember: Codable, Hashable, Sendable { var characterId: String; var displayName: String; var role: String }
    struct SceneCharacter: Codable, Hashable, Sendable {
        var characterId: String
        var position: String
        var scale: Double
        var actionId: String
    }
    struct DialogueLine: Codable, Hashable, Sendable, Identifiable {
        var characterId: String
        var line: String
        var startMs: Int
        var id: String { "\(characterId)-\(startMs)-\(line.hashValue)" }
    }
    struct Scene: Codable, Hashable, Sendable, Identifiable {
        var sceneId: String
        var sequence: Int
        var title: String
        var description: String?
        var durationMs: Int
        var environmentId: String
        var cameraPresetId: String
        var lightingPresetId: String
        var characters: [SceneCharacter]
        var dialogue: [DialogueLine]
        var soundEffectIds: [String]
        var transition: String
        var id: String { sceneId }
    }

    var schemaVersion: Int
    var title: String
    var logline: String
    var synopsis: String
    var durationSeconds: Int
    var aspectRatio: String
    var language: String
    var characters: [CastMember]
    var musicCueId: String?
    var scenes: [Scene]

    var totalDurationMs: Int { scenes.reduce(0) { $0 + $1.durationMs } }

    /// Renumbers scenes 1..n after reorder/add/delete so the document stays valid.
    mutating func renumber() {
        for index in scenes.indices { scenes[index].sequence = index + 1 }
    }
}

struct Project: Identifiable, Hashable, Sendable {
    var id: String
    var title: String
    var description: String
    var status: String
    var version: Int
    var storyboard: Storyboard?
    var updatedAt: Date
}

struct RenderJob: Identifiable, Hashable, Sendable {
    enum Status: String, Sendable { case queued, processing, completed, failed, cancelled }
    var id: String
    var projectId: String
    var projectTitle: String?
    var status: Status
    var progressStage: String
    var progressPercent: Int
    var quality: String
    var aspectRatio: String
    var errorCode: String?
    var attempts: Int
    var cancelRequested: Bool
    var durationMs: Int?
    var createdAt: Date

    var isActive: Bool { status == .queued || status == .processing }

    /// Human-readable stage. We never invent a completion time (plan §4.2 Render Queue).
    var stageLabel: String {
        switch progressStage {
        case "queued": "Waiting in queue"
        case "preparing": "Preparing scene"
        case "rendering_scenes": "Rendering scenes"
        case "composing": "Composing audio & video"
        case "uploading": "Uploading"
        case "completed": "Ready"
        case "cancelled": "Cancelled"
        default: "Failed"
        }
    }
}

struct MixResult: Sendable, Hashable {
    struct Omitted: Hashable, Sendable { var id: String; var kind: String; var reason: String }
    struct LineageEntry: Hashable, Sendable { var sourceCharacterId: String; var weight: Double; var dimensions: [String] }
    var recipe: CharacterRecipe
    var lineage: [LineageEntry]
    var omitted: [Omitted]
    var warningCodes: [String]
    var dominantSourceId: String
}
