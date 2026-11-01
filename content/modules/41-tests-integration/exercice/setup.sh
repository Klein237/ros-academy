#!/usr/bin/env bash
# Installe le package limiteur : un nœud correct, et un test d'intégration qui ne vérifie presque rien.
set -euo pipefail
rm -rf "$WS"
mkdir -p "$WS"
cp -r "$EXERCICE/depart/." "$WS/"
cd "$WS"
colcon build --symlink-install > "$EXERCICE/setup.log" 2>&1
echo "Workspace prêt : $WS"
