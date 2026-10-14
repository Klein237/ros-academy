#!/usr/bin/env bash
# Le Dockerfile et le point d'entrée du cours démarrent le robot (conteneur simulé, sans Docker).
set -e
python3 "$(dirname "$0")/exercice/simuler_conteneur.py" "$PWD"
