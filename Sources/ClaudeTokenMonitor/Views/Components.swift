import SwiftUI

// MARK: - Kachel für eine Kennzahl

struct StatTile: View {
    let title: String
    let value: String
    var subtitle: String?
    var accent: Color = .accentColor

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title)
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(.secondary)
                .textCase(.uppercase)
            Text(value)
                .font(.system(size: 19, weight: .semibold, design: .rounded))
                .foregroundStyle(accent)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            if let subtitle {
                Text(subtitle)
                    .font(.system(size: 10))
                    .foregroundStyle(.tertiary)
                    .lineLimit(1)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.vertical, 8)
        .padding(.horizontal, 10)
        .background(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(Color.primary.opacity(0.05))
        )
    }
}

// MARK: - Fortschrittsbalken

struct UsageBar: View {
    let fraction: Double
    var color: Color = .accentColor
    var height: CGFloat = 6

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule().fill(Color.primary.opacity(0.1))
                Capsule()
                    .fill(color.gradient)
                    .frame(width: max(2, geo.size.width * min(1, max(0, fraction))))
            }
        }
        .frame(height: height)
    }
}

// MARK: - Balkendiagramm über Buckets

struct BarChart: View {
    let buckets: [Bucket]
    let loc: Loc
    let value: (Totals) -> Double
    var formatter: (Double) -> String
    var color: Color = .accentColor
    var height: CGFloat = 96
    /// Jedes n-te Label anzeigen, damit es bei 30 Tagen nicht überläuft.
    var labelStride: Int = 1

    private var maxValue: Double {
        max(1, buckets.map { value($0.totals) }.max() ?? 1)
    }

    var body: some View {
        VStack(spacing: 4) {
            HStack(alignment: .bottom, spacing: 3) {
                ForEach(Array(buckets.enumerated()), id: \.element.id) { _, bucket in
                    let v = value(bucket.totals)
                    VStack(spacing: 0) {
                        Spacer(minLength: 0)
                        RoundedRectangle(cornerRadius: 2, style: .continuous)
                            .fill(v > 0 ? AnyShapeStyle(color.gradient) : AnyShapeStyle(Color.primary.opacity(0.08)))
                            .frame(height: max(v > 0 ? 2 : 1, height * (v / maxValue)))
                    }
                    .frame(maxWidth: .infinity)
                    .help("\(loc.label(for: bucket)): \(formatter(v))")
                }
            }
            .frame(height: height)

            // Labels werden mittig über ihrem Balken platziert und dürfen die
            // Balkenbreite überlappen — sonst würde "08.08." bei 30 Tagen
            // auf "0…" abgeschnitten.
            GeometryReader { geo in
                let slot = geo.size.width / CGFloat(max(1, buckets.count))
                ForEach(Array(buckets.enumerated()), id: \.element.id) { index, bucket in
                    if index % labelStride == 0 {
                        Text(loc.label(for: bucket))
                            .font(.system(size: 8))
                            .foregroundStyle(.tertiary)
                            .fixedSize()
                            .position(x: slot * (CGFloat(index) + 0.5), y: 6)
                    }
                }
            }
            .frame(height: 12)
        }
    }
}

// MARK: - Zeile mit Balken (Modelle, Projekte)

struct RankedRow: View {
    let name: String
    let tokens: String
    let cost: String
    let subtitle: String
    let fraction: Double
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack(spacing: 6) {
                Text(name)
                    .font(.system(size: 11, weight: .medium))
                    .lineLimit(1)
                    .truncationMode(.middle)
                Spacer(minLength: 4)
                Text(tokens)
                    .font(.system(size: 11, weight: .semibold, design: .rounded))
                    .monospacedDigit()
                Text(cost)
                    .font(.system(size: 10))
                    .foregroundStyle(.secondary)
                    .monospacedDigit()
                    .frame(width: 54, alignment: .trailing)
            }
            UsageBar(fraction: fraction, color: color, height: 4)
            Text(subtitle)
                .font(.system(size: 9))
                .foregroundStyle(.tertiary)
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Token-Aufschlüsselung

struct TokenBreakdown: View {
    let totals: Totals
    let loc: Loc

    private var rows: [(String, Int, Color)] {
        [
            (loc.input, totals.input, .blue),
            (loc.output, totals.output, .orange),
            (loc.cacheWrite, totals.cacheWrite, .purple),
            (loc.cacheRead, totals.cacheRead, .teal),
        ]
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            // Gestapelter Anteilsbalken
            GeometryReader { geo in
                HStack(spacing: 1) {
                    ForEach(rows, id: \.0) { row in
                        let fraction = totals.totalTokens > 0
                            ? Double(row.1) / Double(totals.totalTokens) : 0
                        Rectangle()
                            .fill(row.2.gradient)
                            .frame(width: max(0, geo.size.width * fraction))
                    }
                }
                .clipShape(Capsule())
            }
            .frame(height: 6)

            ForEach(rows, id: \.0) { row in
                HStack(spacing: 6) {
                    Circle().fill(row.2).frame(width: 6, height: 6)
                    Text(row.0)
                        .font(.system(size: 10))
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text(loc.exact(row.1))
                        .font(.system(size: 10, weight: .medium))
                        .monospacedDigit()
                    Text(loc.percent(totals.totalTokens > 0
                                     ? Double(row.1) / Double(totals.totalTokens)
                                     : 0))
                        .font(.system(size: 9))
                        .foregroundStyle(.tertiary)
                        .monospacedDigit()
                        .frame(width: 34, alignment: .trailing)
                }
            }
        }
    }
}

// MARK: - Abschnittsüberschrift

struct SectionHeader: View {
    let title: String
    var trailing: String?

    var body: some View {
        HStack {
            Text(title)
                .font(.system(size: 11, weight: .semibold))
            Spacer()
            if let trailing {
                Text(trailing)
                    .font(.system(size: 10))
                    .foregroundStyle(.secondary)
            }
        }
    }
}
