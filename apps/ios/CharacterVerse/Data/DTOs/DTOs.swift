import Foundation

// Wire DTOs (shared/api-contracts/openapi.json). Kept separate from domain models; mapped in repositories.

struct UserDTO: Codable, Sendable { var id: String; var displayName: String; var email: String?; var isGuest: Bool; var createdAt: Date }
struct SessionRequestDTO: Codable, Sendable { var provider: String; var token: String?; var displayName: String? }
struct SessionResponseDTO: Codable, Sendable {
    var accessToken: String; var tokenType: String; var expiresAt: Int; var refreshToken: String; var refreshExpiresAt: Int; var user: UserDTO
}
struct RefreshRequestDTO: Codable, Sendable { var refreshToken: String }
struct UsageDTO: Codable, Sendable { var characters: Int; var projects: Int; var renders: Int; var storageBytes: Int }

struct LineageDTO: Codable, Sendable { var sourceCharacterId: String; var contributionWeight: Double; var mixDimension: String }
struct CharacterDTO: Codable, Sendable {
    var id: String; var name: String; var description: String; var category: String; var style: String
    var recipe: CharacterRecipe; var version: Int; var visibility: String; var isFavorite: Bool; var archived: Bool
    var lineage: [LineageDTO]; var createdAt: Date; var updatedAt: Date

    var domain: CharacterSummary {
        CharacterSummary(id: id, name: name, description: description, category: category, recipe: recipe, version: version,
                         isFavorite: isFavorite, archived: archived,
                         lineage: lineage.map { .init(sourceCharacterId: $0.sourceCharacterId, contributionWeight: $0.contributionWeight,
                                                      mixDimension: $0.mixDimension) },
                         createdAt: createdAt, updatedAt: updatedAt)
    }
}
struct ItemsDTO<T: Codable & Sendable>: Codable, Sendable { var items: [T] }
struct CreateCharacterDTO: Codable, Sendable { var recipe: CharacterRecipe; var description: String }
struct UpdateCharacterDTO: Codable, Sendable {
    var recipe: CharacterRecipe?; var description: String?; var archived: Bool?; var isFavorite: Bool?; var expectedVersion: Int?
}
struct GenerateRecipeRequestDTO: Codable, Sendable { var description: String; var category: String?; var name: String? }
struct WarningDTO: Codable, Sendable, Hashable { var code: String; var message: String }
struct ModerationDTO: Codable, Sendable, Hashable { var decision: String; var reasonCode: String?; var feedback: String? }
struct ProviderDTO: Codable, Sendable { var name: String; var version: String; var local: Bool }
struct GenerateRecipeResponseDTO: Codable, Sendable {
    var recipe: CharacterRecipe; var warnings: [WarningDTO]; var moderation: ModerationDTO; var provider: ProviderDTO
}

struct MixRequestDTO: Codable, Sendable {
    var sourceCharacterIds: [String]; var dimensions: [String]; var weights: [String: Double]?; var name: String?
}
struct OmittedDTO: Codable, Sendable { var id: String; var kind: String; var reason: String }
struct MixLineageDTO: Codable, Sendable { var sourceCharacterId: String; var weight: Double; var dimensions: [String] }
struct SuggestionDTO: Codable, Sendable, Hashable { var name: String; var tagline: String }
struct MixPreviewDTO: Codable, Sendable {
    var recipe: CharacterRecipe; var lineage: [MixLineageDTO]; var omitted: [OmittedDTO]; var warnings: [WarningDTO]
    var dominantSourceId: String; var suggestions: [SuggestionDTO]
}
struct MixDTO: Codable, Sendable { var id: String; var character: CharacterDTO?; var result: MixPreviewDTO; var createdAt: Date }

struct GenerateStoryRequestDTO: Codable, Sendable {
    var prompt: String; var characterIds: [String]; var templateId: String?; var title: String?; var genre: String?
    var tone: String?; var audience: String?; var durationSeconds: Int; var aspectRatio: String; var language: String
}
struct GenerateStoryResponseDTO: Codable, Sendable {
    var storyboard: Storyboard; var moderation: ModerationDTO; var provider: ProviderDTO; var cached: Bool
}
struct ProjectDTO: Codable, Sendable {
    var id: String; var title: String; var description: String; var status: String; var version: Int
    var storyboard: Storyboard?; var createdAt: Date; var updatedAt: Date
    var domain: Project { Project(id: id, title: title, description: description, status: status, version: version,
                                  storyboard: storyboard, updatedAt: updatedAt) }
}
struct CreateProjectDTO: Codable, Sendable { var title: String; var description: String; var storyboard: Storyboard? }
struct StoryboardRequestDTO: Codable, Sendable { var storyboard: Storyboard }

struct CreateRenderDTO: Codable, Sendable { var quality: String; var aspectRatio: String? }
struct RenderJobDTO: Codable, Sendable {
    var id: String; var projectId: String; var projectTitle: String?; var status: String; var progressStage: String
    var progressPercent: Int; var quality: String; var aspectRatio: String; var width: Int; var height: Int
    var errorCode: String?; var attempts: Int; var cancelRequested: Bool; var durationMs: Int?
    var createdAt: Date; var startedAt: Date?; var completedAt: Date?
    var domain: RenderJob {
        RenderJob(id: id, projectId: projectId, projectTitle: projectTitle, status: RenderJob.Status(rawValue: status) ?? .failed,
                  progressStage: progressStage, progressPercent: progressPercent, quality: quality, aspectRatio: aspectRatio,
                  errorCode: errorCode, attempts: attempts, cancelRequested: cancelRequested, durationMs: durationMs,
                  createdAt: createdAt)
    }
}
struct DownloadURLDTO: Codable, Sendable { var url: String; var thumbnailUrl: String?; var expiresAt: Int; var mimeType: String; var fileSize: Int }
struct PreviewDTO: Codable, Sendable { var recipeHash: String; var cached: Bool; var glbUrl: String; var thumbnailUrl: String; var expiresAt: Int }
struct PreviewRequestDTO: Codable, Sendable { var recipe: CharacterRecipe }
struct ModerationCheckDTO: Codable, Sendable { var text: String; var contentType: String }
struct ReportDTO: Codable, Sendable { var contentType: String; var contentId: String; var reason: String; var details: String }
struct ReportResponseDTO: Codable, Sendable { var id: String; var status: String; var createdAt: Date }
