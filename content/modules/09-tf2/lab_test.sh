#!/usr/bin/env bash
# Le launch du cours publie l'arbre odom → base_link → laser, et obstacle_locator place l'obstacle.
set -e
source install/setup.bash
export ROS_DOMAIN_ID=87
setsid ros2 launch my_pkg robot.launch.py > /tmp/launch.log 2>&1 &
NODE=$!
trap 'kill -TERM -- -$NODE 2>/dev/null; wait $NODE 2>/dev/null || true' EXIT
timeout 30 ros2 run tf2_ros tf2_echo odom laser > /tmp/tf.log 2>&1 || true
grep -q "Translation: \[0.150, 0.000, 0.120\]" /tmp/tf.log || { cat /tmp/tf.log /tmp/launch.log | tail -20; exit 1; }
# avec le type, echo attend que le topic apparaisse (sans lui, il abandonne si le nœud démarre encore)
timeout 30 ros2 topic echo --once /obstacle geometry_msgs/msg/PointStamped > /tmp/obstacle.log
grep -q "x: 1.15" /tmp/obstacle.log || { cat /tmp/obstacle.log; exit 1; }
echo "arbre odom → base_link → laser et obstacle à (1.15, 0) : OK"
