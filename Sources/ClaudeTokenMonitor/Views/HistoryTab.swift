import SwiftUI

struct HistoryTab: View {
    @EnvironmentObject var store: UsageStore

    enum Range: String, CaseIterable, Identifiable {
        case days, weeks, months
        var id: String { rawValue }
        func title(_ loc: Loc) -> String {
            switch self {
            case .days: return loc.range30Days
            case .weeks: return loc.range12Weeks
            case .months: return loc.range6Months
            }
        }
    }

    enum Metric: String, CaseIterable, Identifiable {
        case tokens, cost, requests
        var id: String { rawValue }
        func title(_ loc: Loc) -> String {
            switch self {
            case .tokens: return loc.metricTokens
            case .cost: return loc.metricCost
            case .requests: return loc.metricRequests
            }
        }
    }

    @State private var range: Range = .days
    @State private var metric: Metric = .tokens

    private var loc: Loc { store.loc }

    private var buckets: [Bucket] {
        switch range {
        case .days: return store.snapshot.daily
        case .weeks: return store.snapshot.weekly
        case .months: return store.snapshot.monthly
        }
    }

    private var labelStride: Int {
        switch range {
        case .days: return 3
        case .weeks: return 1
        case .months: return 1
        }
    }

    private func value(_ t: Totals) -> Double {
        switch metric {
        case .tokens: return Double(t.totalTokens)
        case .cost: return t.cost
        case .requests: return Double(t.requests)
        }
    }

    private func format(_ v: Double) -> String {
        switch metric {
        case .tokens: return loc.tokensSuffix(loc.tokens(Int(v)))
        case .cost: return loc.money(v)
        case .requests: return loc.requestCount(Int(v))
        }
    }

    private var color: Color {
        switch metric {
        case .tokens: return .blue
        case .cost: return .green
        case .requests: return .purple
        }
    }

    private var sum: Totals {
        buckets.reduce(Totals()) { $0 + $1.totals }
    }

    var body: some View {
        VStack(spacing: 0) {
            VStack(spacing: 8) {
                Picker("", selection: $range) {
                    ForEach(Range.allCases) { Text($0.title(loc)).tag($0) }
                }
                .pickerStyle(.segmented)
                .labelsHidden()

                Picker("", selection: $metric) {
                    ForEach(Metric.allCases) { Text($0.title(loc)).tag($0) }
                }
                .pickerStyle(.segmented)
                .labelsHidden()

                BarChart(
                    buckets: buckets,
                    loc: loc,
                    value: value,
                    formatter: format,
                    color: color,
                    height: 110,
                    labelStride: labelStride
                )
                .padding(.top, 2)

                HStack(spacing: 6) {
                    StatTile(
                        title: loc.sum,
                        value: loc.tokens(sum.totalTokens),
                        subtitle: loc.money(sum.cost)
                    )
                    StatTile(
                        title: loc.averagePerPeriod,
                        value: loc.tokens(buckets.isEmpty ? 0 : sum.totalTokens / buckets.count),
                        subtitle: buckets.isEmpty
                            ? loc.emptyValue
                            : loc.money(sum.cost / Double(buckets.count)),
                        accent: .teal
                    )
                    StatTile(
                        title: loc.peak,
                        value: loc.tokens(buckets.map(\.totals.totalTokens).max() ?? 0),
                        subtitle: peakLabel,
                        accent: .orange
                    )
                }
            }
            .padding(12)

            Divider()

            List {
                ForEach(buckets.reversed()) { bucket in
                    HStack(spacing: 8) {
                        Text(loc.label(for: bucket))
                            .font(.system(size: 11, weight: .medium))
                            .frame(width: 62, alignment: .leading)
                        UsageBar(
                            fraction: relativeFraction(bucket),
                            color: color,
                            height: 5
                        )
                        Text(loc.tokens(bucket.totals.totalTokens))
                            .font(.system(size: 11, design: .rounded))
                            .monospacedDigit()
                            .frame(width: 56, alignment: .trailing)
                        Text(loc.money(bucket.totals.cost))
                            .font(.system(size: 10))
                            .foregroundStyle(.secondary)
                            .monospacedDigit()
                            .frame(width: 56, alignment: .trailing)
                    }
                    .padding(.vertical, 1)
                    .listRowSeparator(.hidden)
                }
            }
            .listStyle(.plain)
            .scrollContentBackground(.hidden)
        }
    }

    private var peakLabel: String {
        guard let peak = buckets.max(by: { $0.totals.totalTokens < $1.totals.totalTokens }),
              peak.totals.totalTokens > 0
        else { return loc.emptyValue }
        return loc.label(for: peak)
    }

    private func relativeFraction(_ bucket: Bucket) -> Double {
        let maxValue = buckets.map { value($0.totals) }.max() ?? 1
        guard maxValue > 0 else { return 0 }
        return value(bucket.totals) / maxValue
    }
}
