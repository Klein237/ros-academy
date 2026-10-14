#!/usr/bin/env bash
# Le nœud de cinématique directe publie la position de la pince, et elle coïncide avec TF2.
set -e
source install/setup.bash
export ROS_DOMAIN_ID=$((RANDOM % 50 + 50))
setsid ros2 launch bras_description display.launch.py jsp:=false > /tmp/launch.log 2>&1 &
DESCRIPTION=$!
setsid ros2 run bras_controle cinematique_directe > /tmp/noeud.log 2>&1 &
NODE=$!
trap 'kill -TERM -- -$DESCRIPTION -$NODE 2>/dev/null; wait 2>/dev/null || true' EXIT
COMPARER="$(dirname "$0")/exercice/comparer.py"
timeout 60 python3 "$COMPARER" position -0.5 0.9 0.6 0.3
timeout 60 python3 "$COMPARER" tf -0.5 0.9 0.6 0.3
