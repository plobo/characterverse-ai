import Foundation

/// Client-side recipe validation. Mirrors backend `recipe_issues` so users get instant feedback; the server
/// remains authoritative. Parity is pinned by shared/fixtures/recipe_validation_cases.json.
struct RecipeIssue: Hashable, Sendable {
    var code: String
    var field: String
    var message: String
}

struct RecipeValidator: Sendable {
    let catalog: Catalog

    private static var idPattern: Regex<Substring> { /^[a-z0-9_]+$/ }
    private static var categoryPattern: Regex<Substring> { /^[a-z_]+$/ }
    private static var hexPattern: Regex<Substring> { /^#[0-9A-Fa-f]{6}$/ }
    private static var versionPattern: Regex<Substring> { /^[0-9]+\.[0-9]+$/ }

    func issues(_ r: CharacterRecipe) -> [RecipeIssue] {
        var schema: [RecipeIssue] = []
        func schemaIssue(_ field: String, _ message: String) { schema.append(.init(code: "SCHEMA_VIOLATION", field: field, message: message)) }
        if r.schemaVersion != 1 { schemaIssue("schemaVersion", "Unsupported schema version") }
        if r.name.isEmpty || r.name.count > 40 { schemaIssue("name", "Name must be 1-40 characters") }
        if r.category.wholeMatch(of: Self.categoryPattern) == nil { schemaIssue("category", "Invalid category") }
        if r.baseModelId.wholeMatch(of: Self.idPattern) == nil { schemaIssue("baseModelId", "Invalid id") }
        if r.style.wholeMatch(of: Self.idPattern) == nil { schemaIssue("style", "Invalid style") }
        for (key, value) in [("height", r.proportions.height), ("shoulderWidth", r.proportions.shoulderWidth),
                             ("headScale", r.proportions.headScale)] where !(0.7...1.3).contains(value) {
            schemaIssue("proportions/\(key)", "Must be between 0.7 and 1.3")
        }
        for (key, value) in [("primary", r.palette.primary), ("secondary", r.palette.secondary), ("accent", r.palette.accent)]
        where value.wholeMatch(of: Self.hexPattern) == nil {
            schemaIssue("palette/\(key)", "Colour must be #RRGGBB")
        }
        func checkList(_ list: [String], _ field: String, max: Int, pattern: Regex<Substring>) {
            if list.count > max { schemaIssue(field, "At most \(max) allowed") }
            if Set(list).count != list.count { schemaIssue(field, "Duplicates are not allowed") }
            if list.contains(where: { $0.wholeMatch(of: pattern) == nil }) { schemaIssue(field, "Invalid id") }
        }
        checkList(r.modules, "modules", max: 6, pattern: Self.idPattern)
        checkList(r.powers, "powers", max: 3, pattern: Self.idPattern)
        checkList(r.personalityTraits, "personalityTraits", max: 5, pattern: Self.categoryPattern)
        if r.voiceProfileId.wholeMatch(of: Self.idPattern) == nil { schemaIssue("voiceProfileId", "Invalid id") }
        if r.assetManifestVersion.wholeMatch(of: Self.versionPattern) == nil { schemaIssue("assetManifestVersion", "Invalid version") }
        if !schema.isEmpty { return schema }

        var out: [RecipeIssue] = []
        let m = catalog.manifest
        if !m.categories.contains(r.category) { out.append(.init(code: "UNKNOWN_CATEGORY", field: "category", message: "Unknown category")) }
        if !m.styles.contains(r.style) { out.append(.init(code: "UNKNOWN_STYLE", field: "style", message: "Unknown style")) }
        if r.assetManifestVersion != m.manifestVersion {
            out.append(.init(code: "MANIFEST_VERSION_MISMATCH", field: "assetManifestVersion", message: "Recipe targets another manifest"))
        }
        var rig: String?
        if let base = catalog.baseModel(r.baseModelId) {
            if !catalog.isApproved(licenceId: base.licenceId) {
                out.append(.init(code: "ASSET_NOT_APPROVED", field: "baseModelId", message: "Base model licence is not approved"))
            } else {
                rig = base.rig
                if m.categories.contains(r.category) && !base.categories.contains(r.category) {
                    out.append(.init(code: "CATEGORY_NOT_SUPPORTED", field: "category", message: "\(base.name) does not support \(r.category)"))
                }
            }
        } else {
            out.append(.init(code: "UNKNOWN_ASSET", field: "baseModelId", message: "Unknown base model"))
        }
        var usedSlots: [String: String] = [:]
        for (i, moduleId) in r.modules.enumerated() {
            let field = "modules/\(i)"
            guard let module = catalog.module(moduleId) else {
                out.append(.init(code: "UNKNOWN_ASSET", field: field, message: "Unknown module \(moduleId)")); continue
            }
            guard catalog.isApproved(licenceId: module.licenceId) else {
                out.append(.init(code: "ASSET_NOT_APPROVED", field: field, message: "\(module.name) is not approved")); continue
            }
            if let rig, !module.rigs.contains(rig) {
                out.append(.init(code: "INCOMPATIBLE_MODULE", field: field, message: "\(module.name) does not fit this body"))
            }
            if let other = usedSlots[module.slot] {
                out.append(.init(code: "SLOT_CONFLICT", field: field, message: "\(moduleId) and \(other) share the \(module.slot) slot"))
            } else {
                usedSlots[module.slot] = moduleId
            }
        }
        for (i, powerId) in r.powers.enumerated() {
            if let power = catalog.power(powerId) {
                if let rig, !power.rigs.contains(rig) {
                    out.append(.init(code: "UNSUPPORTED_POWER", field: "powers/\(i)", message: "\(power.name) is not supported by this body"))
                }
            } else {
                out.append(.init(code: "UNKNOWN_ASSET", field: "powers/\(i)", message: "Unknown power"))
            }
        }
        for (i, trait) in r.personalityTraits.enumerated() where !m.personalityTraits.contains(trait) {
            out.append(.init(code: "UNKNOWN_TRAIT", field: "personalityTraits/\(i)", message: "Unknown trait"))
        }
        if let voice = catalog.voice(r.voiceProfileId) {
            if !catalog.isApproved(licenceId: voice.licenceId) {
                out.append(.init(code: "ASSET_NOT_APPROVED", field: "voiceProfileId", message: "Voice is not approved"))
            }
        } else {
            out.append(.init(code: "UNKNOWN_ASSET", field: "voiceProfileId", message: "Unknown voice profile"))
        }
        return out
    }
}
