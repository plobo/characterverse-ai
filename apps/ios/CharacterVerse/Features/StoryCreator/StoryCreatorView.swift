import SwiftUI

struct StudioHomeView: View {
    @Environment(AppStore.self) private var store
    @Environment(AppRouter.self) private var router

    var body: some View {
        List {
            Section {
                Button { router.push(.storyCreator) } label: { Label("New animated short", systemImage: "plus.rectangle.on.rectangle") }
                Button { router.push(.renderQueue) } label: {
                    HStack {
                        Label("Render queue", systemImage: "square.stack.3d.down.forward")
                        Spacer()
                        let active = store.renders.filter(\.isActive).count
                        if active > 0 { Text("\(active) active").font(.caption.bold()).foregroundStyle(Theme.brand) }
                    }
                }
            }
            Section("Projects") {
                if store.projects.isEmpty {
                    EmptyStateView(symbol: "film", title: "No projects yet", message: "Generate a story with your characters to start a storyboard.")
                }
                ForEach(store.projects) { p in
                    Button { router.push(.storyboard(p.id)) } label: {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(p.title).font(.headline)
                            Text("\(p.storyboard?.scenes.count ?? 0) scenes · \(p.storyboard?.durationSeconds ?? 0)s · \(p.status.capitalized)")
                                .font(.caption).foregroundStyle(Theme.textSecondary)
                        }
                    }
                    .foregroundStyle(.primary)
                }
                .onDelete { idx in
                    let ids = idx.map { store.projects[$0].id }
                    Task { for id in ids { try? await store.repo.deleteProject(id) }; await store.refreshProjects() }
                }
            }
        }
        .navigationTitle("Studio")
        .refreshable { await store.refreshAll() }
    }
}

struct StoryCreatorView: View {
    @Environment(AppStore.self) private var store
    @Environment(AppRouter.self) private var router
    @State private var prompt = "find the glowing map in the crystal forest"
    @State private var genre = "adventure"
    @State private var tone = "playful"
    @State private var audience = "family"
    @State private var duration = 30
    @State private var aspect = "16:9"
    @State private var language = "en"
    @State private var cast: [String] = []
    @State private var result: GenerateStoryResponseDTO?
    @State private var busy = false
    @State private var error: String?

    var body: some View {
        Form {
            Section("Story idea") {
                TextField("What happens?", text: $prompt, axis: .vertical).lineLimit(2...5)
                Picker("Template", selection: Binding(get: { "" }, set: { id in
                    if let t = store.env.catalog.manifest.storyTemplates.first(where: { $0.id == id }) { genre = t.genre; tone = t.tone; prompt = t.name.lowercased() }
                })) {
                    Text("Custom").tag("")
                    ForEach(store.env.catalog.manifest.storyTemplates) { Text($0.name).tag($0.id) }
                }
            }
            Section("Style") {
                Picker("Genre", selection: $genre) { ForEach(["adventure", "comedy", "fantasy", "mystery", "sci-fi"], id: \.self) { Text($0.capitalized) } }
                Picker("Tone", selection: $tone) { ForEach(["playful", "uplifting", "heartwarming", "mysterious", "calm"], id: \.self) { Text($0.capitalized) } }
                Picker("Audience", selection: $audience) { ForEach(["family", "kids", "teens", "everyone"], id: \.self) { Text($0.capitalized) } }
                Picker("Duration", selection: $duration) { ForEach([15, 30, 60], id: \.self) { Text("\($0) s") } }.pickerStyle(.segmented)
                Picker("Aspect", selection: $aspect) { Text("Landscape 16:9").tag("16:9"); Text("Vertical 9:16").tag("9:16") }.pickerStyle(.segmented)
                Picker("Language", selection: $language) { Text("English").tag("en"); Text("Français").tag("fr"); Text("Español").tag("es") }
            }
            Section {
                ForEach(store.characters.filter { !$0.archived }) { c in
                    Button { toggle(c.id) } label: {
                        HStack {
                            CharacterThumbnail(parts: store.env.assembler.assemble(c.recipe)).frame(width: 40, height: 44)
                            Text(c.name).foregroundStyle(.primary)
                            Spacer()
                            if cast.contains(c.id) { Image(systemName: "checkmark.circle.fill").foregroundStyle(Theme.brand) }
                        }
                    }
                    .accessibilityAddTraits(cast.contains(c.id) ? .isSelected : [])
                }
            } header: { Text("Cast (1–4)") }
            if let error { Section { ErrorBanner(message: error) } }
            if let r = result { outline(r) }
            Section {
                Button { Task { await generate() } } label: { Label(result == nil ? "Generate story" : "Regenerate", systemImage: "sparkles") }
                    .disabled(cast.isEmpty || busy)
                if result != nil {
                    Button { Task { await createProject() } } label: { Label("Open storyboard", systemImage: "rectangle.split.3x1") }
                        .buttonStyle(PrimaryButtonStyle()).listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
                }
            }
        }
        .navigationTitle("Story Creator")
        .overlay { if busy { LoadingOverlay(label: "Writing your story…") } }
        .onAppear { if cast.isEmpty { cast = Array(store.characters.filter { !$0.archived && $0.lineage.isEmpty }.prefix(2).map(\.id)) } }
    }

    private func toggle(_ id: String) {
        if let i = cast.firstIndex(of: id) { cast.remove(at: i) } else if cast.count < 4 { cast.append(id) }
    }

    private func outline(_ r: GenerateStoryResponseDTO) -> some View {
        Section {
            Text(r.storyboard.title).font(.headline)
            Text(r.storyboard.logline).font(.subheadline)
            ForEach(r.storyboard.scenes) { s in
                VStack(alignment: .leading) {
                    Text("\(s.sequence). \(s.title)").font(.subheadline.bold())
                    ForEach(s.dialogue) { Text("“\($0.line)”").font(.footnote).foregroundStyle(Theme.textSecondary) }
                }
            }
            if let fb = r.moderation.feedback { Label(fb, systemImage: "lightbulb").font(.footnote).foregroundStyle(Theme.warning) }
            else { Label("Originality check passed", systemImage: "checkmark.seal").font(.footnote).foregroundStyle(Theme.success) }
        } header: { Text("Outline") }
    }

    private func generate() async {
        busy = true
        defer { busy = false }
        do {
            result = try await store.repo.generateStory(GenerateStoryRequestDTO(prompt: prompt, characterIds: cast, templateId: nil, title: nil,
                                                                               genre: genre, tone: tone, audience: audience, durationSeconds: duration,
                                                                               aspectRatio: aspect, language: language))
            error = nil
        } catch { self.error = error.localizedDescription }
    }

    private func createProject() async {
        guard let sb = result?.storyboard else { return }
        busy = true
        defer { busy = false }
        do {
            let project = try await store.repo.create(title: sb.title, storyboard: sb)
            store.projects.insert(project, at: 0)
            router.push(.storyboard(project.id))
        } catch { self.error = error.localizedDescription }
    }
}
