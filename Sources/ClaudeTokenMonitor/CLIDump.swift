import Foundation

/// Synchroner Textabzug derselben Aggregation, die die UI benutzt.
/// Aufruf: `ClaudeTokenMonitor --dump [--de|--en]`
enum CLIDump {
    /// Sprache: explizites Flag, sonst die in der App gewählte Einstellung.
    static func language() -> Language {
        let args = CommandLine.arguments
        if args.contains("--de") { return .de }
        if args.contains("--en") { return .en }
        let stored = UserDefaults.standard.string(forKey: DefaultsKey.language)
        return (stored.flatMap(AppLanguage.init(rawValue:)) ?? .system).resolved
    }

    static func run() {
        let loc = Loc(language: language())
        let reader = TranscriptReader()
        reader.refresh()
        let agg = Aggregator(entries: reader.entries)

        print("\(loc.cliSource): \(reader.rootPath)")
        print("\(loc.cliEntries): \(reader.entries.count)")
        if let first = agg.firstEntryDate, let last = agg.lastEntryDate {
            print("\(loc.cliPeriod): \(loc.day(first)) – \(loc.day(last))")
        }
        print("")

        func line(_ label: String, _ t: Totals) {
            let padded = label.padding(toLength: 18, withPad: " ", startingAt: 0)
            let tokens = loc.exact(t.totalTokens).leftPadded(to: 15)
            let money = loc.money(t.cost).leftPadded(to: 10)
            print("\(padded)\(tokens) \(loc.cliTokensAbbrev) \(money)  \(t.requests) \(loc.requestsShort)")
        }

        line(loc.today, agg.today)
        line(loc.thisWeek, agg.currentWeek)
        line(loc.thisMonth, agg.currentMonth)
        line(loc.cliLast7Days, agg.last7Days)
        line(loc.cliLast30Days, agg.last30Days)
        line(loc.total, agg.allTime)

        let all = agg.allTime
        print("")
        print("\(loc.cliBreakdown):")
        func detail(_ label: String, _ value: Int) {
            print("  \(label.padding(toLength: 18, withPad: " ", startingAt: 0))\(loc.exact(value))")
        }
        detail(loc.input, all.input)
        detail(loc.output, all.output)
        detail("\(loc.cacheWrite) 5m", all.cacheWrite5m)
        detail("\(loc.cacheWrite) 1h", all.cacheWrite1h)
        detail(loc.cacheRead, all.cacheRead)
        detail(loc.cliWebSearches, all.webSearches)

        print("")
        print("\(loc.models):")
        for m in agg.byModel() {
            let name = m.name.padding(toLength: 16, withPad: " ", startingAt: 0)
            print("  \(name)\(loc.exact(m.totals.totalTokens).leftPadded(to: 14)) \(loc.cliTokensAbbrev)"
                  + "  \(loc.money(m.totals.cost))")
        }

        print("")
        print("\(loc.cliProjects):")
        for p in agg.byProject().prefix(15) {
            let name = p.name.padding(toLength: 30, withPad: " ", startingAt: 0)
            print("  \(name)\(loc.exact(p.totals.totalTokens).leftPadded(to: 14)) \(loc.cliTokensAbbrev)"
                  + "  \(loc.money(p.totals.cost))")
        }

        let blocks = agg.blocks
        print("")
        print(loc.cliWindowSummary(count: blocks.count, peak: loc.exact(agg.peakBlockTokens)))
        if let active = agg.activeBlock {
            print("\(loc.cliActive): \(loc.dayTime(active.start)) – \(loc.time(active.end)), "
                  + "\(loc.exact(active.totals.totalTokens)) \(loc.cliTokensAbbrev), "
                  + loc.stillRemaining(loc.duration(active.remaining)))
        } else {
            print("\(loc.cliActive): \(loc.cliNone)")
        }
        for b in blocks.suffix(5) {
            print("  \(loc.dayTime(b.start)) – \(loc.time(b.end))"
                  + "  \(loc.exact(b.totals.totalTokens).leftPadded(to: 14)) \(loc.cliTokensAbbrev)"
                  + "  \(loc.money(b.totals.cost))")
        }

        print("")
        print("\(loc.cliLast10Days):")
        for d in agg.daily(count: 10) {
            print("  \(loc.label(for: d)) \(loc.exact(d.totals.totalTokens).leftPadded(to: 14)) \(loc.cliTokensAbbrev)"
                  + "  \(loc.money(d.totals.cost))")
        }
    }
}

private extension String {
    func leftPadded(to width: Int) -> String {
        count >= width ? self : String(repeating: " ", count: width - count) + self
    }
}
