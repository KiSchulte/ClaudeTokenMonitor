"""Übersetzungen und sprachabhängige Zahlen-/Datumsformate (entspricht Localization.swift).

Für Englisch wird wie auf dem Mac en_GB-Schreibweise verwendet: 24-Stunden-Uhr
und tagesführende Datumsangaben halten das Layout kompakt.
"""

from __future__ import annotations

import locale
import os
import time
from datetime import datetime

from . import APP_NAME

DE, EN = "de", "en"

# Gespeicherte Sprachwahl
SYSTEM, GERMAN, ENGLISH = "system", "german", "english"
LANGUAGE_CHOICES = (SYSTEM, GERMAN, ENGLISH)


def system_language() -> str:
    for var in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        value = os.environ.get(var)
        if value:
            return DE if value.lower().startswith("de") else EN
    try:
        lang = locale.getlocale()[0] or ""
    except ValueError:
        lang = ""
    return DE if lang.lower().startswith("de") else EN


def resolve(choice: str) -> str:
    if choice == GERMAN:
        return DE
    if choice == ENGLISH:
        return EN
    return system_language()


_MONTHS = {
    DE: ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez."],
    EN: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sept", "Oct", "Nov", "Dec"],
}

NBSP = " "


class Loc:
    def __init__(self, language: str) -> None:
        self.language = language

    def s(self, de: str, en: str) -> str:
        return de if self.language == DE else en

    def language_label(self, choice: str) -> str:
        """Sprachnamen bleiben in ihrer eigenen Sprache, nur "System" wird übersetzt."""
        if choice == GERMAN:
            return "Deutsch"
        if choice == ENGLISH:
            return "English"
        native = "Deutsch" if system_language() == DE else "English"
        return f"{self.system_language} ({native})"

    # MARK: Tabs und Rahmen

    app_name = APP_NAME
    tab_overview = property(lambda self: self.s("Übersicht", "Overview"))
    tab_history = property(lambda self: self.s("Verlauf", "History"))
    tab_blocks = property(lambda self: self.s("Fenster", "Windows"))
    tab_models = property(lambda self: self.s("Modelle", "Models"))
    tab_projects = property(lambda self: self.s("Projekte", "Projects"))

    def header_subtitle(self, requests: int, updated: float) -> str:
        return self.s(f"{self.exact(requests)} Anfragen · Stand {self.relative(updated)}",
                      f"{self.exact(requests)} requests · updated {self.relative(updated)}")

    loading_transcripts = property(lambda self: self.s("Lade Transkripte …", "Loading transcripts …"))
    reading_transcripts = property(lambda self: self.s("Transkripte werden gelesen …", "Reading transcripts …"))
    refresh_tooltip = property(lambda self: self.s("Jetzt neu einlesen", "Reload now"))

    # MARK: Leer- und Fehlerzustände

    def no_transcript_directory(self, path: str) -> str:
        return self.s(f"Kein Transkript-Verzeichnis gefunden unter {path}",
                      f"No transcript directory found at {path}")

    no_usage_data = property(lambda self: self.s("Keine Usage-Daten in den Transkripten gefunden.",
                                                 "No usage data found in the transcripts."))
    no_data = property(lambda self: self.s("Keine Daten.", "No data."))
    no_blocks_recorded = property(lambda self: self.s("Noch keine Fenster aufgezeichnet.",
                                                      "No windows recorded yet."))
    no_activity_recorded = property(lambda self: self.s("Noch keine Aktivität aufgezeichnet.",
                                                        "No activity recorded yet."))

    # MARK: Menü

    settings = property(lambda self: self.s("Einstellungen", "Settings"))
    panel_shows = property(lambda self: self.s("Obere Leiste zeigt", "Top bar shows"))
    cost_also_in_panel = property(lambda self: self.s("Kosten zusätzlich in oberer Leiste",
                                                      "Also show cost in top bar"))
    launch_at_login = property(lambda self: self.s("Bei Anmeldung starten", "Launch at login"))
    open_data_folder = property(lambda self: self.s("Datenquelle in Dateien öffnen", "Open data folder"))
    open_window = property(lambda self: self.s("Übersicht öffnen", "Open overview"))
    refresh = property(lambda self: self.s("Neu einlesen", "Reload"))
    about = property(lambda self: self.s("Über Claude Token Monitor", "About Claude Token Monitor"))
    quit = property(lambda self: self.s("Beenden", "Quit"))
    language_setting = property(lambda self: self.s("Sprache", "Language"))
    system_language = property(lambda self: self.s("Systemsprache", "System language"))
    no_tray_hint = property(lambda self: self.s(
        "Für das Symbol in der oberen Leiste wird die GNOME-Erweiterung "
        "„AppIndicator and KStatusNotifierItem Support“ benötigt.",
        "The top bar icon needs the GNOME extension "
        "“AppIndicator and KStatusNotifierItem Support”."))

    # MARK: Kennzahlen der oberen Leiste

    metric_block_tokens = property(lambda self: self.s("Tokens im 5-Std-Fenster", "Tokens in 5-hour window"))
    metric_today_tokens = property(lambda self: self.s("Tokens heute", "Tokens today"))
    metric_today_cost = property(lambda self: self.s("Kosten heute", "Cost today"))
    metric_month_cost = property(lambda self: self.s("Kosten diesen Monat", "Cost this month"))

    # MARK: Übersicht

    current_window_title = property(lambda self: self.s("Aktuelles 5-Std-Fenster", "Current 5-hour window"))
    until_reset = property(lambda self: self.s("bis Reset", "until reset"))
    tokens_word = property(lambda self: "Tokens")
    requests = property(lambda self: self.s("Anfragen", "Requests"))
    requests_short = property(lambda self: self.s("Anfr.", "req."))
    projection = property(lambda self: self.s("Hochrechnung", "Projection"))
    models = property(lambda self: self.s("Modelle", "Models"))
    no_active_window = property(lambda self: self.s("Kein aktives 5-Std-Fenster", "No active 5-hour window"))

    def record_comparison(self, percent: str, reference: str) -> str:
        return self.s(f"Rekord — {percent} deines bisherigen Höchstwerts ({reference})",
                      f"Record — {percent} of your previous peak ({reference})")

    def peak_comparison(self, percent: str, reference: str) -> str:
        return self.s(f"{percent} deines stärksten Fensters ({reference})",
                      f"{percent} of your strongest window ({reference})")

    def burn_rate(self, value: str) -> str:
        return self.s(f"Rate: {value}/Min", f"Rate: {value}/min")

    def last_window_info(self, tokens: str, ended: str) -> str:
        return self.s(f"Letztes Fenster: {tokens} Tokens, endete {ended}",
                      f"Last window: {tokens} tokens, ended {ended}")

    today = property(lambda self: self.s("Heute", "Today"))
    last_7_days = property(lambda self: self.s("Letzte 7 Tage", "Last 7 days"))
    this_week = property(lambda self: self.s("Diese Woche", "This week"))
    this_month = property(lambda self: self.s("Dieser Monat", "This month"))
    composition_today = property(lambda self: self.s("Zusammensetzung heute", "Composition today"))
    models_today = property(lambda self: self.s("Modelle heute", "Models today"))
    last_14_days = property(lambda self: self.s("Letzte 14 Tage", "Last 14 days"))

    def tokens_suffix(self, value: str) -> str:
        return f"{value} {self.tokens_word}"

    def cost_and_requests(self, cost: str, requests: int) -> str:
        return f"{cost} · {requests} {self.requests_short}"

    # MARK: Token-Arten

    input = property(lambda self: "Input")
    output = property(lambda self: "Output")
    cache_write = property(lambda self: self.s("Cache-Write", "Cache write"))
    cache_read = property(lambda self: self.s("Cache-Read", "Cache read"))

    # MARK: Verlauf

    range_30_days = property(lambda self: self.s("30 Tage", "30 days"))
    range_12_weeks = property(lambda self: self.s("12 Wochen", "12 weeks"))
    range_6_months = property(lambda self: self.s("6 Monate", "6 months"))
    metric_tokens = property(lambda self: "Tokens")
    metric_cost = property(lambda self: self.s("Kosten", "Cost"))
    metric_requests = property(lambda self: self.s("Anfragen", "Requests"))
    sum = property(lambda self: self.s("Summe", "Total"))
    average_per_period = property(lambda self: self.s("Ø pro Periode", "Avg per period"))
    peak = property(lambda self: self.s("Spitze", "Peak"))
    empty_value = "–"

    # MARK: Fenster

    recent_windows = property(lambda self: self.s("Letzte 5-Std-Fenster", "Recent 5-hour windows"))

    def bar_relative_to_max(self, value: str) -> str:
        return self.s(f"Balken relativ zum Maximum ({value})", f"Bars relative to maximum ({value})")

    def still_remaining(self, duration: str) -> str:
        return self.s(f"noch {duration}", f"{duration} left")

    total = property(lambda self: self.s("Gesamt", "Total"))

    def requests_and_tokens(self, requests: int, tokens: int) -> str:
        return self.s(f"{self.exact(requests)} Anfragen · {self.exact(tokens)} Tokens",
                      f"{self.exact(requests)} requests · {self.exact(tokens)} tokens")

    def request_count(self, count: int) -> str:
        return self.s(f"{count} Anfragen", f"{count} requests")

    # MARK: Autostart

    login_active = property(lambda self: self.s("aktiv", "enabled"))
    login_not_registered = property(lambda self: self.s("nicht registriert", "not registered"))

    # MARK: Zahlenformate

    def _swap(self, s: str) -> str:
        """Python formatiert en-Schreibweise; für Deutsch Trennzeichen tauschen."""
        if self.language == DE:
            return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
        return s

    def exact(self, value: int) -> str:
        """Vollständige Zahl mit Tausendertrennzeichen."""
        return self._swap(f"{int(value):,}")

    def _one_decimal(self, v: float) -> str:
        return self._swap(f"{v:,.1f}")

    def tokens(self, value: int) -> str:
        """1.234 / 45K / 1,2M — Dezimaltrennzeichen folgt der Sprache."""
        v = float(value)
        if v >= 1_000_000:
            return self._one_decimal(v / 1_000_000) + "M"
        if v >= 10_000:
            return self.exact(round(v / 1000)) + "K"
        if v >= 1_000:
            return self._one_decimal(v / 1000) + "K"
        return self.exact(int(value))

    def money(self, value: float) -> str:
        """Immer USD — nur die Schreibweise folgt der Sprache."""
        if value < 10:
            text = f"{value:,.2f}"
        else:
            digits = 1 if value < 1000 else 0
            text = f"{value:,.{digits}f}"
            if "." in text:
                text = text.rstrip("0").rstrip(".")
        text = self._swap(text)
        return f"{text}{NBSP}$" if self.language == DE else f"${text}"

    def percent(self, fraction: float) -> str:
        p = self._swap(f"{round(fraction * 100):,}")
        return f"{p}{NBSP}%" if self.language == DE else f"{p}%"

    # MARK: Zeitformate

    def duration(self, seconds: float) -> str:
        total = int(round(seconds))
        hours, minutes = total // 3600, (total % 3600) // 60
        if hours > 0:
            return self.s(f"{hours} Std {minutes} Min", f"{hours} h {minutes} min")
        return self.s(f"{minutes} Min", f"{minutes} min")

    def relative(self, ts: float) -> str:
        seconds = max(0, int(time.time() - ts))
        if seconds < 60:
            return self.s(f"vor {seconds} Sek", f"{seconds} s ago")
        minutes = seconds // 60
        if minutes < 60:
            return self.s(f"vor {minutes} Min", f"{minutes} min ago")
        hours = minutes // 60
        if hours < 24:
            return self.s(f"vor {hours} Std", f"{hours} h ago")
        return self.s(f"vor {hours // 24} Tg", f"{hours // 24} d ago")

    def time(self, ts: float) -> str:
        return datetime.fromtimestamp(ts).strftime("%H:%M")

    def day_month(self, ts: float) -> str:
        d = datetime.fromtimestamp(ts)
        return f"{d.day:02d}.{d.month:02d}." if self.language == DE else f"{d.day:02d}/{d.month:02d}"

    def day_time(self, ts: float) -> str:
        return f"{self.day_month(ts)}, {self.time(ts)}"

    def day(self, ts: float) -> str:
        d = datetime.fromtimestamp(ts)
        sep = "." if self.language == DE else "/"
        return f"{d.day:02d}{sep}{d.month:02d}{sep}{d.year}"

    def label_for(self, bucket) -> str:
        """Achsen- und Zeilenbeschriftung eines Buckets."""
        if bucket.kind == "day":
            return self.day_month(bucket.start)
        if bucket.kind == "week":
            return self.s(f"KW {bucket.week_number}", f"W {bucket.week_number}")
        d = datetime.fromtimestamp(bucket.start)
        return f"{_MONTHS[self.language][d.month - 1]} {d.year % 100:02d}"

    # MARK: Kommandozeilen-Abzug

    cli_source = property(lambda self: self.s("Quelle", "Source"))
    cli_entries = property(lambda self: self.s("Einträge (dedupliziert)", "Entries (deduplicated)"))
    cli_period = property(lambda self: self.s("Zeitraum", "Period"))
    cli_last_30_days = property(lambda self: self.s("Letzte 30 Tage", "Last 30 days"))
    cli_breakdown = property(lambda self: self.s("Aufschlüsselung gesamt", "Overall breakdown"))
    cli_web_searches = property(lambda self: self.s("Web-Suchen", "Web searches"))
    cli_tokens_abbrev = "tok"

    def cli_window_summary(self, count: int, peak: str) -> str:
        return self.s(f"5-Std-Fenster: {count} insgesamt, Maximum {peak} tok",
                      f"5-hour windows: {count} total, maximum {peak} tok")

    cli_active = property(lambda self: self.s("Aktiv", "Active"))
    cli_none = property(lambda self: self.s("keines", "none"))
    cli_last_10_days = property(lambda self: self.s("Letzte 10 Tage", "Last 10 days"))
    cli_autostart = property(lambda self: self.s("Autostart", "Launch at login"))
