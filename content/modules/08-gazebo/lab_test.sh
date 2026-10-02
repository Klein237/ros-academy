#!/usr/bin/env bash
# Le launch du cours démarre Gazebo, le robot y apparaît, le laser voit la caisse et la TF odom → laser existe.
set -e
source install/setup.bash
export ROS_DOMAIN_ID=88
export GAZEBO_MASTER_URI=http://127.0.0.1:11400
setsid ros2 launch my_robot_description gazebo.launch.py > /tmp/gazebo.log 2>&1 &
NODE=$!
trap 'kill -TERM -- -$NODE 2>/dev/null; sleep 2; kill -KILL -- -$NODE 2>/dev/null; wait $NODE 2>/dev/null || true' EXIT
python3 - <<'PY' || { tail -30 /tmp/gazebo.log; exit 1; }
import math
import sys
import time

import rclpy
from rclpy.time import Time
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformListener

rclpy.init()
node = rclpy.create_node('lab_test_gazebo')
scans = []
node.create_subscription(LaserScan, 'scan', lambda m: scans.append(m), 10)
buf = Buffer()
TransformListener(buf, node)
deadline = time.time() + 150
while time.time() < deadline and not (scans and buf.can_transform('odom', 'laser', Time())):
    rclpy.spin_once(node, timeout_sec=0.5)
if not scans:
    sys.exit("aucun message sur /scan")
if not buf.can_transform('odom', 'laser', Time()):
    sys.exit("pas de TF odom → laser")
s = scans[-1]
i = round((0.0 - s.angle_min) / s.angle_increment)  # rayon droit devant
avant = min(r for r in s.ranges[max(0, i - 2):i + 3] if math.isfinite(r))
print(f"laser : caisse droit devant à {avant:.2f} m (attendu ≈ 0.90)")
if abs(avant - 0.90) > 0.1:
    sys.exit("la caisse n'est pas à la distance attendue")
PY
echo "Gazebo, robot, laser et TF : OK"
