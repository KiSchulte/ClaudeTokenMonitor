# Claude Token Monitor for Linux (GNOME)

This folder holds the Linux/GNOME version: a top-bar icon showing your current
usage, plus a libadwaita window with the same five tabs as the macOS app
(Overview, History, Windows, Models, Projects).

Install it with:

```sh
./linux/install.sh
```

For requirements, the top-bar extension, usage and uninstalling, see the
[main README](../README.md#linux-fedora--gnome).

## How it differs from the macOS version

| macOS | Linux |
|---|---|
| Menu-bar panel | Top-bar icon plus a separate window (Wayland does not let apps position a window at the icon) |
| Settings in UserDefaults | `~/.config/claude-token-monitor/settings.json` |
| Launch at login via `SMAppService` | `~/.config/autostart/io.github.KiSchulte.ClaudeTokenMonitor.desktop`, which starts the app with `--hidden` |
| System language from macOS | From `LC_ALL`, `LC_MESSAGES` or `LANG` |
| *Show data source in Finder* | *Open data folder* |

## Why the top-bar icon needs an extension

GNOME has no built-in tray API. The app therefore implements the
StatusNotifierItem protocol, plus `com.canonical.dbusmenu` for the menu,
directly over D-Bus with Gio. It doesn't use libappindicator, which is tied to
GTK 3.

The *AppIndicator and KStatusNotifierItem Support* extension
(`appindicatorsupport@rgcjonas.gmail.com`) displays the icon. The text next to
the icon uses the `XAyatanaLabel` property, which that extension supports.
