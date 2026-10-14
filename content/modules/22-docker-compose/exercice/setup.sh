#!/usr/bin/env bash
# Installe le dossier du robot (compose.yaml et package) et compile le workspace, comme dans l'image.
set -euo pipefail
rm -rf "$WS"
mkdir -p "$WS"
cp -r "$EXERCICE/depart/." "$WS/"
cd "$WS"
colcon build > "$EXERCICE/setup.log" 2>&1
echo "Dossier du robot prêt : $WS"
