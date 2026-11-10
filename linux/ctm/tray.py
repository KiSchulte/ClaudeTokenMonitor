"""Symbol mit Text in der oberen GNOME-Leiste.

GNOME hat keine eingebaute Tray-API. Implementiert wird deshalb das
StatusNotifierItem-Protokoll (plus com.canonical.dbusmenu für das Menü) direkt
über Gio/D-Bus — ohne libappindicator, das an GTK 3 gebunden ist. Angezeigt
wird das Symbol von der GNOME-Erweiterung "AppIndicator and KStatusNotifierItem
Support" (bei Fedora vorinstalliert als gnome-shell-extension-appindicator).

Der Text neben dem Symbol läuft über die Ayatana-Erweiterung `XAyatanaLabel`,
die von der GNOME-Erweiterung unterstützt wird.
"""

from __future__ import annotations

from typing import Callable

from gi.repository import Gio, GLib

ITEM_PATH = "/StatusNotifierItem"
MENU_PATH = "/MenuBar"
WATCHER_NAME = "org.kde.StatusNotifierWatcher"
WATCHER_PATH = "/StatusNotifierWatcher"

_SNI_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="i" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconThemePath" type="s" access="read"/>
    <property name="OverlayIconName" type="s" access="read"/>
    <property name="AttentionIconName" type="s" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <property name="XAyatanaLabel" type="s" access="read"/>
    <property name="XAyatanaLabelGuide" type="s" access="read"/>
    <method name="Activate">
      <arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/>
    </method>
    <method name="SecondaryActivate">
      <arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/>
    </method>
    <method name="ContextMenu">
      <arg name="x" type="i" direction="in"/><arg name="y" type="i" direction="in"/>
    </method>
    <method name="Scroll">
      <arg name="delta" type="i" direction="in"/><arg name="orientation" type="s" direction="in"/>
    </method>
    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewAttentionIcon"/>
    <signal name="NewOverlayIcon"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus"><arg name="status" type="s"/></signal>
    <signal name="XAyatanaNewLabel">
      <arg name="label" type="s"/><arg name="guide" type="s"/>
    </signal>
  </interface>
</node>
"""

_MENU_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg type="i" name="parentId" direction="in"/>
      <arg type="i" name="recursionDepth" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="u" name="revision" direction="out"/>
      <arg type="(ia{sv}av)" name="layout" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg type="ai" name="ids" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="a(ia{sv})" name="properties" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="name" direction="in"/>
      <arg type="v" name="value" direction="out"/>
    </method>
    <method name="Event">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="eventId" direction="in"/>
      <arg type="v" name="data" direction="in"/>
      <arg type="u" name="timestamp" direction="in"/>
    </method>
    <method name="EventGroup">
      <arg type="a(isvu)" name="events" direction="in"/>
      <arg type="ai" name="idErrors" direction="out"/>
    </method>
    <method name="AboutToShow">
      <arg type="i" name="id" direction="in"/>
      <arg type="b" name="needUpdate" direction="out"/>
    </method>
    <method name="AboutToShowGroup">
      <arg type="ai" name="ids" direction="in"/>
      <arg type="ai" name="updatesNeeded" direction="out"/>
      <arg type="ai" name="idErrors" direction="out"/>
    </method>
    <signal name="ItemsPropertiesUpdated">
      <arg type="a(ia{sv})" name="updatedProps"/>
      <arg type="a(ias)" name="removedProps"/>
    </signal>
    <signal name="LayoutUpdated">
      <arg type="u" name="revision"/>
      <arg type="i" name="parent"/>
    </signal>
    <signal name="ItemActivationRequested">
      <arg type="i" name="id"/>
      <arg type="u" name="timestamp"/>
    </signal>
  </interface>
</node>
"""


class MenuItem:
    """Ein Eintrag des Kontextmenüs.

    kind: "normal", "separator", "radio", "check" oder "header" (deaktiviert).
    """

    def __init__(self, label: str = "", kind: str = "normal", checked: bool = False,
                 on_click: Callable[[], None] | None = None) -> None:
        self.label = label
        self.kind = kind
        self.checked = checked
        self.on_click = on_click

    def properties(self) -> dict[str, GLib.Variant]:
        if self.kind == "separator":
            return {"type": GLib.Variant("s", "separator")}
        props = {
            "label": GLib.Variant("s", self.label.replace("_", "__")),
            "enabled": GLib.Variant("b", self.kind != "header"),
            "visible": GLib.Variant("b", True),
        }
        if self.kind in ("radio", "check"):
            props["toggle-type"] = GLib.Variant("s", "radio" if self.kind == "radio" else "checkmark")
            props["toggle-state"] = GLib.Variant("i", 1 if self.checked else 0)
        return props


class TrayIcon:
    """StatusNotifierItem mit Text, Menü und Klick-Aktion."""

    def __init__(self, connection: Gio.DBusConnection, item_id: str, icon_name: str,
                 icon_theme_path: str, on_activate: Callable[[], None],
                 on_availability: Callable[[bool], None] | None = None) -> None:
        self._conn = connection
        self._id = item_id
        self._icon_name = icon_name
        self._icon_theme_path = icon_theme_path
        self._on_activate = on_activate
        self._on_availability = on_availability
        self._title = item_id
        self._label = ""
        self._guide = ""
        self._tooltip = ""
        self._items: list[MenuItem] = []
        self._revision = 1
        self.available = False

        sni_info = Gio.DBusNodeInfo.new_for_xml(_SNI_XML).interfaces[0]
        menu_info = Gio.DBusNodeInfo.new_for_xml(_MENU_XML).interfaces[0]
        self._reg_ids = [
            connection.register_object(ITEM_PATH, sni_info, self._sni_call, self._sni_prop, None),
            connection.register_object(MENU_PATH, menu_info, self._menu_call, self._menu_prop, None),
        ]
        # Die Erweiterung kann neu geladen werden (z. B. nach Neustart der
        # Shell) — dann muss sich das Symbol neu anmelden.
        self._watch_id = Gio.bus_watch_name_on_connection(
            connection, WATCHER_NAME, Gio.BusNameWatcherFlags.NONE,
            self._watcher_appeared, self._watcher_vanished)

    # MARK: - Öffentliche API

    def set_title(self, title: str) -> None:
        self._title = title
        self._emit_item("NewTitle", None)

    def set_label(self, label: str, guide: str = "") -> None:
        if label == self._label and guide == self._guide:
            return
        self._label, self._guide = label, guide
        self._emit_item("XAyatanaNewLabel", GLib.Variant("(ss)", (label, guide)))

    def set_tooltip(self, text: str) -> None:
        if text == self._tooltip:
            return
        self._tooltip = text
        self._emit_item("NewToolTip", None)

    def set_menu(self, items: list[MenuItem]) -> None:
        self._items = items
        self._revision += 1
        self._emit_menu("LayoutUpdated", GLib.Variant("(ui)", (self._revision, 0)))

    def close(self) -> None:
        Gio.bus_unwatch_name(self._watch_id)
        for rid in self._reg_ids:
            self._conn.unregister_object(rid)

    # MARK: - Anmeldung beim Watcher

    def _watcher_appeared(self, conn, name, owner) -> None:
        conn.call(
            WATCHER_NAME, WATCHER_PATH, WATCHER_NAME, "RegisterStatusNotifierItem",
            GLib.Variant("(s)", (conn.get_unique_name(),)), None,
            Gio.DBusCallFlags.NONE, -1, None, self._registered)

    def _registered(self, conn, result) -> None:
        try:
            conn.call_finish(result)
            self._set_available(True)
        except GLib.Error:
            self._set_available(False)

    def _watcher_vanished(self, conn, name) -> None:
        self._set_available(False)

    def _set_available(self, value: bool) -> None:
        if value != self.available:
            self.available = value
            if self._on_availability:
                self._on_availability(value)

    # MARK: - StatusNotifierItem

    def _emit_item(self, signal: str, params) -> None:
        try:
            self._conn.emit_signal(None, ITEM_PATH, "org.kde.StatusNotifierItem", signal, params)
        except GLib.Error:
            pass

    def _sni_prop(self, conn, sender, path, iface, prop):
        values = {
            "Category": GLib.Variant("s", "ApplicationStatus"),
            "Id": GLib.Variant("s", self._id),
            "Title": GLib.Variant("s", self._title),
            "Status": GLib.Variant("s", "Active"),
            "WindowId": GLib.Variant("i", 0),
            "IconName": GLib.Variant("s", self._icon_name),
            "IconThemePath": GLib.Variant("s", self._icon_theme_path),
            "OverlayIconName": GLib.Variant("s", ""),
            "AttentionIconName": GLib.Variant("s", ""),
            "ToolTip": GLib.Variant("(sa(iiay)ss)", ("", [], self._title, self._tooltip)),
            "ItemIsMenu": GLib.Variant("b", False),
            "Menu": GLib.Variant("o", MENU_PATH),
            "XAyatanaLabel": GLib.Variant("s", self._label),
            "XAyatanaLabelGuide": GLib.Variant("s", self._guide),
        }
        return values.get(prop)

    def _sni_call(self, conn, sender, path, iface, method, params, invocation) -> None:
        if method in ("Activate", "SecondaryActivate"):
            GLib.idle_add(self._activate)
        invocation.return_value(None)

    def _activate(self) -> bool:
        self._on_activate()
        return GLib.SOURCE_REMOVE

    # MARK: - dbusmenu

    def _emit_menu(self, signal: str, params) -> None:
        try:
            self._conn.emit_signal(None, MENU_PATH, "com.canonical.dbusmenu", signal, params)
        except GLib.Error:
            pass

    def _menu_prop(self, conn, sender, path, iface, prop):
        values = {
            "Version": GLib.Variant("u", 3),
            "TextDirection": GLib.Variant("s", "ltr"),
            "Status": GLib.Variant("s", "normal"),
            "IconThemePath": GLib.Variant("as", []),
        }
        return values.get(prop)

    def _item_props(self, item_id: int) -> dict[str, GLib.Variant]:
        if item_id == 0:
            return {"children-display": GLib.Variant("s", "submenu")}
        return self._items[item_id - 1].properties()

    def _node(self, item_id: int, depth: int) -> GLib.Variant:
        children = []
        if item_id == 0 and depth != 0:
            children = [self._node(i + 1, depth - 1) for i in range(len(self._items))]
        return GLib.Variant("(ia{sv}av)", (item_id, self._item_props(item_id), children))

    def _valid(self, item_id: int) -> bool:
        return 0 <= item_id <= len(self._items)

    def _menu_call(self, conn, sender, path, iface, method, params, invocation) -> None:
        args = params.unpack()
        if method == "GetLayout":
            parent, depth, _ = args
            if not self._valid(parent):
                parent = 0
            node = self._node(parent, depth)
            invocation.return_value(GLib.Variant.new_tuple(GLib.Variant("u", self._revision), node))
        elif method == "GetGroupProperties":
            ids, _ = args
            ids = ids or list(range(len(self._items) + 1))
            result = [(i, self._item_props(i)) for i in ids if self._valid(i)]
            invocation.return_value(GLib.Variant("(a(ia{sv}))", (result,)))
        elif method == "GetProperty":
            item_id, name = args
            value = self._item_props(item_id).get(name) if self._valid(item_id) else None
            invocation.return_value(GLib.Variant("(v)", (value or GLib.Variant("s", ""),)))
        elif method == "Event":
            item_id, event_id, _, _ = args
            self._handle_event(item_id, event_id)
            invocation.return_value(None)
        elif method == "EventGroup":
            errors = []
            for item_id, event_id, _, _ in args[0]:
                if self._valid(item_id):
                    self._handle_event(item_id, event_id)
                else:
                    errors.append(item_id)
            invocation.return_value(GLib.Variant("(ai)", (errors,)))
        elif method == "AboutToShow":
            invocation.return_value(GLib.Variant("(b)", (False,)))
        elif method == "AboutToShowGroup":
            invocation.return_value(GLib.Variant("(aiai)", ([], [])))
        else:
            invocation.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod", method)

    def _handle_event(self, item_id: int, event_id: str) -> None:
        if event_id != "clicked" or not (1 <= item_id <= len(self._items)):
            return
        callback = self._items[item_id - 1].on_click
        if callback:
            GLib.idle_add(lambda: (callback(), GLib.SOURCE_REMOVE)[1])
