import Foundation
import Observation

/// App-wide observable state shared across tabs (session, library, projects, render jobs).
@MainActor
@Observable
final class AppStore {
    enum Phase: Equatable { case launching, signedOut, signedIn }

    let env: AppEnvironment
    var phase: Phase = .launching
    var user: UserDTO?
    var characters: [CharacterSummary] = []
    var projects: [Project] = []
    var renders: [RenderJob] = []
    var usage: UsageDTO?
    var isOffline = false
    var lastError: String?
    var loadingLibrary = false

    init(env: AppEnvironment) { self.env = env }

    var repo: RemoteRepository { env.remote }

    func bootstrap() async {
        if await repo.hasSession() {
            do {
                user = try await repo.me()
                phase = .signedIn
                await refreshAll()
            } catch APIError.offline {
                isOffline = true
                phase = .signedIn
            } catch {
                await repo.signOut()
                phase = .signedOut
            }
        } else {
            phase = .signedOut
        }
    }

    func signIn(provider: String, token: String?, name: String?) async {
        do {
            user = try await repo.signIn(provider: provider, token: token, displayName: name)
            phase = .signedIn
            env.analytics.track("sign_in", ["provider": provider])
            await refreshAll()
        } catch {
            lastError = error.localizedDescription
        }
    }

    func signOut() async {
        await repo.signOut()
        user = nil
        characters = []
        projects = []
        renders = []
        phase = .signedOut
    }

    func refreshAll() async {
        async let c: Void = refreshCharacters()
        async let p: Void = refreshProjects()
        async let r: Void = refreshRenders()
        _ = await (c, p, r)
        usage = try? await repo.usage()
    }

    func refreshCharacters() async {
        loadingLibrary = true
        defer { loadingLibrary = false }
        do {
            characters = try await repo.list(search: nil, sort: "updated", includeArchived: true)
            isOffline = false
        } catch { handle(error) }
    }

    func refreshProjects() async {
        do { projects = try await (repo as ProjectRepository).list() } catch { handle(error) }
    }

    func refreshRenders() async {
        do { renders = try await (repo as RenderRepository).list() } catch { handle(error) }
    }

    func character(_ id: String) -> CharacterSummary? { characters.first { $0.id == id } }

    func handle(_ error: Error) {
        if case APIError.offline = error { isOffline = true; return }
        if let api = error as? APIError, api.code == "AUTH_INVALID" { phase = .signedOut }
        lastError = error.localizedDescription
        env.analytics.error((error as? APIError)?.code ?? "UNKNOWN", area: "store")
    }

    func upsert(_ character: CharacterSummary) {
        if let i = characters.firstIndex(where: { $0.id == character.id }) { characters[i] = character } else { characters.insert(character, at: 0) }
    }
}
