import SwiftUI

struct CharacterCreatorView: View {
    @Environment(AppStore.self) private var store
    @Environment(AppRouter.self) private var router
    @State private var vm: CharacterCreatorViewModel?

    var body: some View {
        Group {
            if let vm { CreatorForm(vm: vm) } else { ProgressView() }
        }
        .navigationTitle(vm?.editingCharacterId == nil ? "Create" : "Edit Character")
        .onAppear(perform: syncSeed)
        .onChange(of: router.creatorSeed) { syncSeed() }
    }

    private func syncSeed() {
        if vm == nil || router.creatorSeed != nil {
            vm = CharacterCreatorViewModel(env: store.env, seed: router.creatorSeed, editing: router.creatorEditingId)
            router.creatorSeed = nil
            router.creatorEditingId = nil
        }
    }
}

private struct CreatorForm: View {
    @Environment(AppStore.self) private var store
    @Environment(AppRouter.self) private var router
    @Bindable var vm: CharacterCreatorViewModel

    var body: some View {
        VStack(spacing: 0) {
            CharacterSceneView(parts: vm.parts, background: "#EDE9FF", accessibilityName: "\(vm.recipe.name) 3D preview")
                .frame(height: 280)
                .overlay(alignment: .bottomLeading) {
                    if !vm.issues.isEmpty {
                        Label("\(vm.issues.count) issue(s)", systemImage: "exclamationmark.circle.fill")
                            .font(.caption.bold()).padding(8).background(.thinMaterial, in: Capsule()).padding(10)
                    }
                }
            Form {
                aiSection
                identitySection
                proportionsSection
                colorsSection
                modulesSection
                powersSection
                personalitySection
                if !vm.issues.isEmpty {
                    Section("Fix before saving") {
                        ForEach(vm.issues, id: \.self) { Label($0.message, systemImage: "xmark.octagon").foregroundStyle(Theme.danger) }
                    }
                }
                Section {
                    if let error = vm.errorMessage { ErrorBanner(message: error) }
                    if let ok = vm.savedMessage { Label(ok, systemImage: "checkmark.circle.fill").foregroundStyle(Theme.success) }
                    Button {
                        Task { if let saved = await vm.save() { store.upsert(saved) } }
                    } label: { Label(vm.editingCharacterId == nil ? "Save to My Universe" : "Save new version", systemImage: "tray.and.arrow.down.fill") }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(vm.busy || !vm.issues.isEmpty)
                    .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
                }
            }
        }
        .overlay { if vm.busy { LoadingOverlay(label: "Working…") } }
    }

    private var aiSection: some View {
        Section {
            TextField("Describe an original character…", text: $vm.aiPrompt, axis: .vertical).lineLimit(2...4)
            Button { Task { await vm.generateFromDescription() } } label: { Label("Generate recipe with AI", systemImage: "sparkles") }
                .disabled(vm.aiPrompt.isEmpty || vm.busy)
            ForEach(vm.aiWarnings, id: \.self) { Text($0).font(.footnote).foregroundStyle(Theme.warning) }
            if let note = vm.moderationNote { Text(note).font(.footnote).foregroundStyle(Theme.textSecondary) }
        } header: { Text("AI description") } footer: {
            Text("AI picks from approved, licence-cleared parts only. You can tweak everything below.")
        }
    }

    private var identitySection: some View {
        Section("Identity") {
            TextField("Name", text: $vm.recipe.name)
            Picker("Category", selection: Binding(get: { vm.recipe.category }, set: { vm.setCategory($0) })) {
                ForEach(CharacterCategory.allCases) { Text($0.title).tag($0.rawValue) }
            }
            Picker("Base body", selection: Binding(get: { vm.recipe.baseModelId }, set: { vm.setBaseModel($0) })) {
                ForEach(vm.baseModelsForCategory) { Text($0.name).tag($0.id) }
            }
            Picker("Style", selection: $vm.recipe.style) {
                ForEach(store.env.catalog.manifest.styles, id: \.self) { Text($0.humanized).tag($0) }
            }
            Picker("Voice", selection: $vm.recipe.voiceProfileId) {
                ForEach(store.env.catalog.approvedVoices) { Text($0.name).tag($0.id) }
            }
        }
    }

    private var proportionsSection: some View {
        Section("Body & face") {
            slider("Height", value: $vm.recipe.proportions.height)
            slider("Shoulder width", value: $vm.recipe.proportions.shoulderWidth)
            slider("Head size", value: $vm.recipe.proportions.headScale)
        }
    }

    private func slider(_ label: String, value: Binding<Double>) -> some View {
        VStack(alignment: .leading) {
            HStack { Text(label); Spacer(); Text(value.wrappedValue, format: .number.precision(.fractionLength(2))).monospacedDigit().foregroundStyle(Theme.textSecondary) }
            Slider(value: value, in: 0.7...1.3, step: 0.01).accessibilityLabel(label)
        }
    }

    private var colorsSection: some View {
        Section("Colours & materials") {
            colorPicker("Primary", \.primary)
            colorPicker("Secondary", \.secondary)
            colorPicker("Accent", \.accent)
        }
    }

    private func colorPicker(_ label: String, _ key: WritableKeyPath<CharacterRecipe.Palette, String>) -> some View {
        ColorPicker(label, selection: Binding(
            get: { Color(hex: vm.recipe.palette[keyPath: key]) },
            set: { vm.recipe.palette[keyPath: key] = UIColor($0).hexString }), supportsOpacity: false)
    }

    private var modulesSection: some View {
        Section {
            ForEach(vm.slots, id: \.slot) { group in
                Picker(group.slot.humanized, selection: Binding(get: { vm.selectedModule(in: group.slot) }, set: { vm.setModule($0, slot: group.slot) })) {
                    Text("None").tag(String?.none)
                    ForEach(group.modules) { Text($0.name).tag(Optional($0.id)) }
                }
            }
        } header: { Text("Outfit & accessories") } footer: { Text("Only parts that fit this body are shown. One item per slot.") }
    }

    private var powersSection: some View {
        Section {
            FlowLayout {
                ForEach(vm.availablePowers) { p in
                    Button { vm.togglePower(p.id) } label: { Chip(label: p.name, selected: vm.recipe.powers.contains(p.id), color: Theme.brand) }
                        .buttonStyle(.plain)
                }
            }
            .padding(.vertical, 4)
        } header: { Text("Powers & effects (up to 3)") }
    }

    private var personalitySection: some View {
        Section {
            FlowLayout {
                ForEach(store.env.catalog.manifest.personalityTraits, id: \.self) { t in
                    Button { vm.toggleTrait(t) } label: { Chip(label: t.capitalized, selected: vm.recipe.personalityTraits.contains(t), color: Theme.brandSecondary) }
                        .buttonStyle(.plain)
                }
            }
            .padding(.vertical, 4)
        } header: { Text("Personality (up to 5)") }
    }
}
