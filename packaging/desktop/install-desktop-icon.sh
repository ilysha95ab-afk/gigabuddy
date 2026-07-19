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

# Locate the ouroboros binary: prefer PATH, fall back to the pipx/pip-user path.
OURO_BIN="$(command -v ouroboros || true)"
if [ -z "$OURO_BIN" ]; then
  OURO_BIN="$HOME/.local/bin/ouroboros"
fi
if [ ! -x "$OURO_BIN" ]; then
  echo "Ошибка: не найден исполняемый бинарь 'ouroboros'." >&2
  echo "Установи проект (pipx install . или pip install --user -e .) и повтори." >&2
  echo "Проверенные пути: PATH и $HOME/.local/bin/ouroboros" >&2
  exit 1
fi

APPS_DIR="$HOME/.local/share/applications"
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
if [ -z "$DESKTOP_DIR" ]; then
  DESKTOP_DIR="$HOME/Desktop"
fi
mkdir -p "$APPS_DIR"

# Render the template into a target .desktop file with real absolute paths.
render() {
  local target="$1"
  sed -e "s|__OURO_BIN__|$OURO_BIN|g" \
      -e "s|__OURO_DIR__|$REPO_DIR|g" \
      -e "s|__OURO_ICON__|$ICON|g" \
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

echo "Готово. Ярлык Ouroboros добавлен:"
echo "  - в меню приложений: $APPS_DIR/ouroboros.desktop"
echo "  - на рабочий стол:   $DESKTOP_DIR/ouroboros.desktop"
echo
echo "Если иконка на рабочем столе неактивна — правый клик по ней → 'Allow Launching'."
