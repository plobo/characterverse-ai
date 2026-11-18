import SwiftUI

struct OnboardingView: View {
    @Environment(AppStore.self) private var store
    @State private var acceptedPolicy = false
    @State private var showDevSignIn = false
    @State private var devName = ""
    @State private var busy = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                ZStack {
                    Theme.heroGradient
                    CharacterThumbnail(parts: heroParts).padding(24)
                }
                .frame(height: 260)
                .clipShape(RoundedRectangle(cornerRadius: 28))
                .accessibilityHidden(true)

                VStack(alignment: .leading, spacing: 8) {
                    Text("CharacterVerse AI").font(.largeTitle.bold())
                    Text("Create, mix and animate your own original 3D characters.")
                        .font(.title3).foregroundStyle(Theme.textSecondary)
                }

                Card {
                    Label("Original characters only", systemImage: "checkmark.seal.fill").font(.headline).foregroundStyle(Theme.brand)
                    Text("CharacterVerse is built for your own ideas. Requests to copy existing characters, franchises, logos or real people are blocked, and every built-in asset has a reviewed commercial-use licence.")
                        .font(.subheadline).foregroundStyle(Theme.textSecondary)
                    Toggle(isOn: $acceptedPolicy) {
                        Text("I agree to the Terms, Privacy Policy and Content Policy").font(.subheadline)
                    }
                    .accessibilityHint("Required to continue")
                }

                VStack(spacing: 12) {
                    Button { Task { busy = true; await store.signIn(provider: "guest", token: nil, name: nil); busy = false } } label: {
                        Label("Continue as guest", systemImage: "person.crop.circle.badge.plus")
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(!acceptedPolicy || busy)

                    Button { showDevSignIn = true } label: { Label("Sign in", systemImage: "person.badge.key") }
                        .buttonStyle(SecondaryButtonStyle())
                        .disabled(!acceptedPolicy || busy)
                }
                if let error = store.lastError { ErrorBanner(message: error) }
                Text("Guest drafts stay on this device. You can delete your account and data at any time in Settings.")
                    .font(.footnote).foregroundStyle(Theme.textSecondary)
            }
            .padding(20)
        }
        .background(Theme.background)
        .alert("Sign in", isPresented: $showDevSignIn) {
            TextField("Display name", text: $devName)
            Button("Continue") {
                Task { await store.signIn(provider: "dev", token: devName.lowercased().replacingOccurrences(of: " ", with: "-"), name: devName) }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Development builds use the local identity provider. Production builds use your OIDC provider.")
        }
    }

    private var heroParts: [ResolvedPart] {
        guard let t = store.env.catalog.manifest.characterTemplates.first else { return [] }
        return store.env.assembler.assemble(t.recipe)
    }
}
