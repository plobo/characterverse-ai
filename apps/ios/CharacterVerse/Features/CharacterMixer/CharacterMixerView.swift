import SwiftUI

struct CharacterMixerView: View {
    @Environment(AppStore.self) private var store
    @Environment(AppRouter.self) private var router
    @State private var vm: CharacterMixerViewModel?

    var body: some View {
        Group {
            if let vm { MixerContent(vm: vm) } else { ProgressView() }
        }
        .navigationTitle("Mixer")
        .task {
            if vm == nil { vm = CharacterMixerViewModel(env: store.env) }
            vm?.characters = store.characters.filter { !$0.archived }
            #if DEBUG
            if let vm, vm.selected.isEmpty, UserDefaults.standard.string(forKey: "cvScreen") == "mixer" {
                let ids = vm.characters.filter(\.lineage.isEmpty).prefix(2).map(\.id)
                ids.forEach { vm.toggle($0) }
                if let first = ids.first { vm.weights[first] = 1.6 }
                await vm.fetchSuggestions()
            }
            #endif
        }
        .onChange(of: store.characters) { vm?.characters = store.characters.filter { !$0.archived } }
    }
}

private struct MixerContent: View {
    @Environment(AppStore.self) private var store
    @Environment(AppRouter.self) private var router
    @Bindable var vm: CharacterMixerViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                SectionHeader(title: "1. Pick 2–3 characters", subtitle: "Only characters you own can be mixed")
                if vm.characters.count < 2 {
                    EmptyStateView(symbol: "person.2", title: "Need two characters", message: "Create or save at least two characters to start mixing.",
                                   actionTitle: "Create a character") { router.openCreator(with: nil) }
                }
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 10) {
                        ForEach(vm.characters) { c in
                            Button { vm.toggle(c.id) } label: { sourceCard(c) }.buttonStyle(.plain)
                        }
                    }
                }
                SectionHeader(title: "2. What to mix")
                FlowLayout {
                    ForEach(MixDimension.allCases) { d in
                        Button { vm.toggleDimension(d) } label: { Chip(label: d.title, selected: vm.dimensions.contains(d)) }.buttonStyle(.plain)
                    }
                }
                if vm.selected.count >= 2 {
                    SectionHeader(title: "3. Trait contribution")
                    ForEach(vm.selected, id: \.self) { id in
                        if let c = store.character(id) {
                            VStack(alignment: .leading, spacing: 2) {
                                HStack { Text(c.name).font(.subheadline.bold()); Spacer()
                                    Text("\(Int(share(id) * 100))%").monospacedDigit().foregroundStyle(Theme.textSecondary) }
                                Slider(value: Binding(get: { vm.weights[id] ?? 1 }, set: { vm.setWeight(id, $0) }), in: 0...3,
                                       onEditingChanged: { if $0 { vm.beginWeightChange() } })
                                    .accessibilityLabel("\(c.name) contribution")
                                    .accessibilityValue("\(Int(share(id) * 100)) percent")
                            }
                        }
                    }
                }
                if let r = vm.result { preview(r) }
                ForEach(vm.warnings, id: \.self) { w in
                    Label(w, systemImage: "exclamationmark.triangle").font(.footnote).foregroundStyle(Theme.warning)
                }
                if let e = vm.errorMessage { ErrorBanner(message: e) }
            }
            .padding(16)
        }
        .background(Theme.background)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button { vm.undo() } label: { Label("Undo", systemImage: "arrow.uturn.backward") }.disabled(!vm.canUndo)
            }
        }
        .overlay { if vm.busy { LoadingOverlay(label: "Mixing…") } }
    }

    private func share(_ id: String) -> Double {
        let total = vm.selected.reduce(0) { $0 + (vm.weights[$1] ?? 1) }
        return total > 0 ? (vm.weights[id] ?? 1) / total : 0
    }

    private func sourceCard(_ c: CharacterSummary) -> some View {
        let selected = vm.selected.contains(c.id)
        return VStack(spacing: 6) {
            CharacterThumbnail(parts: store.env.assembler.assemble(c.recipe)).frame(width: 96, height: 104)
            Text(c.name).font(.caption.bold()).lineLimit(1).frame(width: 100)
        }
        .padding(8)
        .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.radius))
        .overlay(RoundedRectangle(cornerRadius: Theme.radius).stroke(selected ? Theme.brand : .clear, lineWidth: 3))
        .overlay(alignment: .topTrailing) {
            if selected { Image(systemName: "checkmark.circle.fill").foregroundStyle(Theme.brand).padding(6) }
        }
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(selected ? [.isSelected, .isButton] : .isButton)
    }

    private func preview(_ r: MixResult) -> some View {
        Card {
            HStack {
                Text("Fusion preview").font(.headline)
                Spacer()
                PaletteDots(palette: r.recipe.palette)
            }
            CharacterSceneView(parts: store.env.assembler.assemble(r.recipe), accessibilityName: "\(r.recipe.name) fusion preview")
                .frame(height: 260).clipShape(RoundedRectangle(cornerRadius: Theme.radius))
            TextField("Name", text: $vm.customName, prompt: Text(r.recipe.name)).textFieldStyle(.roundedBorder)
            if !vm.suggestions.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack {
                        ForEach(vm.suggestions, id: \.self) { s in
                            Button { vm.customName = s.name } label: { Chip(label: s.name, selected: vm.customName == s.name, color: Theme.brandSecondary) }
                                .buttonStyle(.plain)
                        }
                    }
                }
            }
            Text("Powers: \(r.recipe.powers.map(\.humanized).joined(separator: ", "))  ·  Traits: \(r.recipe.personalityTraits.joined(separator: ", "))")
                .font(.footnote).foregroundStyle(Theme.textSecondary)
            HStack {
                Button { Task { vm.suggestions.isEmpty ? await vm.fetchSuggestions() : vm.applyNextSuggestion() } } label: {
                    Label(vm.suggestions.isEmpty ? "AI suggestions" : "Regenerate", systemImage: "sparkles")
                }.buttonStyle(SecondaryButtonStyle())
                Button {
                    Task { if let saved = await vm.save() { store.upsert(saved); router.push(.characterDetail(saved.id), on: .universe) } }
                } label: { Label("Save", systemImage: "plus.circle.fill") }.buttonStyle(PrimaryButtonStyle())
            }
        }
    }
}
