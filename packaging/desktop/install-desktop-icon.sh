#!/usr/bin/env bash
#
# install-desktop-icon.sh — create a desktop/menu launcher for the Ouroboros
# web service on Linux/GNOME. Writes only into the current user's own dirs
# (no sudo). Substitutes absolute paths into the .desktop template because
# "~" is NOT expanded inside a .desktop file.
#
set -euo pipefail

# Repo root = two levels above this script (packaging/desktop/ -> repo).
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ICON="$REPO_DIR/packaging/desktop/ouroboros.png"
TEMPLATE="$REPO_DIR/packaging/desktop/ouroboros.desktop.in"

# Locate the ouroboros binary: prefer the repo .venv (dev/source mode supports
# `server`), then PATH, then the pipx/pip-user fallback.
OURO_BIN=""
if [ -x "$REPO_DIR/.venv/bin/ouroboros" ]; then
  OURO_BIN="$REPO_DIR/.venv/bin/ouroboros"
fi
if [ -z "$OURO_BIN" ]; then
  OURO_BIN="$(command -v ouroboros || true)"
fi
if [ -z "$OURO_BIN" ]; then
  OURO_BIN="$HOME/.local/bin/ouroboros"
fi
if [ ! -x "$OURO_BIN" ]; then
  echo "Ошибка: не найден исполняемый бинарь 'ouroboros'." >&2
  echo "Проверенные пути: $REPO_DIR/.venv/bin/ouroboros, PATH, $HOME/.local/bin/ouroboros" >&2
  exit 1
fi

APPS_DIR="$HOME/.local/share/applications"
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
if [ -z "$DESKTOP_DIR" ]; then
  DESKTOP_DIR="$HOME/Desktop"
fi
mkdir -p "$APPS_DIR"

# Install the icon into the hicolor theme so GNOME renders it at full size
# (full-path Icon= renders at a tiny default size; Icon=<name> uses the theme).
HICOLOR_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
mkdir -p "$HICOLOR_DIR"
cp "$ICON" "$HICOLOR_DIR/gigabuddy.png" 2>/dev/null || true

# Render the template into a target .desktop file with real absolute paths.
# Note: Icon=gigabuddy (name) is used directly from the template — no substitution
# needed because the icon is installed into the hicolor theme above.
render() {
  local target="$1"
  sed -e "s|__OURO_BIN__|$OURO_BIN|g" \
      -e "s|__OURO_DIR__|$REPO_DIR|g" \
      "$TEMPLATE" > "$target"
  chmod +x "$target"
}

# 1) Applications menu entry.
render "$APPS_DIR/ouroboros.desktop"
update-desktop-database "$APPS_DIR" 2>/dev/null || true

# 2) Desktop icon.
mkdir -p "$DESKTOP_DIR"
render "$DESKTOP_DIR/ouroboros.desktop"
# GNOME: mark trusted so a click launches without the "Allow Launching" prompt.
gio set "$DESKTOP_DIR/ouroboros.desktop" metadata::trusted true 2>/dev/null || true

echo "Готово. Ярлык GigaBuddy добавлен:"
echo "  - в меню приложений: $APPS_DIR/ouroboros.desktop"
echo "  - на рабочий стол:   $DESKTOP_DIR/ouroboros.desktop"
echo
echo "Если иконка на рабочем столе неактивна — правый клик по ней → 'Allow Launching'."
