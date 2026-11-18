import Foundation

/// Deterministic fusion resolver — a Swift port of backend `app/services/mixer.py`.
/// Pinned by shared/fixtures/mix_golden.json; see docs/ARCHITECTURE.md#fusion for the rules.
enum MixDimension: String, CaseIterable, Sendable, Identifiable {
    case appearance, powers, personality, voice
    var id: String { rawValue }
    var title: String { rawValue.capitalized }
}

struct FusionError: Error, Equatable { var message: String }

struct FusionResolver: Sendable {
    let catalog: Catalog
    static let maxModules = 6, maxPowers = 3, maxTraits = 5

    static func roundHalfUp(_ x: Double) -> Int { Int((x + 0.5).rounded(.down)) }
    static func round2(_ x: Double) -> Double { (x * 100 + 0.5).rounded(.down) / 100 }

    static func blendHex(_ colors: [String], _ weights: [Double]) -> String {
        var channels: [Int] = []
        for ch in 0..<3 {
            var total = 0.0
            for (color, w) in zip(colors, weights) {
                let hex = color.dropFirst()
                let start = hex.index(hex.startIndex, offsetBy: ch * 2)
                total += w * Double(Int(hex[start..<hex.index(start, offsetBy: 2)], radix: 16) ?? 0)
            }
            channels.append(min(255, max(0, roundHalfUp(total))))
        }
        return String(format: "#%02X%02X%02X", channels[0], channels[1], channels[2])
    }

    static func defaultName(namesByRank: [String], sourceNames: [String]) -> String {
        let first = namesByRank[0].split(separator: " ").first.map(String.init) ?? namesByRank[0]
        let second = namesByRank.count > 1 ? (namesByRank[1].split(separator: " ").last.map(String.init) ?? "Fusion") : "Fusion"
        var name = first != second ? "\(first) \(second)" : "\(first) Fusion"
        if sourceNames.contains(name) { name += " Fusion" }
        return String(name.prefix(40)).trimmingCharacters(in: .whitespaces)
    }

    func resolve(sources: [(id: String, recipe: CharacterRecipe)], weights: [String: Double]?,
                 dimensions: Set<MixDimension>, name: String? = nil) throws -> MixResult {
        guard (2...3).contains(sources.count) else { throw FusionError(message: "Select two or three characters to mix") }
        guard !dimensions.isEmpty else { throw FusionError(message: "Choose at least one mix dimension") }
        let ids = sources.map(\.id)
        guard Set(ids).count == ids.count else { throw FusionError(message: "Each source character can only be used once") }
        let dims = MixDimension.allCases.filter { dimensions.contains($0) }
        let raw = ids.map { weights?[$0] ?? 1.0 }
        var total = 0.0
        for w in raw { total += w }
        guard raw.allSatisfy({ $0 >= 0 }), total > 0 else { throw FusionError(message: "Weights must be non-negative and not all zero") }
        let w = raw.map { $0 / total }
        let order = sources.indices.sorted { w[$0] != w[$1] ? w[$0] > w[$1] : $0 < $1 }
        let recipes = sources.map(\.recipe)
        let dom = recipes[order[0]]
        let rig = catalog.rig(of: dom.baseModelId)
        var omitted: [MixResult.Omitted] = []
        var warnings: [String] = []
        if Set(recipes.map { catalog.rig(of: $0.baseModelId) ?? "" }).count > 1 { warnings.append("RIG_MISMATCH") }

        var proportions = dom.proportions
        var palette = CharacterRecipe.Palette(primary: dom.palette.primary.uppercased(), secondary: dom.palette.secondary.uppercased(),
                                              accent: dom.palette.accent.uppercased())
        var modulePool = dom.modules
        if dims.contains(.appearance) {
            func blend(_ key: KeyPath<CharacterRecipe.Proportions, Double>) -> Double {
                var sum = 0.0
                for i in recipes.indices { sum += w[i] * recipes[i].proportions[keyPath: key] }
                return min(1.3, max(0.7, Self.round2(sum)))
            }
            proportions = .init(height: blend(\.height), shoulderWidth: blend(\.shoulderWidth), headScale: blend(\.headScale))
            palette = .init(primary: Self.blendHex(recipes.map(\.palette.primary), w),
                            secondary: Self.blendHex(recipes.map(\.palette.secondary), w),
                            accent: Self.blendHex(recipes.map(\.palette.accent), w))
            modulePool = order.flatMap { recipes[$0].modules }
        }
        func wasOmitted(_ id: String) -> Bool { omitted.contains { $0.id == id } }

        var modules: [String] = []
        var slots: Set<String> = []
        for moduleId in modulePool where !modules.contains(moduleId) && !wasOmitted(moduleId) {
            let module = catalog.module(moduleId)
            var reason: String?
            if module == nil || !catalog.isApproved(licenceId: module!.licenceId) { reason = "not_approved" }
            else if let rig, !module!.rigs.contains(rig) { reason = "incompatible_rig" }
            else if slots.contains(module!.slot) { reason = "slot_taken" }
            else if modules.count >= Self.maxModules { reason = "limit_reached" }
            if let reason { omitted.append(.init(id: moduleId, kind: "module", reason: reason)); continue }
            modules.append(moduleId)
            slots.insert(module!.slot)
        }

        let powerPool = dims.contains(.powers) ? order.flatMap { recipes[$0].powers } : dom.powers
        var powers: [String] = []
        for powerId in powerPool where !powers.contains(powerId) && !wasOmitted(powerId) {
            let power = catalog.power(powerId)
            var reason: String?
            if power == nil { reason = "not_approved" }
            else if let rig, !power!.rigs.contains(rig) { reason = "unsupported_by_rig" }
            else if powers.count >= Self.maxPowers { reason = "limit_reached" }
            if let reason { omitted.append(.init(id: powerId, kind: "power", reason: reason)); continue }
            powers.append(powerId)
        }

        let traitPool = dims.contains(.personality) ? order.flatMap { recipes[$0].personalityTraits } : dom.personalityTraits
        var traits: [String] = []
        for trait in traitPool where !traits.contains(trait) && !wasOmitted(trait) {
            if traits.count >= Self.maxTraits { omitted.append(.init(id: trait, kind: "trait", reason: "limit_reached")); continue }
            traits.append(trait)
        }
        let voice = dims.contains(.voice) ? recipes[order[1]].voiceProfileId : dom.voiceProfileId
        if !omitted.isEmpty { warnings.append("TRAITS_OMITTED") }

        let finalName = String((name ?? Self.defaultName(namesByRank: order.map { recipes[$0].name }, sourceNames: recipes.map(\.name))).prefix(40))
        let recipe = CharacterRecipe(schemaVersion: 1, name: finalName, category: dom.category, baseModelId: dom.baseModelId,
                                     style: dom.style, proportions: proportions, palette: palette, modules: modules, powers: powers,
                                     personalityTraits: traits, voiceProfileId: voice,
                                     assetManifestVersion: catalog.manifest.manifestVersion)
        let lineage = ids.indices.map {
            MixResult.LineageEntry(sourceCharacterId: ids[$0], weight: (w[$0] * 10000).rounded() / 10000, dimensions: dims.map(\.rawValue))
        }
        return MixResult(recipe: recipe, lineage: lineage, omitted: omitted, warningCodes: warnings, dominantSourceId: ids[order[0]])
    }
}
