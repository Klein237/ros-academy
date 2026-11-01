#!/usr/bin/env bash
# Installe le dépôt du robot de livraison : le package odometrie, ses tests, et un workflow
# d'intégration continue qui laisse passer des erreurs.
set -euo pipefail
rm -rf "$WS"
mkdir -p "$WS/.github/workflows"
cp -r "$EXERCICE/depart/." "$WS/"
cp "$EXERCICE/workflow-depart.yml" "$WS/.github/workflows/ci.yml"
cd "$WS"
colcon build --symlink-install > "$EXERCICE/setup.log" 2>&1
echo "Workspace prêt : $WS (workflow : .github/workflows/ci.yml)"
