import Foundation

/// Rechnet die rohen Usage-Einträge in die Ansichten der App um.
struct Aggregator {
    static let blockDuration: TimeInterval = 5 * 60 * 60

    let entries: [UsageEntry]
    private let calendar: Calendar

    init(entries: [UsageEntry]) {
        self.entries = entries
        // Kalender bewusst unabhängig von der UI-Sprache: ISO-8601-Wochen
        // (Montag als Wochenstart). Sonst würden sich die Wochensummen beim
        // Sprachwechsel verschieben.
        var cal = Calendar(identifier: .gregorian)
        cal.locale = Locale(identifier: "en_US_POSIX")
        cal.firstWeekday = 2
        cal.minimumDaysInFirstWeek = 4
        self.calendar = cal
    }

    // MARK: - Zeiträume

    func totals(since date: Date) -> Totals {
        var t = Totals()
        for e in entries where e.timestamp >= date { t.add(e) }
        return t
    }

    func totals(from: Date, to: Date) -> Totals {
        var t = Totals()
        for e in entries where e.timestamp >= from && e.timestamp < to { t.add(e) }
        return t
    }

    var today: Totals { totals(since: calendar.startOfDay(for: Date())) }

    var currentWeek: Totals {
        guard let interval = calendar.dateInterval(of: .weekOfYear, for: Date()) else {
            return Totals()
        }
        return totals(since: interval.start)
    }

    var currentMonth: Totals {
        guard let interval = calendar.dateInterval(of: .month, for: Date()) else {
            return Totals()
        }
        return totals(since: interval.start)
    }

    var last7Days: Totals { totals(since: Date().addingTimeInterval(-7 * 24 * 3600)) }
    var last30Days: Totals { totals(since: Date().addingTimeInterval(-30 * 24 * 3600)) }
    var allTime: Totals {
        var t = Totals()
        for e in entries { t.add(e) }
        return t
    }

    var firstEntryDate: Date? { entries.first?.timestamp }
    var lastEntryDate: Date? { entries.last?.timestamp }

    // MARK: - Historie

    /// Tages-Buckets der letzten `count` Tage, chronologisch, inkl. Nulltagen.
    func daily(count: Int) -> [Bucket] {
        buckets(component: .day, count: count, kind: .day)
    }

    func weekly(count: Int) -> [Bucket] {
        buckets(component: .weekOfYear, count: count, kind: .week)
    }

    func monthly(count: Int) -> [Bucket] {
        buckets(component: .month, count: count, kind: .month)
    }

    private func buckets(
        component: Calendar.Component,
        count: Int,
        kind: BucketKind
    ) -> [Bucket] {
        let now = Date()
        var starts: [Date] = []
        for offset in stride(from: count - 1, through: 0, by: -1) {
            guard
                let shifted = calendar.date(byAdding: component, value: -offset, to: now),
                let interval = calendar.dateInterval(of: component, for: shifted)
            else { continue }
            starts.append(interval.start)
        }

        // Ein Durchlauf über alle Einträge, Zuordnung per Binärsuche über die Grenzen.
        var sums = [Totals](repeating: Totals(), count: starts.count)
        for e in entries {
            guard let idx = bucketIndex(for: e.timestamp, in: starts) else { continue }
            sums[idx].add(e)
        }

        return starts.enumerated().map { idx, start in
            Bucket(
                id: start,
                start: start,
                kind: kind,
                weekNumber: kind == .week
                    ? calendar.component(.weekOfYear, from: start)
                    : 0,
                totals: sums[idx]
            )
        }
    }

    private func bucketIndex(for date: Date, in starts: [Date]) -> Int? {
        guard let first = starts.first, date >= first else { return nil }
        var low = 0
        var high = starts.count - 1
        var result = 0
        while low <= high {
            let mid = (low + high) / 2
            if starts[mid] <= date {
                result = mid
                low = mid + 1
            } else {
                high = mid - 1
            }
        }
        return result
    }

    // MARK: - Aufschlüsselung

    func byModel(since date: Date? = nil) -> [NamedTotals] {
        group(since: date) { Pricing.displayName($0.model) }
    }

    func byProject(since date: Date? = nil) -> [NamedTotals] {
        group(since: date) { $0.project }
    }

    private func group(
        since date: Date?, key: (UsageEntry) -> String
    ) -> [NamedTotals] {
        var map: [String: Totals] = [:]
        for e in entries {
            if let date, e.timestamp < date { continue }
            map[key(e), default: Totals()].add(e)
        }
        return map
            .map { NamedTotals(id: $0.key, name: $0.key, totals: $0.value) }
            .sorted { $0.totals.totalTokens > $1.totals.totalTokens }
    }

    // MARK: - 5-Stunden-Fenster

    /// Bildet Blöcke wie die Abo-Abrechnungsfenster: ein Block startet zur
    /// vollen Stunde der ersten Aktivität, läuft 5 Stunden und wird zusätzlich
    /// beendet, wenn 5 Stunden lang nichts passiert ist.
    var blocks: [UsageBlock] {
        guard !entries.isEmpty else { return [] }

        var result: [UsageBlock] = []
        var blockStart: Date?
        var lastActivity = Date.distantPast
        var totals = Totals()
        var models: Set<String> = []

        func flush() {
            guard let start = blockStart else { return }
            result.append(UsageBlock(
                id: start,
                start: start,
                end: start.addingTimeInterval(Self.blockDuration),
                lastActivity: lastActivity,
                totals: totals,
                models: models.sorted()
            ))
            blockStart = nil
            totals = Totals()
            models = []
        }

        for e in entries {
            let start = floorToHour(e.timestamp)
            if let current = blockStart {
                let exceedsWindow = e.timestamp >= current.addingTimeInterval(Self.blockDuration)
                let longGap = e.timestamp.timeIntervalSince(lastActivity) >= Self.blockDuration
                if exceedsWindow || longGap {
                    flush()
                    blockStart = start
                }
            } else {
                blockStart = start
            }
            totals.add(e)
            models.insert(Pricing.displayName(e.model))
            lastActivity = e.timestamp
        }
        flush()
        return result
    }

    /// Der aktuell laufende Block, falls das letzte 5-Stunden-Fenster noch offen ist.
    var activeBlock: UsageBlock? {
        guard let last = blocks.last, last.isActive else { return nil }
        return last
    }

    private func floorToHour(_ date: Date) -> Date {
        let comps = calendar.dateComponents([.year, .month, .day, .hour], from: date)
        return calendar.date(from: comps) ?? date
    }

    /// Höchster Block-Verbrauch der Historie — dient als Referenz für den
    /// Auslastungsbalken, solange keine echten Limits lokal verfügbar sind.
    var peakBlockTokens: Int {
        blocks.map(\.totals.totalTokens).max() ?? 0
    }
}
