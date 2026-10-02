#!/usr/bin/env bash
# Vérifie que /get_pose répond avec la pose du robot.
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

if ! out=$(timeout 20 ros2 service call /get_pose my_interface/srv/GetPose 2>&1); then
  echo "Pas de réponse de /get_pose en 20 s : le service n'existe pas sous ce nom."
  exit 1
fi
if ! grep -q "GetPose_Response(x=" <<<"$out"; then
  echo "Réponse inattendue de /get_pose :"
  echo "$out"
  exit 1
fi
echo "/get_pose répond : $(grep -o 'GetPose_Response(.*)' <<<"$out")"
