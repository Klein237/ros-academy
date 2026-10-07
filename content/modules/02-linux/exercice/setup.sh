#!/usr/bin/env bash
# Installe le dossier du robot, avec la panne : le script de démarrage a perdu son droit d'exécution.
set -euo pipefail
rm -rf "$WS"
mkdir -p "$WS"
cp -r "$EXERCICE/depart/." "$WS/"
chmod a-x "$WS/demarrer_robot.sh"
echo "Dossier prêt : $WS"
