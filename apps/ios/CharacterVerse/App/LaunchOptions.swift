import Foundation

/// Debug-only launch arguments used for UI tests and README screenshots:
///   -cvDevSignIn <subject>   sign in with the dev provider (local backend only)
///   -cvScreen <name>         open a screen: discover|create|mixer|studio|storyboard|scene|renders|universe|detail|story|settings
@MainActor
enum LaunchOptions {
    static func apply(store: AppStore, router: AppRouter) async {
        #if DEBUG
        let defaults = UserDefaults.standard
        if let subject = defaults.string(forKey: "cvDevSignIn"), store.phase != .signedIn {
            while store.phase == .launching { try? await Task.sleep(for: .milliseconds(100)) }
            if store.phase == .signedOut { await store.signIn(provider: "dev", token: subject, name: "Demo Creator") }
        }
        guard let screen = defaults.string(forKey: "cvScreen") else { return }
        while store.phase != .signedIn { try? await Task.sleep(for: .milliseconds(100)); if store.phase == .signedOut { return } }
        await store.refreshAll()
        let first = store.characters.first { !$0.archived && $0.lineage.isEmpty }
        let project = store.projects.first
        switch screen {
        case "create": router.openCreator(with: store.env.catalog.manifest.characterTemplates.first?.recipe)
        case "mixer": router.tab = .mixer
        case "studio": router.tab = .studio
        case "story": router.push(.storyCreator, on: .studio)
        case "storyboard": if let project { router.push(.storyboard(project.id), on: .studio) }
        case "scene":
            if let project, let scene = project.storyboard?.scenes.first {
                router.push(.storyboard(project.id), on: .studio)
                router.push(.sceneEditor(projectId: project.id, sceneId: scene.sceneId), on: .studio)
            }
        case "renders": router.push(.renderQueue, on: .studio)
        case "universe": router.tab = .universe
        case "detail": if let first { router.push(.characterDetail(first.id), on: .universe) }
        case "settings": router.push(.settings, on: .universe)
        default: router.tab = .discover
        }
        #endif
    }
}
