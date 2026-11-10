"""GTK4/libadwaita-Oberfläche und Symbol in der oberen Leiste.

Entspricht App.swift, UsageStore.swift und Views/*. Das Lesen und Aggregieren
läuft in einem Hintergrund-Thread (wie die serielle Queue der UsageEngine),
die Oberfläche bekommt fertige Snapshots über GLib.idle_add.
"""

from __future__ import annotations

import os
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from . import APP_ID, APP_NAME, VERSION  # noqa: E402
from .aggregator import Snapshot, build_snapshot  # noqa: E402
from .loc import LANGUAGE_CHOICES, Loc, resolve  # noqa: E402
from .reader import TranscriptReader  # noqa: E402
from .settings import (METRIC_BLOCK_TOKENS, METRIC_MONTH_COST,  # noqa: E402
                       METRIC_TODAY_COST, METRIC_TODAY_TOKENS, METRICS,
                       Settings, autostart_enabled, set_autostart)
from .tray import MenuItem, TrayIcon  # noqa: E402
from .widgets import (ACCENT, BLUE, CSS, GREEN, INDIGO, ORANGE,  # noqa: E402
                      PURPLE, RED, TEAL, BarChart, StackedBar, UsageBar, chip,
                      color_dot, hbox, label, ranked_row, section_header,
                      stat_tile, vbox)

REFRESH_SECONDS = 10
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ICON_DIR = os.path.join(DATA_DIR, "icons")
TRAY_ICON = f"{APP_ID}-symbolic"


# MARK: - Engine


class UsageEngine:
    """Besitzt den Reader. Jeder Zugriff passiert unter dem Lock im Worker-Thread."""

    def __init__(self) -> None:
        self.reader = TranscriptReader()
        self._lock = threading.Lock()
        self._busy = False

    @property
    def transcript_path(self) -> str:
        return self.reader.root

    def load(self, done) -> None:
        if self._busy:
            return
        self._busy = True

        def work():
            with self._lock:
                try:
                    if not os.path.isdir(self.reader.root):
                        result = (Snapshot(), "missing")
                    else:
                        self.reader.refresh()
                        entries = list(self.reader.entries)
                        result = (build_snapshot(entries), None if entries else "empty")
                except Exception as e:  # nie die Oberfläche einfrieren lassen
                    print(f"claude-token-monitor: {e!r}", file=sys.stderr)
                    result = (Snapshot(), "empty")
            self._busy = False
            GLib.idle_add(lambda: (done(*result), GLib.SOURCE_REMOVE)[1])

        threading.Thread(target=work, daemon=True).start()


# MARK: - Tab-Seite


class TabPage(Gtk.ScrolledWindow):
    """Scrollbarer Container, dessen Inhalt bei jedem Refresh neu gebaut wird.
    Die Scrollposition bleibt dabei erhalten."""

    def __init__(self) -> None:
        super().__init__(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        self._clamp = Adw.Clamp(maximum_size=720, tightening_threshold=520)
        self.set_child(self._clamp)

    def set_content(self, widget: Gtk.Widget) -> None:
        adj = self.get_vadjustment()
        pos = adj.get_value()
        widget.set_margin_top(12)
        widget.set_margin_bottom(16)
        widget.set_margin_start(12)
        widget.set_margin_end(12)
        self._clamp.set_child(widget)
        if pos > 0:
            GLib.idle_add(lambda: (adj.set_value(pos), GLib.SOURCE_REMOVE)[1])


# MARK: - Fenster


class MainWindow(Adw.ApplicationWindow):
    TABS = ("overview", "history", "blocks", "models", "projects")

    def __init__(self, app: "MonitorApp") -> None:
        super().__init__(application=app, default_width=500, default_height=720,
                         title=APP_NAME, icon_name=APP_ID)
        self.app = app
        self.set_size_request(380, 480)
        self.history_range = "days"
        self.history_metric = "tokens"

        self.title = Adw.WindowTitle(title=APP_NAME)
        header = Adw.HeaderBar(title_widget=self.title)

        refresh = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh.connect("clicked", lambda *_: app.refresh())
        self.refresh_button = refresh
        header.pack_start(refresh)

        self.menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", primary=True)
        header.pack_end(self.menu_button)

        self.stack = Adw.ViewStack(vexpand=True)
        self.pages: dict[str, TabPage] = {}
        self.stack_pages: dict[str, Adw.ViewStackPage] = {}
        icons = {"overview": "ctm-overview-symbolic", "history": "ctm-history-symbolic",
                 "blocks": "ctm-windows-symbolic", "models": "ctm-models-symbolic",
                 "projects": "ctm-projects-symbolic"}
        for name in self.TABS:
            page = TabPage()
            self.pages[name] = page
            self.stack_pages[name] = self.stack.add_titled_with_icon(page, name, name, icons[name])
        self.stack.connect("notify::visible-child-name", lambda *_: self.rebuild())

        # Zustände für Laden und Fehler liegen über den Tabs.
        self.status = Adw.StatusPage(icon_name="content-loading-symbolic", vexpand=True)
        self.status_path = label("", "caption", "dim-label", xalign=0.5, wrap=True)
        self.status_path.set_selectable(True)
        self.status.set_child(self.status_path)
        self.outer = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.outer.add_named(self.status, "status")
        self.outer.add_named(self.stack, "content")

        switcher = Adw.ViewSwitcherBar(stack=self.stack, reveal=True)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(self.outer)
        toolbar.add_bottom_bar(switcher)

        self.toast_overlay = Adw.ToastOverlay(child=toolbar)
        self.set_content(self.toast_overlay)
        self.connect("close-request", self._on_close)

        self.update_texts()

    def _on_close(self, *_):
        # Mit Symbol in der Leiste läuft die App weiter, wie auf dem Mac.
        if self.app.tray and self.app.tray.available:
            self.set_visible(False)
            return True
        self.app.quit()
        return False

    # MARK: Texte

    @property
    def loc(self) -> Loc:
        return self.app.loc

    def update_texts(self) -> None:
        loc = self.loc
        titles = {"overview": loc.tab_overview, "history": loc.tab_history,
                  "blocks": loc.tab_blocks, "models": loc.tab_models,
                  "projects": loc.tab_projects}
        for name, page in self.stack_pages.items():
            page.set_title(titles[name])
        self.refresh_button.set_tooltip_text(loc.refresh_tooltip)
        self.menu_button.set_menu_model(self.app.build_menu())
        self.update_header()

    def update_header(self) -> None:
        snap = self.app.snapshot
        if snap.entry_count > 0:
            self.title.set_subtitle(self.loc.header_subtitle(snap.entry_count, snap.updated_at))
        else:
            self.title.set_subtitle(self.loc.loading_transcripts)

    # MARK: Inhalt

    def rebuild(self) -> None:
        if not self.get_visible():
            return
        app, loc = self.app, self.loc
        self.update_header()
        if app.is_loading:
            self.status.set_icon_name("content-loading-symbolic")
            self.status.set_title(loc.reading_transcripts)
            self.status.set_description(None)
            self.status_path.set_text("")
            self.outer.set_visible_child_name("status")
            return
        if app.problem and app.snapshot.entry_count == 0:
            self.status.set_icon_name("folder-symbolic")
            self.status.set_title(loc.no_transcript_directory(app.engine.transcript_path)
                                  if app.problem == "missing" else loc.no_usage_data)
            self.status_path.set_text(app.engine.transcript_path)
            self.outer.set_visible_child_name("status")
            return
        self.outer.set_visible_child_name("content")

        name = self.stack.get_visible_child_name() or "overview"
        builder = {
            "overview": self._overview,
            "history": self._history,
            "blocks": self._blocks,
            "models": lambda: self._breakdown("models"),
            "projects": lambda: self._breakdown("projects"),
        }[name]
        self.pages[name].set_content(builder())

    # MARK: Übersicht

    def _overview(self) -> Gtk.Widget:
        snap, loc = self.app.snapshot, self.loc
        root = vbox(14)
        root.append(self._block_card())

        grid = Gtk.Grid(column_spacing=6, row_spacing=6, column_homogeneous=True)
        grid.attach(stat_tile(loc.today, loc.tokens(snap.today.total_tokens),
                              loc.cost_and_requests(loc.money(snap.today.cost), snap.today.requests)),
                    0, 0, 1, 1)
        grid.attach(stat_tile(loc.last_7_days, loc.tokens(snap.last_7_days.total_tokens),
                              loc.money(snap.last_7_days.cost), PURPLE), 1, 0, 1, 1)
        grid.attach(stat_tile(loc.this_week, loc.tokens(snap.week.total_tokens),
                              loc.money(snap.week.cost), TEAL), 0, 1, 1, 1)
        grid.attach(stat_tile(loc.this_month, loc.tokens(snap.month.total_tokens),
                              loc.money(snap.month.cost), INDIGO), 1, 1, 1, 1)
        root.append(grid)

        comp = vbox(7, "ctm-section")
        comp.append(section_header(loc.composition_today,
                                   loc.tokens_suffix(loc.exact(snap.today.total_tokens))))
        comp.append(self._token_breakdown(snap.today))
        root.append(comp)

        if snap.models_today:
            sec = vbox(8)
            sec.append(section_header(loc.models_today))
            max_tokens = max(1, snap.models_today[0].totals.total_tokens)
            for item in snap.models_today[:4]:
                t = item.totals
                sec.append(ranked_row(item.name, loc.tokens(t.total_tokens), loc.money(t.cost),
                                      loc.requests_and_tokens(t.requests, t.total_tokens),
                                      t.total_tokens / max_tokens, ORANGE))
            root.append(sec)

        last14 = snap.daily[-14:]
        if last14:
            sec = vbox(6)
            sec.append(section_header(loc.last_14_days,
                                      loc.tokens(sum(b.totals.total_tokens for b in last14))))
            sec.append(BarChart([float(b.totals.total_tokens) for b in last14],
                                [loc.label_for(b) for b in last14],
                                lambda v: loc.tokens_suffix(loc.tokens(int(v))),
                                BLUE, height=64, label_stride=2))
            root.append(sec)

        if snap.first_entry is not None:
            root.append(label(f"{loc.day(snap.first_entry)} – {loc.day(snap.last_entry)}",
                              "caption", "dim-label", xalign=0.5))
        return root

    def _block_card(self) -> Gtk.Widget:
        snap, loc = self.app.snapshot, self.loc
        card = vbox(8, "ctm-block-card")
        block = snap.active_block
        if block is None:
            row = hbox(12)
            icon = Gtk.Image(icon_name="weather-clear-night-symbolic", pixel_size=24)
            icon.add_css_class("dim-label")
            row.append(icon)
            col = vbox(2)
            col.append(label(loc.no_active_window, "heading"))
            if snap.recent_blocks:
                last = snap.recent_blocks[0]
                col.append(label(loc.last_window_info(loc.tokens(last.totals.total_tokens),
                                                      loc.relative(last.end)),
                                 "caption", "dim-label", wrap=True))
            else:
                col.append(label(loc.no_activity_recorded, "caption", "dim-label"))
            row.append(col)
            card.append(row)
            return card

        top = hbox(8)
        left = vbox(1)
        left.set_hexpand(True)
        left.append(label(loc.current_window_title.upper(), "ctm-tile-title", "dim-label"))
        left.append(label(f"{loc.time(block.start)} – {loc.time(block.end)}", "caption", "dim-label"))
        top.append(left)
        right = vbox(1)
        right.append(label(loc.duration(block.remaining), "ctm-remaining", xalign=1.0))
        right.append(label(loc.until_reset, "ctm-small", "dim-label", xalign=1.0))
        top.append(right)
        card.append(top)

        nums = hbox(8)
        big = label(loc.tokens(block.totals.total_tokens), "ctm-big", "numeric")
        big.set_valign(Gtk.Align.BASELINE_FILL)
        nums.append(big)
        unit = label(loc.tokens_word, "dim-label", hexpand=True)
        unit.set_valign(Gtk.Align.BASELINE_FILL)
        nums.append(unit)
        cost = label(loc.money(block.totals.cost), "title-3", "dim-label", "numeric")
        cost.set_valign(Gtk.Align.BASELINE_FILL)
        nums.append(cost)
        card.append(nums)

        # Referenz ist das stärkste *abgeschlossene* Fenster — echte
        # Abo-Limits stehen lokal nicht zur Verfügung.
        if snap.reference_block_tokens > 0:
            fraction = block.totals.total_tokens / snap.reference_block_tokens
            color = RED if fraction >= 0.9 else ORANGE if fraction >= 0.65 else ACCENT
            card.append(UsageBar(fraction, color, 6))
            info = hbox(8)
            percent, ref = loc.percent(fraction), loc.tokens(snap.reference_block_tokens)
            text = (loc.record_comparison(percent, ref) if fraction > 1
                    else loc.peak_comparison(percent, ref))
            info.append(label(text, "ctm-small", "dim-label", hexpand=True, ellipsize=True))
            info.append(label(loc.burn_rate(loc.tokens(int(block.burn_rate))), "ctm-small", "dim-label"))
            card.append(info)

        chips = hbox(6)
        chips.append(chip(loc.projection, loc.tokens(block.projected_tokens)))
        chips.append(chip(loc.requests, loc.exact(block.totals.requests)))
        if block.models:
            chips.append(chip(loc.models, ", ".join(block.models)))
        card.append(chips)
        return card

    def _token_breakdown(self, totals) -> Gtk.Widget:
        loc = self.loc
        rows = [(loc.input, totals.input, BLUE), (loc.output, totals.output, ORANGE),
                (loc.cache_write, totals.cache_write, PURPLE),
                (loc.cache_read, totals.cache_read, TEAL)]
        total = totals.total_tokens
        box = vbox(5)
        box.append(StackedBar([((v / total) if total else 0, c) for _, v, c in rows]))
        for name, value, color in rows:
            row = hbox(6)
            row.append(color_dot(color))
            row.append(label(name, "caption", "dim-label", hexpand=True))
            row.append(label(loc.exact(value), "caption", "numeric"))
            pct = label(loc.percent(value / total if total else 0), "ctm-small", "dim-label",
                        "numeric", xalign=1.0)
            pct.set_size_request(40, -1)
            row.append(pct)
            box.append(row)
        return box

    # MARK: Verlauf

    def _history(self) -> Gtk.Widget:
        snap, loc = self.app.snapshot, self.loc
        buckets = {"days": snap.daily, "weeks": snap.weekly, "months": snap.monthly}[self.history_range]
        stride = 3 if self.history_range == "days" else 1
        metric = self.history_metric

        def value(t) -> float:
            return {"tokens": float(t.total_tokens), "cost": t.cost,
                    "requests": float(t.requests)}[metric]

        def fmt(v: float) -> str:
            if metric == "tokens":
                return loc.tokens_suffix(loc.tokens(int(v)))
            if metric == "cost":
                return loc.money(v)
            return loc.request_count(int(v))

        color = {"tokens": BLUE, "cost": GREEN, "requests": PURPLE}[metric]

        root = vbox(10)
        root.append(self._toggle_group(
            [("days", loc.range_30_days), ("weeks", loc.range_12_weeks), ("months", loc.range_6_months)],
            self.history_range, "history_range"))
        root.append(self._toggle_group(
            [("tokens", loc.metric_tokens), ("cost", loc.metric_cost), ("requests", loc.metric_requests)],
            self.history_metric, "history_metric"))

        root.append(BarChart([value(b.totals) for b in buckets], [loc.label_for(b) for b in buckets],
                             fmt, color, height=120, label_stride=stride))

        total_tokens = sum(b.totals.total_tokens for b in buckets)
        total_cost = sum(b.totals.cost for b in buckets)
        n = len(buckets)
        peak = max(buckets, key=lambda b: b.totals.total_tokens, default=None)
        peak_label = loc.label_for(peak) if peak and peak.totals.total_tokens > 0 else loc.empty_value
        tiles = Gtk.Grid(column_spacing=6, column_homogeneous=True)
        tiles.attach(stat_tile(loc.sum, loc.tokens(total_tokens), loc.money(total_cost)), 0, 0, 1, 1)
        tiles.attach(stat_tile(loc.average_per_period, loc.tokens(total_tokens // n if n else 0),
                               loc.money(total_cost / n) if n else loc.empty_value, TEAL), 1, 0, 1, 1)
        tiles.attach(stat_tile(loc.peak, loc.tokens(peak.totals.total_tokens if peak else 0),
                               peak_label, ORANGE), 2, 0, 1, 1)
        root.append(tiles)

        root.append(Gtk.Separator())
        max_v = max((value(b.totals) for b in buckets), default=0)
        rows = vbox(4)
        for b in reversed(buckets):
            row = hbox(8)
            name = label(loc.label_for(b), "caption", "ctm-row-title")
            name.set_size_request(64, -1)
            row.append(name)
            row.append(UsageBar(value(b.totals) / max_v if max_v > 0 else 0, color, 5))
            tok = label(loc.tokens(b.totals.total_tokens), "caption", "numeric", xalign=1.0)
            tok.set_size_request(58, -1)
            row.append(tok)
            cost = label(loc.money(b.totals.cost), "ctm-small", "dim-label", "numeric", xalign=1.0)
            cost.set_size_request(58, -1)
            row.append(cost)
            rows.append(row)
        root.append(rows)
        return root

    def _toggle_group(self, items, active: str, attr: str) -> Gtk.Widget:
        group = Adw.ToggleGroup(homogeneous=True)
        for name, title in items:
            group.add(Adw.Toggle(name=name, label=title))
        group.set_active_name(active)

        def changed(g, _pspec):
            new = g.get_active_name()
            if new and new != getattr(self, attr):
                setattr(self, attr, new)
                GLib.idle_add(lambda: (self.rebuild(), GLib.SOURCE_REMOVE)[1])

        group.connect("notify::active-name", changed)
        return group

    # MARK: Fenster

    def _blocks(self) -> Gtk.Widget:
        snap, loc = self.app.snapshot, self.loc
        peak = max(1, snap.peak_block_tokens)
        root = vbox(10)
        head = hbox(8)
        head.append(label(loc.recent_windows, "heading", hexpand=True))
        head.append(label(loc.bar_relative_to_max(loc.tokens(peak)), "ctm-small", "dim-label"))
        root.append(head)
        if not snap.recent_blocks:
            root.append(label(loc.no_blocks_recorded, "dim-label", xalign=0.5))
            return root

        for block in snap.recent_blocks:
            box = vbox(4)
            top = hbox(6)
            if block.is_active:
                top.append(color_dot(GREEN, 7))
            title = label(f"{loc.day_time(block.start)} – {loc.time(block.end)}", hexpand=True)
            if block.is_active:
                title.add_css_class("ctm-row-title")
            top.append(title)
            top.append(label(loc.tokens(block.totals.total_tokens), "ctm-row-title", "numeric"))
            cost = label(loc.money(block.totals.cost), "caption", "dim-label", "numeric", xalign=1.0)
            cost.set_size_request(60, -1)
            top.append(cost)
            box.append(top)
            box.append(UsageBar(block.totals.total_tokens / peak, GREEN if block.is_active else ACCENT, 5))
            meta = hbox(8)
            meta.append(label(loc.request_count(block.totals.requests), "ctm-small", "dim-label"))
            if block.is_active:
                meta.append(label(loc.still_remaining(loc.duration(block.remaining)),
                                  "ctm-small", "ctm-remaining"))
            if block.models:
                meta.append(label(", ".join(block.models), "ctm-small", "dim-label",
                                  ellipsize=True, hexpand=True))
            box.append(meta)
            root.append(box)
        return root

    # MARK: Modelle / Projekte

    def _breakdown(self, mode: str) -> Gtk.Widget:
        snap, loc = self.app.snapshot, self.loc
        items = snap.models if mode == "models" else snap.projects
        color = ORANGE if mode == "models" else TEAL
        tokens = sum(i.totals.total_tokens for i in items)
        cost = sum(i.totals.cost for i in items)
        requests = sum(i.totals.requests for i in items)

        root = vbox(12)
        tiles = Gtk.Grid(column_spacing=6, column_homogeneous=True)
        tiles.attach(stat_tile(loc.total, loc.tokens(tokens), loc.money(cost)), 0, 0, 1, 1)
        tiles.attach(stat_tile(loc.tab_models if mode == "models" else loc.tab_projects,
                               str(len(items)), loc.request_count(requests), color), 1, 0, 1, 1)
        root.append(tiles)
        root.append(Gtk.Separator())
        if not items:
            root.append(label(loc.no_data, "dim-label", xalign=0.5))
            return root
        max_tokens = max(1, items[0].totals.total_tokens)
        for item in items:
            t = item.totals
            root.append(ranked_row(item.name, loc.tokens(t.total_tokens), loc.money(t.cost),
                                   loc.requests_and_tokens(t.requests, t.total_tokens),
                                   t.total_tokens / max_tokens, color))
        return root


# MARK: - Anwendung


class MonitorApp(Adw.Application):
    def __init__(self, start_hidden: bool) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.start_hidden = start_hidden
        self.settings = Settings()
        self.engine = UsageEngine()
        self.snapshot = Snapshot()
        self.is_loading = True
        self.problem: str | None = None
        self.window: MainWindow | None = None
        self.tray: TrayIcon | None = None
        self._held = False
        self._first_activation = True

    @property
    def loc(self) -> Loc:
        return Loc(resolve(self.settings.language))

    # MARK: Lebenszyklus

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        GLib.set_application_name(APP_NAME)

        display = Gdk.Display.get_default()
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        if os.path.isdir(ICON_DIR):
            Gtk.IconTheme.get_for_display(display).add_search_path(ICON_DIR)

        self._create_actions()
        self.set_accels_for_action("app.refresh", ["<Control>r", "F5"])
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("window.close", ["<Control>w"])

        self.window = MainWindow(self)

        try:
            self.tray = TrayIcon(
                self.get_dbus_connection(), "claude-token-monitor", TRAY_ICON,
                ICON_DIR if os.path.isdir(ICON_DIR) else "",
                on_activate=self.toggle_window,
                on_availability=self._tray_availability)
            self.tray.set_title(APP_NAME)
            self._update_tray_menu()
        except Exception as e:  # ohne Symbol bleibt die App als normales Fenster nutzbar
            print(f"claude-token-monitor: kein Symbol in der Leiste: {e!r}", file=sys.stderr)
            self.tray = None

        self.refresh()
        GLib.timeout_add_seconds(REFRESH_SECONDS, self._tick)

    def do_activate(self) -> None:
        # Autostart (--hidden) zeigt beim ersten Mal nur das Symbol —
        # außer es gibt keine Leiste, in der es erscheinen könnte.
        hidden = self._first_activation and self.start_hidden
        self._first_activation = False
        if hidden:
            GLib.timeout_add_seconds(3, self._show_if_no_tray)
            return
        self.show_window()

    def _show_if_no_tray(self) -> bool:
        if not (self.tray and self.tray.available):
            self.show_window()
        return GLib.SOURCE_REMOVE

    def _tray_availability(self, available: bool) -> None:
        # Mit Symbol in der Leiste soll die App ohne offenes Fenster weiterlaufen.
        if available and not self._held:
            self.hold()
            self._held = True
        elif not available and self._held:
            self.release()
            self._held = False
            if self.window and not self.window.get_visible():
                self.show_window()

    # MARK: Fenster

    def show_window(self) -> None:
        if self.window is None:
            return
        was_visible = self.window.get_visible()
        self.window.present()
        if not was_visible:
            self.refresh()
            self.window.rebuild()

    def toggle_window(self) -> None:
        if self.window and self.window.get_visible() and self.window.is_active():
            self.window.set_visible(False)
        else:
            self.show_window()

    # MARK: Daten

    def _tick(self) -> bool:
        self.refresh()
        return GLib.SOURCE_CONTINUE

    def refresh(self) -> None:
        self.engine.load(self._loaded)

    def _loaded(self, snapshot: Snapshot, problem: str | None) -> None:
        self.snapshot = snapshot
        self.problem = problem
        self.is_loading = False
        self._update_tray_label()
        if self.window:
            self.window.rebuild()

    # MARK: Obere Leiste

    def tray_text(self) -> tuple[str, str | None]:
        snap, loc, metric = self.snapshot, self.loc, self.settings.metric
        block = snap.active_block
        if metric == METRIC_BLOCK_TOKENS:
            primary = loc.tokens(block.totals.total_tokens if block else 0)
            secondary = loc.money(block.totals.cost if block else 0)
        elif metric == METRIC_TODAY_TOKENS:
            primary, secondary = loc.tokens(snap.today.total_tokens), loc.money(snap.today.cost)
        elif metric == METRIC_TODAY_COST:
            primary, secondary = loc.money(snap.today.cost), None
        else:
            primary, secondary = loc.money(snap.month.cost), None
        return primary, (secondary if self.settings.show_cost else None)

    def _update_tray_label(self) -> None:
        if not self.tray:
            return
        primary, secondary = self.tray_text()
        self.tray.set_label(f"{primary} · {secondary}" if secondary else primary)
        loc, snap = self.loc, self.snapshot
        lines = [f"{loc.today}: {loc.tokens(snap.today.total_tokens)} · {loc.money(snap.today.cost)}",
                 f"{loc.this_month}: {loc.tokens(snap.month.total_tokens)} · {loc.money(snap.month.cost)}"]
        if snap.active_block:
            lines.insert(0, f"{loc.current_window_title}: "
                            f"{loc.still_remaining(loc.duration(snap.active_block.remaining))}")
        self.tray.set_tooltip("\n".join(lines))

    def _metric_labels(self, loc: Loc) -> dict[str, str]:
        return {METRIC_BLOCK_TOKENS: loc.metric_block_tokens,
                METRIC_TODAY_TOKENS: loc.metric_today_tokens,
                METRIC_TODAY_COST: loc.metric_today_cost,
                METRIC_MONTH_COST: loc.metric_month_cost}

    def _update_tray_menu(self) -> None:
        if not self.tray:
            return
        loc = self.loc
        items = [MenuItem(loc.open_window, on_click=self.show_window),
                 MenuItem(loc.refresh, on_click=self.refresh),
                 MenuItem(kind="separator"),
                 MenuItem(loc.panel_shows, kind="header")]
        for metric, title in self._metric_labels(loc).items():
            items.append(MenuItem(title, kind="radio", checked=self.settings.metric == metric,
                                  on_click=lambda m=metric: self.set_metric(m)))
        items += [MenuItem(loc.cost_also_in_panel, kind="check", checked=self.settings.show_cost,
                           on_click=lambda: self.set_show_cost(not self.settings.show_cost)),
                  MenuItem(kind="separator"),
                  MenuItem(loc.launch_at_login, kind="check", checked=autostart_enabled(),
                           on_click=lambda: self.set_autostart(not autostart_enabled())),
                  MenuItem(kind="separator"),
                  MenuItem(loc.quit, on_click=self.quit)]
        self.tray.set_menu(items)

    # MARK: Einstellungen

    def _settings_changed(self) -> None:
        self.settings.save()
        self._update_tray_label()
        self._update_tray_menu()
        for name in ("language", "metric"):
            action = self.lookup_action(name)
            action.set_state(GLib.Variant("s", getattr(self.settings, name)))
        self.lookup_action("show-cost").set_state(GLib.Variant("b", self.settings.show_cost))
        self.lookup_action("autostart").set_state(GLib.Variant("b", autostart_enabled()))

    def set_metric(self, metric: str) -> None:
        if metric in METRICS:
            self.settings.metric = metric
            self._settings_changed()

    def set_show_cost(self, value: bool) -> None:
        self.settings.show_cost = value
        self._settings_changed()

    def set_language(self, language: str) -> None:
        if language in LANGUAGE_CHOICES:
            self.settings.language = language
            self._settings_changed()
            if self.window:
                self.window.update_texts()
                self.window.rebuild()

    def set_autostart(self, enabled: bool) -> None:
        error = set_autostart(enabled)
        if error and self.window:
            self.window.toast_overlay.add_toast(Adw.Toast(title=error))
        self._settings_changed()

    # MARK: Aktionen und Menü

    def _create_actions(self) -> None:
        def simple(name, callback):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda *_: callback())
            self.add_action(action)

        simple("refresh", self.refresh)
        simple("quit", self.quit)
        simple("about", self._about)
        simple("open-folder", self._open_folder)

        def stateful(name, state, callback):
            ptype = GLib.VariantType.new("s") if state.get_type_string() == "s" else None
            action = Gio.SimpleAction.new_stateful(name, ptype, state)
            action.connect("change-state", callback)
            self.add_action(action)

        stateful("language", GLib.Variant("s", self.settings.language),
                 lambda a, v: self.set_language(v.get_string()))
        stateful("metric", GLib.Variant("s", self.settings.metric),
                 lambda a, v: self.set_metric(v.get_string()))
        stateful("show-cost", GLib.Variant("b", self.settings.show_cost),
                 lambda a, v: self.set_show_cost(v.get_boolean()))
        stateful("autostart", GLib.Variant("b", autostart_enabled()),
                 lambda a, v: self.set_autostart(v.get_boolean()))

    def build_menu(self) -> Gio.Menu:
        loc = self.loc
        menu = Gio.Menu()

        language = Gio.Menu()
        for choice in LANGUAGE_CHOICES:
            language.append(loc.language_label(choice), f"app.language::{choice}")
        menu.append_submenu(loc.language_setting, language)

        panel = Gio.Menu()
        metrics = Gio.Menu()
        for metric, title in self._metric_labels(loc).items():
            metrics.append(title, f"app.metric::{metric}")
        panel.append_section(None, metrics)
        cost = Gio.Menu()
        cost.append(loc.cost_also_in_panel, "app.show-cost")
        panel.append_section(None, cost)
        menu.append_submenu(loc.panel_shows, panel)

        section = Gio.Menu()
        section.append(loc.launch_at_login, "app.autostart")
        section.append(loc.open_data_folder, "app.open-folder")
        menu.append_section(None, section)

        last = Gio.Menu()
        last.append(loc.about, "app.about")
        last.append(loc.quit, "app.quit")
        menu.append_section(None, last)
        return menu

    def _open_folder(self) -> None:
        path = self.engine.transcript_path
        if not os.path.isdir(path):
            path = os.path.dirname(path)
        Gtk.FileLauncher.new(Gio.File.new_for_path(path)).launch(self.window, None, None, None)

    def _about(self) -> None:
        loc = self.loc
        about = Adw.AboutDialog(
            application_name=APP_NAME,
            application_icon=APP_ID,
            version=VERSION,
            developer_name="Kirsten M. Schulte",
            comments=loc.s(
                "Liest den Claude-Token-Verbrauch aus den lokalen Claude-Code-Transkripten. "
                "Keine Netzwerkzugriffe, keine API-Keys.\n\n"
                "Kosten sind der API-Listenpreis-Gegenwert, nicht das, was ein Abo kostet. "
                "Der Balken des 5-Std-Fensters vergleicht mit deinem stärksten "
                "abgeschlossenen Fenster, nicht mit dem echten Limit — dafür /usage in Claude Code.",
                "Reads Claude token usage from the local Claude Code transcripts. "
                "No network access, no API keys.\n\n"
                "Costs are the API list-price equivalent, not what a subscription costs. "
                "The 5-hour window bar compares against your strongest completed window, "
                "not the real limit — use /usage in Claude Code for that."),
        )
        if not (self.tray and self.tray.available):
            about.set_release_notes(f"<p>{GLib.markup_escape_text(loc.no_tray_hint)}</p>")
        about.present(self.window)


def run(argv: list[str]) -> int:
    hidden = "--hidden" in argv
    argv = [a for a in argv if a != "--hidden"]
    app = MonitorApp(start_hidden=hidden)
    return app.run(argv)
