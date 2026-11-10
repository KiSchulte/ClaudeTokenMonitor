"""Textabzug derselben Aggregation, die die UI benutzt (entspricht CLIDump.swift)."""

from __future__ import annotations

import sys

from .aggregator import Aggregator
from .loc import DE, EN, Loc, resolve
from .reader import TranscriptReader
from .settings import Settings


def cli_language(args: list[str]) -> str:
    if "--de" in args:
        return DE
    if "--en" in args:
        return EN
    return resolve(Settings().language)


def dump(args: list[str]) -> None:
    loc = Loc(cli_language(args))
    reader = TranscriptReader()
    reader.refresh()
    agg = Aggregator(reader.entries)
    out = sys.stdout.write

    out(f"{loc.cli_source}: {reader.root}\n")
    out(f"{loc.cli_entries}: {len(reader.entries)}\n")
    if agg.first_entry is not None:
        out(f"{loc.cli_period}: {loc.day(agg.first_entry)} – {loc.day(agg.last_entry)}\n")
    out("\n")

    def line(label, t):
        out(f"{label:<18}{loc.exact(t.total_tokens):>15} {loc.cli_tokens_abbrev} "
            f"{loc.money(t.cost):>10}  {t.requests} {loc.requests_short}\n")

    line(loc.today, agg.today)
    line(loc.this_week, agg.current_week)
    line(loc.this_month, agg.current_month)
    line(loc.last_7_days, agg.last_7_days)
    line(loc.cli_last_30_days, agg.last_30_days)
    line(loc.total, agg.all_time)

    a = agg.all_time
    out(f"\n{loc.cli_breakdown}:\n")
    for label, value in ((loc.input, a.input), (loc.output, a.output),
                         (f"{loc.cache_write} 5m", a.cache_write_5m),
                         (f"{loc.cache_write} 1h", a.cache_write_1h),
                         (loc.cache_read, a.cache_read),
                         (loc.cli_web_searches, a.web_searches)):
        out(f"  {label:<18}{loc.exact(value)}\n")

    out(f"\n{loc.models}:\n")
    for m in agg.by_model():
        out(f"  {m.name:<16}{loc.exact(m.totals.total_tokens):>14} {loc.cli_tokens_abbrev}"
            f"  {loc.money(m.totals.cost)}\n")

    out(f"\n{loc.tab_projects}:\n")
    for p in agg.by_project()[:15]:
        out(f"  {p.name[:30]:<30}{loc.exact(p.totals.total_tokens):>14} {loc.cli_tokens_abbrev}"
            f"  {loc.money(p.totals.cost)}\n")

    blocks = agg.blocks
    peak = max((b.totals.total_tokens for b in blocks), default=0)
    out("\n" + loc.cli_window_summary(len(blocks), loc.exact(peak)) + "\n")
    active = blocks[-1] if blocks and blocks[-1].is_active else None
    if active:
        out(f"{loc.cli_active}: {loc.day_time(active.start)} – {loc.time(active.end)}, "
            f"{loc.exact(active.totals.total_tokens)} {loc.cli_tokens_abbrev}, "
            f"{loc.still_remaining(loc.duration(active.remaining))}\n")
    else:
        out(f"{loc.cli_active}: {loc.cli_none}\n")
    for b in blocks[-5:]:
        out(f"  {loc.day_time(b.start)} – {loc.time(b.end)}"
            f"  {loc.exact(b.totals.total_tokens):>14} {loc.cli_tokens_abbrev}"
            f"  {loc.money(b.totals.cost)}\n")

    out(f"\n{loc.cli_last_10_days}:\n")
    for d in agg.daily(10):
        out(f"  {loc.label_for(d)} {loc.exact(d.totals.total_tokens):>14} {loc.cli_tokens_abbrev}"
            f"  {loc.money(d.totals.cost)}\n")
