#!/usr/bin/env bash
# Les deux versions du serveur goto (Python et C++) amènent le robot à la cible.
set -e
source install/setup.bash
DOMAIN=81
for pkg in my_pkg my_pkg_cpp; do
  export ROS_DOMAIN_ID=$((DOMAIN++))
  setsid ros2 run "$pkg" diff_drive_node > /dev/null 2>&1 &
  NODE=$!
  out=$(timeout 90 ros2 action send_goal /goto my_interface/action/Goto "{target: {x: 1.0, y: 0.5}}" 2>&1) || true
  kill -TERM -- -$NODE; wait $NODE 2>/dev/null || true
  grep -q "Goal finished with status: SUCCEEDED" <<<"$out" || { echo "$pkg : $out"; exit 1; }
  echo "$pkg : goal atteint"
done
