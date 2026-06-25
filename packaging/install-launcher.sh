#!/usr/bin/env bash
# Pasang Stock Ranger ke launcher desktop (per-user, tanpa root).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ICONS="$HOME/.local/share/icons/hicolor"
APPS="$HOME/.local/share/applications"

mkdir -p "$ICONS/scalable/apps" "$APPS"

# Icon: SVG scalable + PNG raster fallback (butuh inkscape utk PNG).
cp "$ROOT/assets/stock-ranger.svg" "$ICONS/scalable/apps/stock-ranger.svg"
if command -v inkscape >/dev/null 2>&1; then
  for s in 256 128 64 48; do
    mkdir -p "$ICONS/${s}x${s}/apps"
    inkscape --export-type=png -w "$s" -h "$s" \
      --export-filename="$ICONS/${s}x${s}/apps/stock-ranger.png" \
      "$ROOT/assets/stock-ranger.svg" >/dev/null 2>&1
  done
fi

# Desktop entry — tulis dgn path absolut repo ini.
sed -e "s#^Exec=.*#Exec=python3 $ROOT/main.py#" \
    -e "s#^Path=.*#Path=$ROOT#" \
    "$ROOT/packaging/stock-ranger.desktop" > "$APPS/stock-ranger.desktop"
chmod 644 "$APPS/stock-ranger.desktop"

# Refresh cache (silent jika tool tak ada).
update-desktop-database "$APPS" 2>/dev/null || true
gtk-update-icon-cache -f -t "$ICONS" 2>/dev/null || true

echo "✓ Stock Ranger terpasang di launcher. Cari 'Stock Ranger' di menu aplikasi."
