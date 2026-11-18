import SwiftUI

@main
struct CharacterVerseApp: App {
    @State private var env: AppEnvironment
    @State private var store: AppStore
    @State private var router = AppRouter()

    init() {
        let env = AppEnvironment()
        _env = State(initialValue: env)
        _store = State(initialValue: AppStore(env: env))
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(store)
                .environment(router)
                .tint(Theme.brand)
                .task { await LaunchOptions.apply(store: store, router: router) }
        }
    }
}

struct RootView: View {
    @Environment(AppStore.self) private var store
    var body: some View {
        switch store.phase {
        case .launching: ProgressView().task { await store.bootstrap() }
        case .signedOut: OnboardingView()
        case .signedIn: MainTabView()
        }
    }
}

struct MainTabView: View {
    @Environment(AppRouter.self) private var router
    @Environment(AppStore.self) private var store

    var body: some View {
        @Bindable var router = router
        TabView(selection: $router.tab) {
            ForEach(AppTab.allCases, id: \.self) { tab in
                NavigationStack(path: router.path(tab)) {
                    root(for: tab)
                        .navigationDestination(for: Route.self, destination: destination)
                }
                .tabItem { Label(tab.title, systemImage: tab.symbol) }
                .tag(tab)
            }
        }
        .overlay(alignment: .top) {
            if store.isOffline {
                Text("Offline — showing saved drafts").font(.caption.bold()).padding(6).frame(maxWidth: .infinity)
                    .background(Theme.warning).foregroundStyle(.black)
            }
        }
    }

    @ViewBuilder func root(for tab: AppTab) -> some View {
        switch tab {
        case .discover: DiscoverView()
        case .create: CharacterCreatorView()
        case .mixer: CharacterMixerView()
        case .studio: StudioHomeView()
        case .universe: MyUniverseView()
        }
    }

    @ViewBuilder func destination(_ route: Route) -> some View {
        switch route {
        case .characterDetail(let id): CharacterDetailView(characterId: id)
        case .template(let id): TemplateDetailView(templateId: id)
        case .storyCreator: StoryCreatorView()
        case .storyboard(let id): StoryboardView(projectId: id)
        case .sceneEditor(let pid, let sid): AnimationStudioView(projectId: pid, sceneId: sid)
        case .renderQueue: RenderQueueView()
        case .settings: SettingsView()
        }
    }
}
