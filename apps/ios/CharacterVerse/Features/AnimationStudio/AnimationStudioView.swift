import SceneKit
import SwiftUI

/// Scene editor: environment, placement, animation clips, camera/lighting presets, timing and dialogue.
struct AnimationStudioView: View {
    @Environment(AppStore.self) private var store
    @Environment(\.dismiss) private var dismiss
    var projectId: String
    var sceneId: String
    @State private var scene: Storyboard.Scene?
    @State private var busy = false
    @State private var error: String?
    @State private var newLine = ""

    private var project: Project? { store.projects.first { $0.id == projectId } }

    var body: some View {
        Group {
            if let binding = Binding($scene) { editor(binding) } else { ProgressView() }
        }
        .navigationTitle(scene?.title ?? "Scene")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear { if scene == nil { scene = project?.storyboard?.scenes.first { $0.sceneId == sceneId } } }
        .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Save") { Task { await save() } }.disabled(busy) } }
        .overlay { if busy { LoadingOverlay(label: "Validating scene…") } }
    }

    private func editor(_ s: Binding<Storyboard.Scene>) -> some View {
        let catalog = store.env.catalog
        return VStack(spacing: 0) {
            StageSceneView(scene: s.wrappedValue).frame(height: 230)
            timeline(s.wrappedValue)
            Form {
                if let error { Section { ErrorBanner(message: error) } }
                Section("Scene") {
                    TextField("Title", text: s.title)
                    Stepper(value: s.durationMs, in: 2000...15000, step: 500) {
                        Text("Duration \(Double(s.wrappedValue.durationMs) / 1000, specifier: "%.1f")s")
                    }
                    Picker("Environment", selection: s.environmentId) { ForEach(catalog.approvedEnvironments) { Text($0.name).tag($0.id) } }
                    Picker("Camera", selection: s.cameraPresetId) {
                        ForEach(catalog.manifest.cameraPresets) { Text($0.id.replacingOccurrences(of: "cam_", with: "").humanized).tag($0.id) }
                    }
                    Picker("Lighting", selection: s.lightingPresetId) {
                        ForEach(catalog.manifest.lightingPresets) { Text($0.id.replacingOccurrences(of: "light_", with: "").humanized).tag($0.id) }
                    }
                    Picker("Transition in", selection: s.transition) { Text("Cut").tag("cut"); Text("Fade").tag("fade") }.pickerStyle(.segmented)
                }
                ForEach(s.characters) { $sc in
                    Section(store.character(sc.characterId)?.name ?? "Character") {
                        let rig = store.character(sc.characterId).flatMap { catalog.rig(of: $0.recipe.baseModelId) } ?? "humanoid_v1"
                        Picker("Action clip", selection: $sc.actionId) { ForEach(catalog.clips(for: rig)) { Text($0.id.humanized).tag($0.id) } }
                        Picker("Position", selection: $sc.position) {
                            ForEach(["far_left", "left", "center", "right", "far_right"], id: \.self) { Text($0.humanized).tag($0) }
                        }
                        VStack(alignment: .leading) {
                            Text("Scale \(sc.scale, specifier: "%.2f")")
                            Slider(value: $sc.scale, in: 0.5...1.5, step: 0.05).accessibilityLabel("Character scale")
                        }
                    }
                }
                Section("Dialogue & audio") {
                    ForEach(s.dialogue) { $d in
                        VStack(alignment: .leading) {
                            Text(store.character(d.characterId)?.name ?? "").font(.caption.bold())
                            TextField("Line", text: $d.line, axis: .vertical)
                            Stepper(value: $d.startMs, in: 0...max(0, s.wrappedValue.durationMs - 500), step: 250) {
                                Text("Starts at \(Double(d.startMs) / 1000, specifier: "%.2f")s").font(.caption)
                            }
                        }
                    }
                    .onDelete { s.dialogue.wrappedValue.remove(atOffsets: $0) }
                    HStack {
                        TextField("Add a line…", text: $newLine)
                        Button("Add") {
                            guard let speaker = s.wrappedValue.characters.first?.characterId, !newLine.isEmpty else { return }
                            s.dialogue.wrappedValue.append(.init(characterId: speaker, line: newLine, startMs: min(1000, s.wrappedValue.durationMs - 500)))
                            newLine = ""
                        }
                    }
                    FlowLayout {
                        ForEach(catalog.manifest.soundEffects) { fx in
                            let on = s.wrappedValue.soundEffectIds.contains(fx.id)
                            Button {
                                if on { s.soundEffectIds.wrappedValue.removeAll { $0 == fx.id } }
                                else if s.wrappedValue.soundEffectIds.count < 4 { s.soundEffectIds.wrappedValue.append(fx.id) }
                            } label: { Chip(label: fx.id.replacingOccurrences(of: "sfx_", with: "").humanized, selected: on, color: Theme.brandSecondary) }
                                .buttonStyle(.plain)
                        }
                    }
                }
            }
        }
    }

    private func timeline(_ s: Storyboard.Scene) -> some View {
        let scenes = project?.storyboard?.scenes ?? []
        let total = max(1, scenes.reduce(0) { $0 + $1.durationMs })
        return GeometryReader { geo in
            HStack(spacing: 2) {
                ForEach(scenes) { sc in
                    RoundedRectangle(cornerRadius: 4)
                        .fill(sc.sceneId == s.sceneId ? Theme.brand : Theme.brand.opacity(0.25))
                        .frame(width: max(6, geo.size.width * Double(sc.sceneId == s.sceneId ? s.durationMs : sc.durationMs) / Double(total) - 2))
                        .overlay(Text("\(sc.sequence)").font(.caption2.bold()).foregroundStyle(.white))
                }
            }
        }
        .frame(height: 22)
        .padding(.horizontal, 12).padding(.vertical, 6)
        .accessibilityLabel("Timeline, scene \(s.sequence) of \(scenes.count)")
    }

    private func save() async {
        guard let scene, var doc = project?.storyboard, let i = doc.scenes.firstIndex(where: { $0.sceneId == sceneId }) else { return }
        doc.scenes[i] = scene
        busy = true
        defer { busy = false }
        do {
            let p = try await store.repo.saveStoryboard(projectId: projectId, doc)
            if let idx = store.projects.firstIndex(where: { $0.id == projectId }) { store.projects[idx] = p }
            dismiss()
        } catch let e as APIError {
            if case .server(_, _, let message, let details, _) = e { error = ([message] + details.prefix(3).map { "• \($0.message)" }).joined(separator: "\n") }
            else { error = e.localizedDescription }
        } catch { self.error = error.localizedDescription }
    }
}

extension Storyboard.SceneCharacter: Identifiable { var id: String { characterId } }

/// 3D stage preview: all scene characters placed at their slots in front of the environment colours.
struct StageSceneView: UIViewRepresentable {
    @Environment(AppStore.self) private var store
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    var scene: Storyboard.Scene

    func makeUIView(context: Context) -> SCNView {
        let v = SCNView()
        v.antialiasingMode = .multisampling4X
        v.allowsCameraControl = true
        v.isAccessibilityElement = true
        return v
    }

    func updateUIView(_ view: SCNView, context: Context) {
        let env = store.env.catalog.environment(scene.environmentId)
        view.backgroundColor = UIColor(hex: env?.skyBottom ?? "#BFE3FF")
        view.accessibilityLabel = "Scene preview in \(env?.name ?? "environment") with \(scene.characters.count) characters"
        let root = SCNScene()
        let ground = SCNNode(geometry: SCNBox(width: 14, height: 0.05, length: 6, chamferRadius: 0))
        ground.geometry?.firstMaterial?.diffuse.contents = UIColor(hex: env?.ground ?? "#8FA3B8")
        ground.position = SCNVector3(0, -0.03, 0)
        root.rootNode.addChildNode(ground)
        let backdrop = SCNNode(geometry: SCNPlane(width: 16, height: 8))
        backdrop.geometry?.firstMaterial?.diffuse.contents = UIColor(hex: env?.skyTop ?? "#4A90D9")
        backdrop.position = SCNVector3(0, 3.5, -3)
        root.rootNode.addChildNode(backdrop)
        for sc in scene.characters {
            guard let c = store.character(sc.characterId) else { continue }
            let node = SCNNode()
            store.env.assembler.assemble(c.recipe).forEach { node.addChildNode(PreviewSceneBuilder.node(for: $0)) }
            node.position = SCNVector3(((StageThumbnail.slotX[sc.position] ?? 0.5) - 0.5) * 6, 0, 0)
            node.scale = SCNVector3(sc.scale, sc.scale, sc.scale)
            if !reduceMotion, let motion = store.env.catalog.clip(sc.actionId)?.motion { node.runAction(Self.action(for: motion)) }
            root.rootNode.addChildNode(node)
        }
        let zoom: Double = (["cam_wide": 0.8, "cam_medium": 1.0, "cam_closeup": 1.45, "cam_low_hero": 1.15, "cam_orbit": 0.95] as [String: Double])[scene.cameraPresetId] ?? 1
        let cam = SCNNode(); cam.camera = SCNCamera(); cam.camera?.fieldOfView = 40
        cam.position = SCNVector3(0.0, scene.cameraPresetId == "cam_low_hero" ? 0.5 : 1.3, 7.5 / zoom)
        cam.look(at: SCNVector3(0, 1.0, 0))
        root.rootNode.addChildNode(cam)
        let light = SCNNode(); light.light = SCNLight(); light.light?.type = .directional; light.light?.intensity = 1000
        light.eulerAngles = SCNVector3(-0.8, 0.4, 0)
        let tint = ["light_sunset": "#FFD1A6", "light_night_neon": "#C7B8FF"][scene.lightingPresetId] ?? "#FFFFFF"
        light.light?.color = UIColor(hex: tint)
        let ambient = SCNNode(); ambient.light = SCNLight(); ambient.light?.type = .ambient; ambient.light?.intensity = 500
        [light, ambient].forEach(root.rootNode.addChildNode)
        view.scene = root
        view.pointOfView = cam
    }

    static func action(for motion: String) -> SCNAction {
        switch motion {
        case "hop": .repeatForever(.sequence([.moveBy(x: 0, y: 0.4, z: 0, duration: 0.3), .moveBy(x: 0, y: -0.4, z: 0, duration: 0.3), .wait(duration: 0.3)]))
        case "spin": .repeatForever(.rotateBy(x: 0, y: .pi * 2, z: 0, duration: 1.6))
        case "float", "soar": .repeatForever(.sequence([.moveBy(x: 0, y: 0.25, z: 0, duration: 0.8), .moveBy(x: 0, y: -0.25, z: 0, duration: 0.8)]))
        case "stride", "dash": .repeatForever(.sequence([.moveBy(x: 0.6, y: 0, z: 0, duration: 1), .moveBy(x: -0.6, y: 0, z: 0, duration: 1)]))
        case "sway", "shake", "lunge": .repeatForever(.sequence([.rotateBy(x: 0, y: 0, z: 0.12, duration: 0.25), .rotateBy(x: 0, y: 0, z: -0.12, duration: 0.25)]))
        default: .repeatForever(.sequence([.moveBy(x: 0, y: 0.05, z: 0, duration: 0.6), .moveBy(x: 0, y: -0.05, z: 0, duration: 0.6)]))
        }
    }
}
