import Foundation
import Security

/// Session credentials (short-lived access token + long-lived refresh token). An actor serialises access; the values
/// live in the Keychain (this-device-only).
actor TokenStore {
    private let service: String
    private var cache: [String: String] = [:]

    init(service: String = "ai.characterverse.session") { self.service = service }

    func token() -> String? { read("accessToken") }
    func refreshToken() -> String? { read("refreshToken") }

    func save(access: String, refresh: String?) {
        write("accessToken", access)
        if let refresh { write("refreshToken", refresh) }
    }

    func clear() {
        for account in ["accessToken", "refreshToken"] {
            cache[account] = nil
            SecItemDelete(query(account) as CFDictionary)
        }
    }

    private func read(_ account: String) -> String? {
        if let hit = cache[account] { return hit }
        var q = query(account)
        q[kSecReturnData as String] = true
        q[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &item) == errSecSuccess, let data = item as? Data else { return nil }
        let value = String(data: data, encoding: .utf8)
        cache[account] = value
        return value
    }

    private func write(_ account: String, _ value: String) {
        cache[account] = value
        SecItemDelete(query(account) as CFDictionary)
        var add = query(account)
        add[kSecValueData as String] = Data(value.utf8)
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        SecItemAdd(add as CFDictionary, nil)
    }

    private func query(_ account: String) -> [String: Any] {
        [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: account]
    }
}
