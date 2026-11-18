import SwiftUI

struct DiscoverView: View {
    @Environment(AppStore.self) private var store
    @Environment(AppRouter.self) private var router
    @State private var search = ""
    @State private var category: String?
    @AppStorage("cv.tutorialDismissed") private var tutorialDismissed = false

    private var templates: [AssetManifest.CharacterTemplate] {
        store.env.catalog.manifest.characterTemplates.filter { t in
            (category == nil || t.recipe.category == category) &&
                (search.isEmpty || t.recipe.name.localizedCaseInsensitiveContains(search) || t.recipe.powers.joined(separator: " ").contains(search.lowercased()))
        }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if !tutorialDismissed { tutorial }
                SectionHeader(title: "Categories", subtitle: "Start from an original template")
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 100), spacing: 10)], spacing: 10) {
                    ForEach(CharacterCategory.allCases) { c in
                        Button { category = category == c.rawValue ? nil : c.rawValue } label: {
                            VStack(spacing: 6) {
                                Image(systemName: c.symbol).font(.title2)
                                Text(c.title).font(.footnote.bold())
                            }
                            .frame(maxWidth: .infinity, minHeight: 74)
                            .foregroundStyle(category == c.rawValue ? .white : Theme.categoryColor(c.rawValue))
                            .background(category == c.rawValue ? Theme.categoryColor(c.rawValue) : Theme.categoryColor(c.rawValue).opacity(0.12),
                                        in: RoundedRectangle(cornerRadius: Theme.radius))
                        }
                        .accessibilityLabel("\(c.title) category")
                        .accessibilityAddTraits(category == c.rawValue ? .isSelected : [])
                    }
                }
                SectionHeader(title: category == nil ? "Featured originals" : "\(category!.capitalized) templates")
                if templates.isEmpty {
                    EmptyStateView(symbol: "magnifyingglass", title: "No matches", message: "Try another search or category.")
                }
                LazyVGrid(columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)], spacing: 12) {
                    ForEach(templates) { t in
                        Button { router.push(.template(t.id)) } label: { TemplateCard(template: t) }.buttonStyle(.plain)
                    }
                }
            }
            .padding(16)
        }
        .background(Theme.background)
        .navigationTitle("Discover")
        .searchable(text: $search, prompt: "Search templates or powers")
    }

    private var tutorial: some View {
        ZStack(alignment: .topTrailing) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Welcome, \(store.user?.displayName ?? "creator")!").font(.title2.bold())
                Text("1. Create a character  2. Mix two into a hybrid  3. Generate a story  4. Render a short video")
                    .font(.subheadline)
                Button("Create my first character") { router.openCreator(with: nil) }
                    .font(.subheadline.bold()).padding(.top, 4)
                    .foregroundStyle(.white)
            }
            .padding(18)
            .frame(maxWidth: .infinity, alignment: .leading)
            .foregroundStyle(.white)
            .background(Theme.heroGradient, in: RoundedRectangle(cornerRadius: Theme.largeRadius))
            Button { tutorialDismissed = true } label: { Image(systemName: "xmark.circle.fill").font(.title3) }
                .foregroundStyle(.white.opacity(0.8)).padding(10).accessibilityLabel("Dismiss tutorial")
        }
    }
}

struct TemplateCard: View {
    @Environment(AppStore.self) private var store
    var template: AssetManifest.CharacterTemplate
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            CharacterThumbnail(parts: store.env.assembler.assemble(template.recipe))
                .frame(height: 150)
                .frame(maxWidth: .infinity)
                .background(Theme.categoryColor(template.recipe.category).opacity(0.12), in: RoundedRectangle(cornerRadius: Theme.radius))
            Text(template.recipe.name).font(.headline).lineLimit(1)
            HStack {
                Text(template.recipe.category.capitalized).font(.caption.bold()).foregroundStyle(Theme.categoryColor(template.recipe.category))
                Spacer()
                PaletteDots(palette: template.recipe.palette)
            }
        }
        .padding(10)
        .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.largeRadius))
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(template.recipe.name), \(template.recipe.category) template")
    }
}

struct TemplateDetailView: View {
    @Environment(AppStore.self) private var store
    @Environment(AppRouter.self) private var router
    var templateId: String

    var body: some View {
        if let t = store.env.catalog.manifest.characterTemplates.first(where: { $0.id == templateId }) {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    CharacterSceneView(parts: store.env.assembler.assemble(t.recipe), accessibilityName: "\(t.recipe.name) 3D preview")
                        .frame(height: 340).clipShape(RoundedRectangle(cornerRadius: Theme.largeRadius))
                    RecipeSummary(recipe: t.recipe)
                    Button { router.openCreator(with: t.recipe) } label: { Label("Customize this template", systemImage: "slider.horizontal.3") }
                        .buttonStyle(PrimaryButtonStyle())
                    Text("Original CharacterVerse template · licence lic_cv_original_v1 (commercial use approved)")
                        .font(.footnote).foregroundStyle(Theme.textSecondary)
                }
                .padding(16)
            }
            .background(Theme.background)
            .navigationTitle(t.recipe.name)
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

struct RecipeSummary: View {
    @Environment(AppStore.self) private var store
    var recipe: CharacterRecipe
    var body: some View {
        Card {
            HStack {
                Text(recipe.category.capitalized).font(.caption.bold()).padding(.horizontal, 10).padding(.vertical, 4)
                    .background(Theme.categoryColor(recipe.category).opacity(0.15), in: Capsule())
                    .foregroundStyle(Theme.categoryColor(recipe.category))
                Text(recipe.style.humanized).font(.caption).foregroundStyle(Theme.textSecondary)
                Spacer()
                PaletteDots(palette: recipe.palette)
            }
            row("Body", store.env.catalog.baseModel(recipe.baseModelId)?.name ?? recipe.baseModelId)
            row("Outfit & accessories", recipe.modules.map { store.env.catalog.module($0)?.name ?? $0 }.joined(separator: ", "))
            row("Powers", recipe.powers.map(\.humanized).joined(separator: ", "))
            row("Personality", recipe.personalityTraits.map(\.capitalized).joined(separator: ", "))
            row("Voice", store.env.catalog.voice(recipe.voiceProfileId)?.name ?? recipe.voiceProfileId)
        }
    }
    func row(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.caption).foregroundStyle(Theme.textSecondary)
            Text(value.isEmpty ? "None" : value).font(.subheadline)
        }
        .accessibilityElement(children: .combine)
    }
}
