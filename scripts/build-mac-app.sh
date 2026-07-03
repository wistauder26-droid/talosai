#!/usr/bin/env bash
# Erzeugt ein doppelklickbares TalosAI.app-Bundle für den Mac.
# Das Bundle startet `talos-app` aus der Projekt-venv (natives Fenster).
#
# Voraussetzung: einmalig die App-Abhängigkeit installieren:
#   uv pip install -p .venv/bin/python '.[app]'
#
# Aufruf:  bash scripts/build-mac-app.sh
# Ergebnis: ./TalosAI.app  (in den Ordner "Programme" ziehen oder direkt starten)

set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT_DIR="$(pwd)"
VENV_PY="$PROJECT_DIR/.venv/bin/python"

if [ ! -x "$VENV_PY" ]; then
  echo "Fehler: $VENV_PY nicht gefunden. Erst die venv anlegen und '.[app]' installieren." >&2
  exit 1
fi

APP="TalosAI.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# Startskript im Bundle
cat > "$APP/Contents/MacOS/TalosAI" <<EOF
#!/usr/bin/env bash
cd "$PROJECT_DIR"
exec "$VENV_PY" -m talos.app
EOF
chmod +x "$APP/Contents/MacOS/TalosAI"

# Info.plist
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

# Logo als App-Icon übernehmen, falls vorhanden (PNG -> ICNS)
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

echo "Fertig: $PROJECT_DIR/$APP"
echo "Doppelklick zum Starten, oder in den Ordner 'Programme' ziehen."
