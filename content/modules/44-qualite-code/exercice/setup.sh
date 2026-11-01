#!/usr/bin/env bash
# Installe le package C++ vitesse de la pull request de Sam : il compile, mais colcon test est rouge.
set -euo pipefail
rm -rf "$WS"
mkdir -p "$WS"
cp -r "$EXERCICE/depart/." "$WS/"
cd "$WS"
colcon build > "$EXERCICE/setup.log" 2>&1
echo "Workspace prêt : $WS"
