#!/bin/bash
# Baut ClaudeTokenMonitor.app aus dem SwiftPM-Target.
# Xcode ist nicht nötig — die Command Line Tools genügen.
set -euo pipefail

cd "$(dirname "$0")"

APP_NAME="Claude Token Monitor"
BINARY="ClaudeTokenMonitor"
APP_DIR="build/${APP_NAME}.app"
ICONSET="build/AppIcon.iconset"

echo "==> Kompiliere (release)"
swift build -c release

# fullBleed = randlos deckend, wird von macOS 26 auf die Squircle-Form maskiert.
# Für macOS 14/15: ICON_STYLE=plate ./build.sh
ICON_STYLE="${ICON_STYLE:-fullBleed}"

echo "==> Erzeuge App-Icon (Stil: $ICON_STYLE)"
rm -rf "$ICONSET"
./.build/release/IconGen "$ICONSET" --style "$ICON_STYLE" >/dev/null
iconutil --convert icns --output "build/AppIcon.icns" "$ICONSET"

echo "==> Baue App-Bundle"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"
cp ".build/release/$BINARY" "$APP_DIR/Contents/MacOS/$BINARY"
cp "Bundle/Info.plist" "$APP_DIR/Contents/Info.plist"
cp "build/AppIcon.icns" "$APP_DIR/Contents/Resources/AppIcon.icns"
printf 'APPL????' > "$APP_DIR/Contents/PkgInfo"

echo "==> Signiere (ad-hoc)"
codesign --force --sign - --timestamp=none "$APP_DIR" >/dev/null

# Der Icon-Cache von macOS hält das alte Bild sonst fest.
touch "$APP_DIR"

echo "==> Fertig: $(pwd)/$APP_DIR"
echo "    Starten:      open \"$APP_DIR\""
echo "    Installieren: cp -R \"$APP_DIR\" /Applications/"
