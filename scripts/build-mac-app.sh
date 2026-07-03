#!/usr/bin/env bash
# Erzeugt ein doppelklickbares TalosAI.app-Bundle für den Mac.
#
# WICHTIG: macOS schützt Desktop/Dokumente/Downloads (TCC). Eine per Doppelklick
# gestartete App darf dort NICHT lesen. Liegt das Projekt auf dem Schreibtisch,
# scheitert eine App, die von dort startet. Darum installiert dieses Skript eine
# eigenständige Kopie nach ~/.talosai (nicht geschützt) und lässt die App von dort
# laufen — unabhängig vom Projektordner.
#
# Aufruf:  bash scripts/build-mac-app.sh
# Ergebnis: ./TalosAI.app  (in den Ordner "Programme" ziehen oder direkt starten)

set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT_DIR="$(pwd)"
APP_HOME="$HOME/.talosai"
VENV="$APP_HOME/venv"
mkdir -p "$APP_HOME/data"

echo "1/3  Eigenständige Installation in $APP_HOME …"
if command -v uv >/dev/null 2>&1; then
  uv venv -q -p 3.12 "$VENV" 2>/dev/null || true
  uv pip install -q -p "$VENV/bin/python" "$PROJECT_DIR[app]"
else
  PY="$(command -v python3.12 || command -v python3)"
  "$PY" -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q "$PROJECT_DIR[app]"
fi

# Konfiguration (API-Keys usw.) nach ~/.talosai kopieren, falls noch nicht vorhanden.
# Die App kann die .env auf dem Desktop nicht lesen (TCC) — daher hier ablegen.
if [ -f "$PROJECT_DIR/.env" ] && [ ! -f "$APP_HOME/.env" ]; then
  cp "$PROJECT_DIR/.env" "$APP_HOME/.env"
  echo "     .env nach $APP_HOME/.env kopiert (API-Keys)."
fi

echo "2/3  App-Bundle bauen …"
APP="TalosAI.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/MacOS/TalosAI" <<EOF
#!/bin/bash
# Log fürs Debugging: ~/Library/Logs/TalosAI.log
exec > "\$HOME/Library/Logs/TalosAI.log" 2>&1
cd "$APP_HOME"
export TALOS_DATA_DIR="$APP_HOME/data"
exec "$VENV/bin/python" -m talos.app
EOF
chmod +x "$APP/Contents/MacOS/TalosAI"

cat > "$APP/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>TalosAI</string>
  <key>CFBundleDisplayName</key><string>TalosAI</string>
  <key>CFBundleIdentifier</key><string>app.talosai.desktop</string>
  <key>CFBundleVersion</key><string>0.1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>TalosAI</string>
  <key>CFBundleIconFile</key><string>icon.icns</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
</dict></plist>
EOF

echo "3/3  App-Icon aus dem Logo erzeugen …"
LOGO="$PROJECT_DIR/website/assets/logo.png"
if [ -f "$LOGO" ] && command -v sips >/dev/null && command -v iconutil >/dev/null; then
  ICONSET="$(mktemp -d)/icon.iconset"; mkdir -p "$ICONSET"
  for SZ in 16 32 64 128 256 512; do
    sips -z $SZ $SZ "$LOGO" --out "$ICONSET/icon_${SZ}x${SZ}.png" >/dev/null 2>&1 || true
    D=$((SZ*2))
    sips -z $D $D "$LOGO" --out "$ICONSET/icon_${SZ}x${SZ}@2x.png" >/dev/null 2>&1 || true
  done
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/icon.icns" 2>/dev/null || true
fi

echo ""
echo "Fertig: $PROJECT_DIR/$APP"
echo "Doppelklick zum Starten, oder in den Ordner 'Programme' ziehen."
echo "Läuft unabhängig vom Projektordner aus $APP_HOME."
