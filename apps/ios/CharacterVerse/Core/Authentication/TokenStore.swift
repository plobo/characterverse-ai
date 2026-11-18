import Foundation
import Security

/// Session token storage. An actor serialises access; the token itself lives in the Keychain.
actor TokenStore {
    private let service = "ai.characterverse.session"
    private let account = "accessToken"
    private var cached: String?

    func token() -> String? {
        if let cached { return cached }
        var query = baseQuery
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess, let data = item as? Data else { return nil }
        cached = String(data: data, encoding: .utf8)
        return cached
    }

    func save(_ token: String) {
        cached = token
        SecItemDelete(baseQuery as CFDictionary)
        var add = baseQuery
        add[kSecValueData as String] = Data(token.utf8)
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        SecItemAdd(add as CFDictionary, nil)
    }

    func clear() {
        cached = nil
        SecItemDelete(baseQuery as CFDictionary)
    }

    private var baseQuery: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: account]
    }
}
