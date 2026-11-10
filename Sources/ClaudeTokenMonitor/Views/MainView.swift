import AppKit
import SwiftUI

enum Tab: String, CaseIterable, Identifiable {
    case overview, history, blocks, models, projects

    var id: String { rawValue }

    func title(_ loc: Loc) -> String {
        switch self {
        case .overview: return loc.tabOverview
        case .history: return loc.tabHistory
        case .blocks: return loc.tabBlocks
        case .models: return loc.tabModels
        case .projects: return loc.tabProjects
        }
    }

    var icon: String {
        switch self {
        case .overview: return "gauge.with.needle"
        case .history: return "chart.bar.fill"
        case .blocks: return "clock.fill"
        case .models: return "cpu"
        case .projects: return "folder.fill"
        }
    }
}

struct MainView: View {
    @EnvironmentObject var store: UsageStore
    @State private var tab: Tab = .overview

    private var loc: Loc { store.loc }

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            tabBar
            Divider()

            Group {
                if store.isLoading {
                    loadingState
                } else if let error = store.errorMessage, store.snapshot.entryCount == 0 {
                    emptyState(error)
                } else {
                    switch tab {
                    case .overview: OverviewTab()
                    case .history: HistoryTab()
                    case .blocks: BlocksTab()
                    case .models: BreakdownTab(mode: .models)
                    case .projects: BreakdownTab(mode: .projects)
                    }
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            Divider()
            FooterView()
        }
        .frame(width: 470, height: 630)
        .onAppear { store.refresh() }
    }

    private var header: some View {
        HStack(spacing: 8) {
            Image(systemName: "sparkles")
                .foregroundStyle(.orange)
            VStack(alignment: .leading, spacing: 0) {
                Text(loc.appName)
                    .font(.system(size: 12, weight: .semibold))
                Text(store.snapshot.entryCount > 0
                     ? loc.headerSubtitle(
                        requests: store.snapshot.entryCount,
                        updated: store.snapshot.updatedAt)
                     : loc.loadingTranscripts)
                    .font(.system(size: 9))
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Button {
                store.refresh()
            } label: {
                Image(systemName: "arrow.clockwise")
            }
            .buttonStyle(.borderless)
            .help(loc.refreshTooltip)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 9)
    }

    private var tabBar: some View {
        HStack(spacing: 2) {
            ForEach(Tab.allCases) { item in
                Button {
                    tab = item
                } label: {
                    VStack(spacing: 2) {
                        Image(systemName: item.icon).font(.system(size: 11))
                        Text(item.title(loc)).font(.system(size: 9))
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 5)
                    .background(
                        RoundedRectangle(cornerRadius: 6, style: .continuous)
                            .fill(tab == item ? Color.accentColor.opacity(0.18) : .clear)
                    )
                    .foregroundStyle(tab == item ? Color.accentColor : Color.secondary)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 5)
    }

    private var loadingState: some View {
        VStack(spacing: 8) {
            ProgressView()
            Text(loc.readingTranscripts)
                .font(.system(size: 11))
                .foregroundStyle(.secondary)
        }
    }

    private func emptyState(_ message: String) -> some View {
        VStack(spacing: 10) {
            Image(systemName: "tray")
                .font(.system(size: 28))
                .foregroundStyle(.tertiary)
            Text(message)
                .font(.system(size: 11))
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)
            Text(store.transcriptPath)
                .font(.system(size: 9, design: .monospaced))
                .foregroundStyle(.tertiary)
                .textSelection(.enabled)
        }
        .padding(24)
    }
}

// MARK: - Fußzeile

struct FooterView: View {
    @EnvironmentObject var store: UsageStore

    private var loc: Loc { store.loc }

    var body: some View {
        HStack(spacing: 8) {
            Menu {
                Picker(loc.languageSetting, selection: $store.language) {
                    ForEach(AppLanguage.allCases) { language in
                        Text(language.label(loc)).tag(language)
                    }
                }
                .pickerStyle(.inline)

                Divider()

                Picker(loc.menuBarShows, selection: $store.metric) {
                    ForEach(MenuBarMetric.allCases) { m in
                        Text(m.label(loc)).tag(m)
                    }
                }
                .pickerStyle(.inline)

                Divider()
                Toggle(loc.costAlsoInMenuBar, isOn: $store.showCostInMenu)
                Divider()
                Toggle(loc.launchAtLogin, isOn: Binding(
                    get: { store.launchAtLogin },
                    set: { store.setLaunchAtLogin($0) }
                ))
                if let error = store.loginItemError {
                    Text(error).font(.system(size: 9))
                }
                Divider()
                Button(loc.showSourceInFinder) {
                    NSWorkspace.shared.selectFile(
                        nil, inFileViewerRootedAtPath: store.transcriptPath
                    )
                }
            } label: {
                Label(loc.display, systemImage: "slider.horizontal.3")
                    .font(.system(size: 10))
            }
            .menuStyle(.borderlessButton)
            .fixedSize()

            Spacer()

            if let first = store.snapshot.firstEntry, let last = store.snapshot.lastEntry {
                Text("\(loc.day(first)) – \(loc.day(last))")
                    .font(.system(size: 9))
                    .foregroundStyle(.tertiary)
            }

            Button(loc.quit) { NSApplication.shared.terminate(nil) }
                .buttonStyle(.borderless)
                .font(.system(size: 10))
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 7)
    }
}
