import SwiftUI

struct MyUniverseView: View {
    @Environment(AppStore.self) private var store
    @Environment(AppRouter.self) private var router
    enum Segment: String, CaseIterable { case characters = "Characters", favorites = "Favorites", projects = "Projects", videos = "Videos", drafts = "Drafts" }
    @State private var segment: Segment = .characters
    @State private var search = ""
    @State private var sort = "updated"
    @State private var category: String?
    @State private var showArchived = false

    private var filtered: [CharacterSummary] {
        var list = store.characters.filter { (showArchived || !$0.archived) && (segment != .favorites || $0.isFavorite) }
        if let category { list = list.filter { $0.category == category } }
        if !search.isEmpty { list = list.filter { $0.name.localizedCaseInsensitiveContains(search) } }
        switch sort {
        case "name": list.sort { $0.name < $1.name }
        case "created": list.sort { $0.createdAt > $1.createdAt }
        default: list.sort { $0.updatedAt > $1.updatedAt }
        }
        return list
    }

    var body: some View {
        List {
            Section {
                Picker("Show", selection: $segment) { ForEach(Segment.allCases, id: \.self) { Text($0.rawValue).tag($0) } }
                    .pickerStyle(.segmented)
                if let usage = store.usage {
                    Label("\(usage.characters) characters · \(usage.projects) projects · \(usage.renders) renders · \(ByteCountFormatter.string(fromByteCount: Int64(usage.storageBytes), countStyle: .file))",
                          systemImage: "internaldrive").font(.caption).foregroundStyle(Theme.textSecondary)
                }
            }
            switch segment {
            case .characters, .favorites: characterRows
            case .projects: projectRows
            case .videos: videoRows
            case .drafts: draftRows
            }
        }
        .navigationTitle("My Universe")
        .searchable(text: $search, prompt: "Search characters")
        .refreshable { await store.refreshAll() }
        .toolbar {
            ToolbarItem(placement: .topBarLeading) {
                Menu {
                    Picker("Sort", selection: $sort) { Text("Recently edited").tag("updated"); Text("Newest").tag("created"); Text("Name").tag("name") }
                    Picker("Category", selection: $category) {
                        Text("All categories").tag(String?.none)
                        ForEach(CharacterCategory.allCases) { Text($0.title).tag(Optional($0.rawValue)) }
                    }
                    Toggle("Show archived", isOn: $showArchived)
                } label: { Label("Sort & filter", systemImage: "line.3.horizontal.decrease.circle") }
            }
            ToolbarItem(placement: .topBarTrailing) {
                Button { router.push(.settings) } label: { Label("Settings", systemImage: "gearshape") }
            }
        }
    }

    @ViewBuilder private var characterRows: some View {
        if store.loadingLibrary && store.characters.isEmpty { ProgressView() }
        if filtered.isEmpty && !store.loadingLibrary {
            EmptyStateView(symbol: "person.crop.square", title: "No characters here", message: "Create an original character to fill your universe.",
                           actionTitle: "Create") { router.openCreator(with: nil) }
        }
        ForEach(filtered) { c in
            Button { router.push(.characterDetail(c.id)) } label: { CharacterRow(character: c) }
                .foregroundStyle(.primary)
                .swipeActions {
                    Button(role: .destructive) { Task { try? await store.repo.delete(c.id); await store.refreshCharacters() } } label: { Label("Delete", systemImage: "trash") }
                    Button { Task { if let u = try? await store.repo.update(c.id, .init(archived: !c.archived)) { store.upsert(u) } } } label: {
                        Label(c.archived ? "Unarchive" : "Archive", systemImage: "archivebox")
                    }.tint(Theme.warning)
                }
                .swipeActions(edge: .leading) {
                    Button { Task { if let d = try? await store.repo.duplicate(c.id) { store.upsert(d) } } } label: { Label("Duplicate", systemImage: "plus.square.on.square") }
                        .tint(Theme.brandSecondary)
                }
        }
    }

    @ViewBuilder private var projectRows: some View {
        if store.projects.isEmpty { EmptyStateView(symbol: "film", title: "No projects", message: "Projects you create in the Studio appear here.") }
        ForEach(store.projects) { p in
            Button { router.push(.storyboard(p.id), on: .studio) } label: {
                VStack(alignment: .leading) { Text(p.title).font(.headline); Text("\(p.storyboard?.scenes.count ?? 0) scenes").font(.caption) }
            }.foregroundStyle(.primary)
        }
    }

    @ViewBuilder private var videoRows: some View {
        let done = store.renders.filter { $0.status == .completed }
        if done.isEmpty { EmptyStateView(symbol: "play.rectangle", title: "No videos yet", message: "Finished renders appear here.") }
        ForEach(done) { job in
            Button { router.push(.renderQueue, on: .studio) } label: {
                Label("\(job.projectTitle ?? "Video") · \(job.quality) · \((job.durationMs ?? 0) / 1000)s", systemImage: "play.rectangle.fill")
            }
        }
    }

    @ViewBuilder private var draftRows: some View {
        let drafts = store.env.drafts.all()
        if drafts.isEmpty { EmptyStateView(symbol: "doc", title: "No local drafts", message: "Unsaved creator edits are kept here, even offline.") }
        ForEach(drafts, id: \.id) { d in
            if let r = d.recipe {
                Button { router.openCreator(with: r, editing: d.serverCharacterId) } label: {
                    HStack {
                        CharacterThumbnail(parts: store.env.assembler.assemble(r)).frame(width: 44, height: 48)
                        VStack(alignment: .leading) { Text(r.name).font(.headline); Text(d.updatedAt, style: .relative).font(.caption) }
                    }
                }
                .foregroundStyle(.primary)
                .swipeActions { Button(role: .destructive) { store.env.drafts.remove(id: d.id) } label: { Label("Discard", systemImage: "trash") } }
            }
        }
    }
}

struct CharacterRow: View {
    @Environment(AppStore.self) private var store
    var character: CharacterSummary
    var body: some View {
        HStack(spacing: 12) {
            CharacterThumbnail(parts: store.env.assembler.assemble(character.recipe))
                .frame(width: 58, height: 64)
                .background(Theme.categoryColor(character.category).opacity(0.12), in: RoundedRectangle(cornerRadius: 12))
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    Text(character.name).font(.headline)
                    if character.isFavorite { Image(systemName: "star.fill").font(.caption).foregroundStyle(Theme.accent).accessibilityLabel("Favorite") }
                    if !character.lineage.isEmpty { Image(systemName: "arrow.triangle.merge").font(.caption).foregroundStyle(Theme.brand).accessibilityLabel("Fusion") }
                }
                Text(character.category.capitalized).font(.caption.bold()).foregroundStyle(Theme.categoryColor(character.category))
                Text("Edited \(character.updatedAt.formatted(.relative(presentation: .named)))\(character.archived ? " · Archived" : "")")
                    .font(.caption).foregroundStyle(Theme.textSecondary)
            }
            Spacer()
            PaletteDots(palette: character.recipe.palette)
        }
        .accessibilityElement(children: .combine)
    }
}

struct CharacterDetailView: View {
    @Environment(AppStore.self) private var store
    @Environment(AppRouter.self) private var router
    @Environment(\.dismiss) private var dismiss
    var characterId: String
    @State private var confirmDelete = false
    @State private var reported = false

    var body: some View {
        if let c = store.character(characterId) {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    CharacterSceneView(parts: store.env.assembler.assemble(c.recipe), accessibilityName: "\(c.name) 3D preview")
                        .frame(height: 340).clipShape(RoundedRectangle(cornerRadius: Theme.largeRadius))
                    RecipeSummary(recipe: c.recipe)
                    if !c.lineage.isEmpty {
                        Card {
                            Text("Fusion lineage").font(.headline)
                            ForEach(c.lineage, id: \.sourceCharacterId) { li in
                                HStack {
                                    Text(store.character(li.sourceCharacterId)?.name ?? "Deleted character")
                                    Spacer()
                                    Text("\(Int(li.contributionWeight * 100))% · \(li.mixDimension.replacingOccurrences(of: ",", with: ", "))")
                                        .font(.caption).foregroundStyle(Theme.textSecondary)
                                }
                            }
                        }
                    }
                    Text("Version \(c.version) · created \(c.createdAt.formatted(date: .abbreviated, time: .omitted))").font(.footnote).foregroundStyle(Theme.textSecondary)
                    HStack {
                        Button { router.openCreator(with: c.recipe, editing: c.id) } label: { Label("Edit", systemImage: "pencil") }.buttonStyle(PrimaryButtonStyle())
                        Button { Task { if let d = try? await store.repo.duplicate(c.id) { store.upsert(d) } } } label: { Label("Duplicate", systemImage: "plus.square.on.square") }
                            .buttonStyle(SecondaryButtonStyle())
                    }
                }
                .padding(16)
            }
            .background(Theme.background)
            .navigationTitle(c.name)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { Task { if let u = try? await store.repo.update(c.id, .init(isFavorite: !c.isFavorite)) { store.upsert(u) } } } label: {
                        Label("Favorite", systemImage: c.isFavorite ? "star.fill" : "star")
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Button { Task { if let u = try? await store.repo.update(c.id, .init(archived: !c.archived)) { store.upsert(u) } } } label: {
                            Label(c.archived ? "Unarchive" : "Archive", systemImage: "archivebox")
                        }
                        Button { Task { try? await store.repo.report(contentType: "character", contentId: c.id, reason: "copyright", details: ""); reported = true } } label: {
                            Label("Report content", systemImage: "flag")
                        }
                        Button(role: .destructive) { confirmDelete = true } label: { Label("Delete", systemImage: "trash") }
                    } label: { Label("More", systemImage: "ellipsis.circle") }
                }
            }
            .confirmationDialog("Delete \(c.name)?", isPresented: $confirmDelete, titleVisibility: .visible) {
                Button("Delete", role: .destructive) { Task { try? await store.repo.delete(c.id); await store.refreshCharacters(); dismiss() } }
            }
            .alert("Thanks — our team will review this.", isPresented: $reported) {}
        } else {
            EmptyStateView(symbol: "questionmark", title: "Character not found", message: "It may have been deleted.")
        }
    }
}
