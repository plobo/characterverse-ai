import Foundation
import Observation

/// Dependency container. Built once at launch; views receive it through the SwiftUI environment.
@MainActor
final class AppEnvironment {
    let catalog: Catalog
    let validator: RecipeValidator
    let assembler: PartAssembler
    let fusion: FusionResolver
    let tokens = TokenStore()
    let api: APIClient
    let remote: RemoteRepository
    let drafts: DraftStore
    let assetCache = AssetCache()
    let analytics = Analytics()

    init(baseURL: URL = AppEnvironment.defaultBaseURL, inMemoryDrafts: Bool = false) {
        catalog = (try? Catalog.bundled()) ?? Catalog(manifest: .empty, parts: .empty)
        validator = RecipeValidator(catalog: catalog)
        assembler = PartAssembler(catalog: catalog)
        fusion = FusionResolver(catalog: catalog)
        api = APIClient(baseURL: baseURL, tokens: tokens)
        remote = RemoteRepository(api: api, tokens: tokens)
        drafts = DraftStore(inMemory: inMemoryDrafts)
    }

    static var defaultBaseURL: URL {
        if let override = ProcessInfo.processInfo.environment["CV_API_BASE_URL"], let url = URL(string: override) { return url }
        return URL(string: Bundle.main.object(forInfoDictionaryKey: "CVAPIBaseURL") as? String ?? "http://localhost:8000")!
    }
}

extension AssetManifest {
    static let empty = AssetManifest(manifestVersion: "1.0", licences: [], categories: [], styles: [], rigs: [], baseModels: [],
                                     modules: [], powers: [], personalityTraits: [], voiceProfiles: [], animationClips: [],
                                     environments: [], cameraPresets: [], lightingPresets: [], soundEffects: [], musicCues: [],
                                     storyTemplates: [], characterTemplates: [])
}

extension ProceduralParts {
    static let empty = ProceduralParts(partsVersion: "1.0", baseModels: [:], modules: [:])
}
