import Foundation

/// Thin typed HTTP client. Cancellation follows Swift structured concurrency (cancel the Task to cancel the request).
final class APIClient: Sendable {
    let baseURL: URL
    private let session: URLSession
    private let tokens: TokenStore
    private let retry: RetryPolicy

    init(baseURL: URL, tokens: TokenStore, session: URLSession = .shared, retry: RetryPolicy = .init()) {
        self.baseURL = baseURL
        self.tokens = tokens
        self.session = session
        self.retry = retry
    }

    static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .custom { decoder in
            let raw = try decoder.singleValueContainer().decode(String.self)
            if let date = try? Date(raw, strategy: Date.ISO8601FormatStyle(includingFractionalSeconds: true)) { return date }
            if let date = try? Date(raw, strategy: Date.ISO8601FormatStyle()) { return date }
            throw DecodingError.dataCorrupted(.init(codingPath: decoder.codingPath, debugDescription: "Bad date \(raw)"))
        }
        return d
    }()

    static let encoder = JSONEncoder()

    struct Empty: Codable, Sendable {}

    func send<Response: Decodable & Sendable>(_ method: String, _ path: String, query: [URLQueryItem] = [],
                                              body: (any Encodable & Sendable)? = nil, headers: [String: String] = [:],
                                              as: Response.Type = Response.self) async throws -> Response {
        var components = URLComponents(url: baseURL.appending(path: path), resolvingAgainstBaseURL: false)!
        if !query.isEmpty { components.queryItems = query }
        var request = URLRequest(url: components.url!)
        request.httpMethod = method
        request.timeoutInterval = 30
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let body {
            request.httpBody = try Self.encoder.encode(body)
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        if let token = await tokens.token() { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        headers.forEach { request.setValue($1, forHTTPHeaderField: $0) }

        var attempt = 1
        var refreshed = false
        while true {
            do {
                return try await perform(request, as: Response.self)
            } catch let error as APIError where error.code == "AUTH_INVALID" && !refreshed && !path.hasPrefix("v1/auth/") {
                // Access tokens are short-lived; swap the refresh token for a new session once, then replay.
                guard let newToken = try await refreshSession() else { throw error }
                request.setValue("Bearer \(newToken)", forHTTPHeaderField: "Authorization")
                refreshed = true
            } catch let error as APIError where error.isRetryable && attempt < retry.maxAttempts
                && (method == "GET" || request.value(forHTTPHeaderField: "Idempotency-Key") != nil) {
                try await Task.sleep(for: .seconds(retry.delay(forAttempt: attempt)))
                attempt += 1
            }
        }
    }

    /// Returns the new access token, or nil when there is no refresh token (caller then signs the user out).
    private func refreshSession() async throws -> String? {
        guard let refresh = await tokens.refreshToken() else { return nil }
        var request = URLRequest(url: baseURL.appending(path: "v1/auth/refresh"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try Self.encoder.encode(RefreshRequestDTO(refreshToken: refresh))
        let session: SessionResponseDTO = try await perform(request, as: SessionResponseDTO.self)
        await tokens.save(access: session.accessToken, refresh: session.refreshToken)
        return session.accessToken
    }

    private func perform<Response: Decodable>(_ request: URLRequest, as: Response.Type) async throws -> Response {
        let data: Data, response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch let error as URLError where error.code != .cancelled {
            throw APIError.offline
        }
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else {
            if let env = try? Self.decoder.decode(APIErrorEnvelope.self, from: data) {
                throw APIError.server(status: http.statusCode, code: env.error.code, message: env.error.message,
                                      details: env.error.details, retryable: env.error.retryable)
            }
            throw APIError.server(status: http.statusCode, code: "INTERNAL", message: "Unexpected error", details: [],
                                  retryable: http.statusCode >= 500)
        }
        if Response.self == Empty.self, data.isEmpty { return Empty() as! Response }
        do {
            return try Self.decoder.decode(Response.self, from: data)
        } catch {
            throw APIError.decoding(String(describing: error))
        }
    }
}
