import Foundation

/// UserDefaults-Schlüssel. Bewusst außerhalb von `UsageStore`, damit auch der
/// nicht-MainActor-Code (Kommandozeilen-Modi) sie lesen kann.
enum DefaultsKey {
    static let language = "appLanguage"
    static let menuBarMetric = "menuBarMetric"
    static let showCostInMenu = "showCostInMenu"
}

// MARK: - Spracheinstellung

/// Vom Benutzer gewählte Sprache. `system` folgt der macOS-Systemsprache.
enum AppLanguage: String, CaseIterable, Identifiable {
    case system, german, english

    var id: String { rawValue }

    var resolved: Language {
        switch self {
        case .german: return .de
        case .english: return .en
        case .system:
            let preferred = Locale.preferredLanguages.first ?? "en"
            return preferred.hasPrefix("de") ? .de : .en
        }
    }

    /// Menütext — die Sprachnamen bleiben in ihrer eigenen Sprache stehen,
    /// nur "System" wird übersetzt.
    func label(_ loc: Loc) -> String {
        switch self {
        case .system: return "\(loc.systemLanguage) (\(resolved.nativeName))"
        case .german: return "Deutsch"
        case .english: return "English"
        }
    }
}

enum Language {
    case de, en

    var nativeName: String {
        switch self {
        case .de: return "Deutsch"
        case .en: return "English"
        }
    }

    /// Für Englisch bewusst en_GB: 24-Stunden-Uhr und tagesführende Datumsangaben
    /// halten das Layout kompakt und näher an der deutschen Variante.
    var locale: Locale {
        switch self {
        case .de: return Locale(identifier: "de_DE")
        case .en: return Locale(identifier: "en_GB")
        }
    }
}

// MARK: - Texte und Formate

/// Bündelt Übersetzungen und sprachabhängige Zahlen-/Datumsformate.
/// Wird vom Store gehalten und in die Views gegeben.
struct Loc {
    let language: Language

    init(language: Language) {
        self.language = language
    }

    /// Kurzhelfer: erst Deutsch, dann Englisch.
    private func s(_ de: String, _ en: String) -> String {
        language == .de ? de : en
    }

    private var locale: Locale { language.locale }

    // MARK: Tabs und Rahmen

    var appName: String { "Claude Token Monitor" }
    var tabOverview: String { s("Übersicht", "Overview") }
    var tabHistory: String { s("Verlauf", "History") }
    var tabBlocks: String { s("Fenster", "Windows") }
    var tabModels: String { s("Modelle", "Models") }
    var tabProjects: String { s("Projekte", "Projects") }

    func headerSubtitle(requests: Int, updated: Date) -> String {
        s("\(exact(requests)) Anfragen · Stand \(relative(updated))",
          "\(exact(requests)) requests · updated \(relative(updated))")
    }
    var loadingTranscripts: String { s("Lade Transkripte …", "Loading transcripts …") }
    var readingTranscripts: String { s("Transkripte werden gelesen …", "Reading transcripts …") }
    var refreshTooltip: String { s("Jetzt neu einlesen", "Reload now") }

    // MARK: Leer- und Fehlerzustände

    func noTranscriptDirectory(path: String) -> String {
        s("Kein Transkript-Verzeichnis gefunden unter \(path)",
          "No transcript directory found at \(path)")
    }
    var noUsageData: String {
        s("Keine Usage-Daten in den Transkripten gefunden.",
          "No usage data found in the transcripts.")
    }
    var noData: String { s("Keine Daten.", "No data.") }
    var noBlocksRecorded: String {
        s("Noch keine Fenster aufgezeichnet.", "No windows recorded yet.")
    }
    var noActivityRecorded: String {
        s("Noch keine Aktivität aufgezeichnet.", "No activity recorded yet.")
    }

    // MARK: Fußzeile

    var display: String { s("Anzeige", "Display") }
    var menuBarShows: String { s("Menüleiste zeigt", "Menu bar shows") }
    var costAlsoInMenuBar: String {
        s("Kosten zusätzlich in Menüleiste", "Also show cost in menu bar")
    }
    var launchAtLogin: String { s("Bei Anmeldung starten", "Launch at login") }
    var showSourceInFinder: String {
        s("Datenquelle im Finder zeigen", "Show data source in Finder")
    }
    var quit: String { s("Beenden", "Quit") }
    var languageSetting: String { s("Sprache", "Language") }
    var systemLanguage: String { s("Systemsprache", "System language") }

    // MARK: Menüleisten-Kennzahlen

    var metricBlockTokens: String { s("Tokens im 5-Std-Fenster", "Tokens in 5-hour window") }
    var metricTodayTokens: String { s("Tokens heute", "Tokens today") }
    var metricTodayCost: String { s("Kosten heute", "Cost today") }
    var metricMonthCost: String { s("Kosten diesen Monat", "Cost this month") }

    // MARK: Übersicht

    var currentWindowTitle: String { s("Aktuelles 5-Std-Fenster", "Current 5-hour window") }
    var untilReset: String { s("bis Reset", "until reset") }
    var tokens: String { s("Tokens", "Tokens") }
    var requests: String { s("Anfragen", "Requests") }
    var requestsShort: String { s("Anfr.", "req.") }
    var projection: String { s("Hochrechnung", "Projection") }
    var models: String { s("Modelle", "Models") }
    var noActiveWindow: String { s("Kein aktives 5-Std-Fenster", "No active 5-hour window") }

    func recordComparison(percent: String, reference: String) -> String {
        s("Rekord — \(percent) deines bisherigen Höchstwerts (\(reference))",
          "Record — \(percent) of your previous peak (\(reference))")
    }
    func peakComparison(percent: String, reference: String) -> String {
        s("\(percent) deines stärksten Fensters (\(reference))",
          "\(percent) of your strongest window (\(reference))")
    }
    func burnRate(_ value: String) -> String {
        s("Rate: \(value)/Min", "Rate: \(value)/min")
    }
    func lastWindowInfo(tokens: String, ended: String) -> String {
        s("Letztes Fenster: \(tokens) Tokens, endete \(ended)",
          "Last window: \(tokens) tokens, ended \(ended)")
    }

    var today: String { s("Heute", "Today") }
    var last7Days: String { s("Letzte 7 Tage", "Last 7 days") }
    var thisWeek: String { s("Diese Woche", "This week") }
    var thisMonth: String { s("Dieser Monat", "This month") }
    var compositionToday: String { s("Zusammensetzung heute", "Composition today") }
    var modelsToday: String { s("Modelle heute", "Models today") }
    var last14Days: String { s("Letzte 14 Tage", "Last 14 days") }

    func tokensSuffix(_ value: String) -> String { "\(value) \(tokens)" }
    func costAndRequests(cost: String, requests: Int) -> String {
        "\(cost) · \(requests) \(requestsShort)"
    }

    // MARK: Token-Arten

    var input: String { s("Input", "Input") }
    var output: String { s("Output", "Output") }
    var cacheWrite: String { s("Cache-Write", "Cache write") }
    var cacheRead: String { s("Cache-Read", "Cache read") }

    // MARK: Verlauf

    var range30Days: String { s("30 Tage", "30 days") }
    var range12Weeks: String { s("12 Wochen", "12 weeks") }
    var range6Months: String { s("6 Monate", "6 months") }
    var metricTokens: String { s("Tokens", "Tokens") }
    var metricCost: String { s("Kosten", "Cost") }
    var metricRequests: String { s("Anfragen", "Requests") }
    var sum: String { s("Summe", "Total") }
    var averagePerPeriod: String { s("Ø pro Periode", "Avg per period") }
    var peak: String { s("Spitze", "Peak") }
    var emptyValue: String { "–" }

    // MARK: Fenster

    var recentWindows: String { s("Letzte 5-Std-Fenster", "Recent 5-hour windows") }
    func barRelativeToMax(_ value: String) -> String {
        s("Balken relativ zum Maximum (\(value))",
          "Bars relative to maximum (\(value))")
    }
    func stillRemaining(_ duration: String) -> String {
        s("noch \(duration)", "\(duration) left")
    }
    var total: String { s("Gesamt", "Total") }

    func requestsAndTokens(requests: Int, tokens: Int) -> String {
        s("\(exact(requests)) Anfragen · \(exact(tokens)) Tokens",
          "\(exact(requests)) requests · \(exact(tokens)) tokens")
    }
    func requestCount(_ count: Int) -> String {
        s("\(count) Anfragen", "\(count) requests")
    }

    // MARK: Autostart-Status

    var loginActive: String { s("aktiv", "enabled") }
    var loginNotRegistered: String { s("nicht registriert", "not registered") }
    var loginRequiresApproval: String {
        s("wartet auf Freigabe in den Systemeinstellungen",
          "waiting for approval in System Settings")
    }
    var loginNotFound: String { s("nicht gefunden", "not found") }
    var loginUnknown: String { s("unbekannt", "unknown") }

    // MARK: Zahlenformate

    private var decimalFormatter: NumberFormatter {
        let f = NumberFormatter()
        f.locale = locale
        f.numberStyle = .decimal
        f.maximumFractionDigits = 0
        return f
    }

    private var compactFormatter: NumberFormatter {
        let f = NumberFormatter()
        f.locale = locale
        f.numberStyle = .decimal
        f.minimumFractionDigits = 1
        f.maximumFractionDigits = 1
        return f
    }

    /// 1.234 / 45K / 1,2M — Dezimaltrennzeichen folgt der Sprache.
    func tokens(_ value: Int) -> String {
        let v = Double(value)
        if v >= 1_000_000 {
            return (compactFormatter.string(from: NSNumber(value: v / 1_000_000)) ?? "0") + "M"
        }
        if v >= 10_000 {
            return (decimalFormatter.string(from: NSNumber(value: (v / 1000).rounded())) ?? "0") + "K"
        }
        if v >= 1_000 {
            return (compactFormatter.string(from: NSNumber(value: v / 1000)) ?? "0") + "K"
        }
        return decimalFormatter.string(from: NSNumber(value: value)) ?? "0"
    }

    /// Vollständige Zahl mit Tausendertrennzeichen.
    func exact(_ value: Int) -> String {
        decimalFormatter.string(from: NSNumber(value: value)) ?? "0"
    }

    /// Immer USD — nur die Schreibweise folgt der Sprache.
    func money(_ value: Double) -> String {
        let f = NumberFormatter()
        f.locale = locale
        f.numberStyle = .currency
        f.currencyCode = "USD"
        f.currencySymbol = "$"
        f.maximumFractionDigits = value < 10 ? 2 : (value < 1000 ? 1 : 0)
        f.minimumFractionDigits = value < 10 ? 2 : 0
        return f.string(from: NSNumber(value: value)) ?? "$0"
    }

    func percent(_ fraction: Double) -> String {
        let f = NumberFormatter()
        f.locale = locale
        f.numberStyle = .percent
        f.maximumFractionDigits = 0
        return f.string(from: NSNumber(value: fraction)) ?? s("0 %", "0%")
    }

    // MARK: Zeitformate

    /// "2 Std 14 Min" / "2 h 14 min"
    func duration(_ interval: TimeInterval) -> String {
        let total = Int(interval.rounded())
        let hours = total / 3600
        let minutes = (total % 3600) / 60
        if hours > 0 {
            return s("\(hours) Std \(minutes) Min", "\(hours) h \(minutes) min")
        }
        return s("\(minutes) Min", "\(minutes) min")
    }

    /// "vor 3 Min" / "3 min ago"
    func relative(_ date: Date) -> String {
        let seconds = max(0, Int(Date().timeIntervalSince(date)))
        if seconds < 60 { return s("vor \(seconds) Sek", "\(seconds) s ago") }
        let minutes = seconds / 60
        if minutes < 60 { return s("vor \(minutes) Min", "\(minutes) min ago") }
        let hours = minutes / 60
        if hours < 24 { return s("vor \(hours) Std", "\(hours) h ago") }
        return s("vor \(hours / 24) Tg", "\(hours / 24) d ago")
    }

    private func formatter(template: String) -> DateFormatter {
        let f = DateFormatter()
        f.locale = locale
        f.setLocalizedDateFormatFromTemplate(template)
        return f
    }

    func time(_ date: Date) -> String {
        formatter(template: "HHmm").string(from: date)
    }

    func dayTime(_ date: Date) -> String {
        formatter(template: "ddMMHHmm").string(from: date)
    }

    func day(_ date: Date) -> String {
        formatter(template: "ddMMyyyy").string(from: date)
    }

    /// Achsen- und Zeilenbeschriftung eines Buckets.
    func label(for bucket: Bucket) -> String {
        switch bucket.kind {
        case .day:
            return formatter(template: "ddMM").string(from: bucket.start)
        case .week:
            return s("KW \(bucket.weekNumber)", "W \(bucket.weekNumber)")
        case .month:
            return formatter(template: "MMMyy").string(from: bucket.start)
        }
    }

    // MARK: Kommandozeilen-Abzug

    var cliSource: String { s("Quelle", "Source") }
    var cliEntries: String { s("Einträge (dedupliziert)", "Entries (deduplicated)") }
    var cliPeriod: String { s("Zeitraum", "Period") }
    var cliLast7Days: String { s("Letzte 7 Tage", "Last 7 days") }
    var cliLast30Days: String { s("Letzte 30 Tage", "Last 30 days") }
    var cliBreakdown: String { s("Aufschlüsselung gesamt", "Overall breakdown") }
    var cliWebSearches: String { s("Web-Suchen", "Web searches") }
    var cliProjects: String { s("Projekte", "Projects") }
    var cliTokensAbbrev: String { s("tok", "tok") }
    func cliWindowSummary(count: Int, peak: String) -> String {
        s("5-Std-Fenster: \(count) insgesamt, Maximum \(peak) tok",
          "5-hour windows: \(count) total, maximum \(peak) tok")
    }
    var cliActive: String { s("Aktiv", "Active") }
    var cliNone: String { s("keines", "none") }
    var cliLast10Days: String { s("Letzte 10 Tage", "Last 10 days") }
    var cliAutostart: String { s("Autostart", "Launch at login") }
    var cliError: String { s("Fehler", "Error") }
}
