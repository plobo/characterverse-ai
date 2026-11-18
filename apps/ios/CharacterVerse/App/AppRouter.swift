import SwiftUI

enum AppTab: String, CaseIterable, Hashable {
    case discover, create, mixer, studio, universe
    var title: String {
        switch self {
        case .discover: "Discover"
        case .create: "Create"
        case .mixer: "Mixer"
        case .studio: "Studio"
        case .universe: "My Universe"
        }
    }
    var symbol: String {
        switch self {
        case .discover: "sparkle.magnifyingglass"
        case .create: "wand.and.stars"
        case .mixer: "arrow.triangle.merge"
        case .studio: "film.stack"
        case .universe: "globe.americas"
        }
    }
}

enum Route: Hashable {
    case characterDetail(String)
    case template(String)
    case storyCreator
    case storyboard(String)
    case sceneEditor(projectId: String, sceneId: String)
    case renderQueue
    case settings
}

@MainActor
@Observable
final class AppRouter {
    var tab: AppTab = .discover
    var paths: [AppTab: NavigationPath] = [:]
    var creatorSeed: CharacterRecipe?
    var creatorEditingId: String?

    func path(_ tab: AppTab) -> Binding<NavigationPath> {
        Binding(get: { self.paths[tab] ?? NavigationPath() }, set: { self.paths[tab] = $0 })
    }

    func push(_ route: Route, on tab: AppTab? = nil) {
        let t = tab ?? self.tab
        self.tab = t
        var p = paths[t] ?? NavigationPath()
        p.append(route)
        paths[t] = p
    }

    func openCreator(with recipe: CharacterRecipe?, editing id: String? = nil) {
        creatorSeed = recipe
        creatorEditingId = id
        tab = .create
    }
}
