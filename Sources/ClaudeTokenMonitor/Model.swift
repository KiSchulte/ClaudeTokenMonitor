import Foundation

// MARK: - Ein einzelner Usage-Datensatz (eine Assistant-Antwort)

struct UsageEntry: Sendable {
    let timestamp: Date
    let model: String
    let inputTokens: Int
    let outputTokens: Int
    let cacheWrite5m: Int
    let cacheWrite1h: Int
    let cacheRead: Int
    let webSearches: Int
    let sessionId: String
    let project: String
    let isSidechain: Bool

    /// Dedup-Schlüssel: dieselbe Antwort taucht in mehreren Transkripten auf,
    /// wenn eine Session fortgesetzt oder geforkt wird.
    let dedupKey: String

    var totalTokens: Int {
        inputTokens + outputTokens + cacheWrite5m + cacheWrite1h + cacheRead
    }

    var cost: Double { Pricing.cost(for: self) }
}

// MARK: - Preise (USD pro 1 Mio. Tokens)

struct ModelPrice: Sendable {
    let input: Double
    let output: Double

    /// Cache-Write 5 Min = 1,25x Input-Preis
    var cacheWrite5m: Double { input * 1.25 }
    /// Cache-Write 1 Std = 2x Input-Preis
    var cacheWrite1h: Double { input * 2.0 }
    /// Cache-Read = 0,1x Input-Preis
    var cacheRead: Double { input * 0.1 }
}

enum Pricing {
    /// Web-Suche: 10 USD pro 1000 Requests
    static let webSearchCost = 10.0 / 1000.0

    /// Reihenfolge ist relevant: längere Präfixe zuerst prüfen.
    private static let table: [(prefix: String, price: ModelPrice)] = [
        ("claude-fable-5", ModelPrice(input: 10, output: 50)),
        ("claude-mythos-5", ModelPrice(input: 10, output: 50)),
        ("claude-mythos-preview", ModelPrice(input: 10, output: 50)),
        ("claude-opus-5", ModelPrice(input: 5, output: 25)),
        ("claude-opus-4-8", ModelPrice(input: 5, output: 25)),
        ("claude-opus-4-7", ModelPrice(input: 5, output: 25)),
        ("claude-opus-4-6", ModelPrice(input: 5, output: 25)),
        ("claude-opus-4-5", ModelPrice(input: 5, output: 25)),
        ("claude-opus-4-1", ModelPrice(input: 15, output: 75)),
        ("claude-opus-4", ModelPrice(input: 15, output: 75)),
        ("claude-sonnet-5", ModelPrice(input: 3, output: 15)),
        ("claude-sonnet-4-6", ModelPrice(input: 3, output: 15)),
        ("claude-sonnet-4-5", ModelPrice(input: 3, output: 15)),
        ("claude-sonnet-4", ModelPrice(input: 3, output: 15)),
        ("claude-haiku-4-5", ModelPrice(input: 1, output: 5)),
        ("claude-3-5-haiku", ModelPrice(input: 0.8, output: 4)),
        ("claude-3-haiku", ModelPrice(input: 0.25, output: 1.25)),
    ]

    static func price(for model: String) -> ModelPrice? {
        let m = model.lowercased()
        for entry in table where m.hasPrefix(entry.prefix) {
            return entry.price
        }
        return nil
    }

    static func cost(for e: UsageEntry) -> Double {
        guard let p = price(for: e.model) else { return 0 }
        let perMillion = 1_000_000.0
        return Double(e.inputTokens) / perMillion * p.input
            + Double(e.outputTokens) / perMillion * p.output
            + Double(e.cacheWrite5m) / perMillion * p.cacheWrite5m
            + Double(e.cacheWrite1h) / perMillion * p.cacheWrite1h
            + Double(e.cacheRead) / perMillion * p.cacheRead
            + Double(e.webSearches) * webSearchCost
    }

    /// Kurzer, lesbarer Modellname für die UI.
    static func displayName(_ model: String) -> String {
        var m = model
        // Datums-Suffix entfernen: claude-haiku-4-5-20251001 -> claude-haiku-4-5
        if let range = m.range(of: "-20[0-9]{6}$", options: .regularExpression) {
            m.removeSubrange(range)
        }
        m = m.replacingOccurrences(of: "claude-", with: "")
        let parts = m.split(separator: "-").map(String.init)
        guard let family = parts.first else { return m }
        let version = parts.dropFirst().joined(separator: ".")
        return version.isEmpty
            ? family.capitalized
            : "\(family.capitalized) \(version)"
    }
}

// MARK: - Summen

struct Totals: Sendable {
    var input = 0
    var output = 0
    var cacheWrite5m = 0
    var cacheWrite1h = 0
    var cacheRead = 0
    var webSearches = 0
    var cost = 0.0
    var requests = 0

    var totalTokens: Int { input + output + cacheWrite5m + cacheWrite1h + cacheRead }
    var cacheWrite: Int { cacheWrite5m + cacheWrite1h }
    /// Tokens ohne Cache-Reads — näher an dem, was "echte" Arbeit war.
    var billableInputTokens: Int { input + cacheWrite5m + cacheWrite1h }

    mutating func add(_ e: UsageEntry) {
        input += e.inputTokens
        output += e.outputTokens
        cacheWrite5m += e.cacheWrite5m
        cacheWrite1h += e.cacheWrite1h
        cacheRead += e.cacheRead
        webSearches += e.webSearches
        cost += e.cost
        requests += 1
    }

    static func + (a: Totals, b: Totals) -> Totals {
        var r = a
        r.input += b.input
        r.output += b.output
        r.cacheWrite5m += b.cacheWrite5m
        r.cacheWrite1h += b.cacheWrite1h
        r.cacheRead += b.cacheRead
        r.webSearches += b.webSearches
        r.cost += b.cost
        r.requests += b.requests
        return r
    }
}

// MARK: - Aggregierte Buckets

enum BucketKind: Sendable {
    case day, week, month
}

/// Ein Zeitabschnitt der Historie. Die Beschriftung entsteht erst in der
/// Anzeige (`Loc.label(for:)`), damit ein Sprachwechsel keine Neuaggregation
/// auslöst.
struct Bucket: Identifiable, Sendable {
    let id: Date
    let start: Date
    let kind: BucketKind
    /// Nur bei `kind == .week` gesetzt.
    let weekNumber: Int
    let totals: Totals
}

struct NamedTotals: Identifiable, Sendable {
    let id: String
    let name: String
    let totals: Totals
}

/// Ein 5-Stunden-Fenster (entspricht dem Abrechnungsfenster der Claude-Abos).
struct UsageBlock: Identifiable, Sendable {
    let id: Date
    let start: Date
    let end: Date
    let lastActivity: Date
    let totals: Totals
    let models: [String]

    var isActive: Bool { Date() < end }
    var remaining: TimeInterval { max(0, end.timeIntervalSince(Date())) }
    var elapsed: TimeInterval { max(60, min(Date(), end).timeIntervalSince(start)) }
    /// Tokens pro Minute im laufenden Block.
    var burnRate: Double { Double(totals.totalTokens) / (elapsed / 60) }
    /// Hochrechnung auf das Blockende bei gleichbleibender Rate.
    var projectedTokens: Int {
        guard isActive else { return totals.totalTokens }
        return Int(burnRate * (end.timeIntervalSince(start) / 60))
    }
}
