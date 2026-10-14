#!/usr/bin/env bash
# Installe le dossier du robot (Dockerfile, point d'entrée, package) et compile le workspace,
# comme le fait l'étape « build » de l'image.
set -euo pipefail
rm -rf "$WS"
mkdir -p "$WS"
cp -r "$EXERCICE/depart/." "$WS/"
chmod +x "$WS/docker/ros_entrypoint.sh"
cd "$WS"
colcon build > "$EXERCICE/setup.log" 2>&1
echo "Dossier du robot prêt : $WS"
