import SwiftUI

struct SettingsView: View {
    @Environment(AppStore.self) private var store
    @AppStorage("cv.analyticsConsent") private var analytics = false
    @AppStorage("cv.notifications") private var notifications = true
    @AppStorage("cv.familyMode") private var familyMode = true
    @State private var exportURL: URL?
    @State private var confirmDelete = false
    @State private var cacheBytes = 0
    @State private var error: String?

    var body: some View {
        Form {
            Section("Account") {
                LabeledContent("Name", value: store.user?.displayName ?? "—")
                LabeledContent("Type", value: store.user?.isGuest == true ? "Guest" : "Signed in")
                Button("Sign out") { Task { await store.signOut() } }
            }
            Section {
                Toggle("Share anonymous usage analytics", isOn: $analytics)
                    .onChange(of: analytics) { store.env.analytics.consented = analytics }
            } header: { Text("Privacy") } footer: {
                Text("Analytics never include your prompts, dialogue, character names or videos.")
            }
            Section("Content preferences") {
                Toggle("Family-friendly story suggestions", isOn: $familyMode)
                Toggle("Render notifications", isOn: $notifications)
            }
            Section {
                Button { Task { await export() } } label: { Label("Export my data", systemImage: "square.and.arrow.up") }
                LabeledContent("Cached media", value: ByteCountFormatter.string(fromByteCount: Int64(cacheBytes), countStyle: .file))
                Button("Clear cached media") { Task { await store.env.assetCache.clear(); cacheBytes = 0 } }
                Button(role: .destructive) { confirmDelete = true } label: { Label("Delete account and data", systemImage: "trash") }
            } header: { Text("Your data") } footer: {
                Text("Deleting removes your characters, projects, videos and uploads immediately. Moderation records without content are retained per our retention policy.")
            }
            if let error { Section { ErrorBanner(message: error) } }
            Section("Help & legal") {
                Link("Content policy — original characters only", destination: URL(string: "https://characterverse.example/policy")!)
                Link("Terms of service", destination: URL(string: "https://characterverse.example/terms")!)
                Link("Privacy notice", destination: URL(string: "https://characterverse.example/privacy")!)
                Link("Report content or request a takedown", destination: URL(string: "https://characterverse.example/report")!)
                LabeledContent("Asset manifest", value: store.env.catalog.manifest.manifestVersion)
            }
        }
        .navigationTitle("Settings")
        .task { cacheBytes = await store.env.assetCache.totalBytes() }
        .sheet(item: Binding(get: { exportURL.map(IdentifiedURL.init) }, set: { exportURL = $0?.url })) { ShareSheet(items: [$0.url]) }
        .confirmationDialog("Delete your account?", isPresented: $confirmDelete, titleVisibility: .visible) {
            Button("Delete everything", role: .destructive) {
                Task {
                    do { try await store.repo.deleteAccount(); store.env.drafts.removeAll(); await store.signOut() }
                    catch { self.error = error.localizedDescription }
                }
            }
        } message: { Text("This cannot be undone.") }
    }

    private func export() async {
        do {
            let data = try await store.repo.exportData()
            let url = FileManager.default.temporaryDirectory.appending(path: "characterverse-export.json")
            try data.write(to: url)
            exportURL = url
        } catch { self.error = error.localizedDescription }
    }
}
