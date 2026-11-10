import Foundation

/// Besitzt den Reader und führt alles Lesen/Aggregieren auf einer eigenen
/// seriellen Queue aus. Dadurch berührt kein Main-Actor-Code den Reader-State.
///
/// `@unchecked Sendable` ist hier korrekt, weil jeder Zugriff auf `reader`
/// ausschließlich innerhalb von `queue` passiert.
/// Was beim Laden schiefgehen kann. Bewusst unlokalisiert — den Text baut
/// erst der Store in der aktuell gewählten Sprache.
enum LoadProblem: Sendable {
    case missingDirectory(path: String)
    case noUsageData
}

final class UsageEngine: @unchecked Sendable {
    private let reader = TranscriptReader()
    private let queue = DispatchQueue(label: "io.github.kischulte.claudetokenmonitor.engine")

    /// Pfad wird nur gelesen und ändert sich nicht — daher außerhalb der Queue ok.
    let transcriptPath: String

    init() {
        transcriptPath = reader.rootPath
    }

    func load(completion: @escaping @Sendable (Snapshot, LoadProblem?) -> Void) {
        queue.async { [reader, transcriptPath] in
            guard FileManager.default.fileExists(atPath: transcriptPath) else {
                completion(Snapshot(), .missingDirectory(path: transcriptPath))
                return
            }

            reader.refresh()
            let entries = reader.entries
            let snapshot = Self.buildSnapshot(from: entries)
            completion(snapshot, entries.isEmpty ? .noUsageData : nil)
        }
    }

    private static func buildSnapshot(from entries: [UsageEntry]) -> Snapshot {
        let agg = Aggregator(entries: entries)
        let blocks = agg.blocks
        let startOfToday = Calendar.current.startOfDay(for: Date())

        var s = Snapshot()
        s.today = agg.today
        s.week = agg.currentWeek
        s.month = agg.currentMonth
        s.last7Days = agg.last7Days
        s.last30Days = agg.last30Days
        s.allTime = agg.allTime
        let active = blocks.last.flatMap { $0.isActive ? $0 : nil }
        s.activeBlock = active
        s.recentBlocks = Array(blocks.suffix(12).reversed())
        s.peakBlockTokens = blocks.map(\.totals.totalTokens).max() ?? 0
        s.referenceBlockTokens = blocks
            .filter { $0.id != active?.id }
            .map(\.totals.totalTokens)
            .max() ?? 0
        s.daily = agg.daily(count: 30)
        s.weekly = agg.weekly(count: 12)
        s.monthly = agg.monthly(count: 6)
        s.models = agg.byModel()
        s.modelsToday = agg.byModel(since: startOfToday)
        s.projects = agg.byProject()
        s.firstEntry = agg.firstEntryDate
        s.lastEntry = agg.lastEntryDate
        s.entryCount = entries.count
        s.updatedAt = Date()
        return s
    }
}
