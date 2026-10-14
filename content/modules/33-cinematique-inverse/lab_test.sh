#!/usr/bin/env bash
# La cinématique inverse amène la pince sur deux cibles, de part et d'autre du bras.
set -e
source install/setup.bash
export ROS_DOMAIN_ID=$((RANDOM % 50 + 50))
setsid ros2 launch bras_description display.launch.py jsp:=false > /tmp/launch.log 2>&1 &
DESCRIPTION=$!
setsid ros2 run bras_controle cinematique_inverse > /tmp/noeud.log 2>&1 &
NODE=$!
trap 'kill -TERM -- -$DESCRIPTION -$NODE 2>/dev/null; wait 2>/dev/null || true' EXIT
COMPARER="$(dirname "$0")/exercice/comparer.py"
timeout 60 python3 "$COMPARER" cible 0.35 0.05 0.25
timeout 60 python3 "$COMPARER" cible 0.20 -0.20 0.20
