import Foundation

/// Approved asset catalogue (shared/asset-manifests/asset_manifest_v1.json + procedural_parts_v1.json).
struct AssetManifest: Codable, Sendable {
    struct Licence: Codable, Sendable { var id: String; var name: String; var commercialUse: Bool; var reviewStatus: String }
    struct BaseModel: Codable, Sendable, Identifiable { var id: String; var name: String; var rig: String; var categories: [String]; var licenceId: String }
    struct Module: Codable, Sendable, Identifiable { var id: String; var name: String; var slot: String; var rigs: [String]; var priority: Int; var licenceId: String }
    struct Power: Codable, Sendable, Identifiable { var id: String; var name: String; var rigs: [String]; var effectColor: String }
    struct Voice: Codable, Sendable, Identifiable { var id: String; var name: String; var provider: String; var baseHz: Double; var licenceId: String }
    struct Clip: Codable, Sendable, Identifiable { var id: String; var rigs: [String]; var motion: String; var licenceId: String }
    struct Environment: Codable, Sendable, Identifiable { var id: String; var name: String; var skyTop: String; var skyBottom: String; var ground: String; var licenceId: String }
    struct Preset: Codable, Sendable, Identifiable { var id: String; var licenceId: String }
    struct Music: Codable, Sendable, Identifiable { var id: String; var bpm: Int; var scale: String; var licenceId: String }
    struct StoryTemplate: Codable, Sendable, Identifiable { var id: String; var name: String; var genre: String; var tone: String }
    struct CharacterTemplate: Codable, Sendable, Identifiable { var id: String; var featured: Bool; var recipe: CharacterRecipe }

    var manifestVersion: String
    var licences: [Licence]
    var categories: [String]
    var styles: [String]
    var rigs: [String]
    var baseModels: [BaseModel]
    var modules: [Module]
    var powers: [Power]
    var personalityTraits: [String]
    var voiceProfiles: [Voice]
    var animationClips: [Clip]
    var environments: [Environment]
    var cameraPresets: [Preset]
    var lightingPresets: [Preset]
    var soundEffects: [Preset]
    var musicCues: [Music]
    var storyTemplates: [StoryTemplate]
    var characterTemplates: [CharacterTemplate]
}

struct ProceduralParts: Codable, Sendable {
    struct Part: Codable, Sendable {
        var id: String
        var shape: String
        var group: String?
        var position: [Double]
        var size: [Double]
        var color: String
    }

    struct BaseModel: Codable, Sendable {
        var skin: String
        var headCenter: [Double]
        var anchors: [String: [Double]]
        var parts: [Part]
    }

    struct Module: Codable, Sendable {
        var group: String
        var mirrorX: Bool
        var parts: [Part]
    }

    var partsVersion: String
    var baseModels: [String: BaseModel]
    var modules: [String: Module]
}

/// Read-only lookups with the licence gate applied: an asset is usable only when its licence is approved for
/// commercial use (mirrors backend `Catalog.approved`).
struct Catalog: Sendable {
    let manifest: AssetManifest
    let parts: ProceduralParts
    private let approvedLicences: Set<String>

    init(manifest: AssetManifest, parts: ProceduralParts) {
        self.manifest = manifest
        self.parts = parts
        approvedLicences = Set(manifest.licences.filter { $0.reviewStatus == "approved" && $0.commercialUse }.map(\.id))
    }

    static func bundled(_ bundle: Bundle = .main) throws -> Catalog {
        func load<T: Decodable>(_ name: String) throws -> T {
            guard let url = bundle.url(forResource: name, withExtension: "json") else {
                throw CocoaError(.fileNoSuchFile, userInfo: [NSFilePathErrorKey: name])
            }
            return try JSONDecoder().decode(T.self, from: Data(contentsOf: url))
        }
        return Catalog(manifest: try load("asset_manifest_v1"), parts: try load("procedural_parts_v1"))
    }

    func isApproved(licenceId: String) -> Bool { approvedLicences.contains(licenceId) }
    func baseModel(_ id: String) -> AssetManifest.BaseModel? { manifest.baseModels.first { $0.id == id } }
    func module(_ id: String) -> AssetManifest.Module? { manifest.modules.first { $0.id == id } }
    func power(_ id: String) -> AssetManifest.Power? { manifest.powers.first { $0.id == id } }
    func voice(_ id: String) -> AssetManifest.Voice? { manifest.voiceProfiles.first { $0.id == id } }
    func clip(_ id: String) -> AssetManifest.Clip? { manifest.animationClips.first { $0.id == id } }
    func environment(_ id: String) -> AssetManifest.Environment? { manifest.environments.first { $0.id == id } }
    func rig(of baseModelId: String) -> String? { baseModel(baseModelId)?.rig }

    var approvedBaseModels: [AssetManifest.BaseModel] { manifest.baseModels.filter { isApproved(licenceId: $0.licenceId) } }
    var approvedModules: [AssetManifest.Module] { manifest.modules.filter { isApproved(licenceId: $0.licenceId) } }
    var approvedEnvironments: [AssetManifest.Environment] { manifest.environments.filter { isApproved(licenceId: $0.licenceId) } }
    var approvedVoices: [AssetManifest.Voice] { manifest.voiceProfiles.filter { isApproved(licenceId: $0.licenceId) } }
    func clips(for rig: String) -> [AssetManifest.Clip] {
        manifest.animationClips.filter { $0.rigs.contains(rig) && isApproved(licenceId: $0.licenceId) }
    }
}
