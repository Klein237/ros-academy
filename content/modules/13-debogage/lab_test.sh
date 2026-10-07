#!/usr/bin/env bash
# La patrouille du cours fait rouler le robot, ses messages DEBUG s'affichent, et ros2 bag enregistre /cmd_vel.
set -e
source install/setup.bash
export ROS_DOMAIN_ID=89
setsid ros2 launch my_pkg robot.launch.py > /tmp/launch.log 2>&1 &
ROBOT=$!
setsid ros2 run my_pkg patrouille_node --ros-args --log-level patrouille_node:=debug > /tmp/patrouille.log 2>&1 &
PATROUILLE=$!
trap 'kill -TERM -- -$ROBOT -$PATROUILLE 2>/dev/null; wait 2>/dev/null || true' EXIT
for _ in $(seq 1 20); do grep -q "DEBUG.*v=0.20 m/s" /tmp/patrouille.log && break; sleep 1; done
grep -q "DEBUG.*v=0.20 m/s" /tmp/patrouille.log || { cat /tmp/patrouille.log; exit 1; }
rm -rf /tmp/patrouille_bag
timeout -s INT 5 ros2 bag record -o /tmp/patrouille_bag /cmd_vel > /tmp/bag.log 2>&1 || true
ros2 bag info /tmp/patrouille_bag > /tmp/baginfo.log
grep -Eq "Topic: /cmd_vel \| Type: geometry_msgs/msg/Twist \| Count: [1-9]" /tmp/baginfo.log || { cat /tmp/bag.log /tmp/baginfo.log; exit 1; }
timeout 10 ros2 service call /get_pose my_interface/srv/GetPose > /tmp/pose.log
python3 - /tmp/pose.log <<'PY'
import re, sys
s = open(sys.argv[1]).read()
x, y = (float(re.search(rf"\b{k}=([-0-9.e]+)", s).group(1)) for k in ("x", "y"))
assert (x * x + y * y) ** 0.5 > 0.2, s
PY
echo "patrouille, journaux DEBUG et enregistrement : OK"
