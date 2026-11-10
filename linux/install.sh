#!/bin/bash
# Installiert Claude Token Monitor für den aktuellen Benutzer (kein sudo nötig).
#
#   ./install.sh              installieren bzw. aktualisieren
#   ./install.sh --uninstall  wieder entfernen
set -euo pipefail

cd "$(dirname "$0")"

APP_ID="io.github.KiSchulte.ClaudeTokenMonitor"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
PREFIX="$DATA_HOME/claude-token-monitor"
BIN="$HOME/.local/bin/claude-token-monitor"
DESKTOP="$DATA_HOME/applications/$APP_ID.desktop"
ICONS="$DATA_HOME/icons/hicolor"
AUTOSTART="$CONFIG_HOME/autostart/$APP_ID.desktop"

refresh_caches() {
    gtk-update-icon-cache -q -t -f "$ICONS" 2>/dev/null || true
    update-desktop-database -q "$DATA_HOME/applications" 2>/dev/null || true
}

if [[ "${1:-}" == "--uninstall" ]]; then
    echo "==> Entferne Claude Token Monitor"
    pkill -f "$PREFIX/main.py" 2>/dev/null || true
    rm -rf "$PREFIX"
    rm -f "$BIN" "$DESKTOP" "$AUTOSTART"
    rm -f "$ICONS/scalable/apps/$APP_ID.svg" "$ICONS/symbolic/apps/$APP_ID-symbolic.svg"
    refresh_caches
    echo "    Fertig. Einstellungen bleiben in $CONFIG_HOME/claude-token-monitor/"
    exit 0
fi

echo "==> Prüfe Abhängigkeiten"
if ! python3 - <<'EOF'
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw
assert Adw.get_minor_version() >= 7, "libadwaita >= 1.7 nötig"
EOF
then
    echo "    Fehlt: GTK 4 / libadwaita >= 1.7 für Python. Unter Fedora:"
    echo "    sudo dnf install python3-gobject gtk4 libadwaita"
    exit 1
fi

echo "==> Kopiere Programm nach $PREFIX"
rm -rf "$PREFIX"
mkdir -p "$PREFIX"
cp -R main.py ctm data "$PREFIX/"
find "$PREFIX" -name '__pycache__' -prune -exec rm -rf {} +

echo "==> Lege Starter an: $BIN"
mkdir -p "$(dirname "$BIN")"
cat > "$BIN" <<EOF
#!/bin/sh
exec python3 "$PREFIX/main.py" "\$@"
EOF
chmod +x "$BIN"

echo "==> Installiere Icons und Desktop-Eintrag"
mkdir -p "$ICONS/scalable/apps" "$ICONS/symbolic/apps" "$(dirname "$DESKTOP")"
cp "data/icons/hicolor/scalable/apps/$APP_ID.svg" "$ICONS/scalable/apps/"
cp "data/icons/hicolor/symbolic/apps/$APP_ID-symbolic.svg" "$ICONS/symbolic/apps/"
sed "s|@BIN@|$BIN|g" "data/$APP_ID.desktop.in" > "$DESKTOP"
refresh_caches

# Bestehenden Autostart auf den installierten Starter umbiegen.
if [[ -f "$AUTOSTART" ]]; then
    "$BIN" --register-login >/dev/null
    echo "==> Autostart aktualisiert"
fi

echo "==> Fertig"
echo "    Starten: über die App-Übersicht (\"Claude Token Monitor\") oder claude-token-monitor"

# Das Symbol in der oberen Leiste braucht die AppIndicator-Erweiterung.
EXT="appindicatorsupport@rgcjonas.gmail.com"
if command -v gnome-extensions >/dev/null; then
    if ! gnome-extensions list 2>/dev/null | grep -q "$EXT"; then
        echo
        echo "    Hinweis: Für das Symbol in der oberen Leiste wird die Erweiterung"
        echo "    \"AppIndicator and KStatusNotifierItem Support\" benötigt:"
        echo "      sudo dnf install gnome-shell-extension-appindicator"
        echo "    danach ab- und wieder anmelden und aktivieren:"
        echo "      gnome-extensions enable $EXT"
    elif ! gnome-extensions list --enabled 2>/dev/null | grep -q "$EXT"; then
        echo
        echo "    Hinweis: Die AppIndicator-Erweiterung ist installiert, aber aus:"
        echo "      gnome-extensions enable $EXT"
    fi
fi
