import Foundation

protocol AccountRepository: Sendable {
    func signIn(provider: String, token: String?, displayName: String?) async throws -> UserDTO
    func signOut() async
    func hasSession() async -> Bool
    func me() async throws -> UserDTO
    func usage() async throws -> UsageDTO
    func exportData() async throws -> Data
    func deleteAccount() async throws
    func report(contentType: String, contentId: String, reason: String, details: String) async throws
    func moderationCheck(_ text: String, contentType: String) async throws -> ModerationDTO
}

protocol CharacterRepository: Sendable {
    func list(search: String?, sort: String, includeArchived: Bool) async throws -> [CharacterSummary]
    func create(_ recipe: CharacterRecipe, description: String) async throws -> CharacterSummary
    func update(_ id: String, _ change: UpdateCharacterDTO) async throws -> CharacterSummary
    func delete(_ id: String) async throws
    func duplicate(_ id: String) async throws -> CharacterSummary
    func generateRecipe(description: String, category: String?, name: String?) async throws -> GenerateRecipeResponseDTO
}

protocol MixRepository: Sendable {
    func preview(_ request: MixRequestDTO) async throws -> MixPreviewDTO
    func save(_ request: MixRequestDTO) async throws -> MixDTO
}

protocol ProjectRepository: Sendable {
    func generateStory(_ request: GenerateStoryRequestDTO) async throws -> GenerateStoryResponseDTO
    func list() async throws -> [Project]
    func create(title: String, storyboard: Storyboard?) async throws -> Project
    func saveStoryboard(projectId: String, _ storyboard: Storyboard) async throws -> Project
    func deleteProject(_ id: String) async throws
}

protocol RenderRepository: Sendable {
    func list() async throws -> [RenderJob]
    func submit(projectId: String, quality: String, idempotencyKey: String) async throws -> RenderJob
    func get(_ id: String) async throws -> RenderJob
    func cancel(_ id: String) async throws -> RenderJob
    func retry(_ id: String) async throws -> RenderJob
    func downloadURL(_ id: String) async throws -> DownloadURLDTO
}
