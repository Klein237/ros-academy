#!/usr/bin/env bash
# Le fichier launch du cours démarre le nœud avec config/robot.yaml, et les valeurs invalides sont refusées.
set -e
source install/setup.bash
export ROS_DOMAIN_ID=86
setsid ros2 launch my_pkg robot.launch.py max_linear_speed:=0.25 > /tmp/launch.log 2>&1 &
NODE=$!
trap 'kill -TERM -- -$NODE 2>/dev/null; wait $NODE 2>/dev/null || true' EXIT
for _ in $(seq 1 20); do
  timeout 10 ros2 param get /diff_drive_node goal_tolerance > /tmp/param.txt 2>/dev/null && break
  sleep 1
done
grep -q "0.03" /tmp/param.txt || { echo "goal_tolerance : $(cat /tmp/param.txt)"; cat /tmp/launch.log; exit 1; }
timeout 10 ros2 param get /diff_drive_node max_linear_speed | grep -q "0.25"
timeout 10 ros2 param set /diff_drive_node max_linear_speed -1.0 2>&1 | grep -q "strictement positif"
timeout 10 ros2 param set /diff_drive_node max_linear_speed 0.2 2>&1 | grep -q "successful"
echo "launch, fichier YAML, argument et validation : OK"
