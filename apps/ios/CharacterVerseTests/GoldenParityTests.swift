import Foundation
import Testing
@testable import CharacterVerse

/// Cross-platform parity: the same golden fixtures are asserted by the backend, iOS and Android test suites.
enum Fixtures {
    static let bundle = Bundle(for: BundleToken.self)
    final class BundleToken {}

    static func data(_ name: String) throws -> Data {
        let url = try #require(bundle.url(forResource: name, withExtension: "json"), "missing fixture \(name)")
        return try Data(contentsOf: url)
    }

    static func catalog() throws -> Catalog {
        Catalog(manifest: try JSONDecoder().decode(AssetManifest.self, from: data("asset_manifest_v1")),
                parts: try JSONDecoder().decode(ProceduralParts.self, from: data("procedural_parts_v1")))
    }
}

struct RecipeCase: Decodable { var name: String; var recipe: CharacterRecipe; var expectedCodes: [String] }
struct RecipeCases: Decodable { var cases: [RecipeCase] }

struct MixCase: Decodable {
    struct Source: Decodable { var id: String; var recipe: CharacterRecipe }
    struct Expected: Decodable {
        var recipe: CharacterRecipe
        var omitted: [OmittedDTO]
        var lineage: [MixLineageDTO]
        var dominantSourceId: String
        var warningCodes: [String]
    }
    var name: String; var sources: [Source]; var weights: [String: Double]?; var dimensions: [String]; var expected: Expected
}
struct MixCases: Decodable { var cases: [MixCase] }

struct AssemblyCase: Decodable {
    struct Part: Decodable { var id: String; var shape: String; var position: [Double]; var size: [Double]; var color: String }
    var templateId: String; var recipe: CharacterRecipe; var parts: [Part]
}
struct AssemblyCases: Decodable { var tolerance: Double; var cases: [AssemblyCase] }

@Suite("Golden parity with backend")
struct GoldenParityTests {
    @Test func recipeValidationMatchesBackend() throws {
        let validator = RecipeValidator(catalog: try Fixtures.catalog())
        let cases = try JSONDecoder().decode(RecipeCases.self, from: Fixtures.data("recipe_validation_cases")).cases
        #expect(cases.count >= 15)
        for c in cases {
            let codes = Set(validator.issues(c.recipe).map(\.code))
            #expect(codes == Set(c.expectedCodes), "case \(c.name)")
        }
    }

    @Test func fusionMatchesBackend() throws {
        let resolver = FusionResolver(catalog: try Fixtures.catalog())
        let cases = try JSONDecoder().decode(MixCases.self, from: Fixtures.data("mix_golden")).cases
        #expect(!cases.isEmpty)
        for c in cases {
            let dims = c.dimensions.contains("all") ? Set(MixDimension.allCases) : Set(c.dimensions.compactMap(MixDimension.init(rawValue:)))
            let r = try resolver.resolve(sources: c.sources.map { ($0.id, $0.recipe) }, weights: c.weights, dimensions: dims)
            #expect(r.recipe == c.expected.recipe, "recipe \(c.name)")
            #expect(r.omitted.map { "\($0.id)|\($0.kind)|\($0.reason)" } == c.expected.omitted.map { "\($0.id)|\($0.kind)|\($0.reason)" }, "omitted \(c.name)")
            #expect(r.dominantSourceId == c.expected.dominantSourceId)
            #expect(r.warningCodes == c.expected.warningCodes, "warnings \(c.name)")
            #expect(r.lineage.map(\.weight) == c.expected.lineage.map(\.weight), "lineage \(c.name)")
        }
    }

    @Test func assemblyMatchesBackend() throws {
        let assembler = PartAssembler(catalog: try Fixtures.catalog())
        let golden = try JSONDecoder().decode(AssemblyCases.self, from: Fixtures.data("assembly_golden"))
        for c in golden.cases {
            let parts = assembler.assemble(c.recipe)
            #expect(parts.map(\.id) == c.parts.map(\.id), "ids \(c.templateId)")
            for (a, b) in zip(parts, c.parts) {
                #expect(a.shape == b.shape && a.color == b.color)
                for i in 0..<3 {
                    #expect(abs(a.position[i] - b.position[i]) <= golden.tolerance, "\(c.templateId) \(a.id) pos")
                    #expect(abs(a.size[i] - b.size[i]) <= golden.tolerance, "\(c.templateId) \(a.id) size")
                }
            }
        }
    }

    @Test func unapprovedLicenceHiddenFromPickers() throws {
        let catalog = try Fixtures.catalog()
        #expect(!catalog.approvedModules.contains { $0.id == "experimental_glow_tail_01" })
    }
}
