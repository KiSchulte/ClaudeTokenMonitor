"""Wiederverwendbare Bausteine (entspricht Views/Components.swift)."""

from __future__ import annotations

import math
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Adw, Gdk, Gtk, Pango, PangoCairo  # noqa: E402

# Adwaita-Palette — gut lesbar im hellen wie im dunklen Stil.
BLUE = "#3584e4"
ORANGE = "#ff7800"
PURPLE = "#9141ac"
TEAL = "#2190a4"
INDIGO = "#5a5fd6"
GREEN = "#2ec27e"
RED = "#e01b24"
ACCENT = "accent"  # Systemakzentfarbe


def rgba(color: str) -> Gdk.RGBA:
    if color == ACCENT:
        try:
            return Adw.StyleManager.get_default().get_accent_color_rgba()
        except AttributeError:
            color = BLUE
    c = Gdk.RGBA()
    c.parse(color)
    return c


CSS = """
.ctm-block-card {
  background-color: alpha(var(--accent-bg-color), 0.08);
  border: 1px solid alpha(var(--accent-bg-color), 0.22);
  border-radius: 12px;
  padding: 12px;
}
.ctm-tile {
  background-color: alpha(currentColor, 0.05);
  border-radius: 10px;
  padding: 8px 10px;
}
.ctm-section {
  background-color: alpha(currentColor, 0.04);
  border-radius: 10px;
  padding: 10px;
}
.ctm-big { font-size: 24pt; font-weight: 800; }
.ctm-tile-value { font-size: 15pt; font-weight: 700; }
.ctm-tile-title { font-size: 8pt; font-weight: 600; }
.ctm-chip {
  background-color: alpha(currentColor, 0.07);
  border-radius: 99px;
  padding: 2px 8px;
  font-size: 8pt;
}
.ctm-small { font-size: 8pt; }
.ctm-row-title { font-weight: 600; }
.ctm-remaining { color: #e66100; font-weight: 600; }
.ctm-c-blue { color: #3584e4; }
.ctm-c-orange { color: #e66100; }
.ctm-c-purple { color: #9141ac; }
.ctm-c-teal { color: #2190a4; }
.ctm-c-indigo { color: #5a5fd6; }
.ctm-c-accent { color: var(--accent-color); }
"""

COLOR_CLASS = {BLUE: "ctm-c-blue", ORANGE: "ctm-c-orange", PURPLE: "ctm-c-purple",
               TEAL: "ctm-c-teal", INDIGO: "ctm-c-indigo", ACCENT: "ctm-c-accent"}


def label(text: str, *classes: str, xalign: float = 0.0, ellipsize: bool = False,
          wrap: bool = False, hexpand: bool = False) -> Gtk.Label:
    lbl = Gtk.Label(label=text, xalign=xalign, hexpand=hexpand)
    for c in classes:
        lbl.add_css_class(c)
    if ellipsize:
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
    if wrap:
        lbl.set_wrap(True)
        lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    return lbl


def vbox(spacing: int = 0, *classes: str) -> Gtk.Box:
    b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
    for c in classes:
        b.add_css_class(c)
    return b


def hbox(spacing: int = 0, *classes: str) -> Gtk.Box:
    b = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=spacing)
    for c in classes:
        b.add_css_class(c)
    return b


def _rounded_rect(cr, x, y, w, h, r) -> None:
    r = max(0.0, min(r, w / 2, h / 2))
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _fg(widget: Gtk.Widget) -> Gdk.RGBA:
    return widget.get_color()


# MARK: - Fortschrittsbalken


class UsageBar(Gtk.DrawingArea):
    def __init__(self, fraction: float, color: str = ACCENT, height: int = 6) -> None:
        super().__init__(hexpand=True, valign=Gtk.Align.CENTER)
        self.fraction = fraction
        self.color = color
        self.set_content_height(height)
        self.set_draw_func(self._draw)

    def _draw(self, area, cr, w, h) -> None:
        fg = _fg(self)
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.1)
        _rounded_rect(cr, 0, 0, w, h, h / 2)
        cr.fill()
        f = min(1.0, max(0.0, self.fraction))
        c = rgba(self.color)
        cr.set_source_rgba(c.red, c.green, c.blue, 1)
        _rounded_rect(cr, 0, 0, max(2.0, w * f), h, h / 2)
        cr.fill()


# MARK: - Gestapelter Anteilsbalken


class StackedBar(Gtk.DrawingArea):
    def __init__(self, parts: list[tuple[float, str]], height: int = 6) -> None:
        super().__init__(hexpand=True)
        self.parts = parts
        self.set_content_height(height)
        self.set_draw_func(self._draw)

    def _draw(self, area, cr, w, h) -> None:
        _rounded_rect(cr, 0, 0, w, h, h / 2)
        cr.clip()
        fg = _fg(self)
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.1)
        cr.paint()
        x = 0.0
        for fraction, color in self.parts:
            width = w * fraction
            if width <= 0:
                continue
            c = rgba(color)
            cr.set_source_rgba(c.red, c.green, c.blue, 1)
            cr.rectangle(x, 0, max(0.0, width - 1), h)
            cr.fill()
            x += width


# MARK: - Balkendiagramm über Buckets


class BarChart(Gtk.DrawingArea):
    LABEL_HEIGHT = 14

    def __init__(self, values: list[float], labels: list[str],
                 formatter: Callable[[float], str], color: str = BLUE,
                 height: int = 96, label_stride: int = 1) -> None:
        super().__init__(hexpand=True)
        self.values = values
        self.labels = labels
        self.formatter = formatter
        self.color = color
        self.chart_height = height
        self.label_stride = max(1, label_stride)
        self.set_content_height(height + self.LABEL_HEIGHT + 4)
        self.set_draw_func(self._draw)
        self.set_has_tooltip(True)
        self.connect("query-tooltip", self._tooltip)

    def _slot(self) -> float:
        return self.get_width() / max(1, len(self.values))

    def _draw(self, area, cr, w, h) -> None:
        n = len(self.values)
        if n == 0:
            return
        max_v = max(1e-9, max(self.values))
        slot = w / n
        gap = 3.0 if slot > 8 else 1.0
        fg = _fg(self)
        c = rgba(self.color)
        for i, v in enumerate(self.values):
            x = i * slot + gap / 2
            bw = max(1.0, slot - gap)
            if v > 0:
                bh = max(2.0, self.chart_height * (v / max_v))
                cr.set_source_rgba(c.red, c.green, c.blue, 1)
            else:
                bh = 1.0
                cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.12)
            _rounded_rect(cr, x, self.chart_height - bh, bw, bh, min(2.0, bw / 2))
            cr.fill()

        # Beschriftung mittig unter dem Balken; darf breiter sein als der Balken.
        layout = PangoCairo.create_layout(cr)
        font = Pango.FontDescription.from_string("Sans 7")
        layout.set_font_description(font)
        cr.set_source_rgba(fg.red, fg.green, fg.blue, 0.55)
        for i, text in enumerate(self.labels):
            if i % self.label_stride:
                continue
            layout.set_text(text, -1)
            tw, _ = layout.get_pixel_size()
            x = slot * (i + 0.5) - tw / 2
            x = max(0, min(w - tw, x))
            cr.move_to(x, self.chart_height + 4)
            PangoCairo.show_layout(cr, layout)

    def _tooltip(self, widget, x, y, keyboard, tooltip) -> bool:
        if not self.values:
            return False
        i = int(x / max(1e-9, self._slot()))
        if not 0 <= i < len(self.values):
            return False
        tooltip.set_text(f"{self.labels[i]}: {self.formatter(self.values[i])}")
        return True


# MARK: - Kachel, Zeilen, Überschriften


def stat_tile(title: str, value: str, subtitle: str | None = None, accent: str = ACCENT) -> Gtk.Widget:
    box = vbox(2, "ctm-tile")
    box.set_hexpand(True)
    box.append(label(title.upper(), "ctm-tile-title", "dim-label", ellipsize=True))
    box.append(label(value, "ctm-tile-value", "numeric", COLOR_CLASS.get(accent, ""), ellipsize=True))
    if subtitle:
        box.append(label(subtitle, "caption", "dim-label", ellipsize=True))
    return box


def section_header(title: str, trailing: str | None = None) -> Gtk.Widget:
    row = hbox(6)
    row.append(label(title, "heading", hexpand=True))
    if trailing:
        row.append(label(trailing, "caption", "dim-label"))
    return row


def ranked_row(name: str, tokens: str, cost: str, subtitle: str, fraction: float,
               color: str) -> Gtk.Widget:
    box = vbox(3)
    top = hbox(6)
    name_lbl = label(name, "ctm-row-title", hexpand=True)
    name_lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
    top.append(name_lbl)
    top.append(label(tokens, "ctm-row-title", "numeric"))
    cost_lbl = label(cost, "caption", "dim-label", "numeric", xalign=1.0)
    cost_lbl.set_size_request(60, -1)
    top.append(cost_lbl)
    box.append(top)
    box.append(UsageBar(fraction, color, 4))
    box.append(label(subtitle, "ctm-small", "dim-label"))
    return box


def chip(title: str, value: str) -> Gtk.Widget:
    box = hbox(4, "ctm-chip")
    box.append(label(title, "dim-label"))
    v = label(value, ellipsize=True)
    v.set_max_width_chars(28)
    box.append(v)
    return box


def color_dot(color: str, size: int = 8) -> Gtk.Widget:
    area = Gtk.DrawingArea(valign=Gtk.Align.CENTER)
    area.set_content_width(size)
    area.set_content_height(size)

    def draw(_a, cr, w, h):
        c = rgba(color)
        cr.set_source_rgba(c.red, c.green, c.blue, 1)
        cr.arc(w / 2, h / 2, min(w, h) / 2, 0, 2 * math.pi)
        cr.fill()

    area.set_draw_func(draw)
    return area
