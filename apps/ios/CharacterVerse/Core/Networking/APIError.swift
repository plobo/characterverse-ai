import Foundation

/// Shared error envelope + codes (shared/api-contracts/error_codes.json).
struct APIErrorEnvelope: Decodable, Sendable {
    struct Detail: Decodable, Sendable, Hashable { var code: String; var field: String?; var message: String }
    struct Body: Decodable, Sendable { var code: String; var message: String; var details: [Detail]; var retryable: Bool }
    var error: Body
}

enum APIError: Error, Equatable, LocalizedError {
    case server(status: Int, code: String, message: String, details: [APIErrorEnvelope.Detail], retryable: Bool)
    case offline
    case decoding(String)
    case invalidResponse

    static let retryableCodes: Set<String> = ["RATE_LIMITED", "INTERNAL"]

    var code: String {
        switch self {
        case .server(_, let code, _, _, _): code
        case .offline: "OFFLINE"
        case .decoding: "DECODING"
        case .invalidResponse: "INVALID_RESPONSE"
        }
    }

    var isRetryable: Bool {
        switch self {
        case .server(_, _, _, _, let retryable): retryable
        case .offline: true
        default: false
        }
    }

    var errorDescription: String? {
        switch self {
        case .server(_, let code, let message, _, _):
            code == "AUTH_INVALID" || code == "AUTH_REQUIRED" ? "Please sign in again." : message
        case .offline: "You're offline. Drafts are saved on this device."
        case .decoding: "The server sent something unexpected."
        case .invalidResponse: "The server could not be reached."
        }
    }
}

/// Bounded exponential backoff with jitter; only retryable codes and transport errors are retried.
struct RetryPolicy: Sendable {
    var maxAttempts = 3
    var baseDelay: Double = 0.5
    var maxDelay: Double = 8

    func delay(forAttempt attempt: Int) -> Double {
        min(maxDelay, baseDelay * pow(2, Double(attempt - 1))) * Double.random(in: 0.8...1.2)
    }
}
