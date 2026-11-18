import Foundation

/// REST implementation of all repositories over `APIClient`.
final class RemoteRepository: AccountRepository, CharacterRepository, MixRepository, ProjectRepository, RenderRepository, Sendable {
    let api: APIClient
    let tokens: TokenStore

    init(api: APIClient, tokens: TokenStore) {
        self.api = api
        self.tokens = tokens
    }

    // MARK: account
    func signIn(provider: String, token: String?, displayName: String?) async throws -> UserDTO {
        let res: SessionResponseDTO = try await api.send("POST", "v1/auth/session",
                                                         body: SessionRequestDTO(provider: provider, token: token, displayName: displayName))
        await tokens.save(res.accessToken)
        return res.user
    }
    func signOut() async { await tokens.clear() }
    func hasSession() async -> Bool { await tokens.token() != nil }
    func me() async throws -> UserDTO { try await api.send("GET", "v1/me") }
    func usage() async throws -> UsageDTO { try await api.send("GET", "v1/me/usage") }
    func exportData() async throws -> Data {
        let json: [String: JSONValue] = try await api.send("GET", "v1/me/export")
        return try JSONEncoder().encode(json)
    }
    func deleteAccount() async throws {
        let _: APIClient.Empty = try await api.send("DELETE", "v1/me")
        await tokens.clear()
    }
    func report(contentType: String, contentId: String, reason: String, details: String) async throws {
        let _: ReportResponseDTO = try await api.send("POST", "v1/reports",
                                                      body: ReportDTO(contentType: contentType, contentId: contentId, reason: reason, details: details))
    }
    func moderationCheck(_ text: String, contentType: String) async throws -> ModerationDTO {
        try await api.send("POST", "v1/moderation/check", body: ModerationCheckDTO(text: text, contentType: contentType))
    }

    // MARK: characters
    func list(search: String?, sort: String, includeArchived: Bool) async throws -> [CharacterSummary] {
        var q = [URLQueryItem(name: "sort", value: sort), URLQueryItem(name: "includeArchived", value: String(includeArchived))]
        if let search, !search.isEmpty { q.append(URLQueryItem(name: "search", value: search)) }
        let res: ItemsDTO<CharacterDTO> = try await api.send("GET", "v1/characters", query: q)
        return res.items.map(\.domain)
    }
    func create(_ recipe: CharacterRecipe, description: String) async throws -> CharacterSummary {
        let dto: CharacterDTO = try await api.send("POST", "v1/characters", body: CreateCharacterDTO(recipe: recipe, description: description))
        return dto.domain
    }
    func update(_ id: String, _ change: UpdateCharacterDTO) async throws -> CharacterSummary {
        let dto: CharacterDTO = try await api.send("PATCH", "v1/characters/\(id)", body: change)
        return dto.domain
    }
    func delete(_ id: String) async throws { let _: APIClient.Empty = try await api.send("DELETE", "v1/characters/\(id)") }
    func duplicate(_ id: String) async throws -> CharacterSummary {
        let dto: CharacterDTO = try await api.send("POST", "v1/characters/\(id)/duplicate")
        return dto.domain
    }
    func generateRecipe(description: String, category: String?, name: String?) async throws -> GenerateRecipeResponseDTO {
        try await api.send("POST", "v1/characters/generate-recipe",
                           body: GenerateRecipeRequestDTO(description: description, category: category, name: name))
    }

    // MARK: mixer
    func preview(_ request: MixRequestDTO) async throws -> MixPreviewDTO { try await api.send("POST", "v1/mixes/preview", body: request) }
    func save(_ request: MixRequestDTO) async throws -> MixDTO { try await api.send("POST", "v1/mixes", body: request) }

    // MARK: projects
    func generateStory(_ request: GenerateStoryRequestDTO) async throws -> GenerateStoryResponseDTO {
        try await api.send("POST", "v1/stories/generate", body: request)
    }
    func list() async throws -> [Project] {
        let res: ItemsDTO<ProjectDTO> = try await api.send("GET", "v1/projects")
        return res.items.map(\.domain)
    }
    func create(title: String, storyboard: Storyboard?) async throws -> Project {
        let dto: ProjectDTO = try await api.send("POST", "v1/projects", body: CreateProjectDTO(title: title, description: "", storyboard: storyboard))
        return dto.domain
    }
    func saveStoryboard(projectId: String, _ storyboard: Storyboard) async throws -> Project {
        let dto: ProjectDTO = try await api.send("POST", "v1/projects/\(projectId)/storyboard", body: StoryboardRequestDTO(storyboard: storyboard))
        return dto.domain
    }
    func deleteProject(_ projectId: String) async throws { let _: APIClient.Empty = try await api.send("DELETE", "v1/projects/\(projectId)") }

    // MARK: renders
    func list() async throws -> [RenderJob] {
        let res: ItemsDTO<RenderJobDTO> = try await api.send("GET", "v1/renders")
        return res.items.map(\.domain)
    }
    func submit(projectId: String, quality: String, idempotencyKey: String) async throws -> RenderJob {
        let dto: RenderJobDTO = try await api.send("POST", "v1/projects/\(projectId)/renders", body: CreateRenderDTO(quality: quality, aspectRatio: nil),
                                                   headers: ["Idempotency-Key": idempotencyKey])
        return dto.domain
    }
    func get(_ id: String) async throws -> RenderJob { let dto: RenderJobDTO = try await api.send("GET", "v1/renders/\(id)"); return dto.domain }
    func cancel(_ id: String) async throws -> RenderJob {
        let dto: RenderJobDTO = try await api.send("POST", "v1/renders/\(id)/cancel"); return dto.domain
    }
    func retry(_ id: String) async throws -> RenderJob {
        let dto: RenderJobDTO = try await api.send("POST", "v1/renders/\(id)/retry"); return dto.domain
    }
    func downloadURL(_ id: String) async throws -> DownloadURLDTO { try await api.send("GET", "v1/renders/\(id)/download-url") }
}

/// Minimal JSON value for pass-through payloads (data export).
enum JSONValue: Codable, Sendable {
    case string(String), number(Double), bool(Bool), object([String: JSONValue]), array([JSONValue]), null
    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null }
        else if let v = try? c.decode(Bool.self) { self = .bool(v) }
        else if let v = try? c.decode(Double.self) { self = .number(v) }
        else if let v = try? c.decode(String.self) { self = .string(v) }
        else if let v = try? c.decode([JSONValue].self) { self = .array(v) }
        else { self = .object(try c.decode([String: JSONValue].self)) }
    }
    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .string(let v): try c.encode(v)
        case .number(let v): try c.encode(v)
        case .bool(let v): try c.encode(v)
        case .object(let v): try c.encode(v)
        case .array(let v): try c.encode(v)
        case .null: try c.encodeNil()
        }
    }
}
