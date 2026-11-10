"""Datensätze, Preistabelle, Summen und 5-Std-Fenster (entspricht Model.swift)."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

# MARK: - Preise (USD pro 1 Mio. Tokens)


@dataclass(frozen=True)
class ModelPrice:
    input: float
    output: float

    @property
    def cache_write_5m(self) -> float:  # 1,25x Input
        return self.input * 1.25

    @property
    def cache_write_1h(self) -> float:  # 2x Input
        return self.input * 2.0

    @property
    def cache_read(self) -> float:  # 0,1x Input
        return self.input * 0.1


WEB_SEARCH_COST = 10.0 / 1000.0

# Reihenfolge ist relevant: längere Präfixe zuerst prüfen.
_PRICE_TABLE: list[tuple[str, ModelPrice]] = [
    ("claude-fable-5", ModelPrice(10, 50)),
    ("claude-mythos-5", ModelPrice(10, 50)),
    ("claude-mythos-preview", ModelPrice(10, 50)),
    ("claude-opus-5", ModelPrice(5, 25)),
    ("claude-opus-4-8", ModelPrice(5, 25)),
    ("claude-opus-4-7", ModelPrice(5, 25)),
    ("claude-opus-4-6", ModelPrice(5, 25)),
    ("claude-opus-4-5", ModelPrice(5, 25)),
    ("claude-opus-4-1", ModelPrice(15, 75)),
    ("claude-opus-4", ModelPrice(15, 75)),
    ("claude-sonnet-5", ModelPrice(3, 15)),
    ("claude-sonnet-4-6", ModelPrice(3, 15)),
    ("claude-sonnet-4-5", ModelPrice(3, 15)),
    ("claude-sonnet-4", ModelPrice(3, 15)),
    ("claude-haiku-4-5", ModelPrice(1, 5)),
    ("claude-3-5-haiku", ModelPrice(0.8, 4)),
    ("claude-3-haiku", ModelPrice(0.25, 1.25)),
]


def price_for(model: str) -> ModelPrice | None:
    m = model.lower()
    for prefix, price in _PRICE_TABLE:
        if m.startswith(prefix):
            return price
    return None


_DATE_SUFFIX = re.compile(r"-20[0-9]{6}$")
_display_cache: dict[str, str] = {}


def display_name(model: str) -> str:
    """claude-haiku-4-5-20251001 -> "Haiku 4.5"."""
    cached = _display_cache.get(model)
    if cached is not None:
        return cached
    m = _DATE_SUFFIX.sub("", model).replace("claude-", "")
    parts = m.split("-")
    family = parts[0] if parts else m
    version = ".".join(parts[1:])
    result = f"{family.capitalize()} {version}" if version else family.capitalize()
    _display_cache[model] = result
    return result


# MARK: - Ein einzelner Usage-Datensatz (eine Assistant-Antwort)


@dataclass(slots=True)
class UsageEntry:
    timestamp: float  # Unix-Zeit
    model: str
    input_tokens: int
    output_tokens: int
    cache_write_5m: int
    cache_write_1h: int
    cache_read: int
    web_searches: int
    session_id: str
    project: str
    is_sidechain: bool
    dedup_key: str
    cost: float = 0.0

    def __post_init__(self) -> None:
        p = price_for(self.model)
        if p is None:
            self.cost = 0.0
            return
        per_m = 1_000_000.0
        self.cost = (
            self.input_tokens / per_m * p.input
            + self.output_tokens / per_m * p.output
            + self.cache_write_5m / per_m * p.cache_write_5m
            + self.cache_write_1h / per_m * p.cache_write_1h
            + self.cache_read / per_m * p.cache_read
            + self.web_searches * WEB_SEARCH_COST
        )

    @property
    def total_tokens(self) -> int:
        return (self.input_tokens + self.output_tokens + self.cache_write_5m
                + self.cache_write_1h + self.cache_read)


# MARK: - Summen


@dataclass(slots=True)
class Totals:
    input: int = 0
    output: int = 0
    cache_write_5m: int = 0
    cache_write_1h: int = 0
    cache_read: int = 0
    web_searches: int = 0
    cost: float = 0.0
    requests: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input + self.output + self.cache_write_5m + self.cache_write_1h + self.cache_read

    @property
    def cache_write(self) -> int:
        return self.cache_write_5m + self.cache_write_1h

    def add(self, e: UsageEntry) -> None:
        self.input += e.input_tokens
        self.output += e.output_tokens
        self.cache_write_5m += e.cache_write_5m
        self.cache_write_1h += e.cache_write_1h
        self.cache_read += e.cache_read
        self.web_searches += e.web_searches
        self.cost += e.cost
        self.requests += 1

    def __add__(self, o: Totals) -> Totals:
        return Totals(
            self.input + o.input, self.output + o.output,
            self.cache_write_5m + o.cache_write_5m, self.cache_write_1h + o.cache_write_1h,
            self.cache_read + o.cache_read, self.web_searches + o.web_searches,
            self.cost + o.cost, self.requests + o.requests,
        )


# MARK: - Aggregierte Buckets

DAY, WEEK, MONTH = "day", "week", "month"


@dataclass(slots=True)
class Bucket:
    """Ein Zeitabschnitt der Historie. Die Beschriftung entsteht erst in der
    Anzeige, damit ein Sprachwechsel keine Neuaggregation auslöst."""
    start: float
    kind: str
    week_number: int  # nur bei kind == WEEK gesetzt
    totals: Totals


@dataclass(slots=True)
class NamedTotals:
    name: str
    totals: Totals


@dataclass(slots=True)
class UsageBlock:
    """Ein 5-Stunden-Fenster (entspricht dem Abrechnungsfenster der Claude-Abos)."""
    start: float
    end: float
    last_activity: float
    totals: Totals
    models: list[str] = field(default_factory=list)

    @property
    def is_active(self) -> bool:
        return time.time() < self.end

    @property
    def remaining(self) -> float:
        return max(0.0, self.end - time.time())

    @property
    def elapsed(self) -> float:
        return max(60.0, min(time.time(), self.end) - self.start)

    @property
    def burn_rate(self) -> float:
        """Tokens pro Minute im laufenden Block."""
        return self.totals.total_tokens / (self.elapsed / 60)

    @property
    def projected_tokens(self) -> int:
        """Hochrechnung auf das Blockende bei gleichbleibender Rate."""
        if not self.is_active:
            return self.totals.total_tokens
        return int(self.burn_rate * ((self.end - self.start) / 60))
