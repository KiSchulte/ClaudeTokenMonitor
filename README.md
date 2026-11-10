# Claude Token Monitor

See how many Claude tokens you use, and what that usage would cost at API
prices. The app reads the transcripts that [Claude Code](https://claude.com/claude-code)
already writes to your disk.

Native apps for **macOS** (menu bar) and **Linux/GNOME** (top bar). Both show
the same numbers:

- **Current 5-hour window**: tokens, cost, burn rate, projection and time until
  reset. This mirrors the rolling windows Claude subscriptions use for their
  limits.
- **Today, this week, this month, last 7 days**, at a glance.
- **History**: 30 days, 12 weeks or 6 months, by tokens, cost or requests.
- **Breakdown by model and by project**.
- **Token composition**: input, output, cache write and cache read.
- **German and English**, switchable at runtime.

The app makes no network requests and needs no API key or account. It only
reads local files under `~/.claude/projects`.

> **Note:** Costs are the API list-price equivalent of your usage. On a Pro or
> Max subscription you don't pay this amount. The 5-hour bar compares against
> your strongest *completed* window, not your real limit, because the limits are
> not available locally. For the authoritative figure, run `/usage` in Claude
> Code.

---

## Installation

### Linux (Fedora / GNOME)

**Requirements:** Python 3, GTK 4 and libadwaita ≥ 1.7 (via PyGObject). Fedora
Workstation 41 and newer ships all of these. For the top-bar icon you also need
the GNOME extension *AppIndicator and KStatusNotifierItem Support*.

```sh
# 1. Dependencies (usually already installed on Fedora Workstation)
sudo dnf install python3-gobject gtk4 libadwaita gnome-shell-extension-appindicator

# 2. Enable the top-bar icon extension (log out and back in first if you just installed it)
gnome-extensions enable appindicatorsupport@rgcjonas.gmail.com

# 3. Get the code and install it for your user (no sudo needed)
git clone https://github.com/KiSchulte/ClaudeTokenMonitor.git
cd ClaudeTokenMonitor
./linux/install.sh
```

Then start **Claude Token Monitor** from the app grid, or run
`claude-token-monitor` in a terminal.

- **Update:** `git pull && ./linux/install.sh`
- **Uninstall:** `./linux/install.sh --uninstall`
- **Run without installing:** `python3 linux/main.py`

The installer puts files only in your home directory:

| What | Where |
|---|---|
| Program | `~/.local/share/claude-token-monitor/` |
| Launcher | `~/.local/bin/claude-token-monitor` |
| Desktop entry | `~/.local/share/applications/io.github.KiSchulte.ClaudeTokenMonitor.desktop` |
| Icons | `~/.local/share/icons/hicolor/…` |
| Settings | `~/.config/claude-token-monitor/settings.json` |

Other distributions with GNOME should work if they provide the packages above,
under their own names.

### macOS (14 Sonoma or later)

**Requirements:** the Xcode Command Line Tools (`xcode-select --install`). The
full Xcode is not needed.

```sh
git clone https://github.com/KiSchulte/ClaudeTokenMonitor.git
cd ClaudeTokenMonitor
./build.sh
cp -R "build/Claude Token Monitor.app" /Applications/
open "/Applications/Claude Token Monitor.app"
```

The app has no Dock icon and lives only in the menu bar. The build is ad-hoc
signed, so on first launch macOS may ask you to confirm under *System Settings →
Privacy & Security*.

The icon is borderless by default, which suits macOS 26, where the system
applies the rounded shape itself. On macOS 14/15, build with
`ICON_STYLE=plate ./build.sh` to get a rounded icon with a shadow.

---

## Usage

### Linux

- **Left-click** the top-bar icon to open or hide the window.
- **Right-click** it for a menu where you can:
  - choose which figure the top bar shows
  - also show the cost
  - turn on launch at login
  - reload
  - quit
- In the window, the **☰ menu** has the same settings, plus language and
  *Open data folder*.
- **Shortcuts:** `Ctrl+R`/`F5` reloads, `Ctrl+W` closes the window, `Ctrl+Q`
  quits.

Closing the window keeps the app running in the top bar. If the AppIndicator
extension is not active, the app behaves like a normal window, and closing it
quits.

### macOS

Click the menu-bar item to open the panel. Settings are under **Display**: menu
bar figure, cost, language, launch at login and *Show data source in Finder*.
Turn on launch at login only after copying the app to `/Applications`, because
it registers the app's current location.

### Command line

Both versions print the same text summary, which is useful for checking the
numbers:

```sh
claude-token-monitor --dump                                               # Linux
"/Applications/Claude Token Monitor.app/Contents/MacOS/ClaudeTokenMonitor" --dump   # macOS
```

| Flag | Effect |
|---|---|
| `--dump` | Print all figures as text |
| `--de` / `--en` | Force the language of the dump |
| `--login-status` | Show whether launch at login is enabled |
| `--register-login` / `--unregister-login` | Turn launch at login on or off |
| `--hidden` | *(Linux)* Start with only the top-bar icon; used by autostart |
| `--preview` | *(macOS)* Also show the panel in a regular window |

---

## How the numbers are computed

### Data source

The app reads `~/.claude/projects/**/*.jsonl`. Every assistant response in these
transcripts carries a `usage` object with the following fields:

- input tokens
- output tokens
- cache-write tokens, split into 5-minute and 1-hour
- cache-read tokens
- web searches
- model and timestamp

Two details matter for correct totals:

- **The search is recursive.** Subagent runs are stored under
  `<project>/<session>/subagents/*.jsonl`. Scanning only one level deep misses
  their usage entirely. In testing that was about 10 M tokens and a whole model
  that otherwise never showed up.
- **Requests are deduplicated.** When a session is resumed or forked, its
  entire history is copied into a new file. The app counts each
  `requestId` + `message.id` only once. Without this, totals come out more than
  twice too high.

Files are read incrementally by byte offset. The app refreshes every 10 seconds
and when you open the window.

### 5-hour windows

A window starts at the full hour of the first activity and runs for 5 hours. It
also ends early if 5 hours pass without any activity. The bar for the current
window compares it to your strongest completed window.

### Costs

Costs use the API list prices, by model and token type, in USD:

| Model | Input $/1M | Output $/1M |
|---|---|---|
| Fable 5, Mythos 5 | 10 | 50 |
| Opus 5, Opus 4.8, 4.7, 4.6, 4.5 | 5 | 25 |
| Sonnet 5, Sonnet 4.6, 4.5 | 3 | 15 |
| Haiku 4.5 | 1 | 5 |

Other token types are priced relative to the input price:

- cache write (5 min): 1.25× input
- cache write (1 h): 2× input
- cache read: 0.1× input
- web search: $10 per 1,000 requests

Discounts, batch pricing and promotional prices are not included. To change the
prices, edit both `Pricing.table` in `Sources/ClaudeTokenMonitor/Model.swift` and
`_PRICE_TABLE` in `linux/ctm/model.py`.

### Language and formats

Switching the language also changes the formats:

| | German | English |
|---|---|---|
| Decimal and thousands separators | `1.234,5` | `1,234.5` |
| Currency | `34,6 $` | `$34.6` |
| Date | `08.08.2026` | `08/08/2026` (en-GB style, 24-hour clock) |
| Calendar week | `KW 32` | `W 32` |

The figures themselves never change with the language. Weeks are always ISO
8601 weeks, starting on Monday.

---

## Project layout

```
Sources/ClaudeTokenMonitor/   macOS app (Swift, SwiftUI): reader, aggregation, views
Sources/IconGen/              Draws the macOS app icon at build time
Bundle/Info.plist             macOS bundle metadata
build.sh                      Builds the .app bundle
linux/                        Linux/GNOME app (Python, GTK 4, libadwaita)
  main.py                       Entry point and command-line modes
  ctm/reader.py                 Incremental, recursive JSONL reader with dedup
  ctm/model.py                  Entries, prices, totals, 5-hour windows
  ctm/aggregator.py             Days/weeks/months, models, projects, snapshot
  ctm/loc.py                    German/English texts and formats
  ctm/tray.py                   StatusNotifierItem + dbusmenu over D-Bus (top-bar icon)
  ctm/app.py, ctm/widgets.py    Window, tabs, charts
  install.sh                    Per-user installer
```

The Linux version is a direct port of the Swift logic: each Python module
mirrors the Swift file of the same role, so both apps report identical numbers.

## License

[MIT](LICENSE)
