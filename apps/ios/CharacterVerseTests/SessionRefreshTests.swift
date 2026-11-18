import Foundation
import Testing
@testable import CharacterVerse

/// Scripted URLProtocol: responds by path, records requests.
final class StubProtocol: URLProtocol, @unchecked Sendable {
    nonisolated(unsafe) static var responses: [String: [(Int, Data)]] = [:]
    nonisolated(unsafe) static var seen: [URLRequest] = []
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        Self.seen.append(request)
        let path = request.url!.path
        var queue = Self.responses[path] ?? [(500, Data())]
        let (status, body) = queue.removeFirst()
        if !queue.isEmpty { Self.responses[path] = queue }
        client?.urlProtocol(self, didReceive: HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: nil)!,
                            cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: body)
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}

@Suite("Session refresh", .serialized)
struct SessionRefreshTests {
    @Test func expiredSessionIsRefreshedAndRequestRetried() async throws {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [StubProtocol.self]
        let expired = #"{"error":{"code":"AUTH_INVALID","message":"Session expired","details":[],"retryable":false}}"#
        let user = #"{"id":"u1","displayName":"Guest Creator","email":null,"isGuest":true,"createdAt":"2026-11-17T22:41:05.123Z"}"#
        let session = #"{"accessToken":"new-access","tokenType":"Bearer","expiresAt":1,"refreshToken":"new-refresh","refreshExpiresAt":2,"user":\#(user)}"#
        StubProtocol.seen = []
        StubProtocol.responses = ["/v1/me": [(401, Data(expired.utf8)), (200, Data(user.utf8))],
                                  "/v1/auth/refresh": [(200, Data(session.utf8))]]
        let tokens = TokenStore(service: "test.\(UUID().uuidString)")
        await tokens.save(access: "old-access", refresh: "old-refresh")
        let api = APIClient(baseURL: URL(string: "https://example.test")!, tokens: tokens, session: URLSession(configuration: config))
        let me: UserDTO = try await api.send("GET", "v1/me")
        #expect(me.isGuest)
        #expect(await tokens.token() == "new-access")
        #expect(await tokens.refreshToken() == "new-refresh")
        #expect(StubProtocol.seen.map(\.url!.path) == ["/v1/me", "/v1/auth/refresh", "/v1/me"])
        #expect(StubProtocol.seen.last?.value(forHTTPHeaderField: "Authorization") == "Bearer new-access")
        await tokens.clear()
    }
}
