import SwiftUI

/// Historie der 5-Stunden-Fenster — das ist die Einheit, in der die
/// Claude-Abos ihre Limits zurücksetzen.
struct BlocksTab: View {
    @EnvironmentObject var store: UsageStore

    private var loc: Loc { store.loc }
    private var blocks: [UsageBlock] { store.snapshot.recentBlocks }
    private var peak: Int { max(1, store.snapshot.peakBlockTokens) }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(loc.recentWindows)
                    .font(.system(size: 11, weight: .semibold))
                Spacer()
                Text(loc.barRelativeToMax(loc.tokens(peak)))
                    .font(.system(size: 9))
                    .foregroundStyle(.tertiary)
            }
            .padding(.horizontal, 12)
            .padding(.top, 10)
            .padding(.bottom, 8)

            if blocks.isEmpty {
                Spacer()
                Text(loc.noBlocksRecorded)
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                Spacer()
            } else {
                List {
                    ForEach(blocks) { block in
                        row(block)
                            .listRowSeparator(.hidden)
                    }
                }
                .listStyle(.plain)
                .scrollContentBackground(.hidden)
            }
        }
    }

    private func row(_ block: UsageBlock) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 6) {
                if block.isActive {
                    Circle().fill(Color.green).frame(width: 6, height: 6)
                }
                Text("\(loc.dayTime(block.start)) – \(loc.time(block.end))")
                    .font(.system(size: 11, weight: block.isActive ? .semibold : .regular))
                Spacer()
                Text(loc.tokens(block.totals.totalTokens))
                    .font(.system(size: 11, weight: .semibold, design: .rounded))
                    .monospacedDigit()
                Text(loc.money(block.totals.cost))
                    .font(.system(size: 10))
                    .foregroundStyle(.secondary)
                    .monospacedDigit()
                    .frame(width: 54, alignment: .trailing)
            }

            UsageBar(
                fraction: Double(block.totals.totalTokens) / Double(peak),
                color: block.isActive ? .green : .accentColor,
                height: 5
            )

            HStack(spacing: 8) {
                Text(loc.requestCount(block.totals.requests))
                if block.isActive {
                    Text(loc.stillRemaining(loc.duration(block.remaining)))
                        .foregroundStyle(.orange)
                }
                if !block.models.isEmpty {
                    Text(block.models.joined(separator: ", "))
                        .lineLimit(1)
                        .truncationMode(.tail)
                }
                Spacer()
            }
            .font(.system(size: 9))
            .foregroundStyle(.tertiary)
        }
        .padding(.vertical, 3)
    }
}

// MARK: - Modelle / Projekte

struct BreakdownTab: View {
    enum Mode {
        case models, projects

        func title(_ loc: Loc) -> String {
            switch self {
            case .models: return loc.tabModels
            case .projects: return loc.tabProjects
            }
        }

        var color: Color {
            switch self {
            case .models: return .orange
            case .projects: return .teal
            }
        }
    }

    @EnvironmentObject var store: UsageStore
    let mode: Mode

    private var loc: Loc { store.loc }

    private var items: [NamedTotals] {
        switch mode {
        case .models: return store.snapshot.models
        case .projects: return store.snapshot.projects
        }
    }

    private var total: Totals {
        items.reduce(Totals()) { $0 + $1.totals }
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 6) {
                StatTile(
                    title: loc.total,
                    value: loc.tokens(total.totalTokens),
                    subtitle: loc.money(total.cost)
                )
                StatTile(
                    title: mode.title(loc),
                    value: "\(items.count)",
                    subtitle: loc.requestCount(total.requests),
                    accent: mode.color
                )
            }
            .padding(12)

            Divider()

            if items.isEmpty {
                Spacer()
                Text(loc.noData)
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                Spacer()
            } else {
                List {
                    let maxTokens = items.first?.totals.totalTokens ?? 1
                    ForEach(items) { item in
                        RankedRow(
                            name: item.name,
                            tokens: loc.tokens(item.totals.totalTokens),
                            cost: loc.money(item.totals.cost),
                            subtitle: loc.requestsAndTokens(
                                requests: item.totals.requests,
                                tokens: item.totals.totalTokens),
                            fraction: Double(item.totals.totalTokens) / Double(max(1, maxTokens)),
                            color: mode.color
                        )
                        .listRowSeparator(.hidden)
                    }
                }
                .listStyle(.plain)
                .scrollContentBackground(.hidden)
            }
        }
    }
}
