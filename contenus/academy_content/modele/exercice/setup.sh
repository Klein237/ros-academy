#!/usr/bin/env bash
# Installe le workspace de l'exercice, avec le bug, dans $WS.
# $EXERCICE contient ce dossier exercice/ (sans solution/ ni explication.md).
set -euo pipefail
rm -rf "$WS"
mkdir -p "$WS"
cp -r "$EXERCICE/depart/." "$WS/"
echo "Workspace prêt : $WS"
