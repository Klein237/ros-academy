#!/usr/bin/env bash
# Les deux versions du nœud (Python et C++) font avancer le robot.
set -e
source install/setup.bash
DOMAIN=61
for pkg in my_pkg my_pkg_cpp; do
  export ROS_DOMAIN_ID=$((DOMAIN++))  # un domaine par version : aucun mélange possible
  setsid ros2 run "$pkg" diff_drive_node > /dev/null 2>&1 &
  NODE=$!
  python3 - "$pkg" <<'PY'
import sys, time
import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
rclpy.init()
n = rclpy.create_node('lab_test')
pub = n.create_publisher(Twist, 'cmd_vel', 10)
last = {}
n.create_subscription(Odometry, 'odom', lambda m: last.update(x=m.pose.pose.position.x), 10)
t = time.time() + 15
while 'x' not in last and time.time() < t:
    rclpy.spin_once(n, timeout_sec=0.1)
x0 = last.get('x', 0.0)
cmd = Twist(); cmd.linear.x = 0.5
t = time.time() + 2
while time.time() < t:
    pub.publish(cmd); rclpy.spin_once(n, timeout_sec=0.1)
dx = last.get('x', 0.0) - x0
print(f"{sys.argv[1]} : {dx:.2f} m en 2 s à 0,5 m/s")
sys.exit(0 if 0.6 < dx < 1.5 else 1)
PY
  kill -TERM -- -$NODE; wait $NODE 2>/dev/null || true
done
