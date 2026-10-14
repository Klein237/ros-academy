#!/usr/bin/env bash
# Vérifie que /position_pince donne la position de la pince pour une pose du bras.
cd "$WS" || { echo "Workspace introuvable : $WS"; exit 1; }
if ! colcon build --symlink-install > "$EXERCICE/check-build.log" 2>&1; then
  echo "La compilation échoue (détails : $EXERCICE/check-build.log)."
  exit 1
fi
source install/setup.bash
# Domaine ROS dédié : la vérification ne voit pas les nœuds que vous avez lancés.
export ROS_DOMAIN_ID=$((RANDOM % 50 + 50))
setsid ros2 run bras_controle cinematique_directe > "$EXERCICE/check-noeud.log" 2>&1 &
NODE=$!
trap 'kill -TERM -- -$NODE 2>/dev/null; wait $NODE 2>/dev/null' EXIT
# tourelle 0,3 rad, épaule 0,5, coude 0,8, poignet -0,4
timeout 60 python3 "$EXERCICE/comparer.py" position 0.3 0.5 0.8 -0.4 2> "$EXERCICE/comparer.log"
