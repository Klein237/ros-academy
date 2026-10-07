#!/usr/bin/env bash
# Installe le workspace de l'exercice (avec le bug) et le compile.
set -euo pipefail
rm -rf "$WS"
mkdir -p "$WS"
cp -r "$EXERCICE/depart/." "$WS/"
cd "$WS"
colcon build --symlink-install > "$EXERCICE/setup.log" 2>&1
echo "Workspace prêt : $WS"
