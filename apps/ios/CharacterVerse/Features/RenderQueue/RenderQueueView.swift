import AVKit
import SwiftUI

@MainActor
@Observable
final class RenderQueueViewModel {
    let store: AppStore
    var playerURL: URL?
    var shareURL: URL?
    var error: String?
    private var polling: Task<Void, Never>?

    init(store: AppStore) { self.store = store }

    /// Polls while any job is active (plan §10: polling first; SSE only if insufficient).
    func startPolling() {
        polling?.cancel()
        polling = Task { [weak self] in
            while !Task.isCancelled {
                guard let self else { return }
                await self.store.refreshRenders()
                let active = self.store.renders.contains(where: \.isActive)
                try? await Task.sleep(for: .seconds(active ? 2 : 10))
            }
        }
    }

    func stopPolling() { polling?.cancel() }

    func cancel(_ job: RenderJob) async { await mutate { try await self.store.repo.cancel(job.id) } }
    func retry(_ job: RenderJob) async { await mutate { try await self.store.repo.retry(job.id) } }

    private func mutate(_ op: @escaping () async throws -> RenderJob) async {
        do {
            let updated = try await op()
            if let i = store.renders.firstIndex(where: { $0.id == updated.id }) { store.renders[i] = updated }
        } catch { self.error = error.localizedDescription }
    }

    func preview(_ job: RenderJob) async {
        do {
            let dl = try await store.repo.downloadURL(job.id)
            playerURL = URL(string: dl.url)
        } catch { self.error = error.localizedDescription }
    }

    /// Downloads to the cache (resumable via retry) and hands a local file to the share sheet (user-initiated only).
    func export(_ job: RenderJob) async {
        do {
            let dl = try await store.repo.downloadURL(job.id)
            guard let remote = URL(string: dl.url) else { return }
            shareURL = try await store.env.assetCache.file(for: remote, key: "render-\(job.id)", ext: "mp4")
        } catch { self.error = error.localizedDescription }
    }
}

struct RenderQueueView: View {
    @Environment(AppStore.self) private var store
    @State private var vm: RenderQueueViewModel?

    var body: some View {
        List {
            if let error = vm?.error { ErrorBanner(message: error) }
            if store.renders.isEmpty {
                EmptyStateView(symbol: "square.stack.3d.down.forward", title: "No renders yet", message: "Render a storyboard from the Studio to see it here.")
            }
            ForEach(["Processing": store.renders.filter(\.isActive),
                     "Completed": store.renders.filter { $0.status == .completed },
                     "Failed & cancelled": store.renders.filter { $0.status == .failed || $0.status == .cancelled }].sorted { $0.key > $1.key },
                    id: \.key) { title, jobs in
                if !jobs.isEmpty {
                    Section(title) { ForEach(jobs) { row($0) } }
                }
            }
        }
        .navigationTitle("Render Queue")
        .refreshable { await store.refreshRenders() }
        .onAppear {
            if vm == nil { vm = RenderQueueViewModel(store: store) }
            vm?.startPolling()
        }
        .onDisappear { vm?.stopPolling() }
        .sheet(item: Binding(get: { vm?.playerURL.map(IdentifiedURL.init) }, set: { vm?.playerURL = $0?.url })) { item in
            VideoPlayer(player: AVPlayer(url: item.url)).ignoresSafeArea()
        }
        .sheet(item: Binding(get: { vm?.shareURL.map(IdentifiedURL.init) }, set: { vm?.shareURL = $0?.url })) { item in
            ShareSheet(items: [item.url])
        }
    }

    private func row(_ job: RenderJob) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(job.projectTitle ?? "Project").font(.headline)
                Spacer()
                Text("\(job.quality.capitalized) · \(job.aspectRatio)").font(.caption).foregroundStyle(Theme.textSecondary)
            }
            HStack {
                statusBadge(job)
                Text(job.stageLabel).font(.subheadline)
                if job.attempts > 1 { Text("attempt \(job.attempts)").font(.caption).foregroundStyle(Theme.textSecondary) }
            }
            if job.isActive {
                ProgressView(value: Double(job.progressPercent), total: 100).accessibilityLabel("Render progress").accessibilityValue(job.stageLabel)
            }
            if let code = job.errorCode, job.status == .failed { Text("Error: \(code.humanized)").font(.caption).foregroundStyle(Theme.danger) }
            HStack {
                switch job.status {
                case .completed:
                    Button { Task { await vm?.preview(job) } } label: { Label("Preview", systemImage: "play.fill") }
                    Button { Task { await vm?.export(job) } } label: { Label("Share", systemImage: "square.and.arrow.up") }
                case .failed, .cancelled:
                    Button { Task { await vm?.retry(job) } } label: { Label("Retry", systemImage: "arrow.clockwise") }
                case .queued, .processing:
                    Button(role: .destructive) { Task { await vm?.cancel(job) } } label: { Label(job.cancelRequested ? "Cancelling…" : "Cancel", systemImage: "xmark") }
                        .disabled(job.cancelRequested)
                }
            }
            .buttonStyle(.bordered)
            .font(.subheadline)
        }
        .padding(.vertical, 4)
    }

    private func statusBadge(_ job: RenderJob) -> some View {
        let (color, symbol): (Color, String) = switch job.status {
        case .completed: (Theme.success, "checkmark.circle.fill")
        case .failed: (Theme.danger, "xmark.octagon.fill")
        case .cancelled: (Theme.textSecondary, "slash.circle")
        case .queued: (Theme.warning, "clock")
        case .processing: (Theme.brand, "gearshape.2.fill")
        }
        return Image(systemName: symbol).foregroundStyle(color).accessibilityLabel(job.status.rawValue)
    }
}

struct IdentifiedURL: Identifiable { var url: URL; var id: String { url.absoluteString } }

struct ShareSheet: UIViewControllerRepresentable {
    var items: [Any]
    func makeUIViewController(context: Context) -> UIActivityViewController { UIActivityViewController(activityItems: items, applicationActivities: nil) }
    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}
