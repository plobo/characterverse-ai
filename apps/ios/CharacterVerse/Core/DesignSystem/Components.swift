import SwiftUI

struct PrimaryButtonStyle: ButtonStyle {
    var color: Color = Theme.brand
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .frame(maxWidth: .infinity, minHeight: 50)
            .foregroundStyle(.white)
            .background(color.opacity(configuration.isPressed ? 0.8 : 1), in: RoundedRectangle(cornerRadius: Theme.radius))
    }
}

struct SecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .frame(maxWidth: .infinity, minHeight: 50)
            .foregroundStyle(Theme.brand)
            .background(Theme.brand.opacity(configuration.isPressed ? 0.2 : 0.1), in: RoundedRectangle(cornerRadius: Theme.radius))
    }
}

struct Card<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 10) { content }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.surface, in: RoundedRectangle(cornerRadius: Theme.largeRadius))
            .shadow(color: .black.opacity(0.06), radius: 10, y: 4)
    }
}

struct SectionHeader: View {
    var title: String
    var subtitle: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.title3.bold())
            if let subtitle { Text(subtitle).font(.subheadline).foregroundStyle(Theme.textSecondary) }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityAddTraits(.isHeader)
    }
}

struct Chip: View {
    var label: String
    var selected: Bool = false
    var color: Color = Theme.brand
    var body: some View {
        Text(label)
            .font(.subheadline.weight(.semibold))
            .padding(.horizontal, 12).padding(.vertical, 7)
            .foregroundStyle(selected ? .white : color)
            .background(selected ? color : color.opacity(0.12), in: Capsule())
            .accessibilityAddTraits(selected ? [.isSelected, .isButton] : .isButton)
    }
}

struct EmptyStateView: View {
    var symbol: String
    var title: String
    var message: String
    var actionTitle: String?
    var action: (() -> Void)?
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: symbol).font(.system(size: 44)).foregroundStyle(Theme.brand).accessibilityHidden(true)
            Text(title).font(.headline)
            Text(message).font(.subheadline).foregroundStyle(Theme.textSecondary).multilineTextAlignment(.center)
            if let actionTitle, let action {
                Button(actionTitle, action: action).buttonStyle(PrimaryButtonStyle()).frame(maxWidth: 260)
            }
        }
        .padding(32)
        .frame(maxWidth: .infinity)
    }
}

struct ErrorBanner: View {
    var message: String
    var retry: (() -> Void)?
    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(Theme.warning).accessibilityHidden(true)
            Text(message).font(.subheadline).frame(maxWidth: .infinity, alignment: .leading)
            if let retry { Button("Retry", action: retry).font(.subheadline.bold()) }
        }
        .padding(12)
        .background(Theme.warning.opacity(0.12), in: RoundedRectangle(cornerRadius: Theme.radius))
        .accessibilityElement(children: .combine)
    }
}

struct FlowLayout: Layout {
    var spacing: CGFloat = 8
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, row: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x + s.width > width, x > 0 { x = 0; y += row + spacing; row = 0 }
            x += s.width + spacing
            row = max(row, s.height)
        }
        return CGSize(width: width == .infinity ? x : width, height: y + row)
    }
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, row: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x + s.width > bounds.maxX, x > bounds.minX { x = bounds.minX; y += row + spacing; row = 0 }
            v.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(s))
            x += s.width + spacing
            row = max(row, s.height)
        }
    }
}

struct PaletteDots: View {
    var palette: CharacterRecipe.Palette
    var body: some View {
        HStack(spacing: 4) {
            ForEach([palette.primary, palette.secondary, palette.accent], id: \.self) {
                Circle().fill(Color(hex: $0)).frame(width: 14, height: 14).overlay(Circle().stroke(.white, lineWidth: 1.5))
            }
        }
        .accessibilityHidden(true)
    }
}

struct LoadingOverlay: View {
    var label: String
    var body: some View {
        VStack(spacing: 10) {
            ProgressView().controlSize(.large)
            Text(label).font(.subheadline)
        }
        .padding(24)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: Theme.largeRadius))
        .accessibilityElement(children: .combine)
    }
}
