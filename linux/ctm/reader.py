"""Liest die JSONL-Transkripte inkrementell (entspricht TranscriptReader.swift).

Zwei Details, die hier zwingend nötig sind:
 1. Dedup über (requestId, message.id) — beim Fortsetzen oder Forken einer
    Session wird die komplette Historie in eine neue Datei kopiert.
 2. Inkrementelles Lesen per Byte-Offset, damit nicht bei jedem Refresh alle
    Dateien neu geparst werden.

Die Suche ist bewusst rekursiv: Subagent-Läufe liegen unter
`<projekt>/<sessionId>/subagents/*.jsonl` und zählen voll mit.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from .model import UsageEntry


def default_root() -> str:
    return os.path.join(os.path.expanduser("~"), ".claude", "projects")


class TranscriptReader:
    def __init__(self, root: str | None = None) -> None:
        self.root = root or default_root()
        # Pfad -> (offset, size)
        self._cursors: dict[str, tuple[int, int]] = {}
        self._seen: set[str] = set()
        self.entries: list[UsageEntry] = []

    def refresh(self) -> bool:
        """Sucht alle Transkripte, liest nur neu angehängte Zeilen.
        Gibt zurück, ob sich etwas geändert hat."""
        if not os.path.isdir(self.root):
            return False

        changed = False
        new_entries: list[UsageEntry] = []

        for dirpath, dirnames, filenames in os.walk(self.root):
            # Versteckte Verzeichnisse überspringen (wie .skipsHiddenFiles).
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in filenames:
                if name.startswith(".") or not name.endswith(".jsonl"):
                    continue
                path = os.path.join(dirpath, name)
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                if not os.path.isfile(path):
                    continue

                size = st.st_size
                offset, last_size = self._cursors.get(path, (0, 0))
                # Datei geschrumpft oder ersetzt -> von vorn lesen
                if size < last_size:
                    offset, last_size = 0, 0
                if size == last_size and offset > 0:
                    continue

                parsed, consumed = self._read_lines(path, offset, self._project_name(path))
                if consumed > offset or parsed:
                    changed = True
                self._cursors[path] = (consumed, size)
                new_entries.extend(parsed)

        if not new_entries:
            return changed

        for e in new_entries:
            if e.dedup_key in self._seen:
                continue
            self._seen.add(e.dedup_key)
            self.entries.append(e)
        self.entries.sort(key=lambda e: e.timestamp)
        return True

    # MARK: - Zeilen lesen

    def _project_name(self, path: str) -> str:
        """Fallback, wenn ein Eintrag kein `cwd` mitbringt."""
        rel = os.path.relpath(path, self.root)
        first = rel.split(os.sep, 1)[0]
        return decode_project_name(first) if first and first != rel else "unbekannt"

    def _read_lines(self, path: str, offset: int, project: str) -> tuple[list[UsageEntry], int]:
        try:
            with open(path, "rb") as f:
                f.seek(offset)
                data = f.read()
        except OSError:
            return [], offset
        if not data:
            return [], offset

        # Nur bis zum letzten vollständigen Zeilenumbruch verarbeiten —
        # die Datei kann gerade mitten in einer Zeile beschrieben werden.
        last_nl = data.rfind(b"\n")
        if last_nl < 0:
            return [], offset
        usable = data[: last_nl + 1]
        new_offset = offset + len(usable)

        result = []
        for line in usable.split(b"\n"):
            # Schneller Vorfilter: nur Zeilen mit usage-Objekt parsen.
            if not line or b'"usage"' not in line:
                continue
            entry = _parse(line, project)
            if entry is not None:
                result.append(entry)
        return result, new_offset


def _int(v) -> int:
    if isinstance(v, bool):
        return 0
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _parse_date(s: str) -> float | None:
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s).timestamp()
    except ValueError:
        return None


def _parse(line: bytes, project: str) -> UsageEntry | None:
    try:
        root = json.loads(line)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(root, dict):
        return None
    message = root.get("message")
    if not isinstance(message, dict):
        return None
    usage = message.get("usage")
    model = message.get("model")
    ts_string = root.get("timestamp")
    if not isinstance(usage, dict) or not isinstance(model, str) or model == "<synthetic>":
        return None
    if not isinstance(ts_string, str):
        return None
    timestamp = _parse_date(ts_string)
    if timestamp is None:
        return None

    inp = _int(usage.get("input_tokens"))
    out = _int(usage.get("output_tokens"))
    cache_read = _int(usage.get("cache_read_input_tokens"))

    # Cache-Writes nach TTL aufschlüsseln (5 Min vs. 1 Std kosten unterschiedlich).
    write5m = write1h = 0
    creation = usage.get("cache_creation")
    if isinstance(creation, dict):
        write5m = _int(creation.get("ephemeral_5m_input_tokens"))
        write1h = _int(creation.get("ephemeral_1h_input_tokens"))
    if write5m == 0 and write1h == 0:
        write5m = _int(usage.get("cache_creation_input_tokens"))

    searches = 0
    server_tool = usage.get("server_tool_use")
    if isinstance(server_tool, dict):
        searches = _int(server_tool.get("web_search_requests"))

    if inp + out + cache_read + write5m + write1h <= 0:
        return None

    request_id = root.get("requestId") or ""
    message_id = message.get("id") or ""
    session_id = root.get("sessionId") or ""
    if not request_id and not message_id:
        dedup_key = f"{session_id}:{ts_string}:{out}"
    else:
        dedup_key = f"{request_id}|{message_id}"

    # cwd ist präziser als der kodierte Verzeichnisname.
    cwd = root.get("cwd")
    resolved = project
    if isinstance(cwd, str):
        last = [p for p in cwd.split("/") if p]
        if last:
            resolved = last[-1]

    return UsageEntry(
        timestamp=timestamp,
        model=model,
        input_tokens=inp,
        output_tokens=out,
        cache_write_5m=write5m,
        cache_write_1h=write1h,
        cache_read=cache_read,
        web_searches=searches,
        session_id=str(session_id),
        project=resolved,
        is_sidechain=bool(root.get("isSidechain", False)),
        dedup_key=dedup_key,
    )


def decode_project_name(encoded: str) -> str:
    """Der Verzeichnisname kodiert "/" als "-" — nicht eindeutig auflösbar.
    Deshalb nur den Home-Präfix abschneiden.
    "-home-alice-Development-my-app" -> "Development-my-app"
    """
    home = os.path.expanduser("~")
    prefix = home.replace("/", "-") + "-"
    if encoded.startswith(prefix):
        rest = encoded[len(prefix):]
        return rest or "~"
    if encoded == home.replace("/", "-"):
        return "~"
    return encoded
