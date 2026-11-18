import Foundation
import OSLog

/// Privacy-preserving analytics/diagnostics facade. Events carry names and coarse properties only — never prompts,
/// dialogue, character names or other user content (plan §19). Disabled until the user consents.
@MainActor
final class Analytics {
    private let log = Logger(subsystem: "ai.characterverse", category: "analytics")
    var consented = UserDefaults.standard.bool(forKey: "cv.analyticsConsent") {
        didSet { UserDefaults.standard.set(consented, forKey: "cv.analyticsConsent") }
    }

    func track(_ event: String, _ properties: [String: String] = [:]) {
        guard consented else { return }
        log.info("event \(event, privacy: .public) \(properties.description, privacy: .public)")
    }

    func error(_ code: String, area: String) {
        log.error("error \(code, privacy: .public) in \(area, privacy: .public)")
    }
}
