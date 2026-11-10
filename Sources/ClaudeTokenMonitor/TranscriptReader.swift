import Foundation

/// Liest die JSONL-Transkripte aus ~/.claude/projects inkrementell ein.
///
/// Zwei Details, die hier zwingend nötig sind:
///  1. Dedup über (requestId, message.id) — beim Fortsetzen oder Forken einer
///     Session wird die komplette Historie in eine neue Datei kopiert.
///  2. Inkrementelles Lesen per Byte-Offset, damit die App nicht bei jedem
///     Refresh alle Dateien neu parst.
final class TranscriptReader {
    struct FileCursor {
        var offset: UInt64 = 0
        var size: UInt64 = 0
    }

    private let root: URL
    private var cursors: [String: FileCursor] = [:]
    private var seenKeys: Set<String> = []
    private(set) var entries: [UsageEntry] = []

    private let isoWithFraction: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()
    private let isoPlain: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()

    init(root: URL? = nil) {
        self.root = root ?? FileManager.default
            .homeDirectoryForCurrentUser
            .appendingPathComponent(".claude/projects", isDirectory: true)
    }

    var rootPath: String { root.path }

    /// Sucht alle Transkripte und liest nur neu angehängte Zeilen.
    /// Gibt zurück, ob sich etwas geändert hat.
    ///
    /// Die Suche ist bewusst rekursiv: Subagent-Läufe liegen unter
    /// `<projekt>/<sessionId>/subagents/*.jsonl` und zählen voll mit.
    @discardableResult
    func refresh() -> Bool {
        let fm = FileManager.default
        guard let enumerator = fm.enumerator(
            at: root,
            includingPropertiesForKeys: [.fileSizeKey, .isRegularFileKey],
            options: [.skipsHiddenFiles, .skipsPackageDescendants]
        ) else { return false }

        var changed = false
        var newEntries: [UsageEntry] = []

        for case let file as URL in enumerator {
            guard file.pathExtension == "jsonl" else { continue }
            let values = try? file.resourceValues(forKeys: [.fileSizeKey, .isRegularFileKey])
            guard values?.isRegularFile == true else { continue }

            let key = file.path
            let size = UInt64(values?.fileSize ?? 0)
            var cursor = cursors[key] ?? FileCursor()

            // Datei geschrumpft oder ersetzt -> von vorn lesen
            if size < cursor.size { cursor = FileCursor() }
            if size == cursor.size && cursor.offset > 0 { continue }

            let (parsed, consumed) = readLines(
                at: file, from: cursor.offset, project: projectName(for: file)
            )
            if consumed > cursor.offset || !parsed.isEmpty { changed = true }
            cursor.offset = consumed
            cursor.size = size
            cursors[key] = cursor
            newEntries.append(contentsOf: parsed)
        }

        guard !newEntries.isEmpty else { return changed }

        for e in newEntries where !seenKeys.contains(e.dedupKey) {
            seenKeys.insert(e.dedupKey)
            entries.append(e)
        }
        entries.sort { $0.timestamp < $1.timestamp }
        return true
    }

    /// Projektname aus dem ersten Pfadsegment unter dem Wurzelverzeichnis.
    /// Wird nur als Fallback benutzt, wenn der Eintrag kein `cwd` mitbringt.
    private func projectName(for file: URL) -> String {
        let rootComponents = root.standardizedFileURL.pathComponents
        let fileComponents = file.standardizedFileURL.pathComponents
        guard fileComponents.count > rootComponents.count else { return "unbekannt" }
        return Self.decodeProjectName(fileComponents[rootComponents.count])
    }

    // MARK: - Zeilen lesen

    private func readLines(
        at url: URL, from offset: UInt64, project: String
    ) -> ([UsageEntry], UInt64) {
        guard let handle = try? FileHandle(forReadingFrom: url) else { return ([], offset) }
        defer { try? handle.close() }

        do {
            try handle.seek(toOffset: offset)
        } catch {
            return ([], offset)
        }
        guard let data = try? handle.readToEnd(), !data.isEmpty else { return ([], offset) }

        // Nur bis zum letzten vollständigen Zeilenumbruch verarbeiten —
        // die Datei kann gerade mitten in einer Zeile beschrieben werden.
        guard let lastNewline = data.lastIndex(of: UInt8(0x0A)) else { return ([], offset) }
        let usable = data[data.startIndex...lastNewline]
        let newOffset = offset + UInt64(usable.count)

        var result: [UsageEntry] = []
        for lineData in usable.split(separator: UInt8(0x0A)) where !lineData.isEmpty {
            if let entry = parse(lineData, project: project) {
                result.append(entry)
            }
        }
        return (result, newOffset)
    }

    private func parse(_ data: Data, project: String) -> UsageEntry? {
        guard
            let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let message = root["message"] as? [String: Any],
            let usage = message["usage"] as? [String: Any],
            let model = message["model"] as? String,
            model != "<synthetic>",
            let tsString = root["timestamp"] as? String,
            let timestamp = parseDate(tsString)
        else { return nil }

        let input = int(usage["input_tokens"])
        let output = int(usage["output_tokens"])
        let cacheRead = int(usage["cache_read_input_tokens"])

        // Cache-Writes nach TTL aufschlüsseln (5 Min vs. 1 Std kosten unterschiedlich).
        var write5m = 0
        var write1h = 0
        if let creation = usage["cache_creation"] as? [String: Any] {
            write5m = int(creation["ephemeral_5m_input_tokens"])
            write1h = int(creation["ephemeral_1h_input_tokens"])
        }
        if write5m == 0 && write1h == 0 {
            write5m = int(usage["cache_creation_input_tokens"])
        }

        var searches = 0
        if let serverTool = usage["server_tool_use"] as? [String: Any] {
            searches = int(serverTool["web_search_requests"])
        }

        guard input + output + cacheRead + write5m + write1h > 0 else { return nil }

        let requestId = root["requestId"] as? String ?? ""
        let messageId = message["id"] as? String ?? ""
        let sessionId = root["sessionId"] as? String ?? ""
        let dedupKey = requestId.isEmpty && messageId.isEmpty
            ? "\(sessionId):\(tsString):\(output)"
            : "\(requestId)|\(messageId)"

        // cwd ist präziser als der kodierte Verzeichnisname.
        let resolvedProject: String
        if let cwd = root["cwd"] as? String, let last = cwd.split(separator: "/").last {
            resolvedProject = String(last)
        } else {
            resolvedProject = project
        }

        return UsageEntry(
            timestamp: timestamp,
            model: model,
            inputTokens: input,
            outputTokens: output,
            cacheWrite5m: write5m,
            cacheWrite1h: write1h,
            cacheRead: cacheRead,
            webSearches: searches,
            sessionId: sessionId,
            project: resolvedProject,
            isSidechain: root["isSidechain"] as? Bool ?? false,
            dedupKey: dedupKey
        )
    }

    private func parseDate(_ s: String) -> Date? {
        isoWithFraction.date(from: s) ?? isoPlain.date(from: s)
    }

    private func int(_ any: Any?) -> Int {
        if let i = any as? Int { return i }
        if let d = any as? Double { return Int(d) }
        return 0
    }

    /// Der Verzeichnisname kodiert "/" als "-", was mit echten Bindestrichen
    /// im Pfad nicht eindeutig auflösbar ist. Deshalb nur den Home-Präfix
    /// abschneiden und den Rest so lassen — `cwd` ist ohnehin die primäre Quelle.
    /// "-Users-alice-Development-my-app" -> "Development-my-app"
    static func decodeProjectName(_ encoded: String) -> String {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        let prefix = home.replacingOccurrences(of: "/", with: "-") + "-"
        if encoded.hasPrefix(prefix) {
            let rest = String(encoded.dropFirst(prefix.count))
            return rest.isEmpty ? "~" : rest
        }
        return encoded
    }
}
