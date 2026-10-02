#!/usr/bin/env bash
# Les deux versions du nœud (Python et C++) répondent à /get_pose.
set -e
source install/setup.bash
DOMAIN=71
for pkg in my_pkg my_pkg_cpp; do
  export ROS_DOMAIN_ID=$((DOMAIN++))
  setsid ros2 run "$pkg" diff_drive_node > /dev/null 2>&1 &
  NODE=$!
  out=$(timeout 30 ros2 service call /get_pose my_interface/srv/GetPose 2>&1) || { echo "$pkg : pas de réponse"; kill -TERM -- -$NODE; exit 1; }
  grep -q "GetPose_Response(x=" <<<"$out" || { echo "$pkg : $out"; kill -TERM -- -$NODE; exit 1; }
  echo "$pkg : /get_pose répond"
  kill -TERM -- -$NODE; wait $NODE 2>/dev/null || true
done
