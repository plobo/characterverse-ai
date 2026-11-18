import SceneKit
import SwiftUI
import UIKit

/// Lightweight native 3D viewer. Builds a SceneKit node tree from the shared procedural parts so iOS, Android
/// and the backend GLB show the same character (ADR 0001). Respects Reduce Motion.
struct CharacterSceneView: UIViewRepresentable {
    var parts: [ResolvedPart]
    var background: String = "#EDE9FF"
    var autoRotate: Bool = true
    var allowsInteraction: Bool = true
    var accessibilityName: String = "Character preview"
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func makeUIView(context: Context) -> SCNView {
        let view = SCNView()
        view.antialiasingMode = .multisampling4X
        view.autoenablesDefaultLighting = false
        view.allowsCameraControl = allowsInteraction
        view.isAccessibilityElement = true
        view.scene = SCNScene()
        return view
    }

    func updateUIView(_ view: SCNView, context: Context) {
        view.backgroundColor = UIColor(hex: background)
        view.accessibilityLabel = accessibilityName
        view.accessibilityHint = allowsInteraction ? "Drag to rotate, pinch to zoom" : nil
        let key = parts.map { "\($0.id)\($0.position)\($0.size)\($0.color)" }.joined()
        guard context.coordinator.lastKey != key || context.coordinator.lastMotion != reduceMotion else { return }
        context.coordinator.lastKey = key
        context.coordinator.lastMotion = reduceMotion
        view.scene = PreviewSceneBuilder.scene(for: parts, rotate: autoRotate && !reduceMotion)
        view.pointOfView = view.scene?.rootNode.childNode(withName: "camera", recursively: false)
    }

    func makeCoordinator() -> Coordinator { Coordinator() }
    final class Coordinator { var lastKey = ""; var lastMotion = false }
}

enum PreviewSceneBuilder {
    static func node(for part: ResolvedPart) -> SCNNode {
        let s = part.size.map { CGFloat($0) }
        let geometry: SCNGeometry
        switch part.shape {
        case "box": geometry = SCNBox(width: s[0], height: s[1], length: s[2], chamferRadius: min(s[0], s[1], s[2]) * 0.18)
        case "cylinder": geometry = SCNCylinder(radius: 0.5, height: 1)
        case "cone": geometry = SCNCone(topRadius: 0, bottomRadius: 0.5, height: 1)
        case "capsule": geometry = SCNCapsule(capRadius: 0.5, height: max(1, s[1] / max(s[0], 0.001)))
        default: geometry = SCNSphere(radius: 0.5)
        }
        let material = SCNMaterial()
        material.lightingModel = .physicallyBased
        material.diffuse.contents = UIColor(hex: part.color)
        material.roughness.contents = 0.55
        material.metalness.contents = 0.05
        geometry.materials = [material]
        let node = SCNNode(geometry: geometry)
        node.name = part.id
        node.position = SCNVector3(part.position[0], part.position[1], part.position[2])
        switch part.shape {
        case "box": break
        case "capsule": node.scale = SCNVector3(s[0], s[1] / max(1, s[1] / max(s[0], 0.001)), s[2])
        default: node.scale = SCNVector3(s[0], s[1], s[2])
        }
        return node
    }

    static func scene(for parts: [ResolvedPart], rotate: Bool) -> SCNScene {
        let scene = SCNScene()
        let character = SCNNode()
        character.name = "character"
        parts.forEach { character.addChildNode(node(for: $0)) }
        scene.rootNode.addChildNode(character)
        if rotate { character.runAction(.repeatForever(.rotateBy(x: 0, y: .pi * 2, z: 0, duration: 14))) }

        let top = parts.map { $0.position[1] + $0.size[1] / 2 }.max() ?? 2
        let floor = SCNNode(geometry: SCNCylinder(radius: 1.1, height: 0.04))
        floor.geometry?.firstMaterial?.diffuse.contents = UIColor.black.withAlphaComponent(0.08)
        floor.position = SCNVector3(0, -0.02, 0)
        scene.rootNode.addChildNode(floor)

        let camera = SCNNode()
        camera.name = "camera"
        camera.camera = SCNCamera()
        camera.camera?.fieldOfView = 32
        camera.position = SCNVector3(0, top * 0.55, Double(top) * 2.35 + 1.2)
        camera.look(at: SCNVector3(0, top * 0.48, 0))
        scene.rootNode.addChildNode(camera)

        let key = SCNNode(); key.light = SCNLight(); key.light?.type = .directional; key.light?.intensity = 900
        key.eulerAngles = SCNVector3(-0.7, 0.5, 0)
        let fill = SCNNode(); fill.light = SCNLight(); fill.light?.type = .ambient; fill.light?.intensity = 450
        let rim = SCNNode(); rim.light = SCNLight(); rim.light?.type = .directional; rim.light?.intensity = 350
        rim.eulerAngles = SCNVector3(-0.3, .pi, 0)
        [key, fill, rim].forEach(scene.rootNode.addChildNode)
        return scene
    }
}

/// Fast 2D thumbnail of the same parts (lists, cards) without spinning up a 3D view per row.
struct CharacterThumbnail: View {
    var parts: [ResolvedPart]
    var body: some View {
        Canvas { ctx, size in
            guard !parts.isEmpty else { return }
            let top = parts.map { $0.position[1] + $0.size[1] / 2 }.max() ?? 2
            let width = (parts.map { abs($0.position[0]) + $0.size[0] / 2 }.max() ?? 1) * 2
            let scale = min(size.height * 0.84 / top, size.width * 0.84 / width)
            let origin = CGPoint(x: size.width / 2, y: size.height * 0.93)
            for p in parts.sorted(by: { $0.position[2] - $0.size[2] / 2 < $1.position[2] - $1.size[2] / 2 }) {
                let w = p.size[0] * scale, h = p.size[1] * scale
                let rect = CGRect(x: origin.x + p.position[0] * scale - w / 2, y: origin.y - p.position[1] * scale - h / 2, width: w, height: h)
                let color = Color(hex: p.color)
                let path: Path
                switch p.shape {
                case "sphere": path = Path(ellipseIn: rect)
                case "capsule": path = Path(roundedRect: rect, cornerRadius: min(w, h) / 2)
                case "cone": path = Path { $0.move(to: CGPoint(x: rect.minX, y: rect.maxY)); $0.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY)); $0.addLine(to: CGPoint(x: rect.midX, y: rect.minY)); $0.closeSubpath() }
                default: path = Path(roundedRect: rect, cornerRadius: min(w, h) * 0.18)
                }
                ctx.fill(path, with: .color(color))
                ctx.stroke(path, with: .color(.black.opacity(0.18)), lineWidth: 1)
            }
        }
        .accessibilityHidden(true)
    }
}
