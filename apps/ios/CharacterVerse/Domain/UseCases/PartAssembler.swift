import Foundation

/// Deterministic recipe -> primitive parts resolution. Swift port of backend `assemble_parts`;
/// parity pinned by shared/fixtures/assembly_golden.json.
struct ResolvedPart: Hashable, Sendable, Identifiable {
    var id: String
    var shape: String
    var position: [Double]
    var size: [Double]
    var color: String
}

struct PartAssembler: Sendable {
    let catalog: Catalog

    func resolveColor(_ key: String, palette: CharacterRecipe.Palette, skin: String) -> String {
        switch key {
        case "primary": palette.primary.uppercased()
        case "secondary": palette.secondary.uppercased()
        case "accent": palette.accent.uppercased()
        case "skin": skin.uppercased()
        default: key.uppercased()
        }
    }

    func assemble(_ recipe: CharacterRecipe) -> [ResolvedPart] {
        guard let base = catalog.parts.baseModels[recipe.baseModelId] else { return [] }
        typealias Raw = (id: String, shape: String, group: String, pos: [Double], size: [Double], color: String)
        var raw: [Raw] = base.parts.map { ($0.id, $0.shape, $0.group ?? "body", $0.position, $0.size, $0.color) }
        for moduleId in recipe.modules {
            guard let def = catalog.parts.modules[moduleId], let slot = catalog.module(moduleId)?.slot,
                  let anchor = base.anchors[slot] else { continue }
            for p in def.parts {
                let pos = (0..<3).map { anchor[$0] + p.position[$0] }
                let pid = "\(moduleId).\(p.id)"
                if def.mirrorX {
                    raw.append((pid + ".l", p.shape, def.group, [-pos[0], pos[1], pos[2]], p.size, p.color))
                    raw.append((pid + ".r", p.shape, def.group, pos, p.size, p.color))
                } else {
                    raw.append((pid, p.shape, def.group, pos, p.size, p.color))
                }
            }
        }
        let h = recipe.proportions.height, w = recipe.proportions.shoulderWidth, k = recipe.proportions.headScale
        let c = base.headCenter
        return raw.map { part in
            let pos: [Double], size: [Double]
            if part.group == "head" {
                pos = [c[0] * w + (part.pos[0] - c[0]) * k, c[1] * h + (part.pos[1] - c[1]) * k, c[2] + (part.pos[2] - c[2]) * k]
                size = part.size.map { $0 * k }
            } else {
                pos = [part.pos[0] * w, part.pos[1] * h, part.pos[2]]
                size = [part.size[0] * w, part.size[1] * h, part.size[2]]
            }
            return ResolvedPart(id: part.id, shape: part.shape, position: pos, size: size,
                                color: resolveColor(part.color, palette: recipe.palette, skin: base.skin))
        }
    }
}
