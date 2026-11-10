"""Rechnet die rohen Usage-Einträge in die Ansichten um (entspricht Aggregator.swift).

Alle Kalenderrechnungen in lokaler Zeit, Wochen bewusst immer nach ISO 8601
(Montag als Wochenstart) — unabhängig von der UI-Sprache.
"""

from __future__ import annotations

import bisect
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .model import (DAY, MONTH, WEEK, Bucket, NamedTotals, Totals, UsageBlock,
                    UsageEntry, display_name)

BLOCK_DURATION = 5 * 60 * 60


def _local(ts: float) -> datetime:
    return datetime.fromtimestamp(ts)


def start_of_day(ts: float) -> float:
    d = _local(ts)
    return datetime(d.year, d.month, d.day).timestamp()


def start_of_week(ts: float) -> float:
    d = _local(ts)
    monday = datetime(d.year, d.month, d.day) - timedelta(days=d.weekday())
    return datetime(monday.year, monday.month, monday.day).timestamp()


def start_of_month(ts: float) -> float:
    d = _local(ts)
    return datetime(d.year, d.month, 1).timestamp()


def floor_to_hour(ts: float) -> float:
    d = _local(ts)
    return datetime(d.year, d.month, d.day, d.hour).timestamp()


def _shift_months(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


class Aggregator:
    def __init__(self, entries: list[UsageEntry]) -> None:
        self.entries = entries
        self._times = [e.timestamp for e in entries]

    # MARK: - Zeiträume

    def totals_since(self, ts: float) -> Totals:
        t = Totals()
        for e in self.entries[bisect.bisect_left(self._times, ts):]:
            t.add(e)
        return t

    @property
    def today(self) -> Totals:
        return self.totals_since(start_of_day(time.time()))

    @property
    def current_week(self) -> Totals:
        return self.totals_since(start_of_week(time.time()))

    @property
    def current_month(self) -> Totals:
        return self.totals_since(start_of_month(time.time()))

    @property
    def last_7_days(self) -> Totals:
        return self.totals_since(time.time() - 7 * 24 * 3600)

    @property
    def last_30_days(self) -> Totals:
        return self.totals_since(time.time() - 30 * 24 * 3600)

    @property
    def all_time(self) -> Totals:
        t = Totals()
        for e in self.entries:
            t.add(e)
        return t

    @property
    def first_entry(self) -> float | None:
        return self.entries[0].timestamp if self.entries else None

    @property
    def last_entry(self) -> float | None:
        return self.entries[-1].timestamp if self.entries else None

    # MARK: - Historie

    def daily(self, count: int) -> list[Bucket]:
        today = _local(time.time())
        base = datetime(today.year, today.month, today.day)
        starts = []
        for off in range(count - 1, -1, -1):
            d = base - timedelta(days=off)
            starts.append(datetime(d.year, d.month, d.day).timestamp())
        return self._buckets(starts, DAY)

    def weekly(self, count: int) -> list[Bucket]:
        this_week = _local(start_of_week(time.time()))
        starts = []
        for off in range(count - 1, -1, -1):
            d = this_week - timedelta(weeks=off)
            starts.append(datetime(d.year, d.month, d.day).timestamp())
        return self._buckets(starts, WEEK)

    def monthly(self, count: int) -> list[Bucket]:
        now = _local(time.time())
        starts = []
        for off in range(count - 1, -1, -1):
            y, m = _shift_months(now.year, now.month, -off)
            starts.append(datetime(y, m, 1).timestamp())
        return self._buckets(starts, MONTH)

    def _buckets(self, starts: list[float], kind: str) -> list[Bucket]:
        sums = [Totals() for _ in starts]
        if starts:
            first = starts[0]
            for e in self.entries[bisect.bisect_left(self._times, first):]:
                idx = bisect.bisect_right(starts, e.timestamp) - 1
                if idx >= 0:
                    sums[idx].add(e)
        return [
            Bucket(
                start=s,
                kind=kind,
                week_number=_local(s).isocalendar()[1] if kind == WEEK else 0,
                totals=sums[i],
            )
            for i, s in enumerate(starts)
        ]

    # MARK: - Aufschlüsselung

    def by_model(self, since: float | None = None) -> list[NamedTotals]:
        return self._group(since, lambda e: display_name(e.model))

    def by_project(self, since: float | None = None) -> list[NamedTotals]:
        return self._group(since, lambda e: e.project)

    def _group(self, since, key) -> list[NamedTotals]:
        groups: dict[str, Totals] = {}
        start = bisect.bisect_left(self._times, since) if since is not None else 0
        for e in self.entries[start:]:
            k = key(e)
            t = groups.get(k)
            if t is None:
                t = groups[k] = Totals()
            t.add(e)
        items = [NamedTotals(k, v) for k, v in groups.items()]
        items.sort(key=lambda n: n.totals.total_tokens, reverse=True)
        return items

    # MARK: - 5-Stunden-Fenster

    @property
    def blocks(self) -> list[UsageBlock]:
        """Ein Block startet zur vollen Stunde der ersten Aktivität, läuft
        5 Stunden und wird zusätzlich beendet, wenn 5 Stunden lang nichts
        passiert ist."""
        result: list[UsageBlock] = []
        block_start: float | None = None
        last_activity = float("-inf")
        totals = Totals()
        models: set[str] = set()

        def flush():
            nonlocal block_start, totals, models
            if block_start is None:
                return
            result.append(UsageBlock(
                start=block_start,
                end=block_start + BLOCK_DURATION,
                last_activity=last_activity,
                totals=totals,
                models=sorted(models),
            ))
            block_start = None
            totals = Totals()
            models = set()

        for e in self.entries:
            if block_start is not None:
                exceeds = e.timestamp >= block_start + BLOCK_DURATION
                long_gap = e.timestamp - last_activity >= BLOCK_DURATION
                if exceeds or long_gap:
                    flush()
                    block_start = floor_to_hour(e.timestamp)
            else:
                block_start = floor_to_hour(e.timestamp)
            totals.add(e)
            models.add(display_name(e.model))
            last_activity = e.timestamp
        flush()
        return result


# MARK: - Snapshot


@dataclass
class Snapshot:
    """Vorberechnete Sicht — wird im Hintergrund erzeugt, damit die UI nichts
    aggregieren muss."""
    today: Totals = field(default_factory=Totals)
    week: Totals = field(default_factory=Totals)
    month: Totals = field(default_factory=Totals)
    last_7_days: Totals = field(default_factory=Totals)
    last_30_days: Totals = field(default_factory=Totals)
    all_time: Totals = field(default_factory=Totals)

    active_block: UsageBlock | None = None
    recent_blocks: list[UsageBlock] = field(default_factory=list)
    # Höchstwert über alle Fenster — Maßstab in der Fenster-Liste.
    peak_block_tokens: int = 0
    # Höchstwert der *abgeschlossenen* Fenster — Referenz für den Balken des
    # laufenden Fensters, damit dieser sich nicht selbst vergleicht.
    reference_block_tokens: int = 0

    daily: list[Bucket] = field(default_factory=list)
    weekly: list[Bucket] = field(default_factory=list)
    monthly: list[Bucket] = field(default_factory=list)

    models: list[NamedTotals] = field(default_factory=list)
    projects: list[NamedTotals] = field(default_factory=list)
    models_today: list[NamedTotals] = field(default_factory=list)

    first_entry: float | None = None
    last_entry: float | None = None
    entry_count: int = 0
    updated_at: float = field(default_factory=time.time)


def build_snapshot(entries: list[UsageEntry]) -> Snapshot:
    agg = Aggregator(entries)
    blocks = agg.blocks
    s = Snapshot()
    s.today = agg.today
    s.week = agg.current_week
    s.month = agg.current_month
    s.last_7_days = agg.last_7_days
    s.last_30_days = agg.last_30_days
    s.all_time = agg.all_time
    active = blocks[-1] if blocks and blocks[-1].is_active else None
    s.active_block = active
    s.recent_blocks = list(reversed(blocks[-12:]))
    s.peak_block_tokens = max((b.totals.total_tokens for b in blocks), default=0)
    s.reference_block_tokens = max(
        (b.totals.total_tokens for b in blocks if b is not active), default=0)
    s.daily = agg.daily(30)
    s.weekly = agg.weekly(12)
    s.monthly = agg.monthly(6)
    s.models = agg.by_model()
    s.models_today = agg.by_model(since=start_of_day(time.time()))
    s.projects = agg.by_project()
    s.first_entry = agg.first_entry
    s.last_entry = agg.last_entry
    s.entry_count = len(entries)
    s.updated_at = time.time()
    return s
