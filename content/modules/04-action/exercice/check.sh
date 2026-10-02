#!/usr/bin/env bash
# Vérifie qu'un goal goto atteint se termine avec le statut SUCCEEDED.
cd "$WS" || { echo "Workspace introuvable : $WS"; exit 1; }
if ! colcon build --symlink-install > "$EXERCICE/check-build.log" 2>&1; then
  echo "La compilation échoue (détails : $EXERCICE/check-build.log)."
  exit 1
fi
source install/setup.bash
# Domaine ROS dédié : la vérification ne voit pas les nœuds que vous avez lancés.
export ROS_DOMAIN_ID=$((RANDOM % 50 + 50))
setsid ros2 run my_pkg diff_drive_node > "$EXERCICE/check-node.log" 2>&1 &
NODE=$!
trap 'kill -TERM -- -$NODE 2>/dev/null; wait $NODE 2>/dev/null' EXIT

out=$(timeout 60 ros2 action send_goal /goto my_interface/action/Goto "{target: {x: 0.6, y: 0.3}}" 2>&1)
status=$(grep -o "Goal finished with status: [A-Z]*" <<<"$out" | awk '{print $NF}')
if [ "$status" != "SUCCEEDED" ]; then
  echo "Le goal se termine avec le statut ${status:-inconnu} au lieu de SUCCEEDED."
  exit 1
fi
echo "Le goal se termine avec le statut SUCCEEDED."
