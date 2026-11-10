import Foundation
import SwiftUI

/// Was in der Menüleiste angezeigt wird.
enum MenuBarMetric: String, CaseIterable, Identifiable {
    case blockTokens
    case todayTokens
    case todayCost
    case monthCost

    var id: String { rawValue }

    func label(_ loc: Loc) -> String {
        switch self {
        case .blockTokens: return loc.metricBlockTokens
        case .todayTokens: return loc.metricTodayTokens
        case .todayCost: return loc.metricTodayCost
        case .monthCost: return loc.metricMonthCost
        }
    }
}

/// Vorberechnete Sicht auf die Daten — wird im Hintergrund erzeugt, damit
/// die Views nichts aggregieren müssen.
struct Snapshot: Sendable {
    var today = Totals()
    var week = Totals()
    var month = Totals()
    var last7Days = Totals()
    var last30Days = Totals()
    var allTime = Totals()

    var activeBlock: UsageBlock?
    var recentBlocks: [UsageBlock] = []
    /// Höchstwert über alle Fenster — Maßstab in der Fenster-Liste.
    var peakBlockTokens = 0
    /// Höchstwert der *abgeschlossenen* Fenster. Referenz für den Balken des
    /// laufenden Fensters, damit dieser nicht sich selbst vergleicht.
    var referenceBlockTokens = 0

    var daily: [Bucket] = []
    var weekly: [Bucket] = []
    var monthly: [Bucket] = []

    var models: [NamedTotals] = []
    var projects: [NamedTotals] = []
    var modelsToday: [NamedTotals] = []

    var firstEntry: Date?
    var lastEntry: Date?
    var entryCount = 0
    var updatedAt = Date()
}

@MainActor
final class UsageStore: ObservableObject {
    /// Eine Instanz für Menüleisten-Panel und optionales Fenster.
    static let shared = UsageStore()

    @Published private(set) var snapshot = Snapshot()
    @Published private(set) var isLoading = true
    @Published private(set) var errorMessage: String?

    @Published var metric: MenuBarMetric {
        didSet { UserDefaults.standard.set(metric.rawValue, forKey: DefaultsKey.menuBarMetric) }
    }
    @Published var showCostInMenu: Bool {
        didSet { UserDefaults.standard.set(showCostInMenu, forKey: DefaultsKey.showCostInMenu) }
    }
    @Published var language: AppLanguage {
        didSet {
            UserDefaults.standard.set(language.rawValue, forKey: DefaultsKey.language)
            // Die Fehlermeldung ist ein fertiger Satz und muss in der neuen
            // Sprache neu erzeugt werden.
            if errorMessage != nil { refresh(force: true) }
        }
    }

    /// Texte und Formate der aktuell gewählten Sprache.
    var loc: Loc { Loc(language: language.resolved) }

    @Published private(set) var launchAtLogin = LoginItem.isEnabled
    @Published private(set) var loginItemError: String?

    private let engine = UsageEngine()
    private var timer: Timer?
    private var isRefreshing = false

    func setLaunchAtLogin(_ enabled: Bool) {
        loginItemError = LoginItem.set(enabled)
        launchAtLogin = LoginItem.isEnabled
    }

    init() {
        let storedMetric = UserDefaults.standard.string(forKey: DefaultsKey.menuBarMetric)
        metric = storedMetric.flatMap(MenuBarMetric.init(rawValue:)) ?? .blockTokens
        showCostInMenu = UserDefaults.standard.object(forKey: DefaultsKey.showCostInMenu) as? Bool ?? false
        let storedLanguage = UserDefaults.standard.string(forKey: DefaultsKey.language)
        language = storedLanguage.flatMap(AppLanguage.init(rawValue:)) ?? .system

        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 10, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.refresh() }
        }
    }

    var transcriptPath: String { engine.transcriptPath }

    func refresh(force: Bool = false) {
        if isRefreshing && !force { return }
        isRefreshing = true

        engine.load { [weak self] snapshot, problem in
            Task { @MainActor in
                guard let self else { return }
                self.snapshot = snapshot
                self.errorMessage = problem.map { self.message(for: $0) }
                self.isLoading = false
                self.isRefreshing = false
            }
        }
    }

    private func message(for problem: LoadProblem) -> String {
        switch problem {
        case .missingDirectory(let path): return loc.noTranscriptDirectory(path: path)
        case .noUsageData: return loc.noUsageData
        }
    }

    // MARK: - Menüleisten-Text

    var menuBarText: String {
        switch metric {
        case .blockTokens:
            return loc.tokens(snapshot.activeBlock?.totals.totalTokens ?? 0)
        case .todayTokens:
            return loc.tokens(snapshot.today.totalTokens)
        case .todayCost:
            return loc.money(snapshot.today.cost)
        case .monthCost:
            return loc.money(snapshot.month.cost)
        }
    }

    var menuBarSecondaryText: String? {
        guard showCostInMenu else { return nil }
        switch metric {
        case .blockTokens:
            return loc.money(snapshot.activeBlock?.totals.cost ?? 0)
        case .todayTokens:
            return loc.money(snapshot.today.cost)
        case .todayCost, .monthCost:
            return nil
        }
    }
}
