import SwiftUI

struct StoryboardView: View {
    @Environment(AppStore.self) private var store
    @Environment(AppRouter.self) private var router
    var projectId: String
    @State private var doc: Storyboard?
    @State private var dirty = false
    @State private var busy = false
    @State private var error: String?
    @State private var quality = "draft"

    var body: some View {
        Group {
            if let doc { content(doc) } else { EmptyStateView(symbol: "film", title: "No storyboard", message: "Generate a story first.") }
        }
        .navigationTitle(store.projects.first { $0.id == projectId }?.title ?? "Storyboard")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear { if doc == nil { doc = store.projects.first { $0.id == projectId }?.storyboard } }
        .onChange(of: store.projects) { if !dirty { doc = store.projects.first { $0.id == projectId }?.storyboard } }
        .overlay { if busy { LoadingOverlay(label: "Saving…") } }
    }

    private func content(_ sb: Storyboard) -> some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 6) {
                    Text(sb.logline).font(.subheadline)
                    Text("\(sb.scenes.count) scenes · \(Double(sb.totalDurationMs) / 1000, specifier: "%.1f")s of \(sb.durationSeconds)s · \(sb.aspectRatio)")
                        .font(.caption).foregroundStyle(sb.totalDurationMs > sb.durationSeconds * 1000 ? Theme.danger : Theme.textSecondary)
                }
            }
            Section("Scenes") {
                ForEach(sb.scenes) { scene in
                    Button { router.push(.sceneEditor(projectId: projectId, sceneId: scene.sceneId)) } label: { SceneCard(scene: scene, cast: sb.characters) }
                        .buttonStyle(.plain)
                        .swipeActions(edge: .leading) {
                            Button { duplicate(scene) } label: { Label("Duplicate", systemImage: "plus.square.on.square") }.tint(Theme.brandSecondary)
                        }
                }
                .onMove { from, to in edit { $0.scenes.move(fromOffsets: from, toOffset: to) } }
                .onDelete { idx in edit { $0.scenes.remove(atOffsets: idx) } }
                Button { addScene() } label: { Label("Add scene", systemImage: "plus") }
            }
            if let error { Section { ErrorBanner(message: error) } }
            Section {
                if dirty {
                    Button { Task { await save() } } label: { Label("Save storyboard", systemImage: "square.and.arrow.down") }
                        .buttonStyle(SecondaryButtonStyle()).listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
                }
                Picker("Quality", selection: $quality) { Text("Draft 480p").tag("draft"); Text("Final 720p").tag("final") }.pickerStyle(.segmented)
                Button { Task { await render() } } label: { Label("Render video", systemImage: "play.rectangle.fill") }
                    .buttonStyle(PrimaryButtonStyle()).listRowInsets(EdgeInsets()).listRowBackground(Color.clear).disabled(busy)
            } footer: { Text("Rendering runs on our servers. Progress appears in the render queue; time depends on scene complexity and queue depth.") }
        }
        .toolbar { EditButton() }
    }

    private func edit(_ change: (inout Storyboard) -> Void) {
        guard var d = doc else { return }
        change(&d)
        d.renumber()
        doc = d
        dirty = true
    }

    private func duplicate(_ scene: Storyboard.Scene) {
        edit { d in
            guard let i = d.scenes.firstIndex(of: scene), d.scenes.count < 8 else { return }
            var copy = scene
            copy.sceneId = "scene_\(UUID().uuidString.prefix(6).lowercased())"
            d.scenes.insert(copy, at: i + 1)
        }
    }

    private func addScene() {
        edit { d in
            guard d.scenes.count < 8, var copy = d.scenes.last else { return }
            copy.sceneId = "scene_\(UUID().uuidString.prefix(6).lowercased())"
            copy.title = "New scene"
            copy.description = nil
            copy.durationMs = 3000
            copy.dialogue = []
            d.scenes.append(copy)
        }
    }

    private func save() async {
        guard let d = doc else { return }
        busy = true
        defer { busy = false }
        do {
            let p = try await store.repo.saveStoryboard(projectId: projectId, d)
            if let i = store.projects.firstIndex(where: { $0.id == projectId }) { store.projects[i] = p }
            dirty = false
            error = nil
        } catch let e as APIError {
            if case .server(_, _, let message, let details, _) = e { error = ([message] + details.prefix(3).map { "• \($0.message)" }).joined(separator: "\n") }
            else { error = e.localizedDescription }
        } catch { self.error = error.localizedDescription }
    }

    private func render() async {
        if dirty { await save(); if dirty { return } }
        busy = true
        defer { busy = false }
        let version = store.projects.first { $0.id == projectId }?.version ?? 0
        do {
            let job = try await store.repo.submit(projectId: projectId, quality: quality, idempotencyKey: "ios-\(projectId)-v\(version)-\(quality)")
            if !store.renders.contains(where: { $0.id == job.id }) { store.renders.insert(job, at: 0) }
            router.push(.renderQueue)
        } catch { self.error = error.localizedDescription }
    }
}

struct SceneCard: View {
    @Environment(AppStore.self) private var store
    var scene: Storyboard.Scene
    var cast: [Storyboard.CastMember]

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            StageThumbnail(scene: scene)
                .frame(width: 110, height: 72)
                .clipShape(RoundedRectangle(cornerRadius: 10))
            VStack(alignment: .leading, spacing: 4) {
                Text("\(scene.sequence). \(scene.title)").font(.subheadline.bold())
                Text("\(store.env.catalog.environment(scene.environmentId)?.name ?? scene.environmentId) · \(scene.cameraPresetId.replacingOccurrences(of: "cam_", with: "").humanized) · \(Double(scene.durationMs) / 1000, specifier: "%.1f")s")
                    .font(.caption).foregroundStyle(Theme.textSecondary)
                if let line = scene.dialogue.first {
                    Text("\(cast.first { $0.characterId == line.characterId }?.displayName ?? ""): “\(line.line)”")
                        .font(.caption).lineLimit(2)
                }
                Text(scene.characters.map { $0.actionId.humanized }.joined(separator: " · ")).font(.caption2).foregroundStyle(Theme.brand)
            }
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
    }
}

/// 2D stage thumbnail: environment gradient + characters at their slots.
struct StageThumbnail: View {
    @Environment(AppStore.self) private var store
    var scene: Storyboard.Scene
    static let slotX: [String: Double] = ["far_left": 0.12, "left": 0.3, "center": 0.5, "right": 0.7, "far_right": 0.88]

    var body: some View {
        let env = store.env.catalog.environment(scene.environmentId)
        GeometryReader { geo in
            ZStack(alignment: .bottom) {
                LinearGradient(colors: [Color(hex: env?.skyTop ?? "#4A90D9"), Color(hex: env?.skyBottom ?? "#BFE3FF")], startPoint: .top, endPoint: .bottom)
                Rectangle().fill(Color(hex: env?.ground ?? "#8FA3B8")).frame(height: geo.size.height * 0.28)
                ForEach(scene.characters, id: \.characterId) { sc in
                    if let c = store.character(sc.characterId) {
                        CharacterThumbnail(parts: store.env.assembler.assemble(c.recipe))
                            .frame(width: geo.size.width * 0.3 * sc.scale, height: geo.size.height * 0.78 * sc.scale)
                            .position(x: geo.size.width * (Self.slotX[sc.position] ?? 0.5), y: geo.size.height * 0.56)
                    }
                }
            }
        }
        .accessibilityHidden(true)
    }
}
