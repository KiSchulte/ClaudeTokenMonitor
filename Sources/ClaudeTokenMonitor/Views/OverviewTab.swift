import SwiftUI

struct OverviewTab: View {
    @EnvironmentObject var store: UsageStore

    private var snap: Snapshot { store.snapshot }
    private var loc: Loc { store.loc }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                blockCard
                periodTiles
                todayBreakdown
                topModelsToday
                sparkline
            }
            .padding(12)
        }
    }

    // MARK: - Aktuelles 5-Stunden-Fenster

    private var blockCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let block = snap.activeBlock {
                HStack(alignment: .firstTextBaseline) {
                    VStack(alignment: .leading, spacing: 1) {
                        Text(loc.currentWindowTitle)
                            .font(.system(size: 10, weight: .medium))
                            .foregroundStyle(.secondary)
                            .textCase(.uppercase)
                        Text("\(loc.time(block.start)) – \(loc.time(block.end))")
                            .font(.system(size: 10))
                            .foregroundStyle(.tertiary)
                    }
                    Spacer()
                    VStack(alignment: .trailing, spacing: 1) {
                        Label(loc.duration(block.remaining), systemImage: "timer")
                            .font(.system(size: 10, weight: .medium))
                            .foregroundStyle(.orange)
                        Text(loc.untilReset)
                            .font(.system(size: 9))
                            .foregroundStyle(.tertiary)
                    }
                }

                HStack(alignment: .lastTextBaseline, spacing: 8) {
                    Text(loc.tokens(block.totals.totalTokens))
                        .font(.system(size: 30, weight: .bold, design: .rounded))
                    Text(loc.tokens)
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text(loc.money(block.totals.cost))
                        .font(.system(size: 15, weight: .semibold, design: .rounded))
                        .foregroundStyle(.secondary)
                }

                // Referenz ist das stärkste *abgeschlossene* Fenster — echte
                // Abo-Limits stehen lokal nicht zur Verfügung.
                if snap.referenceBlockTokens > 0 {
                    let reference = Double(snap.referenceBlockTokens)
                    let fraction = Double(block.totals.totalTokens) / reference
                    UsageBar(fraction: fraction, color: barColor(fraction))
                    HStack {
                        let percent = loc.percent(fraction)
                        let value = loc.tokens(snap.referenceBlockTokens)
                        Text(fraction > 1
                             ? loc.recordComparison(percent: percent, reference: value)
                             : loc.peakComparison(percent: percent, reference: value))
                        Spacer()
                        Text(loc.burnRate(loc.tokens(Int(block.burnRate))))
                    }
                    .font(.system(size: 9))
                    .foregroundStyle(.tertiary)
                }

                HStack(spacing: 6) {
                    metaChip(loc.projection, loc.tokens(block.projectedTokens))
                    metaChip(loc.requests, loc.exact(block.totals.requests))
                    if !block.models.isEmpty {
                        metaChip(loc.models, block.models.joined(separator: ", "))
                    }
                }
            } else {
                HStack(spacing: 10) {
                    Image(systemName: "moon.zzz.fill")
                        .font(.system(size: 20))
                        .foregroundStyle(.tertiary)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(loc.noActiveWindow)
                            .font(.system(size: 12, weight: .medium))
                        if let last = snap.recentBlocks.first {
                            Text(loc.lastWindowInfo(
                                tokens: loc.tokens(last.totals.totalTokens),
                                ended: loc.relative(last.end)))
                                .font(.system(size: 10))
                                .foregroundStyle(.secondary)
                        } else {
                            Text(loc.noActivityRecorded)
                                .font(.system(size: 10))
                                .foregroundStyle(.secondary)
                        }
                    }
                    Spacer()
                }
            }
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .fill(Color.accentColor.opacity(0.08))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .strokeBorder(Color.accentColor.opacity(0.18), lineWidth: 1)
        )
    }

    private func barColor(_ fraction: Double) -> Color {
        if fraction >= 0.9 { return .red }
        if fraction >= 0.65 { return .orange }
        return .accentColor
    }

    private func metaChip(_ label: String, _ value: String) -> some View {
        HStack(spacing: 3) {
            Text(label)
                .foregroundStyle(.tertiary)
            Text(value)
                .foregroundStyle(.secondary)
                .fontWeight(.medium)
        }
        .font(.system(size: 9))
        .padding(.horizontal, 6)
        .padding(.vertical, 3)
        .background(Capsule().fill(Color.primary.opacity(0.06)))
        .lineLimit(1)
    }

    // MARK: - Zeitraum-Kacheln

    private var periodTiles: some View {
        VStack(spacing: 6) {
            HStack(spacing: 6) {
                StatTile(
                    title: loc.today,
                    value: loc.tokens(snap.today.totalTokens),
                    subtitle: loc.costAndRequests(
                        cost: loc.money(snap.today.cost),
                        requests: snap.today.requests)
                )
                StatTile(
                    title: loc.last7Days,
                    value: loc.tokens(snap.last7Days.totalTokens),
                    subtitle: loc.money(snap.last7Days.cost),
                    accent: .purple
                )
            }
            HStack(spacing: 6) {
                StatTile(
                    title: loc.thisWeek,
                    value: loc.tokens(snap.week.totalTokens),
                    subtitle: loc.money(snap.week.cost),
                    accent: .teal
                )
                StatTile(
                    title: loc.thisMonth,
                    value: loc.tokens(snap.month.totalTokens),
                    subtitle: loc.money(snap.month.cost),
                    accent: .indigo
                )
            }
        }
    }

    // MARK: - Aufschlüsselung heute

    private var todayBreakdown: some View {
        VStack(alignment: .leading, spacing: 7) {
            SectionHeader(
                title: loc.compositionToday,
                trailing: loc.tokensSuffix(loc.exact(snap.today.totalTokens))
            )
            TokenBreakdown(totals: snap.today, loc: loc)
        }
        .padding(10)
        .background(
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(Color.primary.opacity(0.04))
        )
    }

    // MARK: - Modelle heute

    @ViewBuilder
    private var topModelsToday: some View {
        if !snap.modelsToday.isEmpty {
            VStack(alignment: .leading, spacing: 6) {
                SectionHeader(title: loc.modelsToday)
                let maxTokens = snap.modelsToday.first?.totals.totalTokens ?? 1
                ForEach(snap.modelsToday.prefix(4)) { item in
                    RankedRow(
                        name: item.name,
                        tokens: loc.tokens(item.totals.totalTokens),
                        cost: loc.money(item.totals.cost),
                        subtitle: loc.requestsAndTokens(
                            requests: item.totals.requests,
                            tokens: item.totals.totalTokens),
                        fraction: Double(item.totals.totalTokens) / Double(max(1, maxTokens)),
                        color: .orange
                    )
                }
            }
        }
    }

    // MARK: - Kleiner Verlauf

    @ViewBuilder
    private var sparkline: some View {
        let last14 = Array(snap.daily.suffix(14))
        if !last14.isEmpty {
            VStack(alignment: .leading, spacing: 6) {
                SectionHeader(
                    title: loc.last14Days,
                    trailing: loc.tokens(last14.reduce(0) { $0 + $1.totals.totalTokens })
                )
                BarChart(
                    buckets: last14,
                    loc: loc,
                    value: { Double($0.totalTokens) },
                    formatter: { loc.tokensSuffix(loc.tokens(Int($0))) },
                    color: .blue,
                    height: 60,
                    labelStride: 2
                )
            }
        }
    }
}
