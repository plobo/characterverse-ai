import Foundation

/// On-disk cache for downloaded media (rendered videos, thumbnails). Actor-isolated; downloads are retried
/// with backoff and written atomically, so an interrupted download never leaves a corrupt cached file.
actor AssetCache {
    private let directory: URL
    private let session: URLSession
    private var inFlight: [String: Task<URL, Error>] = [:]

    init(directory: URL? = nil, session: URLSession = .shared) {
        self.directory = directory ?? FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0].appending(path: "cv-assets")
        self.session = session
        try? FileManager.default.createDirectory(at: self.directory, withIntermediateDirectories: true)
    }

    func cachedFile(key: String, ext: String) -> URL? {
        let url = directory.appending(path: "\(key).\(ext)")
        return FileManager.default.fileExists(atPath: url.path) ? url : nil
    }

    func file(for remote: URL, key: String, ext: String, retry: RetryPolicy = .init()) async throws -> URL {
        if let hit = cachedFile(key: key, ext: ext) { return hit }
        if let task = inFlight[key] { return try await task.value }
        let destination = directory.appending(path: "\(key).\(ext)")
        let session = self.session
        let task = Task<URL, Error> {
            var attempt = 1
            while true {
                do {
                    let (temp, response) = try await session.download(from: remote)
                    guard let http = response as? HTTPURLResponse, http.statusCode == 200 else { throw APIError.invalidResponse }
                    try? FileManager.default.removeItem(at: destination)
                    try FileManager.default.moveItem(at: temp, to: destination)
                    return destination
                } catch where attempt < retry.maxAttempts && !(error is CancellationError) {
                    try await Task.sleep(for: .seconds(retry.delay(forAttempt: attempt)))
                    attempt += 1
                }
            }
        }
        inFlight[key] = task
        defer { inFlight[key] = nil }
        return try await task.value
    }

    func totalBytes() -> Int {
        let files = (try? FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: [.fileSizeKey])) ?? []
        return files.reduce(0) { $0 + ((try? $1.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0) }
    }

    func clear() {
        try? FileManager.default.removeItem(at: directory)
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    }
}
