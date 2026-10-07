#!/usr/bin/env bash
# Vérifie que « ros2 run demo_pkg talker » démarre et publie sur /bavardage.
cd "$WS" || { echo "Workspace introuvable : $WS"; exit 1; }
if ! colcon build --symlink-install > "$EXERCICE/check-build.log" 2>&1; then
  echo "La compilation échoue (détails : $EXERCICE/check-build.log)."
  exit 1
fi
source install/setup.bash
if ! ros2 pkg executables demo_pkg | grep -qx "demo_pkg talker"; then
  echo "Le package demo_pkg ne fournit toujours pas d'exécutable talker."
  exit 1
fi
# Domaine ROS dédié : la vérification ne voit pas les nœuds que vous avez lancés.
export ROS_DOMAIN_ID=$((RANDOM % 50 + 50))
setsid ros2 run demo_pkg talker > "$EXERCICE/check-node.log" 2>&1 &
NODE=$!
trap 'kill -TERM -- -$NODE 2>/dev/null; wait $NODE 2>/dev/null' EXIT
if ! out=$(timeout 20 ros2 topic echo --once /bavardage std_msgs/msg/String 2>&1) || ! grep -q "Bonjour ROS 2" <<<"$out"; then
  echo "talker démarre mais rien n'arrive sur /bavardage en 20 s."
  exit 1
fi
echo "talker publie sur /bavardage : $(grep -o 'Bonjour ROS 2 ! ([0-9]*)' <<<"$out" | head -1)"
