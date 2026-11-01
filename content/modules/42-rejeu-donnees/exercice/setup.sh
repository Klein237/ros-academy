#!/usr/bin/env bash
# Installe le package arret_urgence, avec le bug, et l'enregistrement de l'allée 3 dans test/donnees/.
set -euo pipefail
rm -rf "$WS"
mkdir -p "$WS"
cp -r "$EXERCICE/depart/." "$WS/"
mkdir -p "$WS/src/arret_urgence/test/donnees"
python3 "$EXERCICE/fabriquer_bag.py" "$WS/src/arret_urgence/test/donnees/allee3" > "$EXERCICE/setup.log" 2>&1
cd "$WS"
colcon build --symlink-install >> "$EXERCICE/setup.log" 2>&1
echo "Workspace prêt : $WS (enregistrement : src/arret_urgence/test/donnees/allee3)"
