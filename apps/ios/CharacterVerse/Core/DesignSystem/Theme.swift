import SwiftUI
import UIKit

/// Design tokens mirrored from shared/design-tokens/tokens.json.
enum Theme {
    static let brand = Color(hex: "#6C4DF6")
    static let brandSecondary = Color(hex: "#00C2A8")
    static let accent = Color(hex: "#FFB547")
    static let danger = Color(hex: "#E5484D")
    static let success = Color(hex: "#30A46C")
    static let warning = Color(hex: "#F5A524")
    static let background = Color(uiColor: UIColor { $0.userInterfaceStyle == .dark ? UIColor(hex: "#0F0D1A") : UIColor(hex: "#F7F5FF") })
    static let surface = Color(uiColor: UIColor { $0.userInterfaceStyle == .dark ? UIColor(hex: "#1C1930") : .white })
    static let textSecondary = Color(uiColor: UIColor { $0.userInterfaceStyle == .dark ? UIColor(hex: "#B7B2CF") : UIColor(hex: "#5C5873") })
    static let radius: CGFloat = 14
    static let largeRadius: CGFloat = 22

    static func categoryColor(_ category: String) -> Color {
        let map = ["hero": "#3E7BFA", "villain": "#8E4EC6", "cartoon": "#FF8A3D", "fantasy": "#30A46C",
                   "robot": "#7C8798", "alien": "#00B3A4", "creature": "#D6409F"]
        return Color(hex: map[category] ?? "#6C4DF6")
    }

    static let heroGradient = LinearGradient(colors: [Color(hex: "#6C4DF6"), Color(hex: "#00C2A8")], startPoint: .topLeading, endPoint: .bottomTrailing)
}

extension UIColor {
    convenience init(hex: String) {
        let v = hex.trimmingCharacters(in: CharacterSet(charactersIn: "#"))
        let n = UInt64(v, radix: 16) ?? 0
        self.init(red: CGFloat((n >> 16) & 0xFF) / 255, green: CGFloat((n >> 8) & 0xFF) / 255, blue: CGFloat(n & 0xFF) / 255, alpha: 1)
    }

    var hexString: String {
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        getRed(&r, green: &g, blue: &b, alpha: &a)
        return String(format: "#%02X%02X%02X", Int(round(r * 255)), Int(round(g * 255)), Int(round(b * 255)))
    }
}

extension Color {
    init(hex: String) { self.init(uiColor: UIColor(hex: hex)) }
}

extension String {
    var humanized: String { replacingOccurrences(of: "_", with: " ").capitalized }
}
