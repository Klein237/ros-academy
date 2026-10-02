#!/usr/bin/env bash
# Installe le workspace de l'exercice (avec le bug).
set -euo pipefail
rm -rf "$WS"
mkdir -p "$WS"
cp -r "$EXERCICE/depart/." "$WS/"
echo "Workspace prêt : $WS"
