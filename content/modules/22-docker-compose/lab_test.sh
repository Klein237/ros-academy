#!/usr/bin/env bash
# Le compose.yaml du cours fait communiquer le robot et sa supervision (Compose simulé, sans Docker).
set -e
python3 "$(dirname "$0")/exercice/simuler_compose.py" "$PWD"
